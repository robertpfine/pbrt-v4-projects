# Scene Module Boundaries

PBRT-v4 Art Studio keeps one authoritative configuration at
`scene_workspace/config.json`. The landscape/sky migration establishes these
artistic boundaries without changing the accepted rendered scene:

```text
scene
├── landscape
│   ├── ground
│   │   ├── active_landform
│   │   ├── landforms
│   │   ├── material
│   │   └── details
│   │       ├── surface
│   │       ├── grass
│   │       ├── poppies
│   │       ├── litter
│   │       ├── rocks
│   │       └── undergrowth
│   └── distant_hills
└── sky
    ├── background
    └── clouds
```

## Landscape

`scene.landscape.ground` owns the contiguous ground system: landform geometry,
ground material, surface treatment, and terrain-aware detail populations. The
complete former `scene.terrain` object moved here without changing its values.

`scene.landscape.distant_hills` is the explicit boundary for receding-horizon
geometry. It is disabled until the step-4 generator and controls are built.

The older tree and phyllotaxis arrays remain at their established scene paths
for now. Moving them would prematurely decide the deferred relationship among
reusable source objects, scene instances, and processes such as L-systems and
space colonization. This bounded migration does not make that decision.

## Sky

`scene.sky.background` owns the neutral infinite environment previously stored
as the first entry in `scene.lights`. The scene builder combines it with the
remaining artistic lights when writing PBRT, preserving light order and output.

`scene.sky.clouds` is the explicit boundary for the future cloud system. It is
disabled until the step-4 generator and controls are built.

Atmosphere, lighting, and camera remain separate artistic categories. The
current `scene.fog` structure is the existing atmosphere implementation and is
outside this bounded landscape/sky migration.

## Compatibility rule

The live configuration uses only the new paths. Archived configurations remain
reproducible with the builder source saved in their render bundles; the live
builder does not maintain duplicate legacy paths. This prevents the old and new
hierarchies from drifting apart.
