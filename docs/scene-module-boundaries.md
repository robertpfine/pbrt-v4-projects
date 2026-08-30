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

### Agreed distant-hill formation

The distant hills will be world-space triangular terrain bands, not painted
backdrops or camera-facing billboards. Each band will rise from a concealed
front edge to a designed ridge and descend behind it, producing real slopes and
normals for PBRT lighting and atmospheric interaction.

The primary form comes from explicit, artist-controlled peaks and ridge
profiles: position, height, width, asymmetry, base elevation, and front-to-back
cross-section. Perlin noise is a secondary irregularity and surface treatment;
it must not dictate the overall silhouette. With noise amplitude set to zero,
the configured hill range must still have a convincing intentional shape.

The first study should use three strongly differentiated depth layers: a nearer
darker and more articulated range, a broader middle range, and a simpler paler
far range. The implementation belongs in a dedicated `distant_hills.py` module
and should remain computationally small compared with the grass system.

### Planned water boundary

Water is the third ordered element of Step 4, after distant hills and clouds.
It is a first-class landscape system on the same architectural level as distant
hills, not a ground material or generic geometry entry. Its live boundary will
be `scene.landscape.water`; that key is not added until the third element begins.

The water module will encompass water bodies, surface geometry, wave formation,
optical behavior, and shoreline interaction. Waves remain subordinate behavior
within water. Shore scenes combine ground and water, while open-ocean scenes may
make water the dominant visible landscape and leave ground as seabed or outside
the frame. Candidate wave algorithms—including designed directional waves,
spectral ocean waves, capillary detail, and shore-related deformation—remain
implementation choices to be discussed before that element begins.

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

### Agreed cloud-formation direction

Clouds will be bounded volumetric formation objects rather than surface meshes
or sky textures. The initial cumulus form will combine an artist-designed
envelope, smoothly blended ellipsoidal density lobes, a vertical profile with a
relatively broad base and selected upward towers, and three-dimensional noise
for edge erosion and internal variation. Noise refines rather than composes the
macro form.

Shape parameters remain separate from optical properties such as density,
scattering, absorption, and phase anisotropy. The artistic configuration names
a cloud formation; the selected PBRT heterogeneous-volume representation stays
a subordinate backend choice. Clouds remain discrete sky objects while fog is
an atmosphere medium. Initial scene use should favor several distinct
formations over obvious repetition of one instanced density field.

Atmosphere, lighting, and camera remain separate artistic categories. The
current `scene.fog` structure is the existing atmosphere implementation and is
outside this bounded landscape/sky migration.

## Compatibility rule

The live configuration uses only the new paths. Archived configurations remain
reproducible with the builder source saved in their render bundles; the live
builder does not maintain duplicate legacy paths. This prevents the old and new
hierarchies from drifting apart.
