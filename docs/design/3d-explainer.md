# 3D explainers (idea, researched 2026-10-30)

**The idea.** Someone is reading about how a water dam works and does not get it. They ask Goop. Goop explains it out loud while a 3D
animation plays in the middle of the screen: the dam is built up, pulled apart into its components, and the water is followed through.
No window, no frame: the model floats over whatever they were doing, Goop narrates, and a keypress dismisses it.

## What it takes (five parts)

1. **Understand the source**: the article or screen content, and what the user did not get. (Today: screenshot + vision. Better: page
   text through the browser adapter, backlog P1.)
2. **Plan the explanation**: which components exist, how they relate, in what order to explain them, one narration sentence per step.
   Language models are good at this.
3. **Build the scene**: turn the plan into 3D parts and positions. **This is the hard part**: current models are weak at 3D spatial
   reasoning (placement, scale, relative position), so the model must not be asked for raw coordinates.
4. **Animate it**: reveal, explode, highlight, flow, camera moves, labels, in step with the narration.
5. **Show it**: a transparent, frameless overlay with a 3D renderer, plus voice (existing Piper TTS) and controls (pause, skip, close).

## The options, and why

| Option | Verdict |
|---|---|
| **Qt Quick 3D** (QML scene graph, PBR materials, lights, glTF import, particles, animation, camera) | **Recommended renderer.** Native to our stack (Quickshell is Qt/QML), GPU-accelerated, animations are plain QML. Official Arch package `qt6-quick3d` 6.12.0-1 (same version as the installed Qt; 7.3 MiB download, pulls in `qt6-quicktimeline` and `openxr`). **Not installed on this machine yet.** Transparency works with `View3D` in Offscreen render mode (`SceneEnvironment.Transparent`); needs verifying on Hyprland/layer-shell. |
| QtWebEngine + three.js | Works (qt6-webengine is installed) and LLMs know three.js, but it adds a Chromium process (heavy) and Quickshell would need WebEngine initialised early. Fallback if Quick 3D fails. |
| Blender | Not for runtime: not installed, offline rendering, minutes per clip on an integrated GPU. Useful later only to *author* a curated library of glTF models. |
| Manim (Python, 3Blue1Brown style) | Excellent explainer tool and LLMs write it fairly well (usually 0-1 repair passes), but it renders **videos**: minutes of latency, not interactive, needs LaTeX for text. Possible "prepare in the background" mode, not the live experience. |
| ozz-animation | MIT, C++ runtime for **skeletal** animation of characters. Our scenes are rigid parts moving on keyframes, which Quick 3D does natively. Not needed. |
| MocapAnything | Video -> joint rotations for animals/humans; needs PyTorch and an NVIDIA GPU. Not relevant. |
| Mesh2Motion | Web app that rigs human/animal models. Not relevant. |
| AI4Animation | Research framework for character motion (Unity); **non-commercial license**, which would block a published plugin. Not relevant. |

The three character-animation projects would matter only if Goop itself got a 3D body, or for explaining anatomy or animal motion.

## Architecture

```
article / screen --> [explain] agent --> explanation plan --> scene builder --> storyboard JSON --> renderer (Qt Quick 3D overlay)
                      (LLM, our tools)    (components, steps)   (parts library +     (validated data,    + Piper narration, captions,
                                                                  layout engine)      never code)         controls, replay
```

- **The model writes data, never code.** Output is a storyboard in a small JSON vocabulary that our renderer interprets. Nothing it
  produces is executed, and sizes are bounded (parts, steps, duration).
- **Semantics instead of coordinates.** The model says *what* and *how related*, our layout engine decides *where*: `stack`, `row`,
  `ring`, `connect(a, b, as: pipe|arrow)`, `container(volume)`, `cutaway(part)`, along a flow direction. A **parametric parts library**
  (wall, water volume, pipe, turbine, generator, gear, tank, valve, arrow, label...) gives consistent proportions. Subjects outside the
  library fall back to generic primitives.
- **Animation verbs:** `reveal`, `explode(group, distance)`, `highlight`, `flow(from, to, color)`, `rotate`, `label`, `camera(focus, orbit)`,
  `cutaway`, `compare`. Each step carries one narration sentence; the step ends when its audio does.
- **Windowless:** a full-screen transparent layer surface that takes no input except one dismiss key; the model is centered with a soft
  dim behind it so the surrounding page stays readable but does not compete. Goop's own avatar sits at the edge as the narrator.
- **Saved and replayable:** storyboards are plain JSON in `~/.local/share/goop/explainers/` (instant replay, shareable, a good marketing artifact).
- **Graceful tiers:** Quick 3D installed -> full 3D. Not installed -> a flat animated diagram mode (Qt Quick Shapes) or voice only, plus a
  one-line hint with the pacman command. The doctor/wizard reports it as an optional dependency.

### Sketch of a storyboard (dam)

