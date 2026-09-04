# Proposed Config Schema: Create a New Scene

Status: approved architectural design
Scope: `scene_description.mode: "new"` only
Active configuration: `scene_workspace/config.json` remains the one authoritative
live scene configuration

## Purpose

This document keeps the proposed configuration structure separate from the
conversation transcript so it can be found, reviewed, and edited directly.
It is a schema proposal, not a second scene configuration and not an input to
the renderer.

This is the approved 20,000-foot architectural design. Its engineering
translation is
`docs/config-schema-new-scene-ground-level.md`, which enumerates fields,
validation, generator ownership, and current-to-proposed paths. Neither
document becomes active merely by being documented.

The immediate goal is to make every active setup value easy to locate while
preserving direct manual JSON editing. The eventual migration must occur in the
one live `scene_workspace/config.json`, one complete artistic object at a time,
with the builder, validation, and Art Studio interface updated at the same time.

## Agreed top-level order

The first four sections of a new-scene configuration are:

1. `file_names`
2. `file_paths`
3. `camera_settings`
4. `render_settings`

They are followed by `scene_description`:

```text
file_names
file_paths
camera_settings
render_settings
scene_description
    mode
    name
    landforms
    objects
    sky
    atmosphere
```

## Meaning of schema terms

The configuration must distinguish these kinds of values clearly:

- **Descriptive identifier:** An artist-assigned name for an object in the
  current scene, such as `foreground_meadow` or `overcast_cloud_deck`. It does
  not load a previously created object and does not select an algorithm.
- **PBRT-v4 type:** A value that maps directly to PBRT-v4 functionality, such
  as `infinite`, `distant`, `volpath`, or `rgbgrid`.
- **Art Studio generator:** A registered Python or C++ construction algorithm,
  such as `poppy`, `sunflower`, or a future `pansy` generator. Selecting a
  generator must not silently supply artistic parameter values.
- **Artist-controlled parameter:** A value that affects the image and must be
  visible beside the object it controls.

The schema must not use invented preset names, hidden parameter bundles, or
silently inherited artistic values. An algorithm remains source code, but its
artistically meaningful inputs belong in the live configuration.

## Working new-scene skeleton

The following JSON illustrates the agreed organization. Values are examples
for review; this block is not a runnable configuration.

```json
{
  "file_names": {
    "pbrt_scene": "scene.pbrt",
    "working_image": "working_scene.png",
    "archive_image": "{scene_name}_{timestamp}.png"
  },

  "file_paths": {
    "scene_files": "scene_workspace/scene_files",
    "local_archive": "Archive",
    "remote_archive": "gdrive:wipImages/pbrt-v4",
    "pbrt_executable": "/home/rpf4/pbrt-v4/build/pbrt"
  },

  "camera_settings": {
    "enabled": true,
    "type": "perspective",
    "look_at": {
      "eye": [290.0, 165.0, 365.0],
      "look": [5.0, 155.0, -5.0],
      "up": [0.0, 1.0, 0.0]
    },
    "fov": 50.0
  },

  "render_settings": {
    "film": {
      "x_resolution": 2000,
      "y_resolution": 1450
    },
    "sampler": {
      "type": "halton",
      "pixel_samples": 512
    },
    "integrator": {
      "type": "volpath",
      "max_depth": 80
    },
    "backend": {
      "type": "gpu",
      "show_statistics": true
    }
  },

  "scene_description": {
    "mode": "new",
    "name": "Poppy Field Overcast 8AM Study",

    "scene_context": {
      "date": "2026-06-21",
      "local_time": "08:00:00",
      "time_zone": "America/New_York",
      "latitude": 43.0,
      "longitude": -76.0,
      "world_north": [0.0, 0.0, 1.0]
    },

    "landforms": [
      {
        "name": "foreground_meadow",
        "enabled": true,
        "placement": {
          "position": [-400.0, 0.0, -700.0],
          "rotation_degrees": [0.0, 0.0, 0.0]
        },
        "geometry": {
          "patches": []
        },
        "topography": {
          "enabled": false
        },
        "surface": {
          "material": {
            "type": "diffuse",
            "reflectance": [0.10, 0.17, 0.045],
            "reflectance_scale": 1.0
          },
          "texture": {
            "enabled": false
          }
        },
        "surface_objects": []
      }
    ],

    "water": {
      "enabled": false
    },

    "objects": [
      {
        "name": "surreal_sphere",
        "enabled": false,
        "geometry": {
          "pbrt_shape": "sphere",
          "radius": 100.0
        },
        "placement": {
          "position": [0.0, 100.0, -500.0],
          "rotation": [0.0, 0.0, 0.0]
        },
        "material": {
          "type": "diffuse",
          "reflectance": [0.8, 0.1, 0.2]
        }
      }
    ],

    "sky": {
      "background": {
        "enabled": true,
        "type": "infinite",
        "color_mode": "rgb",
        "color": [0.62, 0.68, 0.75],
        "scale": 0.16
      },
      "sun": {
        "enabled": true,
        "type": "distant",
        "use_astronomical_direction": true,
        "from": [63.5, 60.7, -47.8],
        "to": [0.0, 0.0, 0.0],
        "color_mode": "blackbody",
        "temperature": 5700,
        "scale": 2.0
      },
      "clouds": [
        {
          "name": "overcast_cloud_deck",
          "enabled": true,
          "placement": {
            "position": [-15000.0, 850.0, -10000.0]
          },
          "dimensions": [50000.0, 800.0, 26000.0],
          "density_field": {
            "generator": "mottled_veil",
            "resolution": [160, 40, 120],
            "shape": {},
            "noise": {}
          },
          "medium": {
            "type": "rgbgrid",
            "scattering": [0.0028, 0.0030, 0.0032],
            "absorption": [0.00045, 0.00050, 0.00055],
            "anisotropy": 0.25,
            "underside": {}
          }
        }
      ]
    },

    "atmosphere": {
      "fog": [],
      "haze": [],
      "mist": [],
      "rain": []
    }
  }
}
```

