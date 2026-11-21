# 3D lessons from a model sheet (design, 2026-11-21)

Status: **proposal with a first prototype** (a chair and a wristwatch). Supersedes the "primitives, relations, laws" plan in [`3d-physics-foundation.md`](3d-physics-foundation.md) as the way to
build a model; that plan's laws and simulation ideas still stand for behaviour. Backlog track **F**.

## 1. The problem, in one sentence

Parts written separately and placed afterwards cannot be made to fit, and motion written by hand is not physics. Everything the owner saw wrong (components far apart, labels off their parts,
tubes that do not meet, a crank that floats, a balloon that flies off sideways) comes from the model never having one consistent picture of the finished object.

## 2. The idea

Before anything is built, the model draws a **model sheet** of the finished object, assembled: every component present, in its working position, touching its neighbours. Like the character
sheets and engineering drawings people use, it is the AI's thinking aid. **Users never see it.** The 3D model is built exactly from it, and the lesson then shows the object assembled, takes it apart
component by component, and puts it back.

Starting from a finished model (an asset library, or a generated mesh) was rejected: there is no model for an arbitrary question, generated meshes are one fused piece with no inside, and splitting a
mesh into working parts is unreliable. The components must exist from the start. This is top-down for structure and bottom-up for detail, as in CAD: a skeleton controls the parts.

## 3. What the sheet contains

Everything is in one frame: **x to the right, y up (the base at y = 0), z toward the viewer (the front)**, scaled so the object is about 8 units across (never beyond +-10).

| Part of the sheet | What it is | Why |
|---|---|---|
| `parts` | The components. Each is a list of `features` in the shared frame: `box`, `beam` (a flat bar between two points), `cylinder`, `tube` (round bar with rounded ends), `ring` (torus), `revolve` (a profile turned about an axis), `sphere`, `band` (a flat strap through points) and `radial` (copies of a feature around an axis: tick marks, bolts) | The model gives structure and real proportions, never raw triangles |
| `views` | Per component, the extents it spans as seen from the front (x, y), the side (z, y) and the top (x, z) | A second, independent statement of the same shape. The two must agree. |
| `connections` | Pairs of components with the 3D point where they meet | The assembly, stated explicitly |
| `spin` | For parts that really turn: axis, pivot point, real period in seconds, direction | Motion with the right ratios (a watch's hands) instead of a fixed rate |
| `steps` | The narration and the verbs (reveal, label, highlight, spin, zoom) over the finished sheet | The explanation comes last |

## 4. Checks by numbers (the sheet is a contract)

Code builds every component from its features and then tests the model's own claims. Each failure is a sentence with numbers that goes straight back to the model for repair.

1. **Features are valid:** known shapes, sensible sizes, inside the frame.
2. **Views agree with the build:** "the side view says 'seat' spans z 0.2 to 4.1, but its features span 0.2 to 4.6".
3. **Connections hold:** the contact point must lie on both components.
4. **Nothing floats, nothing cuts into a neighbour, nothing sinks below the ground, no people** (the geometry validator and invariants that already exist).
5. **Behaviour:** coupled parts turn at the ratio their periods imply (hour hand : minute hand : second hand = 1 : 12 : 720).

## 5. Taking it apart

Because the components exist and touch, taking apart is a view of the same data. For each component, code slides its box along the six axis directions and picks the way out that hits the fewest
neighbours (preferring the way that points away from the middle). The distance is relative to the component and the object. This replaces the fixed radial pull-apart for sheet-built lessons
(`layout: {"explode": "free"}`) and costs no model call.

## 6. Pipeline

```
topic -> [1 model call: sheet + steps] -> build every component from its features
      -> check the sheet (section 4) -> repair with exact numbers (up to 2 rounds)
      -> layout (positions from the sheet, take-apart directions, spin pivots and rates)
      -> timeline and camera -> renderer
```

One model call instead of an outline plus one call per part, so a build should be faster than today's (about 40 to 70 s). Components with surface detail the primitives cannot express
(a saddle, a tread) are the open case: they would be model-written shape code inside the slot the sheet gives them (the existing sandbox), checked to reach their connection points.

## 7. Known difficulties

- **The model's knowledge is the ceiling.** The sheet makes errors visible and checkable; it does not make the model know how a thing is built.
- **Cross-view agreement is the model's weak point.** Three principal views, not six; symmetric parts are repeated features.
- **Primitives cannot express everything.** Organic shapes (a heart, an animal) are out of reach.
- **Internals** are not visible from outside views; for a mechanism the parts are present and an `inside` relation or a cutaway shows them.
- **Closed loops** are fine here because the frame is global (points are shared, nothing is solved from a root).
- **Real motion** beyond constant-rate turning (gears meshing, linkages, buoyancy) needs the simulation work in the physics-foundation design.

## 8. First test

A chair and an analog wristwatch, with no worked example of either in the prompt. Success: the checks pass within two repairs, the rendered pictures (`bin/goop-snap`) show connected,
plausible objects, take-apart looks sensible, and the watch's hands turn about the dial centre in the right direction and ratio. Then a wider set of topics to see how far it generalises.
