# Artistic Tool Vision

Status: Working draft. The artist is developing these thoughts in blocks; do
not treat the document as complete or convert it prematurely into an
implementation specification.

The bounded implementation synthesized from this continuing vision is recorded
separately in
[`qt-proof-of-concept-specification.md`](qt-proof-of-concept-specification.md).

## Foundational purpose

This is a tool for me to create art. It is my medium.

The system should free me to focus on being creative and give me the tools to
create the scene that I can see in my mind. It should remove technical burdens
that interfere with that process. For example, I should no longer have to write
the `.pbrt` scene file myself.

## An evolving medium

The present refactor and introduction of a Qt interface do not mark the
completion of the medium. They establish a clearer foundation for continued
development.

After the refactor, substantial work will remain. The artist will continue to
question existing behavior and develop new ideas that require implementation.
The assistant will continue modifying Python generators, adding capabilities,
exposing parameters, and evolving the interface in response.

The architecture must therefore support an ongoing cycle:

```text
Artistic question or new idea
    -> discussion and clarification
    -> Python implementation
    -> configuration and interface exposure where appropriate
    -> render and artistic evaluation
    -> revision or acceptance
```

Qt is not intended to replace this collaborative development process. It is a
working surface that should make established capabilities easier to use while
remaining open to capabilities that do not yet exist.

The application is named **PBRT-v4 Art Studio**. The name identifies the
creative medium and its PBRT-v4 foundation without tying the application to a
particular scene, visual subject, or rendering implementation.

Renderer-specific names must remain subordinate to the artistic hierarchy.
For example, `rgbgrid` names one particular PBRT-v4 volumetric representation;
it is not a synonym for atmosphere, fog, volumetrics, or the studio itself.

## Beginning a new work

When I sit down ready to create a new work, the first thing I need to think
about is the type of work.

It could be an abstract piece based on the interplay of geometric objects,
lights, and the interaction between the two. Alternatively, it could be a more
figurative piece, such as a landscape. It could also be pure experimentation.

Whichever kind of work it is, realizing it may require more or less
additional coding by the assistant.

## Terminology: project

`Project` is a VS Code term in this context. It refers to an instance or
workspace of VS Code, such as the current body of work opened in VS Code.

Nothing inherent within the artistic medium is presently defined as a project.
Earlier uses of that word for an artwork or internal unit of work were casual
and should not determine the system hierarchy or GUI. A more appropriate term
for an individual artistic undertaking can be chosen later.

The `Project` label visible in the accepted Qt proof-of-concept mockup is
therefore provisional rather than accepted terminology.

## Terminology: scene

A scene is what is encompassed within a `.pbrt` file: everything required by
that file structure to run a render.

A scene represents one complete renderable state. If the camera, lighting, or
any other parameter value changes, the resulting state constitutes a new
scene. Two scenes may be closely related or differ by only one value, but they
are nevertheless distinct scenes.

## Themes and scene grouping

Scenes do not necessarily belong inside a larger mandatory unit such as a
project, work, or artwork. Some scenes will form obvious thematic groupings,
while others may constitute no grouping at all.

Thematic groupings can emerge and evolve over time. A theme might be
subject-based, such as scenes focused on sunflowers. It might also arise from a
visual or atmospheric concern, such as the foggy hillside with light shafts.

These classifications can overlap. Fog or light shafts can be both an
atmospheric choice within a scene and the thematic concern connecting multiple
scenes. Themes should therefore not be treated as exclusive categories or as a
required position in a rigid hierarchy. A scene may participate in multiple
themes or in none.

## Reusable objects and creation processes

Reusable objects are important entities within the medium. The tree used in the
light-shaft scenes and early poppy scenes should be treated as an object that
can be placed directly into a scene or instanced. Future examples will include
objects such as a live oak and a willow.

Once an object has been instantiated in a scene, that instance can be edited.
Its placement and other scene-specific choices belong to the scene rather than
requiring the reusable object to be rebuilt for every use.

Processes also exist. L-systems, space colonization, and a future cloud
generator are examples of processes that can create or shape objects and scene
elements. They may need to remain available through modules in the interface.
However, their exact place in the JSON architecture and GUI hierarchy is not
yet settled, and it is premature to decide it now.

For the present architectural discussion, reusable objects and their instances
are more pertinent than exposing the processes that produced them.

### Source objects and scene instances

Editing an instantiated object affects only that particular instance in its
scene. The reusable source object remains unchanged. Editing a source object is
therefore conceptually different from editing an instance.

Supporting this distinction implies infrastructure that identifies which
objects are instantiable and stores instance-specific edits or overrides. This
adds complexity and may not be appropriate for the initial proof of concept.
The proof of concept can use its required scene elements without first solving
a generalized reusable-object and instance-editing system.

The catalogue of accessible object types will remain fluid. Choices such as
`Poppies`, `Sunflowers`, and future species should eventually be available
through a selector such as a pull-down menu, but the interface must be able to
accommodate new object types without redesigning its hierarchy each time.

Poppies and trees should both provide the option of instancing. They should not
be divided into fundamentally different object mechanisms merely because one
is often distributed as a population and the other is often placed
individually. The timing and interface for generalized instancing remain
subject to the proof-of-concept scope described below.

## Beginning a landscape scene

The question of named starting templates is deferred. Introducing templates at
this point would overcomplicate the proof of concept.