Empty arrays and objects above mark lower-level structures that have not yet
been reviewed. They do not imply hidden defaults.

## Landforms

A landform is a named scene object constructed from one or more geometry
patches. A scene may contain any number of independently named landforms.
Their names are descriptive identifiers only; words such as `foreground` or
`background` do not cause placement or rendering behavior.

Each landform owns:

- its geometry patches;
- its placement;
- its topography;
- its surface appearance; and
- the objects placed on or growing from its surface.

If four plane patches form one continuous artistic ground surface, they can be
four geometry patches within one landform. If those planes require
independent surfaces, surface objects, or topography, they should be separate
landforms.

`patch` is the agreed term for a constituent surface section of a landform.
The schema does not use `primitive` in this additional capacity; that established
graphics term remains reserved for fundamental geometric shapes such as a
sphere, triangle, disk, or curve.

```json
{
  "name": "foreground_meadow",
  "enabled": true,
  "placement": {
    "position": [-400.0, 0.0, -700.0],
    "rotation_degrees": [0.0, 0.0, 0.0]
  },
  "geometry": {
    "patches": [
      {
        "name": "main_patch",
        "enabled": true,
        "generator": "plane",
        "dimensions": [3000.0, 2800.0],
        "subdivisions": [401, 337],
        "local_position": [0.0, 0.0, 0.0],
        "local_rotation_degrees": [0.0, 0.0, 0.0]
      }
    ]
  },
  "topography": {
    "enabled": false
  },
  "surface": {
    "material": {
      "type": "diffuse",
      "reflectance": [0.10, 0.17, 0.045],
      "reflectance_scale": 1.0
    },
    "texture": {
      "enabled": false
    }
  },
  "surface_objects": []
}
```

`plane` in this example would be an Art Studio geometry generator, not a
preexisting landform and not a PBRT-v4 shape name. Its dimensions, placement,
subdivision, and other image-affecting inputs must be explicit when its detailed
schema is defined.

## Standalone scene objects

`scene_description.objects` contains independently placed visible geometry that
is not a landform, sky component, atmospheric effect, or population growing on
a landform. Examples include a surreal sphere, sculpture, building, or abstract
geometric form.

This collection is part of the current schema generation. It is not the
generalized reusable source-object and editable-instance architecture deferred
to `2gen`. Every current-generation object contains its complete geometry,
placement, and material definition in the active scene.