```json
{ "title": "How a hydroelectric dam works", "style": "diagram",
  "parts": [
    {"id": "reservoir", "kind": "water_volume", "label": "Reservoir"},
    {"id": "wall",      "kind": "gravity_wall",  "label": "Dam wall"},
    {"id": "penstock",  "kind": "pipe",          "label": "Penstock", "connect": ["reservoir", "turbine"]},
    {"id": "turbine",   "kind": "turbine",       "label": "Turbine"},
    {"id": "generator", "kind": "generator",     "label": "Generator", "attach": "turbine"},
    {"id": "river",     "kind": "water_volume",  "label": "River below"}
  ],
  "layout": {"flow": "left-to-right"},
  "steps": [
    {"say": "A dam holds back a river and stores water high above the valley.", "do": [{"reveal": ["reservoir", "wall"]}, {"camera": "wide"}]},
    {"say": "Water enters a large pipe, the penstock, and falls with great force.", "do": [{"reveal": ["penstock"]}, {"flow": ["reservoir", "turbine"]}]},
    {"say": "That force spins a turbine.", "do": [{"explode": {"group": ["turbine", "generator"], "distance": 0.6}}, {"rotate": "turbine"}, {"highlight": "turbine"}]},
    {"say": "The turbine drives a generator, which makes the electricity.", "do": [{"highlight": "generator"}]},
    {"say": "The used water flows back into the river.", "do": [{"flow": ["turbine", "river"]}, {"camera": "wide"}]}
  ] }
```

## Risks

- **Spatial reasoning of the model** (studies find current LLMs weak at placement, scale and relative position): mitigated by the layout
  engine and parts library; later a render-and-review loop where a vision model checks a still frame.
- **Visual quality:** a clean low-poly / infographic look, not photorealism; that is also what suits explanation.
- **Integrated GPU** (Iris Plus 655): fine for dozens of primitives; to be measured. Memory and CPU of Quick 3D inside the shell: to be measured.
- **New optional system dependency** (`qt6-quick3d`): Omarchy never runs install hooks, so it is documented and checked, not installed.
- **Source text:** the article body needs the browser adapter (P1); vision on a screenshot works meanwhile but is coarser.

## Phases

- **E1 Feasibility spike** (needs `qt6-quick3d` installed): a transparent, frameless overlay showing an exploded dam made of primitives
  with a camera move; measure CPU/GPU/memory on this laptop; confirm transparency and click-through on Hyprland.
- **E2 Storyboard format + interpreter + narration sync**, with the dam as the hand-written golden example.
- **E3 The planner**: article/screen -> plan -> storyboard using the existing agent providers; validation, layout, repair loop.
- **E4 The experience**: trigger ("Explain visually" in the ask box and bubble), controls, captions, replay and saved list.
- **E5 Library and quality**: more parts, glTF models, vision critique of rendered frames.


## Findings from the spike (2026-10-30)

**It works, and it is "just code".** A detailed hydroelectric dam (terrain with a cutaway skirt, reservoir, dam wall with crest and gates, a
see-through powerhouse, a flanged penstock, a turbine with casing and 12 spinning blades, a generator with copper coils that lifts out,
a power tower with sparks, a river, flowing water drops, labels, and a camera that zooms in while the ground sinks away) is generated by
`shell/explainer3d/meshes.js` + `dam3d.js` and rendered by Qt Quick 3D through `ProceduralMesh`. No model files, no Blender.

| Renderer | CPU while playing (i7-8559U, whole process) | Verdict |
|---|---|---|
| Plain QML/JS canvas (`shell/Explainer.qml`, 860x520 surface, 24-30 fps) | 67-87% of one core | Proves the idea, looks flat, too heavy. Kept only as a possible zero-dependency fallback. |
| **Qt Quick 3D**, own process (`shell/explainer3d/`) | **11-24% of one core, about 260 MB while playing** | Chosen. GPU does the work; real lighting, shadows, materials, translucency. |