The interface should initially be blank. From the artist's point of view, the
first decision will probably be to choose a landform type. The scene should grow
from that decision rather than beginning as a preassembled composition chosen
by the system.

### Landform-first artistic workflow

The artist-approved workflow begins by choosing a landform. In the simplest
case, that landform is a plane. Once the plane exists, the artist decides what
should be on it and what character it should acquire. Those later decisions
include whether it remains flat or becomes hilly, its color and surface
treatment, and contents such as grass and poppies.

This ordering is a key principle for the refactored configuration and future
interface. The plane is not merely renderer scaffolding hidden elsewhere from
the terrain placed on it. It is the chosen landform that receives its relief,
appearance, and contents through subsequent artistic decisions. The
configuration should make that relationship easy to find and edit manually.

Multiple landforms may be present in one scene. For example, the current poppy
meadow, broad rise, and a future vista plane can each be understood as a
landform with its own placement, form, appearance, and possible contents. This
principle does not by itself prescribe the final JSON nesting or require every
landform to expose identical controls.

Once a landform is selected, the system should supply a neutral sky and a
workable default camera. These are technical starting conditions that make the
new scene renderable, not a named template or a preselected artistic direction.
Both remain available for later artistic adjustment.

After the initial landform creates a renderable scene, all other categories
should become available immediately. The interface should not prescribe a
sequence through ground contents, sky, atmosphere, lighting, or other scene
elements. The artist can work among them in any order.

The type of atmosphere is also a foundational artistic choice. It can determine
the scene's depth, visibility, light behavior, and emotional character, rather
than functioning only as an effect added near the end of composition.

The central atmospheric question is whether the scene uses volumetrics.
Volumetrics are sufficiently potent artistically that they may be desirable in
most scenes. Their importance does not necessarily mean that they should be
imposed at the beginning of scene construction, however.

It may be preferable to establish and review the primary scene layout first:
the landform, object positioning, perspective, color, and related compositional
choices. Volumetrics can then be introduced with an understanding of the scene
they will transform. Whether a new scene begins with an explicit atmospheric
choice or a neutral clear default remains unresolved.

An interface switch for comparing the composition with and without volumetrics,
and any automatic handling of those alternatives as related scenes, is deferred.
It is not part of the proof of concept.

## Reproducibility and scene retention

The established practice is to save the data associated with every render. The
artist needs the confidence that any rendered image can be recreated.

For now, every render should continue to archive its complete reproducibility
record, including the generated `.pbrt` scene and the configuration and source
files required by the rendering pipeline. The longer-term question of whether
every scene iteration must be retained, or whether some can be saved more
selectively, is tabled.

## Scene hierarchy and adding elements

The mechanism for introducing elements into a scene is unresolved. The
previously discussed `ADD` control is tabled and is not a proof-of-concept
requirement. No catalogue, menu behavior, or scene-hierarchy population model
should be inferred at this stage.

## Landscape scenes and hierarchy

Focusing on the landscape category, every landscape will initially require:

- A ground plane.
- A sky plane.
- Positioning of the ground plane in relation to the camera angle.

The next concern is filling out the ground and sky.

### Landforms

At a high level, landforms fall into three categories:

- Valleys and plains.
- Mountains.
- Ocean.

Beneath these high-level categories are sub-landforms. In particular, land that
is neither mountains nor ocean can be developed through sub-landforms such as
rolling terrain, gullies, and other forms of relief.

### Filling out the ground

We have already developed many of the tools needed to fill out the ground. In
no particular order, these include:

- Flower forms, with different species.
- Tree forms, including different algorithmic techniques, tree types, and
  species.
- Weeds and undergrowth.
- Grass.
- Rocks and stones.
- Landform shape and texture, including rolling terrain and gullies.
- Litter.

### Filling out the sky

Clouds have not yet been addressed and will be needed as a component of the
sky.

### Atmosphere and camera

There is also a collection of volumetric effects. `Atmosphere` has already been
identified as a key category. Camera settings form another key category.

### An evolving hierarchy

This inventory is by no means complete. Its purpose at this stage is to show
how I am thinking about the scope of the medium: high-level categories that
break down into subcategories. The organization is fundamentally hierarchical.

## Proof-of-concept landscape

The accepted visual reference for the initial proof of concept is the Qt GUI
mockup in [`assets/qt-proof-of-concept.png`](assets/qt-proof-of-concept.png).

The scene brings together:

- Poppies.
- Grass.
- A tree.
- Clouds.
- Far-away hills on the receding horizon.

The distant hills are critical. They have not yet been a principal focus of the
medium, but they establish depth, distance, and the landscape's receding
horizon. They are therefore a required part of the proof-of-concept scene, not
incidental background decoration.

## Interaction and rendering model

The proof-of-concept is not intended to manipulate the finished image or PBRT
scene interactively in real time. The artist sets parameter values in the GUI,
the system validates and saves those values, the scene generator writes the
`.pbrt` scene, and PBRT renders the result.

The large image area in the GUI displays the latest completed render. It is an
image viewer and evaluation surface rather than, initially, a live three-
dimensional editing viewport.

The basic cycle is:

```text
Set parameters
    -> validate and save
    -> generate PBRT scene
    -> render
    -> display and evaluate image
    -> revise parameters
```

The interface may later offer fast, low-resolution preview renders or a
progressively updating render display. A separate real-time proxy viewport is
also technically possible, but it would be a distinct rendering system and is
not required for the initial proof of concept.