The geometry can select a native PBRT-v4 shape explicitly, for example
`pbrt_shape: "sphere"`. Geometry requiring construction beyond a native PBRT
shape instead selects a registered Art Studio `generator`. These fields are
distinct and must not be treated as interchangeable labels.

## Sky

The `sky` section owns the natural sky system:

1. `background` supplies visible sky radiance and broad environmental
   illumination.
2. `sun` supplies directional sunlight.
3. `clouds` contains named volumetric formations in the sky.

The background uses PBRT-v4's `infinite` light. It has no world-space position,
distance, or dimensions. A constant RGB background exposes its color and scale
directly. An environment-image form may be considered later, but no custom
`uniform` preset is part of this schema.

The sun uses PBRT-v4's `distant` light. Its `from` and `to` values determine
only a direction; the light has no finite world-space position. A separate
top-level lighting module is not currently required. If future scenes introduce
artificial lamps or studio lights, that need can be evaluated then.

Clouds are grouped under `sky` for artistic navigation, but remain bounded
three-dimensional participating media. Each cloud object must eventually
contain its complete placement, extent, density construction, grid resolution,
scattering, absorption, anisotropy, and other active controls. Shared hidden
cloud defaults are not permitted.

## Atmosphere

All cloud objects belong exclusively to `sky.clouds`. This includes individual
cumulus clouds, horizon clouds, storm clouds, and continuous overcast cloud
decks. The `atmosphere` section does not contain cloud objects.

`atmosphere` contains fog, haze, mist, and rain. A rain volume may originate
visually beneath a cloud, but it remains a separate atmospheric object rather
than part of the cloud definition.

Clouds and atmospheric effects may both use PBRT-v4 participating media. Their
shared volumetric implementation does not change their configuration ownership.
There is no separate generic `volumetrics` section. Every cloud or atmospheric
object owns its own medium type and active optical controls. The global
volume-capable `volpath` integrator remains in `render_settings`.

## Surface objects

`surface_objects` is the explicit collection of objects placed on, scattered
over, or growing from a landform's surface. It is an Art Studio schema term,
not a PBRT-v4 type, and has no independent rendering behavior. The prototype
does not subdivide this collection into a permanent taxonomy.

```json
"surface_objects": [
  {
    "name": "foreground_poppies",
    "enabled": true,
    "construction": {
      "generator": "poppy",
      "stem": {},
      "leaves": {},
      "flower_head": {},
      "petals": {},
      "pistil": {}
    },
    "population": {},
    "appearance": {}
  },
  {
    "name": "left_live_oaks",
    "enabled": true,
    "construction": {
      "generator": "live_oak"
    },
    "population": {},
    "tree_structure": {},
    "appearance": {}
  }
]
```

The Art Studio selects and configures registered generators; it does not author
generator algorithms. A new generator such as `pansy` is developed ad hoc in
Python or C++, tested independently, and registered with the builder. Once it
exists, the live configuration can select it and expose its explicit inputs.

A new population or variation normally reuses an existing generator with
different visible parameters. A new generator is warranted only when the
construction logic itself differs.

## Render settings and volumetrics

`volpath` is the agreed integrator for scenes containing clouds, fog, rain, or
other participating media. It is a global rendering decision and does not
belong inside `sky`, `clouds`, or `atmosphere`.

The renderer backend is a separate explicit choice:

- `integrator.type: "volpath"` selects volumetric path tracing.
- `backend.type: "gpu"` selects GPU execution.
- each volume independently declares its PBRT-v4 medium type, such as
  `rgbgrid`, `uniformgrid`, `cloud`, `homogeneous`, or `nanovdb`.

## Scope decisions recorded

The artist uses the following review notation:

- `Yes`: include in the ground-level schema and implement with available code.
- `Yes_PH`: include a visible configuration placeholder without implementing
  its generator or rendering code yet.
- `2gen`: defer to a second generation of the configuration and application.

### `Yes`

- Existing surface-object systems beyond flowers and trees: grass, weeds,
  undergrowth, rocks, stones, and litter.
