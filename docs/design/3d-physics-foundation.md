# 3D lessons built on physics (design, 2026-11-21)

Status: **proposal**. Nothing here is built except the geometry validator prototype (`daemon/goop/explainer/validate.py`, L11). Items are in
[`../BACKLOG.md`](../BACKLOG.md) under track **F**. Read [`3d-explainer.md`](3d-explainer.md) first for how lessons work today.

## 1. The problem

Owner feedback after playing lessons (2026-11-21): in many lessons the **placement** of components is wrong, the **size ratios** between them are wrong, the
**physics** is wrong, and **effects** do not fit. Examples seen: a rider placed wrongly on a bicycle seat; a balloon whose hot air floats away from its envelope;
bubbles far too big that leave the water and the model. Lessons should show the thing itself, with no people.

What the code and the saved lessons show:

- **Parts do not know each other.** Each part's shape is written separately, in parallel, from a brief and a width and height (`planner.part_user`). Nothing tells the
  seat where the seat post is, or the envelope where the burner's frame ends.
- **Placement uses coarse words.** The `assembly` template places by `attach` (top, bottom, sides) and `inside`; the `blueprint` template asks the model for numeric boxes
  with no check. Measured on saved lessons with the validator: skirt, envelope and vent 0.6 to 1.9 units off their attach points; a hot-air part declared inside the envelope
  whose centre was 4.3 units away; an envelope drawn 3.5 tall against a planned 7.
- **Sizes have no real-world meaning.** A part is "1 to 4 units"; there is no scale tying a balloon envelope (about 20 m) to its basket (about 1.2 m), or a bubble (millimetres) to a submarine (metres).
- **Effects use absolute sizes** (`shell/explainer3d/lesson.js`): finale particles are a constant times a clamped `R/6`; flow drops are a fixed `0.0024`; both start inside the model and rise on fixed
  speeds with no container bounds.
- **Physics is narrated, not computed.** The lesson says hot air is lighter; the "fly" finale is a canned motion. Nothing in the scene follows from a law.

Research (2026-11-21, sources in the vault page `goop`): systems that place things well do not ask a model for coordinates. The model proposes relations (or code), a solver places,
and geometric checks send exact complaints back (Holodeck, SceneCraft, VULCAN, Blender MCP forks). Text-to-3D models need a 16 to 24 GB discrete GPU and give one fused mesh that cannot be taken apart.
Blender is 383 MiB installed, not here, and what it would add (bounding boxes, collision and distance checks) is a few hundred lines of plain Python on meshes Goop already has.

## 2. Principles

1. **Real units.** Every size is in metres (kg, s, K, Pa). The model supplies real-world values, which it knows well; the engine applies one uniform display scale. Ratios are right by construction.
2. **Build from physical primitives.** Shapes are defined by physical parameters (radius, length, module, teeth, density) and give derived quantities (circumference, area, volume, mass).
3. **Place by relations, not coordinates.** The model says how things meet (tangent, concentric, coincident anchors, meshing gears, hinge, slider, inside with clearance); a small solver computes positions and rotations.
4. **Motion comes from laws.** A lesson names the law that governs it and its real parameters; the renderer animates from the formula. Each formula has a unit test.
5. **Check by numbers.** A validator measures the built scene and sends exact findings back to the model (the repair loop already exists). Looking at renders is an optional later pass, never the only check.
6. **Machines alone.** No people, riders, passengers or animals. (Already in the prompts, 2026-11-21.)
7. **Stay light and fast.** Pure Python, no new packages, no Blender. A lesson still starts playing in about a minute; the checks cost well under a second.

## 3. What the model writes, and what code computes

| The model writes (data, never code, never coordinates) | Code computes |
|---|---|
| Which components exist, as primitives or (for unusual parts) a custom shape | Positions and rotations from the relations |
| Real-world parameters of each component | Display scale, derived quantities (circumference, volume, mass) |
| Relations between components | Contact, clearance, meshing distances |
| Which law drives the motion, and its real inputs | Every animated value, from the formula |
| Narration | Timing (already derived from the text length) |

Custom model-written shape code (the deno sandbox, `codegen.py`) stays as the escape hatch for what primitives cannot make (a bicycle frame, an engine block). It is given the part's **anchors** (section 6)
and a check confirms the generated shape really reaches them.

## 4. Storyboard v2 (sketch)