**It must never run inside the Omarchy shell.** The first attempt loaded Quick 3D in the shell through a `Loader`; the shell **aborted**
(an assertion inside Qt Quick 3D's `QSSGGlobalRenderNodeData::reindex`, found in `~/.cache/quickshell/crashes/`), taking the bar down until
it was restarted. The same scene in its own process ran 30 s and exited cleanly. So: the 3D explainer is a separate, short-lived program
(`quickshell -n -p shell/explainer3d`, started by `goopctl explain3d <name>`); a failure there can only close its own window. The root
cause of the in-shell assertion was not chased further.

**Windowless.** A transparent layer surface with an empty input region (clicks pass through), sized to the picture and centred, no frame.
Do not add a backdrop panel (it reads as a window). Two ideas for soft edges failed: a blur mask via `MultiEffect` made the scene
invisible, and the built-in vignette darkens to black. What works: composition. The ground is a cutaway block with a visible edge, and it
sinks away during close-ups so nothing runs into the frame border.

**Testing hygiene.** Screenshots capture whatever is on screen. Run visual tests on an empty workspace
(`hyprctl dispatch 'hl.dsp.focus({ workspace = "9" })'`, then back), with `QS_DISABLE_CRASH_HANDLER=1` to suppress the crash dialog.

**Still open:** a JSON storyboard format instead of hand-written JS (E2), narration, the planner (E3), and the soft-edge question.


## Making it dynamic (owner direction, 2026-10-30)

Goal: any topic the user is reading (airplane turbines, how a Wi-Fi system works, how a spaceship works...). Goop reads the content, decides on its
own whether a 3D explanation would help, builds a model, and explains the parts "like a teacher does with kids", then stays available for questions.
The dam is only the first golden example; nothing about a specific subject may live in code.

### Three layers: the AI directs, code builds the set

1. **Teaching plan (the model).** Reads the source (screenshot now, page text once the browser adapter exists), decides whether and what kind of 3D
   explanation fits, and writes a lesson: the big idea, 3-10 parts with roles and relations, steps with kid-friendly narration and one analogy
   each, and a question to check understanding. **It never writes coordinates or code.**
2. **Scene builder (deterministic code).** A fixed visual vocabulary, layout templates and a camera director turn the plan into positions,
   materials and shots. This is where spatial correctness lives, because models are weak at 3D placement.
3. **Playback (renderer).** Interprets the storyboard, syncs Piper narration to each step, and keeps listening for questions.

### The visual vocabulary (what the model may ask for)

- **Bodies:** box, cylinder, sphere, cone/frustum, dome/dish, ring, disc, fan/blades, gear, wing (extruded profile), tank, panel, mast, node.
- **Connections:** pipe or cable between two named parts; arrow; bracket.
- **Media in motion:** flow (drops along a path), waves (expanding rings/arcs, for signals), heat/glow, sparks, pulses.
- **Containers and context:** casing (translucent shell with a cutaway), room (walls), ground/terrain, sky or space backdrop.
- **Layout templates:** `axis` (a sequence along one direction: engine, pipeline), `stack` (layers), `radial` (parts around a hub: rotor, satellite),
  `network` (hub and nodes in a space: Wi-Fi in a room), `scene` (ground plus landmarks: dam), `assembly` (a main body with named attachment
  points: spacecraft). **Verbs:** reveal, explode, highlight, flow, spin, pulse, zoom, label, cutaway, analogy, ask.

The model picks template + parts + relations by name; the code decides everything else. Expect **schematic, labelled, animated models** (educational
diagrams), not accurate CAD: say so, and let the narration carry the meaning.

### Fit by subject (honest)

| Subject | Fit | How |
|---|---|---|
| Mechanical (turbine, engine, dam, pump) | very good | `axis` / `scene` + flow + spin + explode |
| Systems with signals (Wi-Fi, radio, networks) | good, abstract | `network` + waves; metaphors (walls absorb, distance weakens) |
| Vehicles and assemblies (spaceship, aircraft) | good | `assembly` + explode, per-part highlight |
| Biology, chemistry, software architecture | later | needs more vocabulary (membranes, molecules, boxes-and-arrows) |

### Decisions and behaviour

- **Whether to build one is goop's call, but never an ambush.** It *offers* ("Want me to show you in 3D?" with quick-reply buttons). A setting
  (Never / Offer / Auto) lets the owner choose; default Offer.
- **Questions are the point.** After the lesson the model stays on screen, paused. The user asks (click goop, later voice); goop answers by voice
  and *drives the model*: highlight, zoom, explode, add a label. This needs a control channel from goop to the renderer process (commands as lines
  on its stdin).
- **Grounded in the article, honest about simplification.** The plan cites what the page said; the narration marks simplified parts.
- **Validation before playback:** schema check, bounds (part count, step count, duration), layout collision check, camera framing, a repair loop
  that returns errors to the model; later a vision critic that reviews a rendered frame.
- **Latency:** the planner call takes tens of seconds. Show a "preparing" state; later start playing as soon as the first steps are ready.
- **Cost:** one planner call per lesson (use the strongest model configured for it, not the quick-chat model) plus vision for the source. Cache by topic.

### Order of work

1. **Vocabulary proof (E2):** the storyboard schema, the parts library, the layout templates and the verbs, proven with **three hand-written lessons in
   different styles** (a jet engine on `axis`, Wi-Fi in a room on `network`, a spacecraft on `assembly`) before any model is involved. If three
   unrelated subjects work, the vocabulary is expressive enough.
2. **Planner (E3):** `daemon/explain.py` turns source + schema + examples into a validated storyboard through the existing providers.
3. **Playback and narration (E4)** and **launch from goop (E7)**, then **teacher mode (E9)**, **page text (E10)**, the **vision critic (E11)** and
   **streaming (E12)**.