- Explicit date, time, latitude, and view-orientation information.
- Explicit neutral camera and sky values when a blank scene is initialized.
- Multi-pass light-shaft compositing and applicable render-pipeline controls.
- Local and remote archive handling.
- Immutable render-input snapshotting. This is mandatory pipeline behavior, not
  an artistic option or a switch that can be disabled in the scene
  configuration. The pipeline freezes its inputs when a render begins and
  archives those exact inputs with the completed render.

### `Yes_PH`

- Water and ocean capability. The ground-level schema will include a visible,
  disabled placeholder, but no new water generator or rendering implementation
  is part of this generation.

### `2gen`

- A generalized system distinguishing landscape, abstract, and experimental
  scene types.
- A generalized architecture for reusable source objects and editable scene
  instances, including direct placement and population instancing.
- A permanent taxonomy or grouping system for grass, flora, trees, weeds,
  undergrowth, rocks, stones, litter, and other landform surface objects.

## Ground-level review status

All fourteen architectural issues identified for this review are resolved.
The approved decisions must now be expressed in a ground-level draft that
enumerates exact fields, valid values, and current-to-proposed paths. That draft
must not introduce hidden defaults or become a disconnected replacement
configuration.

## Resolved ground-level decisions

### Issue 1: file names and file paths

`file_names` contains the files or naming patterns deliberately exposed to the
artist and pipeline. `file_paths` contains directories and executable
locations. `scene_description.name` remains a descriptive scene name rather
than a filename.

The archive filename pattern is explicitly visible as
`{scene_name}_{timestamp}.png`. Generated cloud grids and similar intermediate
artifacts remain managed by their generators rather than cluttering the
top-level file sections.

### Issue 2: direct PBRT shapes and Art Studio geometry generators

The current schema supports both direct PBRT-v4 shapes and registered Art
Studio geometry generators. `pbrt_shape` explicitly selects a native PBRT-v4
shape such as `sphere`. `generator` explicitly selects Art Studio construction
code such as the proposed finite `plane` generator. A generator must expose all
of its artistically meaningful inputs.

`scene_description.objects` is included in the current schema for independently
placed geometry such as a surreal sphere. This simple current-scene collection
does not implement the generalized reusable source-object and editable-instance
architecture deferred to `2gen`.

### Issue 3A: landform placement and dimensions

A landform's `placement.position` and `placement.rotation_degrees` move and
rotate the complete landform, including all of its patches and surface objects. A
landform-level scale is deliberately omitted so that size is not controlled in
two competing places.

Each entry in `geometry.patches` is one constituent landform surface and owns
its `dimensions`, `subdivisions`, `local_position`, and
`local_rotation_degrees`. Dimensions therefore belong to the individual patch,
while local placement locates that patch within the landform. Additional
patches may be added to construct a larger compound landform.

A rectangular plane patch uses `dimensions`. The plane generator may be
extended over time with nonrectangular planar footprints such as triangles and
trapezoids, using explicit generator-specific coordinates. This remains patch
geometry rather than a separate landform boundary system, and the initial
refactor does not have to implement every footprint type.

`primitive` is not used as a landform collection name. It retains its
conventional graphics meaning for fundamental geometric shapes. `plane` in the
landform example selects an Art Studio mesh generator; it does not assert that
PBRT-v4 provides a native plane shape.

### Issue 3B: landform topography

Topography is the landform's shared elevation system. It is declared once for
the complete landform and evaluated on the vertices of every patch in shared
landform-local coordinates. The patches remain separate meshes, but adjacent
patches receive matching elevations from the same function. Flora, trees, and
terrain-aware surface objects query that same elevation system for placement.

Patch geometry continues to own horizontal dimensions, subdivisions, triangle
connectivity, and local placement. Topography changes vertex elevation and the
resulting surface normals; it does not change those patch geometry controls.
Per-patch topography overrides are not included in this schema generation. A
surface requiring fundamentally different elevation behavior should normally
be a separate landform.

A simple flat plane uses an explicit disabled topography block:

```json
"topography": {
  "enabled": false
}
```

The existing terrain implementation is represented explicitly when enabled:

