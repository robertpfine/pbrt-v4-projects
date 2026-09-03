# Scene Module Boundaries

PBRT-v4 Art Studio keeps one authoritative configuration at
`scene_workspace/config.json`. The landscape/sky migration establishes these
artistic boundaries without changing the accepted rendered scene:

```text
scene
├── fog
├── rain
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
│   ├── water
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
geometry. Its generator and Qt controls remain independent of the accepted
ground system. The retained configuration now contains one `broad_rise`
height field; the complete module is disabled in accepted render `054517`.
Grass and poppy definitions stay under ground details and may target the rise
through their own `extension` blocks when the hill module is enabled.

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

That implementation now uses deterministic gradient-Perlin fBm and is described
in [`distant-hills-configuration.md`](distant-hills-configuration.md). Exact
preservation was verified with the module disabled: the complete generated PBRT
scene retained its accepted 936,127,421-byte size and SHA-256 hash
`dfb1781890823c10da1d483358294748d3d2ad2db767a168e24c54774f88a929`.

### Water boundary

Water is the third ordered element of Step 4, after distant hills and clouds.
It is a first-class landscape system on the same architectural level as distant
hills, not a ground material or generic geometry entry. Its live boundary is
now established and disabled at `scene.landscape.water`; its generators and
artistic controls remain the third implementation element.

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

`scene.sky.clouds` is the explicit boundary for the implemented cloud system.
It is enabled in the accepted `054517` scene with two bounded cumulus
formations.

### Cloud-formation implementation

Clouds are bounded volumetric formation objects rather than surface meshes or
sky textures. The current cumulus form combines an artist-designed envelope,
smoothly blended ellipsoidal density lobes, a vertical profile, three-dimensional
Perlin fractal sums, and domain warping. Noise refines the macro form and creates
the accepted mottled internal texture. Separate RGB absorption/scattering grids
darken the cloud undersides.

Shape parameters remain separate from optical properties such as density,
scattering, absorption, and phase anisotropy. The artistic configuration names
each formation; PBRT heterogeneous media remain a subordinate backend choice.
Clouds remain discrete sky objects while fog is an atmosphere medium. The live
scene uses two independently sized cumulus formations. The artist selected the
`025537` grids—`[120,72,48]` and `[128,80,52]`—over a subsequent four-times-
denser test.

The broad `mottled_veil` experiment remains implemented but is not active. The
artist rejected its whole-sky use in `023731`, while retaining one soft
horizontal fragment as a possible future horizon-cloud treatment.

Atmosphere, lighting, and camera remain separate artistic categories. The
current `scene.fog` structure is the existing atmosphere implementation and is
outside this bounded landscape/sky migration.

## Atmosphere and weather

`scene.fog` owns the broad atmospheric medium. `scene.rain` owns discrete,
bounded rain curtains and sits directly beside fog in the live JSON rather than
being hidden inside cloud controls. A curtain may visually connect a cloud to
the landscape, but it remains an independently placeable weather volume. The
first implementation uses vertically coherent 3D fractal noise and soft fades
on all six faces; its manual controls are documented in
[`rain-configuration.md`](rain-configuration.md).

## Compatibility rule

The live configuration uses only the new paths. Archived configurations remain
reproducible with the builder source saved in their render bundles; the live
builder does not maintain duplicate legacy paths. This prevents the old and new
hierarchies from drifting apart.