```json
{ "version": 2, "units": "m", "title": "How a bicycle stays upright",
  "parts": [
    {"id": "rear_wheel",  "primitive": "wheel",  "params": {"radius": 0.34, "width": 0.04, "spokes": 32}, "material": "rubber"},
    {"id": "front_wheel", "primitive": "wheel",  "params": {"radius": 0.34, "width": 0.04, "spokes": 32}, "material": "rubber"},
    {"id": "frame",       "kind": "code", "brief": "a diamond frame of round tubes", "size": [1.0, 0.55, 0.06],
     "anchors": {"rear_axle": [-0.5, 0.0, 0], "head": [0.45, 0.45, 0], "seat_post": [-0.15, 0.55, 0]}},
    {"id": "seat",        "kind": "code", "brief": "a padded saddle on a post", "size": [0.28, 0.12, 0.14],
     "anchors": {"post_base": [0, -0.06, 0]}}
  ],
  "relations": [
    {"tangent":    ["rear_wheel", "ground"]},
    {"tangent":    ["front_wheel", "ground"]},
    {"concentric": ["rear_wheel", "frame.rear_axle"]},
    {"coincident": ["seat.post_base", "frame.seat_post"]}
  ],
  "laws": [{"law": "rolling", "wheel": "rear_wheel", "speed": 4.0}],
  "steps": [ ... as today: reveal, label, highlight, cutaway, flow, zoom ... ] }
```

`units: m` and real values replace "width/height 1 to 4"; `primitive` parts need no shape code; `kind: code` parts carry anchors; relations replace `attach`/`inside`/numeric `at` (the old fields keep working
during the change). Version 1 lessons still play.

## 5. Primitives and their physics

Each primitive is parametric and returns a mesh plus derived quantities. Formulas (the unit tests check these):

| Primitive | Parameters | Derived |
|---|---|---|
| box / plate | w, h, d | volume w·h·d |
| cylinder / tube | r, L (tube: wall t) | circumference 2πr, area πr², volume πr²L |
| sphere / dome | r | area 4πr², volume 4/3 πr³ |
| cone / frustum | r0, r1, h | volume πh(r0² + r0·r1 + r1²)/3 |
| torus | R, r | volume 2π²·R·r² |
| wheel | r, width, spokes | circumference 2πr; distance per turn = circumference |
| gear | module m, teeth z, width | pitch diameter m·z; two gears mesh at centre distance m(z1+z2)/2; ratio z2/z1 |
| pulley / spool | r, width | rope length per turn = 2πr |
| rope / pipe | path, r | length, volume |
| spring | k, free length, turns | force k·x |
| tank / vessel | r, L (or w, h, d) | volume, filled mass = ρ·V·fill |

Material gives density (steel 7850, aluminium 2700, water 1000, air 1.2 at 20 °C, all kg/m³ and typical values), so mass follows.

## 6. Relations and the solver

A relation joins two parts or anchors. The solver walks the relation graph from a fixed root (ground or the first part), so it is deterministic and needs no iteration for the common tree-shaped machines.

| Relation | Meaning | Example |
|---|---|---|
| `tangent(a, ground)` | lowest point of a touches the ground plane | wheel centre height = radius |
| `concentric(a, b)` | shared axis | wheel on its axle |
| `coincident(a.anchor, b.anchor)` | the two anchors are the same point | seat post into the frame |
| `mesh(a, b)` | gears at their centre distance | gear train |
| `inside(a, b, clearance)` | a's box inside b's with a clearance | piston in its cylinder |
| `above(a, b, gap)` / `hang(a, from b, length)` | stacked or hung with a gap or rope | envelope above the burner |
| `hinge` / `slider` (axis, range) | one degree of freedom | door, piston |

Anchors are named points in a part's own frame, given as fractions or real offsets. A relation that cannot be satisfied (two tangent constraints that disagree) is reported to the model with numbers.

## 7. Laws that drive motion

A law is a small pure function of time and real parameters, with a unit test. Lessons name the law; the renderer reads the value.