```json
"topography": {
  "enabled": true,
  "generator": "rolling_hillside",
  "slope": {
    "enabled": true,
    "direction_degrees": 320.0,
    "grade": 0.4,
    "foreground_leveling": {
      "enabled": true,
      "direction_degrees": 51.5,
      "start": 0.0,
      "end": 360.0,
      "minimum_grade_ratio": 0.35
    }
  },
  "noise": {
    "enabled": true,
    "algorithm": "value_noise",
    "seed": 7,
    "amplitude": 14.0,
    "frequency": 0.008,
    "octaves": 3,
    "persistence": 0.45,
    "lacunarity": 2.0
  },
  "features": [
    {
      "name": "right_dip_rise",
      "enabled": true,
      "generator": "dip_rise_profile",
      "direction_degrees": 142.0,
      "dip_center": 140.0,
      "dip_width": 140.0,
      "dip_depth": 100.0,
      "rise_center": 480.0,
      "rise_width": 150.0,
      "rise_height": 260.0
    }
  ]
}
```

`rolling_hillside` selects existing Art Studio construction code rather than a
preset with hidden artistic values. All meaningful controls remain visible.
Size, center, and resolution do not appear under topography because Issue 3A
assigns their responsibilities to patch geometry and placement. The former
`base_height` control is omitted; vertical movement of the complete landform is
controlled only by `placement.position[1]`.

### Issue 3C1: landform material

Each landform owns one material, and that material applies to all of its
patches. Patches requiring different materials should be organized as separate
landforms rather than introducing per-patch material overrides.

```json
"surface": {
  "material": {
    "type": "diffuse",
    "reflectance": [0.10, 0.17, 0.045],
    "reflectance_scale": 1.0
  },
  "texture": {}
}
```

`material.type` directly identifies the PBRT-v4 material type. Its applicable
PBRT controls remain adjacent inside the material block. `reflectance` is the
base linear RGB color. `reflectance_scale` is an explicitly named Art Studio
multiplier rather than a native PBRT diffuse-material parameter, and its
neutral value of `1.0` is written rather than hidden. Procedural color
variation, mottling, and fine bump detail belong separately under
`surface.texture`.

### Issue 3C2: landform surface texture and noise patterns

Every landform independently owns one optional surface-texture system. That
system may combine multiple named, artist-configurable noise patterns into one
coherent surface treatment; it is not a stack of separate materials or
landforms.

Surface-pattern noise is distinct from topographic noise. Topographic noise
changes mesh elevation and terrain-aware placement height. Surface-pattern
noise changes reflectance, mottling, color variation, or fine bump response.
Fine bump changes shading normals but does not change the landform elevation
queried by grass, flora, or trees.

```json
"texture": {
  "enabled": true,
  "generator": "procedural_surface",
  "mapping": {
    "coordinate_space": "landform",
    "scale": [1.0, 1.0],
    "rotation_degrees": 0.0,
    "offset": [0.0, 0.0]
  },
  "patterns": [
    {
      "name": "broad_clusters",
      "enabled": true,
      "algorithm": "periodic_filtered_noise",
      "seed": 941,
      "feature_size": 0.08,
      "weight": 1.0
    },
    {
      "name": "medium_mottle",
      "enabled": true,
      "algorithm": "periodic_filtered_noise",
      "seed": 942,
      "feature_size": 0.012,
      "weight": 0.72
    },
    {
      "name": "fine_accents",
      "enabled": true,
      "algorithm": "periodic_filtered_noise",
      "seed": 943,
      "feature_size": 0.003,
      "weight": 0.28
    }
  ],
  "composition": {
    "coverage": 0.10,
    "softness": 0.08,
    "contrast": 0.85,
    "base_reflectance_weight": 1.0,
    "mottle_reflectance": [0.12, 0.18, 0.06],
    "accent_reflectance": [0.28, 0.32, 0.10],
    "accent_fraction": 0.06
  },
  "bump": {
    "enabled": false
  }
}
```

The texture maps continuously across the complete landform rather than
restarting on each patch. Its generator begins with the landform material's
base reflectance and introduces the configured variation; the explicit
`material.reflectance_scale` applies to the result. Different landforms may use
different texture generators and completely independent pattern definitions.

