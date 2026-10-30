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