| Law | Formula | Drives | Test value (typical) |
|---|---|---|---|
| Rolling | v = ω·r; distance per turn = 2πr | wheels, rollers | r 0.34 m: 2.136 m per turn |
| Gear train | ω2 = ω1·z1/z2 | gear and belt drives | 20 and 40 teeth: half the speed |
| Crank-slider | x(θ) = r·cosθ + √(l² − r²·sin²θ) | pistons, pumps | stroke = 2r |
| Lever / torque | F1·d1 = F2·d2 | levers, scales, wheelbarrows | 3 m and 1 m arms: force ×3 |
| Pulley | rope per turn 2πr; N supporting ropes divide the force by N | hoists | |
| Buoyancy | F = ρ_fluid·V·g; floats if mass < ρ_fluid·V | ships, submarines, balloons | |
| Hot air | ρ = p·M/(R·T) with M = 0.02897 kg/mol; lift = (ρ_out − ρ_in)·V·g | balloons | 20 °C vs 100 °C: about 0.26 kg of lift per m³, so 2800 m³ lifts about 720 kg |
| Hydrostatic | p = p0 + ρ·g·h | dives, dams | 10.3 m of water adds about 1 atm |
| Continuity / Bernoulli | A1·v1 = A2·v2; p + ½ρv² constant | pipes, wings, carburettors | |
| Ideal gas | P·V = n·R·T | engines, pumps, balloons | |
| Ohm / power | V = I·R; P = V·I | circuits | |
| Wave | v = f·λ | sound, radio | |
| Refraction | n1·sinθ1 = n2·sinθ2 | lenses | |
| Stability | centre of mass over the support polygon | bicycles, ships | |

Cases that are subtle (why a bicycle stays upright involves trail and steering as well as gyroscopes) are explained in words from a vetted description and not animated as a derivation.

## 8. Effects in physical units

Flow arrows, bubbles, smoke, sparks and waves are specified in real units and clipped to a container:

- bubble diameter 1 to 10 mm, rise speed about 0.2 m/s in water (typical), and removed when they reach the water surface or leave the container's box;
- flow drops are a fraction of the pipe or port diameter they travel in (about a quarter of the diameter, so a stream fits the pipe);
- exhaust and smoke start at the emitter part's outlet (an anchor), with a size relative to that part;
- every effect has a bounding region (a part's box, the water volume, the model's box with a margin); particles outside it are culled.

## 9. The validator

`daemon/goop/explainer/validate.py` (prototype, 10 tests) already reports: floating parts, partial overlaps (nesting allowed), declared `inside` and `attach` relations that the geometry breaks,
size against the plan, parts below the ground, and people. Planned additions: ratio against real sizes (a part more than about 2 times off the real ratio), law consistency (wheel circumference against the distance
it travels), effect bounds, and relation residuals from the solver. Findings go back to the model through the existing repair loop, with numbers. Cost on saved lessons: 0.3 to 0.8 s.

## 10. How it fits the pipeline

```
outline (model: components, real values, relations, laws, steps)
  -> validate the outline (schema, relation graph solvable, values in plausible ranges)
  -> solve placement (units, relations -> positions)             [new, pure Python]
  -> parts: primitives built in code; custom parts written by the model with anchors, in parallel (as today)
  -> validate the built scene (geometry checks, anchor reach)       [new in the loop, repair on findings]
  -> play (renderer reads positions, laws and bounded effects)
```

The window still opens when the first parts exist. The new stages run before the parts are drawn (solver, microseconds) and after each part (anchor reach) or at the end (whole-scene validator, under a second).

## 11. Order of work and how we prove it

Track **F** in the backlog. Order: units and the validator in the loop (F1, F6), primitives (F2), relations and solver (F3), laws (F4), effects (F5), prompts and schema (F7), then three proof lessons (F8): a bicycle
without a rider, the balloon, the submarine. Optional later: a render-and-review pass with a vision model (F9).

Success means, on the proof lessons and a handful of new topics: the validator finds nothing, the owner picks the new lesson over the old in a blind side-by-side (as done for the prompt change on 2026-11-21),
build time stays near a minute, and the number of model calls does not grow.

## 12. Risks and open questions

- **The model may state a wrong real-world size.** Mitigation: plausible-range tables per primitive and material, and a comparison against ratios from related parts; unsure values are flagged, never silently used.
- **Custom shapes still need to reach their anchors.** The anchor-reach check sends the part back for repair; a part that cannot be fixed still becomes a stand-in.
- **Tree-shaped relations only at first.** Closed loops (a four-bar linkage) need an iterative solver; defer and say so in the lesson plan.
- **Reversing E5c.** Ready-made shapes were removed because they looked generic. These are parametric and physical, and custom code stays for what they cannot make. Worth a second look after F2.
- **Qt Quick 3D Physics** (`qt6-quick3dphysics` 6.12.0, rigid bodies and joints) is available but not needed: lessons are kinematic or law-driven. Revisit for collisions or ropes.
- **Open:** one display scale for the whole scene, or a log-style scale when parts differ by a factor of 100 (a bubble beside a submarine)? Zoom per step may be enough.