The configuration may craft new patterns from registered noise operations.
An entirely new noise algorithm still requires implementation and registration
in Python or C++ before the configuration can select it. The current far-vista
generator's broad cluster, medium mottle, and fine noise fields are the model
for this capability. Artistically meaningful mixture weights, thresholds, and
composition values that are currently hard-coded must become explicit during
migration.

### Issue 3D: no general landform boundary category

The provisional general-purpose `boundary` category is eliminated. It would
ambiguously combine several different responsibilities that already have
clearer homes:

- patch geometry determines the physical extent of a surface;
- population controls determine where grass, flora, trees, and other surface objects
  may be placed;
- surface texture controls determine visual edge effects; and
- any future transition between separate landforms must be an explicitly named
  relationship rather than hidden boundary behavior.

Nonrectangular planar geometry remains an extensible patch capability rather
than an immediate requirement to implement every shape. A rectangular plane
patch uses dimensions. The Art Studio plane generator may gain triangular,
trapezoidal, and other polygonal footprints over time, with explicit footprint
coordinates when each form is implemented. The renderer does not automatically
blend neighboring landforms.

### Issue 4: existing generator inputs during prototype migration

Detailed field-by-field review of the existing poppy, sunflower, grass, and
tree controls is deferred until the prototype hierarchy is established. This
does not mean omitting those controls or replacing them with hidden defaults.

When an existing generator is migrated into the new hierarchy, its complete
current configuration moves with it in one atomic step. Existing values and
internal control names—such as bend, angles, tropism, construction dimensions,
and variation controls—remain intact without requiring individual artistic
review during the structural move. The builder, validation, and applicable Art
Studio controls are updated to the new location at the same time. The old live
path is then removed; duplicate authoritative values are not retained.

Where the structural relocation is intended to preserve behavior, the
generated PBRT output should be compared before and after the move, including a
byte-for-byte comparison when deterministic generation makes that possible.
Detailed renaming, regrouping, and removal of obsolete generator fields becomes
a later ground-level rationalization exercise after the prototype
configuration is operating.

### Issue 5: construction and population

`construction` defines one generated plant, tree, grass tuft, or other reusable
form within the current scene. `population` defines how copies of that form are
placed on the landform that contains it. Because the population is nested under
a landform, that landform is automatically its placement surface.

The initial population methods are `scatter` and `explicit`. `scatter` covers
distributed grass, flowers, groves, and similar populations. `explicit` covers
individually positioned trees and other deliberately arranged instances. All
existing scatter, count, seed, scale, rotation, frustum, depth-fade, and
terrain-alignment controls move intact under `population` without requiring
detailed review during the prototype migration.

This structure applies to grass. Grass `construction` defines one tuft,
including its blade count and blade geometry, while grass `population.count`
specifies the number of tufts distributed on the landform. This remains a
scene-local population mechanism rather than the generalized reusable
source-object architecture deferred to `2gen`.

### Issue 6: surface objects; permanent grouping deferred

`surface` is reserved for a landform's material and texture. The former
provisional `contents` term is replaced by `surface_objects`, meaning the flat
collection of objects placed on, scattered over, or growing from a landform's
surface. The prototype does not subdivide that collection into permanent
grass, flora, tree, rock, or litter categories; that taxonomy is deferred to
`2gen`. Each entry's descriptive name and registered construction generator
identify its present role.

Mountains, cliffs, ridges, and large geological masses are normally landforms
or parts of landform geometry/topography rather than surface objects. Discrete
boulders and stones resting on terrain are surface objects. A freestanding
geological or surreal form that is not owned by a landform belongs under
`scene_description.objects`.

### Issue 7: disabled water placeholder

Water is a top-level scene module beside `landforms`, `objects`, `sky`, and
`atmosphere`. It is not a landform material or a landform surface object. The
first-generation schema contains only the agreed visible disabled placeholder:

```json
"water": {
  "enabled": false
}
```

This `Yes_PH` entry does not imply implemented water behavior or hidden
defaults. Geometry, waves, optical properties, depth, shoreline interaction,
named water bodies, and generator controls will be designed and exposed only
when water functionality is implemented.

### Issue 8: self-contained cloud objects

