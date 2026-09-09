# Moonlight spectrum and nighttime appearance

Research requested by the artist on 2026-09-08 after `223019`: the image
looked like a dimmed sun. Findings below inform a future lighting/display
revision; no perceptual rendering implementation is authorized by this note.

## Spectrum: red is present

Moonlight is broadband reflected sunlight, not a single frequency or a blue
light with red removed. For orientation, 400–700 nm corresponds approximately
to 750–430 THz, using frequency = speed of light / wavelength. This is a
convenient visible-band interval, not a sharp physiological cutoff.

NIST's 2013 near-full-Moon measurement reports these spectral irradiances:

| Wavelength | Spectral irradiance (µW m⁻² nm⁻¹) |
| --- | ---: |
| 449.7 nm (blue) | 2.348 |
| 550.0 nm (green) | 2.633 |
| 650.1 nm (red) | 2.598 |

These are from one observation with atmospheric corrections, not a universal
ground-level full-Moon preset. They establish that substantial red is present.
The paper reports continuous coverage and discusses atmospheric absorption
limitations. [Cramer et al., NIST, 2013, Table 1](https://nvlpubs.nist.gov/nistpubs/jres/118/jres.118.020.pdf).

## Surface reflection and perception are different

There is no ordinary surface-color category that moonlight categorically
cannot reflect from. Reflected spectral radiance depends on the incoming
spectrum and the material's wavelength-dependent reflection, as well as
geometry. A red material still reflects its red component; an absorbing
material returns little light. Color names or RGB triplets alone do not fully
specify a material's spectrum. [NIST reflection and transmission](https://www.nist.gov/news-events/news/2022/01/measuring-light-reflection-and-transmission).

At low adaptation levels, visual weighting shifts toward shorter wavelengths.
Reds can appear relatively darker, while blue-green surfaces may remain
relatively conspicuous. This is not red radiation disappearing. The CIE
distinguishes photopic, scotopic, and intermediate mesopic weighting; its
mesopic system depends on both adaptation luminance and spectral composition.
These brightness functions alone are not a complete color-appearance model.
[CIE TN 004:2016](https://files.cie.co.at/841_CIE_TN_004-2016.pdf).

Do not impose a blanket rule that all colors, or all reds, disappear under a
full Moon. Smith and colleagues tested actual full-moon viewing and found
recognition depended on hue, saturation, and angular size. Saturated red could
be recognized accurately. [Smith et al., 1994](https://opg.optica.org/ao/abstract.cfm?uri=ao-33-21-4741).

## Why 223019 was insufficient

Local source inspection confirms the study used an artistic RGB distant light
`[0.88,0.94,1]` at scale 0.45, with a dim blue environment. It did not use
measured lunar irradiance or calibrated adaptation levels. The builder writes
`Film "rgb"`; the installed PBRT `film.cpp` defaults to the `cie1931` sensor.
This path has no added rod/cone adaptation or nighttime appearance stage.
PBRT remains spectral internally; RGB image output is not itself the defect.

The proposed next approach separates physical illumination from its displayed
appearance: retain a broad lunar spectrum, calibrate light/exposure, then
model reduced colorfulness and changed relative brightness at low adaptation
levels. Preserve pale highlights and readable shapes without making ordinary
greens look like dim daylight. Exact color ranking requires actual material
spectra; a simple RGB/desaturation treatment would be an explicit artistic
approximation. Do not modify the PBRT/CUDA build without artist authorization.

Jensen and colleagues' *Night Rendering* treats illumination and visual
adaptation separately. Its hue/detail treatment includes empirical artistic
choices, so it is a useful foundation rather than an exact physiological
solution. [Author-hosted paper](https://graphics.stanford.edu/~henrik/papers/night/night.pdf).

## Current scene action

At the artist's subsequent request, `flower_probability` is now zero. All 26
blossoms are removed from placement; the 32 clusters / 96 pads and their
transforms are unchanged. Flower recipes remain available but unused. The
existing generator still defines unused flowering prototypes. Lighting is
unchanged while the research is discussed. The pads-only render launch was
declined, so `223019` remains the latest image and still shows flowers.

## Proposed simulation of reduced color/detail discrimination

The artist asked how the reduced visual sensitivity would be simulated.
The proposed observer is dark-adapted: sensitivity to faint light increases,
while color discrimination and fine-detail discrimination decrease. This is
not a second blue light or a modification of the plant recipes.

Work from linear HDR radiance before PNG encoding. Prefer a spectral output
from the existing renderer, retaining both cone-weighted and rod-weighted
brightness. Installed PBRT source contains a spectral-film EXR writer, but
its end-to-end GPU/archive integration still needs validation; do not claim it
implemented or rebuild PBRT. An RGB-only estimate would be labeled approximate
because three color channels cannot recover arbitrary material spectra.

Use scene luminance plus a stable adaptation level to blend mesopic and
scotopic appearance. Dark regions lose saturation most, with wavelength-aware
relative brightness; illuminated pale surfaces retain detail and readability.
Avoid independent auto-normalization of every pixel, which would lift all
shadows. Keep exposure/display brightness distinct from adaptation. Limit loss
of fine texture using an edge-preserving treatment, not a uniform blur. Cool
night coloration, if used, is an artistic display control rather than removal
of red light. A printed or brightly displayed image requires this appearance
mapping because the viewer's eyes are not adapted to the depicted luminance.

First validation would compare ordinary output and the observer mapping from
the same frozen render, with the same geometry/light/materials. Judge pads,
red/brown objects, pale stone, cloud reflections, and deep shadows. Preserve
raw HDR and all mapping controls in each archive. No implementation or new
render was authorized by the research question itself.
