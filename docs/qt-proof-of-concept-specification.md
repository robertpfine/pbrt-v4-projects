# PBRT-v4 Art Studio: Qt Proof-of-Concept Specification

Status: Initial shell implemented and exercised in the desktop workflow. This
document defines the first bounded implementation; it does not define the
complete future medium.

Visual reference:
[`assets/qt-proof-of-concept.png`](assets/qt-proof-of-concept.png)

Source vision:
[`artistic-tool-vision.md`](artistic-tool-vision.md)

## Purpose

PBRT-v4 Art Studio is a medium for creating art. Its purpose is to let the artist
concentrate on the scene being imagined while the system handles configuration,
PBRT scene-file construction, rendering, logging, and reproducibility.

The proof of concept focuses on landscape creation. It should demonstrate a
complete, useful artistic cycle without attempting to solve the entire future
object library or every category of work.

The proof of concept is the beginning of an evolving application, not a frozen
front end for the current code. New artistic questions will continue to require
Python development and corresponding changes to configuration and the
interface. The Qt structure should make those additions coherent without
pretending that future coding has been eliminated.

## Core terminology

### Scene

A scene is one complete renderable `.pbrt` state. Changing any parameter,
including camera or lighting, creates a new scene even when the change is small.

### Project

`Project` is not an entity within the medium. In the present context it refers
only to the surrounding VS Code workspace or instance. The proof-of-concept GUI
should not organize artistic work under a `Project` concept.

### Themes

Themes are optional, evolving, and potentially overlapping groupings of scenes.
They are not required containers and do not need a proof-of-concept interface.

## Initial scene state

The application initially presents a blank scene state rather than a starting
template. The artist's first constructive choice is a landform.

Selecting a landform supplies:

- The selected ground form.
- A neutral sky.
- A workable default camera.

The sky and camera are technical starting conditions, remain editable, and do
not constitute a preassembled artistic template.

After the landform is selected, every supported category becomes available.
The application does not impose a wizard or prescribed order of work.

## Proof-of-concept landscape scope

The controls must be sufficient to construct and render a landscape containing:

- A landform and ground surface.
- Grass.
- Poppies.
- A tree.
- A sky with clouds.
- Far-away hills on the receding horizon.
- Camera controls.
- Lighting controls.
- Atmospheric controls appropriate to the existing implementation.

The distant hills are a required depth-and-horizon component, not incidental
background decoration.

The proof of concept uses the known forms already under development. It does
not require a generalized object catalogue before these controls can be useful.

## Proposed interface structure

The accepted mockup establishes the general desktop arrangement:

```text
+--------------------------------------------------------------+
| Menu and render toolbar                                      |
+---------------+-----------------------------+----------------+
| Scene         |                             | Selected-item  |
| navigation    | Latest completed render     | parameters     |
|               |                             |                |
+---------------+-----------------------------+----------------+
| Persistent render log                                        |
+--------------------------------------------------------------+
```

### Scene navigation

The initial navigation reflects the known artistic categories:

```text
Scene
Composition
Landscape
    Ground
    Landform
    Grass
    Flowers / Poppies
    Trees
Sky
    Clouds
Atmosphere
Lighting
Camera
Render
```

The mechanism for adding elements is deliberately unspecified. `ADD`
functionality, catalogue browsing, search, nested object menus, and automatic
scene-hierarchy population are tabled.

### Parameter inspector

Selecting a supported category displays its controls in the right-hand panel.
The interface should favor exact numeric entry, checkboxes, selectors, and
clearly named groups. Sliders may supplement numeric entry but must not prevent
strong or deliberately extreme values.

### Render display

The central image is the latest completed render. It supports artistic
evaluation rather than real-time three-dimensional manipulation. Basic image
viewing may include fit, zoom, and pan.

### Render log

Render progress remains visible and persists after completion. Whether the
proof of concept uses the docked log shown in the mockup or the established
persistent terminal can be decided during implementation without changing the
artistic model.

## Interaction cycle

```text
Choose landform
    -> edit parameters in any supported category
    -> validate
    -> save the authoritative configuration
    -> generate the .pbrt scene
    -> render with PBRT on the GPU
    -> display and evaluate the image
    -> revise parameters
```