Every cloud is a complete, independently editable object under `sky.clouds`.
The current shared cloud-level appearance, shape, and noise blocks are removed
during migration; each cloud carries its own existing values. Repetition
between similar clouds is accepted in this generation because reusable cloud
sources and presets belong to the object architecture deferred to `2gen`.

Each cloud has three explicit responsibilities:

- `placement` and `dimensions` locate and bound the volumetric object;
- `density_field` selects its Art Studio generator and contains its grid
  resolution, shape, lobes, fades, depth slope, and noise controls; and
- `medium` identifies the PBRT-v4 medium type and contains scattering,
  absorption, anisotropy, underside variation, and other optical controls.

All existing cloud controls move intact into these blocks without a detailed
value-by-value review. The structural migration is not a visual redesign.

### Issue 9: atmosphere systems and placeholders

The first-generation atmosphere structure retains the four agreed artistic
categories:

```json
"atmosphere": {
  "fog": [],
  "haze": [],
  "mist": [],
  "rain": []
}
```

Fog and rain-curtain generation already exist. Their complete current controls
move intact into independently named entries under `atmosphere.fog` and
`atmosphere.rain`. Haze and mist are reserved empty placeholders until their
distinct behavior is developed; they do not imply implemented generators or
hidden defaults.

Clouds remain exclusively under `sky.clouds`. Each implemented atmospheric
volume owns its placement, dimensions, density construction, and medium optical
controls. No separate generic `volumetrics` category is introduced. Proposed
generator names used in schema discussion are not treated as registered
functionality unless corresponding code actually exists.

### Issue 10: astronomical context and explicit sun direction

`scene_description.scene_context` records the date, local time, IANA time-zone
name, latitude, longitude, and the world-space vector that represents north.
These values make the scene's intended place, time, and orientation explicit.

The sun contains the boolean `use_astronomical_direction`:

- when `true`, the application calculates the sun direction from
  `scene_context`; and
- when `false`, the configured PBRT-v4 `from` and `to` values determine the
  sun direction.

The boolean is the sole selector between the two modes. The inactive direction
source must not override or modify the active one. Existing scenes initially
migrate with `use_astronomical_direction: false` so their rendered appearance
is preserved exactly.

Sun color mode, temperature or color, and scale remain explicit artistic
controls in either mode. The infinite-sky color and scale also remain explicit;
they are not calculated silently from the astronomical context. Camera
orientation remains defined by its `look_at` values and can be interpreted
relative to `world_north` without adding a second competing view-direction
control.

### Issue 11: neutral blank-scene camera and sky

A genuinely new blank scene begins with an enabled perspective camera using
these explicit diagnostic values:

```json
"camera_settings": {
  "enabled": true,
  "type": "perspective",
  "look_at": {
    "eye": [0.0, 2.0, 10.0],
    "look": [0.0, 0.0, 0.0],
    "up": [0.0, 1.0, 0.0]
  },
  "fov": 50.0
}
```

It starts above the ground, looks toward the origin, and uses positive Y as up.
The blank sky supplies neutral white illumination without an assumed time of
day or directional sun:

```json
"background": {
  "enabled": true,
  "type": "infinite",
  "color_mode": "rgb",
  "color": [1.0, 1.0, 1.0],
  "scale": 1.0
},
"sun": {
  "enabled": false
}
```

These are initialization values only. Migrated scenes preserve their existing
camera, infinite-sky, and sun settings.

### Issue 12: multi-pass light-shaft rendering

The implemented light-shaft workflow is an optional rendering and compositing
method, so its pass and image-combination controls move from the vague
top-level `pipeline` block to `render_settings.shaft_composite`:

```json
"shaft_composite": {
  "enabled": false,
  "shaft_light": "shaft_sun",
  "base_opacity": 1.0,
  "shaft_opacity": 0.40,
  "surface_reflectance_scale": 0.08,
  "terrain_reflectance_scale": 0.015,
  "blur_radius": 2.0
}
```

When disabled, the application produces one ordinary PBRT render. When enabled,
it produces the base pass, shaft pass, and final composite. Both diagnostic
passes are always retained; reproducibility is mandatory pipeline behavior and
not an optional artistic switch.

