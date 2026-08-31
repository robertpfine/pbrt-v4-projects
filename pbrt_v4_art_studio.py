#!/usr/bin/env python3
"""PBRT-v4 Art Studio Qt proof of concept.

The interface edits the single authoritative scene_workspace/config.json,
launches the existing PBRT pipeline, preserves its log, and displays the most
recent completed render. It is deliberately a render-and-evaluate interface,
not a real-time 3D viewport.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import sys
from typing import Any, Callable

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as error:  # pragma: no cover - exercised before Qt starts
    raise SystemExit(
        "PySide6 is not installed. Create the local environment and install "
        "requirements-gui.txt before starting PBRT-v4 Art Studio."
    ) from error

from scene_config import (
    GROUND_PATH,
    HILLS_PATH,
    SKY_PATH,
    SceneConfig,
    SceneConfigError,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "scene_workspace" / "config.json"


class RenderImage(QtWidgets.QLabel):
    """Aspect-fitted display for the latest completed PBRT render."""

    def __init__(self) -> None:
        super().__init__()
        self._source = QtGui.QPixmap()
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(520, 360)
        self.setText("The latest completed render will appear here.")
        self.setObjectName("renderImage")

    def load(self, filename: Path) -> bool:
        pixmap = QtGui.QPixmap(str(filename))
        if pixmap.isNull():
            return False
        self._source = pixmap
        self.setToolTip(str(filename))
        self._fit()
        return True

    def clear_for_new_scene(self) -> None:
        self._source = QtGui.QPixmap()
        self.setPixmap(QtGui.QPixmap())
        self.setText("Choose a landform to begin the scene.")

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        if self._source.isNull():
            return
        target = self.contentsRect().size() - QtCore.QSize(24, 24)
        self.setPixmap(
            self._source.scaled(
                target,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        )


class Inspector(QtWidgets.QWidget):
    """Stack of exact-value editors for established scene capabilities."""

    changed = QtCore.Signal(str)

    def __init__(self, config: SceneConfig) -> None:
        super().__init__()
        self.config = config
        self.pages: dict[str, QtWidgets.QWidget] = {}
        self.refreshers: list[Callable[[], None]] = []
        self.stack = QtWidgets.QStackedWidget()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)
        self._build_pages()

    def show_page(self, key: str) -> None:
        page = self.pages.get(key, self.pages["scene"])
        self.stack.setCurrentWidget(page)

    def refresh(self) -> None:
        for refresh in self.refreshers:
            refresh()

    def _page(self, key: str, title: str, note: str = "") -> QtWidgets.QFormLayout:
        page = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(page)
        heading = QtWidgets.QLabel(title)
        heading.setObjectName("inspectorHeading")
        outer.addWidget(heading)
        if note:
            explanation = QtWidgets.QLabel(note)
            explanation.setWordWrap(True)
            explanation.setObjectName("inspectorNote")
            outer.addWidget(explanation)
        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        outer.addLayout(form)
        outer.addStretch(1)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.pages[key] = scroll
        self.stack.addWidget(scroll)
        return form

    def _set(self, path: tuple[str | int, ...], value: Any) -> None:
        try:
            self.config.set(path, value)
            self.changed.emit(".".join(str(part) for part in path))
        except SceneConfigError as error:
            QtWidgets.QMessageBox.warning(self, "Configuration value", str(error))

    def _check(
        self,
        form: QtWidgets.QFormLayout,
        label: str,
        path: tuple[str | int, ...],
    ) -> QtWidgets.QCheckBox:
        widget = QtWidgets.QCheckBox()
        widget.setChecked(bool(self.config.get(path)))
        widget.toggled.connect(lambda value, p=path: self._set(p, value))
        form.addRow(label, widget)
        self.refreshers.append(
            lambda w=widget, p=path: self._blocked(w, bool(self.config.get(p)))
        )
        return widget

    def _integer(
        self,
        form: QtWidgets.QFormLayout,
        label: str,
        path: tuple[str | int, ...],
        minimum: int = 0,
        maximum: int = 100_000_000,
    ) -> QtWidgets.QSpinBox:
        widget = QtWidgets.QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setGroupSeparatorShown(True)
        widget.setValue(int(self.config.get(path)))
        widget.valueChanged.connect(lambda value, p=path: self._set(p, value))
        form.addRow(label, widget)
        self.refreshers.append(
            lambda w=widget, p=path: self._blocked(w, int(self.config.get(p)))
        )
        return widget

    def _number(
        self,
        form: QtWidgets.QFormLayout,
        label: str,
        path: tuple[str | int, ...],
        minimum: float = -1_000_000.0,
        maximum: float = 1_000_000.0,
        decimals: int = 5,
    ) -> QtWidgets.QDoubleSpinBox:
        widget = QtWidgets.QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setValue(float(self.config.get(path)))
        widget.valueChanged.connect(lambda value, p=path: self._set(p, value))
        form.addRow(label, widget)
        self.refreshers.append(
            lambda w=widget, p=path: self._blocked(w, float(self.config.get(p)))
        )
        return widget

    def _pair(
        self,
        form: QtWidgets.QFormLayout,
        label: str,
        path: tuple[str | int, ...],
        minimum: float = -1_000_000.0,
        maximum: float = 1_000_000.0,
        decimals: int = 4,
    ) -> None:
        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        values = self.config.get(path)
        widgets: list[QtWidgets.QDoubleSpinBox] = []
        for index in range(2):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(minimum, maximum)
            spin.setDecimals(decimals)
            spin.setValue(float(values[index]))
            spin.valueChanged.connect(
                lambda value, i=index, p=path: self._set_pair_value(p, i, value)
            )
            widgets.append(spin)
            layout.addWidget(spin)
        form.addRow(label, row)

        def refresh_pair() -> None:
            current = self.config.get(path)
            for index, widget in enumerate(widgets):
                self._blocked(widget, float(current[index]))

        self.refreshers.append(refresh_pair)

    def _vector(
        self,
        form: QtWidgets.QFormLayout,
        label: str,
        path: tuple[str | int, ...],
    ) -> None:
        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        widgets: list[QtWidgets.QDoubleSpinBox] = []
        values = self.config.get(path)
        for index, axis in enumerate("XYZ"):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-1_000_000.0, 1_000_000.0)
            spin.setDecimals(3)
            spin.setPrefix(f"{axis} ")
            spin.setValue(float(values[index]))
            spin.valueChanged.connect(
                lambda value, i=index, p=path: self._set_vector_value(p, i, value)
            )
            widgets.append(spin)
            layout.addWidget(spin)
        form.addRow(label, row)

        def refresh_vector() -> None:
            current = self.config.get(path)
            for index, widget in enumerate(widgets):
                self._blocked(widget, float(current[index]))

        self.refreshers.append(refresh_vector)

    def _set_pair_value(
        self, path: tuple[str | int, ...], index: int, value: float
    ) -> None:
        pair = list(self.config.get(path))
        pair[index] = value
        self._set(path, pair)

    def _set_vector_value(
        self, path: tuple[str | int, ...], index: int, value: float
    ) -> None:
        vector = list(self.config.get(path))
        vector[index] = value
        self._set(path, vector)

    @staticmethod
    def _blocked(widget: QtWidgets.QWidget, value: Any) -> None:
        blocker = QtCore.QSignalBlocker(widget)
        if isinstance(widget, QtWidgets.QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QtWidgets.QComboBox):
            if isinstance(value, int):
                widget.setCurrentIndex(value)
            else:
                widget.setCurrentText(str(value))
        else:
            widget.setValue(value)
        del blocker

    def _placeholder(self, key: str, title: str, text: str) -> None:
        self._page(key, title, text)

    def _module_boundary(
        self,
        key: str,
        title: str,
        path: tuple[str | int, ...],
        note: str,
    ) -> None:
        form = self._page(key, title, note)
        location = QtWidgets.QLabel(".".join(str(part) for part in path))
        location.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        state = QtWidgets.QLabel()
        form.addRow("Configuration", location)
        form.addRow("Current state", state)

        def refresh_state() -> None:
            module = self.config.get(path)
            state.setText("enabled" if module.get("enabled", False) else "disabled")

        self.refreshers.append(refresh_state)
        refresh_state()

    def _build_pages(self) -> None:
        self._build_scene_page()
        self._placeholder(
            "composition",
            "Composition",
            "Composition controls will coordinate spatial relationships without "
            "introducing a separate real-time viewport.",
        )
        self._placeholder(
            "landscape",
            "Landscape",
            "scene.landscape is the boundary for the ground and receding-horizon "
            "systems. Ground contents remain independently editable.",
        )
        self._build_ground_page()
        self._build_landform_page()
        self._build_grass_page()
        self._build_poppy_page()
        self._build_tree_page()
        self._module_boundary(
            "water",
            "Water",
            ("scene", "landscape", "water"),
            "The first-class landscape boundary is established and disabled. "
            "Water bodies, waves, optics, and shoreline controls are the third "
            "ordered element of Step 4.",
        )
        self._build_distant_hills_page()
        self._build_sky_page()
        self._module_boundary(
            "clouds",
            "Clouds",
            SKY_PATH + ("clouds",),
            "The configuration boundary is established and disabled. Generator "
            "and artistic controls are the next implementation step.",
        )
        self._build_atmosphere_page()
        self._build_lighting_page()
        self._build_camera_page()
        self._build_render_page()

    def _build_scene_page(self) -> None:
        form = self._page(
            "scene",
            "Working Scene",
            "A saved and rendered parameter state is one complete PBRT scene.",
        )
        name = QtWidgets.QLineEdit(str(self.config.get(("scene", "name"))))
        name.editingFinished.connect(
            lambda: self._set(("scene", "name"), name.text().strip())
        )
        form.addRow("Scene name", name)
        summary = QtWidgets.QPlainTextEdit(self.config.describe())
        summary.setReadOnly(True)
        summary.setMaximumHeight(155)
        form.addRow("Current state", summary)

        def refresh() -> None:
            blocker = QtCore.QSignalBlocker(name)
            name.setText(str(self.config.get(("scene", "name"))))
            del blocker
            summary.setPlainText(self.config.describe())

        self.refreshers.append(refresh)

    def _build_ground_page(self) -> None:
        form = self._page(
            "ground",
            "Ground Surface",
            "This controls the surface treatment beneath independently enabled "
            "grass, flowers, stones, undergrowth, and litter.",
        )
        base = GROUND_PATH + ("details", "surface")
        self._check(form, "Surface treatment", base + ("enabled",))
        mode = QtWidgets.QLabel(str(self.config.get(base + ("mode",))))
        mode.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Current mode", mode)

    def _build_landform_page(self) -> None:
        form = self._page(
            "landform",
            "Landform",
            "The landform defines geometry. Ground contents remain separate and "
            "can be edited after this choice.",
        )
        path = GROUND_PATH + ("active_landform",)
        combo = QtWidgets.QComboBox()
        combo.addItems(self.config.landform_names())
        combo.setCurrentText(str(self.config.get(path)))
        combo.currentTextChanged.connect(lambda value: self._set(path, value))
        form.addRow("Type", combo)
        self.refreshers.append(
            lambda: self._blocked(combo, str(self.config.get(path)))
        )
        active = str(self.config.get(path))
        root = GROUND_PATH + ("landforms", active)
        self._pair(form, "Size", root + ("size",), 1.0, 100_000.0, 2)
        self._number(form, "Base height", root + ("base_height",), decimals=3)
        self._number(
            form,
            "Grade",
            root + ("slope", "grade"),
            minimum=-10.0,
            maximum=10.0,
            decimals=4,
        )
        self._number(
            form,
            "Noise amplitude",
            root + ("noise", "amplitude"),
            minimum=0.0,
            maximum=10_000.0,
            decimals=3,
        )

    def _build_grass_page(self) -> None:
        form = self._page(
            "grass",
            "Grass",
            "Population and blade controls use exact values; the render, not the "
            "interface, shows their visual consequence.",
        )
        base = GROUND_PATH + ("details", "grass")
        self._check(form, "Enabled", base + ("enabled",))
        self._integer(form, "Tuft instances", base + ("layers", 0, "count"))
        self._integer(form, "Blades per tuft", base + ("tuft", "blades"), 1, 100)
        self._pair(form, "Blade height", base + ("blade", "height"), 0.0, 1000.0)
        self._pair(form, "Blade width", base + ("blade", "width"), 0.0, 100.0, 5)
        self._check(form, "Tropism", base + ("blade", "tropism", "enabled"))
        self._pair(
            form,
            "Tropism strength",
            base + ("blade", "tropism", "strength"),
            -100.0,
            100.0,
        )
        self._number(
            form,
            "Direction variation",
            base + ("blade", "tropism", "direction_variation_degrees"),
            0.0,
            360.0,
            2,
        )

    def _build_poppy_page(self) -> None:
        form = self._page(
            "poppies",
            "Flowers / Poppies",
            "Count is the number of selected placement references inside the "
            "full camera frame. Choose whether the reference is the flower or "
            "its root; plant geometry may be cropped at an edge.",
        )
        base = GROUND_PATH + ("details", "poppies")
        self._check(form, "Enabled", base + ("enabled",))
        self._integer(form, "Instances", base + ("count",))
        self._pair(form, "Scale", base + ("scale",), 0.0, 10_000.0, 3)
        self._check(
            form,
            "Constrain placement to frame",
            base + ("camera_frustum", "enabled"),
        )
        reference_path = base + ("camera_frustum", "placement_reference")
        reference = QtWidgets.QComboBox()
        reference.setObjectName("poppy_placement_reference")
        reference.addItem("Flower placement", "flower")
        reference.addItem("Root placement", "root")

        def set_reference(index: int) -> None:
            value = reference.itemData(index)
            if value is not None:
                self._set(reference_path, value)

        def refresh_reference() -> None:
            value = str(self.config.get(reference_path, "root"))
            index = reference.findData(value)
            self._blocked(reference, max(0, index))

        reference.currentIndexChanged.connect(set_reference)
        form.addRow("Framing reference", reference)
        self.refreshers.append(refresh_reference)
        refresh_reference()

    def _build_tree_page(self) -> None:
        form = self._page(
            "trees",
            "Trees",
            "The proof of concept exposes the established tree entries directly. "
            "A generalized source-object and instance editor remains deferred.",
        )
        entries: list[tuple[str, tuple[str | int, ...]]] = []
        for index, tree in enumerate(self.config.get(("scene", "lsystem_trees"), [])):
            label = tree.get("preset", f"procedural tree {index + 1}")
            entries.append((f"{label} (rule-based)", ("scene", "lsystem_trees", index)))
        for index, _tree in enumerate(self.config.get(("scene", "trees"), [])):
            entries.append((f"space-colonization tree {index + 1}", ("scene", "trees", index)))
        selector = QtWidgets.QComboBox()
        for label, _path in entries:
            selector.addItem(label)
        enabled = QtWidgets.QCheckBox()
        scale = QtWidgets.QDoubleSpinBox()
        scale.setRange(0.01, 1000.0)
        scale.setDecimals(3)
        form.addRow("Tree entry", selector)
        form.addRow("Enabled", enabled)
        form.addRow("Uniform scale", scale)

        def selected_path() -> tuple[str | int, ...]:
            return entries[max(0, selector.currentIndex())][1]

        def refresh_tree() -> None:
            if not entries:
                enabled.setEnabled(False)
                scale.setEnabled(False)
                return
            path = selected_path()
            self._blocked(enabled, bool(self.config.get(path + ("enabled",))))
            configured_scale = self.config.get(path + ("scale",), None)
            scale.setEnabled(configured_scale is not None)
            if configured_scale is not None:
                self._blocked(scale, float(configured_scale))

        selector.currentIndexChanged.connect(lambda _index: refresh_tree())
        enabled.toggled.connect(
            lambda value: self._set(selected_path() + ("enabled",), value)
        )
        scale.valueChanged.connect(
            lambda value: self._set(selected_path() + ("scale",), value)
            if scale.isEnabled()
            else None
        )
        self.refreshers.append(refresh_tree)
        refresh_tree()

    def _build_distant_hills_page(self) -> None:
        form = self._page(
            "distant_hills",
            "Distant Hills",
            "One continuous height-field surface creates a broad, low rise "
            "beyond the meadow. Noise remains subordinate to the landform.",
        )
        self._check(form, "Enabled", HILLS_PATH + ("enabled",))
        layers = self.config.get(HILLS_PATH + ("layers",))
        layer_selector = QtWidgets.QComboBox()
        layer_selector.setObjectName("distant_hill_layer")
        for layer in layers:
            layer_selector.addItem(str(layer.get("name", "unnamed layer")))
        form.addRow("Depth layer", layer_selector)

        layer_enabled = QtWidgets.QCheckBox()
        center = [QtWidgets.QDoubleSpinBox(), QtWidgets.QDoubleSpinBox()]
        size = [QtWidgets.QDoubleSpinBox(), QtWidgets.QDoubleSpinBox()]
        rotation = QtWidgets.QDoubleSpinBox()
        base_elevation = QtWidgets.QDoubleSpinBox()
        ridge_height = QtWidgets.QDoubleSpinBox()
        ridge_position = QtWidgets.QDoubleSpinBox()
        front_power = QtWidgets.QDoubleSpinBox()
        back_power = QtWidgets.QDoubleSpinBox()
        noise_amplitude = QtWidgets.QDoubleSpinBox()
        noise_frequency = QtWidgets.QDoubleSpinBox()
        reflectance = [
            QtWidgets.QDoubleSpinBox(),
            QtWidgets.QDoubleSpinBox(),
            QtWidgets.QDoubleSpinBox(),
        ]
        peak_selector = QtWidgets.QComboBox()
        peak_selector.setObjectName("distant_hill_peak")
        peak_position = QtWidgets.QDoubleSpinBox()
        peak_height = QtWidgets.QDoubleSpinBox()
        peak_width = QtWidgets.QDoubleSpinBox()
        peak_asymmetry = QtWidgets.QDoubleSpinBox()

        def configure(
            widget: QtWidgets.QDoubleSpinBox,
            minimum: float,
            maximum: float,
            decimals: int,
        ) -> None:
            widget.setRange(minimum, maximum)
            widget.setDecimals(decimals)

        for widget in center:
            configure(widget, -100_000.0, 100_000.0, 2)
        for widget in size:
            configure(widget, 1.0, 100_000.0, 2)
        configure(rotation, -360.0, 360.0, 2)
        configure(base_elevation, -100_000.0, 100_000.0, 2)
        configure(ridge_height, 0.0, 100_000.0, 2)
        configure(ridge_position, 0.01, 0.99, 3)
        configure(front_power, 0.05, 20.0, 3)
        configure(back_power, 0.05, 20.0, 3)
        configure(noise_amplitude, 0.0, 100_000.0, 2)
        configure(noise_frequency, 0.0, 100.0, 5)
        for widget in reflectance:
            configure(widget, 0.0, 1.0, 4)
        configure(peak_position, -1.5, 1.5, 3)
        configure(peak_height, -100_000.0, 100_000.0, 2)
        configure(peak_width, 0.001, 3.0, 3)
        configure(peak_asymmetry, -0.95, 0.95, 3)

        def vector_row(widgets: list[QtWidgets.QDoubleSpinBox], prefixes: str) -> QtWidgets.QWidget:
            row = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            for widget, prefix in zip(widgets, prefixes):
                widget.setPrefix(f"{prefix} ")
                layout.addWidget(widget)
            return row

        form.addRow("Layer active", layer_enabled)
        form.addRow("World center", vector_row(center, "XZ"))
        form.addRow("Width / depth", vector_row(size, "WD"))
        form.addRow("Rotation", rotation)
        form.addRow("Base elevation", base_elevation)
        form.addRow("Base ridge height", ridge_height)
        form.addRow("Ridge depth", ridge_position)
        form.addRow("Front slope power", front_power)
        form.addRow("Rear slope power", back_power)
        form.addRow("Noise amplitude", noise_amplitude)
        form.addRow("Noise frequency", noise_frequency)
        form.addRow("Reflectance", vector_row(reflectance, "RGB"))
        form.addRow("Designed peak", peak_selector)
        form.addRow("Peak position", peak_position)
        form.addRow("Peak height", peak_height)
        form.addRow("Peak width", peak_width)
        form.addRow("Peak asymmetry", peak_asymmetry)

        def layer_path(*parts: str | int) -> tuple[str | int, ...]:
            return HILLS_PATH + ("layers", layer_selector.currentIndex()) + parts

        def peak_path(field: str) -> tuple[str | int, ...]:
            return layer_path("peaks", peak_selector.currentIndex(), field)

        def set_pair(field: str, index: int, value: float) -> None:
            path = layer_path(field)
            values = list(self.config.get(path))
            values[index] = value
            self._set(path, values)

        def set_reflectance(index: int, value: float) -> None:
            path = layer_path("material", "reflectance")
            values = list(self.config.get(path))
            values[index] = value
            self._set(path, values)

        def populate_peaks() -> None:
            blocker = QtCore.QSignalBlocker(peak_selector)
            previous = max(0, peak_selector.currentIndex())
            peak_selector.clear()
            peaks = self.config.get(layer_path("peaks"))
            for index in range(len(peaks)):
                peak_selector.addItem(f"Peak {index + 1}")
            peak_selector.setCurrentIndex(min(previous, max(0, len(peaks) - 1)))
            del blocker

        def refresh_values() -> None:
            populate_peaks()
            self._blocked(layer_enabled, self.config.get(layer_path("enabled")))
            for index, widget in enumerate(center):
                self._blocked(widget, float(self.config.get(layer_path("center"))[index]))
            for index, widget in enumerate(size):
                self._blocked(widget, float(self.config.get(layer_path("size"))[index]))
            self._blocked(rotation, float(self.config.get(layer_path("rotation_degrees"))))
            self._blocked(base_elevation, float(self.config.get(layer_path("base_elevation"))))
            self._blocked(ridge_height, float(self.config.get(layer_path("ridge_base_height"))))
            self._blocked(
                ridge_position,
                float(self.config.get(layer_path("cross_section", "ridge_position"))),
            )
            self._blocked(
                front_power,
                float(self.config.get(layer_path("cross_section", "front_power"))),
            )
            self._blocked(
                back_power,
                float(self.config.get(layer_path("cross_section", "back_power"))),
            )
            self._blocked(
                noise_amplitude,
                float(self.config.get(layer_path("noise", "amplitude"))),
            )
            self._blocked(
                noise_frequency,
                float(self.config.get(layer_path("noise", "frequency"))),
            )
            colors = self.config.get(layer_path("material", "reflectance"))
            for index, widget in enumerate(reflectance):
                self._blocked(widget, float(colors[index]))
            refresh_peak()

        def refresh_peak() -> None:
            if peak_selector.count() == 0:
                return
            self._blocked(peak_position, float(self.config.get(peak_path("position"))))
            self._blocked(peak_height, float(self.config.get(peak_path("height"))))
            self._blocked(peak_width, float(self.config.get(peak_path("width"))))
            self._blocked(
                peak_asymmetry, float(self.config.get(peak_path("asymmetry")))
            )

        layer_selector.currentIndexChanged.connect(lambda _index: refresh_values())
        peak_selector.currentIndexChanged.connect(lambda _index: refresh_peak())
        layer_enabled.toggled.connect(lambda value: self._set(layer_path("enabled"), value))
        for index, widget in enumerate(center):
            widget.valueChanged.connect(
                lambda value, i=index: set_pair("center", i, value)
            )
        for index, widget in enumerate(size):
            widget.valueChanged.connect(
                lambda value, i=index: set_pair("size", i, value)
            )
        rotation.valueChanged.connect(
            lambda value: self._set(layer_path("rotation_degrees"), value)
        )
        base_elevation.valueChanged.connect(
            lambda value: self._set(layer_path("base_elevation"), value)
        )
        ridge_height.valueChanged.connect(
            lambda value: self._set(layer_path("ridge_base_height"), value)
        )
        ridge_position.valueChanged.connect(
            lambda value: self._set(layer_path("cross_section", "ridge_position"), value)
        )
        front_power.valueChanged.connect(
            lambda value: self._set(layer_path("cross_section", "front_power"), value)
        )
        back_power.valueChanged.connect(
            lambda value: self._set(layer_path("cross_section", "back_power"), value)
        )
        noise_amplitude.valueChanged.connect(
            lambda value: self._set(layer_path("noise", "amplitude"), value)
        )
        noise_frequency.valueChanged.connect(
            lambda value: self._set(layer_path("noise", "frequency"), value)
        )
        for index, widget in enumerate(reflectance):
            widget.valueChanged.connect(
                lambda value, i=index: set_reflectance(i, value)
            )
        peak_position.valueChanged.connect(
            lambda value: self._set(peak_path("position"), value)
        )
        peak_height.valueChanged.connect(
            lambda value: self._set(peak_path("height"), value)
        )
        peak_width.valueChanged.connect(
            lambda value: self._set(peak_path("width"), value)
        )
        peak_asymmetry.valueChanged.connect(
            lambda value: self._set(peak_path("asymmetry"), value)
        )
        self.refreshers.append(refresh_values)
        refresh_values()

    def _build_sky_page(self) -> None:
        form = self._page(
            "sky",
            "Sky",
            "The current neutral sky comes from the established infinite light. "
            "Clouds are a separate category.",
        )
        base = SKY_PATH + ("background",)
        self._check(form, "Enabled", base + ("enabled",))
        self._vector(form, "Color", base + ("color",))
        self._number(form, "Intensity", base + ("scale",), 0.0, 1_000_000.0, 4)

    def _build_atmosphere_page(self) -> None:
        form = self._page(
            "atmosphere",
            "Atmosphere",
            "Atmosphere is the artistic category. The current fog implementation "
            "uses a homogeneous or noise-modulated PBRT medium; RGB-grid is not "
            "a generic atmosphere label.",
        )
        base = ("scene", "fog")
        self._check(form, "Fog enabled", base + ("enabled",))
        self._number(form, "Absorption", base + ("sigma_a",), 0.0, 100.0, 7)
        self._number(form, "Scattering", base + ("sigma_s",), 0.0, 100.0, 7)
        self._number(form, "Anisotropy", base + ("g",), -0.999, 0.999, 4)
        self._check(form, "Density variation", base + ("noise", "enabled"))

    def _build_lighting_page(self) -> None:
        form = self._page("lighting", "Lighting")
        lights = self.config.get(("scene", "lights"))
        sun_index = next(
            (index for index, light in enumerate(lights) if light.get("label") == "morning_sun"),
            0,
        )
        base = ("scene", "lights", sun_index)
        self._check(form, "Morning sun", base + ("enabled",))
        self._number(form, "Temperature", base + ("temperature",), 1000.0, 20_000.0, 0)
        self._number(form, "Intensity", base + ("scale",), 0.0, 1_000_000.0, 3)
        self._vector(form, "Direction from", base + ("from",))

    def _build_camera_page(self) -> None:
        form = self._page("camera", "Camera")
        base = ("scene", "camera")
        self._vector(form, "Eye", base + ("look_at", "eye"))
        self._vector(form, "Look at", base + ("look_at", "look"))
        self._vector(form, "Up", base + ("look_at", "up"))
        self._number(form, "Field of view", base + ("fov",), 1.0, 179.0, 2)

    def _build_render_page(self) -> None:
        form = self._page(
            "render",
            "Render",
            "Each completed render archives its image, PBRT scene, exact JSON, "
            "builder, and pipeline for reproducibility.",
        )
        self._integer(form, "Width", ("scene", "film", "x_resolution"), 1, 32_768)
        self._integer(form, "Height", ("scene", "film", "y_resolution"), 1, 32_768)
        self._check(form, "Override samples", ("scene", "sampler", "enabled"))
        self._integer(
            form,
            "Pixel samples",
            ("scene", "sampler", "pixel_samples"),
            1,
            1_000_000,
        )


class StudioWindow(QtWidgets.QMainWindow):
    """Main PBRT-v4 Art Studio window."""

    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self.config = SceneConfig(config_path)
        self.render_process = QtCore.QProcess(self)
        self.render_process.setProcessChannelMode(
            QtCore.QProcess.ProcessChannelMode.MergedChannels
        )
        self.render_process.readyReadStandardOutput.connect(self._read_render_output)
        self.render_process.finished.connect(self._render_finished)

        self.setWindowTitle("PBRT-v4 Art Studio")
        self.resize(1480, 930)
        self.setMinimumSize(1080, 700)

        self.navigation = self._build_navigation()
        self.image = RenderImage()
        self.inspector = Inspector(self.config)
        self.inspector.changed.connect(self._configuration_changed)
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(100_000)
        self.log.setObjectName("renderLog")
        self._render_output_buffer = ""
        self.status_label = QtWidgets.QLabel()

        self._build_layout()
        self._build_toolbar()
        self._apply_style()
        self._load_latest_render()
        self._update_status("Working scene loaded")

    def _build_navigation(self) -> QtWidgets.QTreeWidget:
        tree = QtWidgets.QTreeWidget()
        tree.setHeaderLabel("SCENE ELEMENTS")
        tree.setMinimumWidth(215)
        tree.setMaximumWidth(290)
        entries = [
            ("Scene", "scene", None),
            ("Composition", "composition", None),
            ("Landscape", "landscape", None),
            ("Ground", "ground", "landscape"),
            ("Landform", "landform", "landscape"),
            ("Grass", "grass", "landscape"),
            ("Flowers / Poppies", "poppies", "landscape"),
            ("Trees", "trees", "landscape"),
            ("Water", "water", "landscape"),
            ("Distant Hills", "distant_hills", "landscape"),
            ("Sky", "sky", None),
            ("Clouds", "clouds", "sky"),
            ("Atmosphere", "atmosphere", None),
            ("Lighting", "lighting", None),
            ("Camera", "camera", None),
            ("Render", "render", None),
        ]
        items: dict[str, QtWidgets.QTreeWidgetItem] = {}
        for label, key, parent_key in entries:
            parent = items.get(parent_key)
            item = QtWidgets.QTreeWidgetItem(parent or tree, [label])
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, key)
            items[key] = item
        tree.expandAll()
        tree.setCurrentItem(items["scene"])
        tree.currentItemChanged.connect(
            lambda current, _previous: self.inspector.show_page(
                current.data(0, QtCore.Qt.ItemDataRole.UserRole) if current else "scene"
            )
        )
        return tree

    def _build_layout(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self.navigation, 0, 0)
        layout.addWidget(self.image, 0, 1)
        layout.addWidget(self.inspector, 0, 2)
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 0)
        self.inspector.setMinimumWidth(330)
        self.inspector.setMaximumWidth(440)
        self.setCentralWidget(central)

        log_dock = QtWidgets.QDockWidget("Persistent Render Log", self)
        log_dock.setObjectName("renderLogDock")
        log_dock.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea
            | QtCore.Qt.DockWidgetArea.TopDockWidgetArea
        )
        log_panel = QtWidgets.QWidget()
        log_layout = QtWidgets.QVBoxLayout(log_panel)
        log_layout.setContentsMargins(4, 2, 4, 4)
        log_layout.setSpacing(2)
        log_layout.addWidget(self.log, 1)
        log_dock.setWidget(log_panel)
        log_dock.setMinimumHeight(170)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
        self.statusBar().addPermanentWidget(self.status_label)

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Scene")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        validate = toolbar.addAction("Validate")
        save = toolbar.addAction("Save Scene")
        render = toolbar.addAction("Render")
        stop = toolbar.addAction("Stop")
        toolbar.addSeparator()
        reload_action = toolbar.addAction("Reload JSON")
        validate.triggered.connect(self.validate_config)
        save.triggered.connect(self.save_config)
        render.triggered.connect(self.start_render)
        stop.triggered.connect(self.stop_render)
        reload_action.triggered.connect(self.reload_config)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #20252b; color: #e8ebed; }
            QTreeWidget, QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox,
            QComboBox { background: #171b20; border: 1px solid #3a424b;
                        selection-background-color: #87662b; }
            QTreeWidget::item { padding: 5px; }
            QTreeWidget::item:selected { background: #87662b; }
            QToolBar { background: #2a3037; border-bottom: 1px solid #3a424b;
                       spacing: 5px; padding: 5px; }
            QToolButton { background: #39414a; padding: 6px 10px; border-radius: 3px; }
            QToolButton:hover { background: #4a5561; }
            QLabel#renderImage { background: #111418; border: 1px solid #3a424b;
                                 color: #8f99a3; font-size: 16px; }
            QLabel#inspectorHeading { font-size: 19px; font-weight: 600;
                                      color: #f0b84c; padding: 8px 0; }
            QLabel#inspectorNote { color: #aeb6bd; padding-bottom: 10px; }
            QDockWidget::title { background: #2a3037; padding: 5px; }
            QPlainTextEdit#renderLog { font-family: monospace; font-size: 12px; }
            """
        )

    def _configuration_changed(self, path: str) -> None:
        self._update_status(f"Unsaved change: {path}")
        if path.startswith("scene.landscape.ground.active_landform"):
            self.log.appendPlainText(
                "Landform selected. Reopen the studio after saving to refresh "
                "landform-specific inspector fields."
            )

    def _update_status(self, message: str) -> None:
        marker = " • modified" if self.config.dirty else ""
        self.status_label.setText(f"{message}{marker}")

    def validate_config(self) -> bool:
        errors = self.config.validate()
        if errors:
            self.log.appendPlainText("VALIDATION FAILED\n- " + "\n- ".join(errors))
            self._update_status("Validation failed")
            return False
        self.log.appendPlainText("Configuration valid.\n" + self.config.describe())
        self._update_status("Configuration valid")
        return True

    def save_config(self) -> bool:
        if not self.validate_config():
            return False
        try:
            self.config.save()
        except SceneConfigError as error:
            self.log.appendPlainText(f"SAVE FAILED: {error}")
            QtWidgets.QMessageBox.warning(self, "Save Scene", str(error))
            return False
        self.inspector.refresh()
        self.log.appendPlainText(f"Saved: {self.config.path}")
        self._update_status("Scene saved")
        return True

    def reload_config(self) -> None:
        if self.config.dirty:
            answer = QtWidgets.QMessageBox.question(
                self,
                "Reload JSON",
                "Discard unsaved interface changes and reload config.json?",
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        try:
            self.config.reload()
            self.inspector.refresh()
        except SceneConfigError as error:
            QtWidgets.QMessageBox.warning(self, "Reload JSON", str(error))
            return
        self.log.appendPlainText("Reloaded config.json from disk.")
        self._update_status("Configuration reloaded")

    def start_render(self) -> None:
        if self.render_process.state() != QtCore.QProcess.ProcessState.NotRunning:
            self.log.appendPlainText("A render is already running.")
            return
        if not self.save_config():
            return
        pipeline = ROOT / "render_pipeline.sh"
        self.log.appendPlainText("\n" + "=" * 68)
        self.log.appendPlainText("PBRT-v4 Art Studio render started")
        self.log.appendPlainText(f"Configuration: {self.config.path}")
        self._render_output_buffer = ""
        self.render_process.setWorkingDirectory(str(ROOT))
        self.render_process.start(str(pipeline), [str(self.config.path)])
        self._update_status("Render running")

    def stop_render(self) -> None:
        if self.render_process.state() == QtCore.QProcess.ProcessState.NotRunning:
            return
        self.log.appendPlainText("Stopping render at artist request...")
        self.render_process.terminate()
        QtCore.QTimer.singleShot(3000, self._kill_if_running)

    def _kill_if_running(self) -> None:
        if self.render_process.state() != QtCore.QProcess.ProcessState.NotRunning:
            self.render_process.kill()

    def _read_render_output(self) -> None:
        output = bytes(self.render_process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        if output:
            self._feed_render_output(output)

    def _feed_render_output(self, output: str) -> None:
        """Append complete terminal records to the persistent render log."""
        text = (self._render_output_buffer + output).replace("\r\n", "\n")
        self._render_output_buffer = ""
        segment_start = 0
        for index, character in enumerate(text):
            if character not in "\r\n":
                continue
            segment = text[segment_start:index]
            self._handle_render_line(segment)
            segment_start = index + 1
        self._render_output_buffer = text[segment_start:]

    def _handle_render_line(self, line: str) -> None:
        marker = "ART_STUDIO_RENDER_READY="
        if line.startswith(marker):
            filename = Path(line[len(marker):])
            if self.image.load(filename):
                self.log.appendPlainText(f"Displayed local render: {filename.name}")
                self._update_status("Local render complete; archive/sync continuing")
            else:
                self.log.appendPlainText(
                    f"Local render completed but could not be displayed: {filename}"
                )
            return
        self.log.appendPlainText(line)

    def _flush_render_output(self) -> None:
        if self._render_output_buffer:
            self._handle_render_line(self._render_output_buffer)
            self._render_output_buffer = ""

    def _render_finished(
        self,
        exit_code: int,
        _status: QtCore.QProcess.ExitStatus,
    ) -> None:
        self._flush_render_output()
        self.log.appendPlainText(f"\nRender process exited with status {exit_code}.")
        if exit_code == 0:
            self._load_latest_render()
            self._update_status("Render complete")
        else:
            self._update_status("Render failed or stopped")

    def _load_latest_render(self) -> None:
        archive = ROOT / "Archive"
        candidates = [
            path
            for path in archive.glob("*.png")
            if not path.name.endswith("_shaft.png")
            and not path.name.endswith("_base.png")
        ]
        if not candidates:
            return
        latest = max(candidates, key=lambda path: path.stat().st_mtime)
        if self.image.load(latest):
            self.log.appendPlainText(f"Displayed render: {latest.name}")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.render_process.state() != QtCore.QProcess.ProcessState.NotRunning:
            QtWidgets.QMessageBox.warning(
                self,
                "Render running",
                "Stop the active render before closing PBRT-v4 Art Studio.",
            )
            event.ignore()
            return
        if self.config.dirty:
            answer = QtWidgets.QMessageBox.question(
                self,
                "Unsaved scene",
                "Save the scene before closing?",
                QtWidgets.QMessageBox.StandardButton.Save
                | QtWidgets.QMessageBox.StandardButton.Discard
                | QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if answer == QtWidgets.QMessageBox.StandardButton.Save:
                if not self.save_config():
                    event.ignore()
                    return
            elif answer == QtWidgets.QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()


def main() -> int:
    # Qt's blocking event loop otherwise prevents Python's default SIGINT
    # handler from running until another Python callback occurs. Restoring the
    # operating-system default makes Ctrl+C reliably return a terminal prompt.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    parser = argparse.ArgumentParser(description="Start PBRT-v4 Art Studio")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="authoritative scene config (default: scene_workspace/config.json)",
    )
    arguments = parser.parse_args()
    application = QtWidgets.QApplication(sys.argv[:1])
    application.setApplicationName("PBRT-v4 Art Studio")
    application.setOrganizationName("PBRT-v4 Art Studio")
    try:
        window = StudioWindow(arguments.config)
    except SceneConfigError as error:
        QtWidgets.QMessageBox.critical(None, "PBRT-v4 Art Studio", str(error))
        return 1
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