There is no real-time PBRT scene manipulation in the proof of concept. Fast,
low-resolution PBRT preview renders may be added later, but a separate
rasterized proxy viewport is outside scope.

## Configuration model

There remains one authoritative scene configuration:

`scene_workspace/config.json`

A Python configuration model will mediate between that file and Qt. It will:

- Load the current JSON.
- Present the proof-of-concept controls under clear names.
- Validate values and required relationships.
- Permit Qt controls to update values.
- Save changes safely back to the same JSON.
- Produce a concise description of the active scene before rendering.

Manual editing of `config.json` remains valid. The Python model does not create
a second scene configuration.

The initial shell preceded any complete JSON refactor. Desktop use then
identified a bounded structural need, implemented behind the Python
configuration model:

```text
scene.landscape.ground
scene.landscape.water
scene.landscape.distant_hills
scene.sky.background
scene.sky.clouds
```

The ground and neutral infinite-sky values migrated without changing PBRT
output. Distant hills and clouds now have disabled module boundaries for their
next implementation step. This is not a complete object/process refactor; see
[`scene-module-boundaries.md`](scene-module-boundaries.md).

## Implemented entry points

- `pbrt_v4_art_studio.py` contains the Qt application.
- `scene_config.py` provides validated, formatting-preserving access to the one
  authoritative JSON file.
- `run_art_studio.sh` starts the application without installing dependencies.
- `requirements-gui.txt` records the repository-local PySide6 dependency.

The application and visible window title are **PBRT-v4 Art Studio**. The
role-based `scene_workspace` directory contains the editable scene; it is not a
VS Code project or an artwork grouping.

## Objects and instancing

Poppies and trees should both support optional instancing conceptually. They
should not be assigned fundamentally different object systems merely because
poppies are often distributed in populations and trees are often placed
individually.

Editing an instance affects only that scene instance; its reusable source object
remains unchanged. A generalized source-object editor, object-registration
system, and instance-override architecture are not prerequisites for the proof
of concept. Existing PBRT instancing and scatter mechanisms may support the
known scene elements without first exposing a universal object library.

## Atmosphere

Volumetrics are artistically potent and may appear in most eventual scenes.
They need not be imposed before the artist evaluates landform, object placement,
perspective, and color.

The following remain unresolved or deferred:

- Whether a scene starts with an explicit atmosphere choice or a neutral clear
  default.
- A master comparison switch between clear and volumetric states.
- Automatic pairing or grouping of those resulting scenes.

## Rendering and reproducibility

Every render continues to archive enough information to recreate it. The
existing render bundle remains the baseline:

- Final image.
- Generated `.pbrt` scene.
- Exact `config.json`.
- Exact scene-builder Python source.
- Exact rendering shell script.
- Any additional files required by a specialized render workflow.

Selective retention of iterations is tabled.

## Explicitly outside the proof of concept

- Starting templates.
- `ADD` behavior or a generalized catalogue browser.
- A complete reusable-object library interface.
- Editing reusable source objects.
- Exposing L-systems, space colonization, or other creation processes as GUI
  modules.
- Theme management.
- A real-time rasterized scene viewport.
- A complete refactor of `config.json`.
- A complete modular refactor of every existing generator.
- Long-term pruning of archived scene data.

## Technical foundation

The GUI should use PySide6 in a repository-local Python virtual environment.
System Python, PBRT, CUDA, and the NVIDIA driver should remain unchanged.

The initial implementation should introduce only the minimum supporting code:

```text
scene_config.py     Python configuration model
scene_gui.py        Qt application entry point and interface
```

Existing generation and rendering entry points remain in place until the proof
of concept demonstrates a need to change them.

## Proof-of-concept success criteria

The proof of concept succeeds when the artist can:

1. Open the application to a blank scene state.
2. Select a landform and receive a neutral sky and workable camera.
3. Reach all supported categories without a prescribed workflow.
4. Set and save parameters for the required landscape components.
5. Validate the scene before rendering.
6. Launch the existing PBRT GPU pipeline and follow its persistent log.
7. View the completed render in the application.
8. Find the complete reproducibility bundle in the established archive.