The physical and artistic formation of the shaft—its light and cloud-aperture
construction—belongs with the sun under `scene_description.sky`. Only the
multi-pass execution and image-combination values belong under
`render_settings`. All currently implemented composite values move intact.
This organization is approved for the prototype and must be validated during
staged migration rather than treated as irreversible.

### Issue 13: local archive, Google Drive, and immutable snapshots

Archive naming remains under `file_names`, while the two archive destinations
remain explicit under `file_paths`:

```json
"file_names": {
  "archive_image": "{scene_name}_{timestamp}.png"
},
"file_paths": {
  "local_archive": "Archive",
  "remote_archive": "gdrive:wipImages/pbrt-v4"
}
```

Starting a render creates one timestamp and render identifier, then immediately
freezes the authoritative `config.json` and every generator or source file
needed for that render. The PBRT scene must be built from those frozen inputs,
not from live files that could be edited while the process is running.

The completed bundle contains the final image, exact input snapshots, generated
PBRT files, required scripts, diagnostic passes, and a manifest of filenames
and hashes. The bundle is saved to the local archive first and then copied to
the configured Google Drive archive without overwriting another render.

Snapshotting is mandatory application behavior and has no configuration switch.
GitHub is separate from both render archives: development checkpoints may
commit source code, JSON, and documentation, but rendered PNGs and generated
PBRT files do not belong in the repository.

### Issue 14: staged migration of the authoritative configuration

Migration proceeds in this order:

1. Complete the ground-level schema, including the exact cloud
   `density_field` contract, without changing the live configuration.
2. Implement mandatory render-input snapshotting.
3. Implement and validate the standalone CPU-based C++ cloud density-grid
   generator described below.
4. Move `file_names` and `file_paths`.
5. Move camera controls into `camera_settings`.
6. Move film, sampler, integrator, backend, and shaft-compositing controls into
   `render_settings`.
7. Establish `scene_description` with `mode`, `name`, and `scene_context`.
8. Migrate landforms one at a time: first their geometry, placement,
   topography, material, and texture, then their grass, flowers, trees, and
   other `surface_objects`, one generator at a time.
9. Migrate independently placed `objects`.
10. Migrate the sky: infinite background, sun, and then each cloud separately.
11. Migrate atmosphere: fog, rain, and the empty haze and mist placeholders.
12. Add the disabled water placeholder.
13. Remove obsolete legacy paths and temporary compatibility code.

`scene_workspace/config.json` remains the sole authoritative configuration
throughout. Each stage moves values rather than copying them; the old path is
removed when the new path becomes active. The builder, validation, and Qt
inspector change together. Existing parameter values and rendered behavior are
preserved, and tests plus a structural PBRT comparison precede the next stage.
A Git checkpoint records each stable migration stage.

The neutral initialization values from Issue 11 apply only when creating a
genuinely new blank scene. They never replace the camera, sky, or other values
of a migrated scene.

#### Pre-migration C++ cloud density-grid generator

The targeted compiled accelerator is a standalone C++ cloud density-grid
generator, not a rewrite of the Python application or the PBRT-v4/CUDA renderer.
Python supplies it with a small normalized grid specification rather than the
C++ program reading the complete live `config.json`. This contract insulates
the generator from both the legacy and proposed configuration layouts.

The implemented helper has a deterministic single-CPU reference path verified
on small grids against the existing Python generator. CPU multithreading is
also deterministic and the helper streams its PBRT declaration to its output
file. The current Python path remains available as the reference and fallback.
Caching remains a later optimization because correctness and the measured
compiled build time do not currently require it. A limited visual comparison
still validates pipeline integration before live schema migration begins.

Additional high-density cloud experiments are deferred until this accelerator
is connected. Grid-construction time and PBRT volumetric render time must be
measured separately: compiled grid construction cannot by itself correct an
expensive `volpath` render caused by a very large or dense volume.

## Migration rule

After this schema is approved, migration must occur in tested, usable stages
inside `scene_workspace/config.json`. Move one complete artistic object at a
time and update its builder, validation, and Art Studio interface together.
Do not retain duplicate live values at old and new paths, and do not create a
second authoritative scene JSON.
