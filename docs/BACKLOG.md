# Backlog

The single list of what is planned, in progress and decided. Completed work moves to [`../CHANGELOG.md`](../CHANGELOG.md).
Once the repo is public this becomes GitHub Issues (one issue per item, same IDs in the title).

**How we work:** pick an item, mark it `doing`, build it with tests, add a line under *Unreleased* in the changelog, commit with the
item ID in the message (`V1: wobbly outline`), then delete it from here. New ideas go under *Ideas* first.
Status: `todo` · `doing` · `blocked` · `decision` (needs the owner).

Tracks: **L** launch · **V** visual · **A** agent · **P** other apps · **T** voice · **Q** quality

## Decisions needed first

| ID | Decision | Recommendation |
|---|---|---|
| L1 | ~~Official name and permanent plugin id~~ | **Decided 2026-10-30: Goop** (owner's pick), repo `omarchy-goop`, id `io.github.magonox.goop`. Fallbacks if it gets taken: Goopy, then Goopi. Checked against the registry that day (6,112 sources, 99 retired ids): none of goop/goopy/goopi/gloop exist. Re-check right before submitting; ids are permanent. |
| L2 | License | MIT (matches the Omarchy ecosystem). A license file is required by the marketplace. |

## Now

| ID | Item | Status | Notes |
|---|---|---|---|
| L3 | Rename the id everywhere (manifest, theme hook, plugin symlink, docs, `goopctl`) | done | Renamed to `io.github.magonox.goop` everywhere on 2026-11-01 (manifest, panel, README, docs, the owner's symlink, shell.json and theme hook; backups `.bak.20261101193118`).
| L4 | Marketplace-ready README: install, **removal**, external dependencies | done | README rewritten 2026-11-01: features, install, requirements, privacy and permissions, troubleshooting, removal, third-party licenses.
| L5 | `preview.png` in the repo root | done | `preview.png` (1600x900) in the repo root, made from real footage and the real goop outline.
| L6 | Self-check against the security baseline | todo | `setup.sh` is an installer (pip, model download) so it will be flagged `review-required`, not rejected. Keep: no `curl | sh`, no unpinned remote code. |
| V1 | Gooey outline: edges that wobble like liquid instead of a plain circle | doing | First pass in (2026-10-30): `shell/goo.js` + `GooBody.qml`, jelly squash-and-stretch breathing, livelier when speaking/thinking/startled, the peel blobs use the same shape. CPU unchanged (5-6% of a core for the whole shell). **Waiting on owner feedback**: more or less wobble? Knobs: amplitudes in `goo.js` (`a2/a3/a4/ab`, sag), breathing 0.05 in `Goop.qml`. |
| V2 | Drips: a small drop forms at the bottom, falls a few pixels, fades | doing | In (2026-10-30): `shell/Drip.qml`, every 7-16 s per goop (rarer while speaking, more often while thinking), `goopctl drip` to see one now. **Waiting on owner feedback** (frequency, size). |
| S1 | **Goop settings in the top bar** | doing | In (2026-10-30): a ghost button in the bar opens a popup (animations Full/Reduced/Off, voice toggle, agent picker, setup checklist that collapses to one line when healthy, Open config / Docs). Built on Omarchy's `Panel` + `KeyboardPanel`. Live state comes from `~/.cache/goop/status.json`. **Waiting on owner feedback** (look, contents). Ideas: speed slider, per-goop provider (A2), show recent audit entries, a Test voice button. |
| V6 | `animations: auto`: drop to reduced on battery or high load | todo | Idea from the performance work; needs a reliable power signal. |

## First-run experience (owner request 2026-10-30: "think as the user would")

Today a new user gets a README, an optional `setup.sh`, and a bare error bubble if something is missing. Every choice lives in a config
file. Goal: install, see goop, and be talking to it within two minutes, with nothing hidden.

| ID | Item | Status | Notes |
|---|---|---|---|
| S2 | **Setup wizard**: runs by itself on first start, re-runnable from the settings panel ("Run setup again") | done (lean) | First-run setup card, five steps (Meet Goop, Check your setup with one-click installs, Voice, Safety and 3D lessons, Try it), opens by itself once and from the panel's Run setup again; `shell/Wizard.qml`. The agent-preset/key-file steps (S2a) stay in the config file for now.
| S2a | Agent step: **presets** (Claude Code, OpenAI, xAI Grok, Gemini, OpenRouter, Ollama, custom URL), key entry (saved to a `chmod 600` file, never the config), **model list fetched from the endpoint** (`GET /models`) or Claude aliases with plain-language notes (fast/cheap vs smart), and a **Test connection** button | folded into S2 or later | Covered in part by the lean card; provider presets and key entry are still config-file only.
| S2b | Voice step: install with a size warning and progress (~275 MB), **audition voices** with a Hear-it button, speed slider, skip option | folded into S2 or later | Covered in part by the lean card; provider presets and key entry are still config-file only.
| S2d | Animations step: recommend a level from the hardware (core count, laptop/battery) | folded into S2 or later | Covered in part by the lean card; provider presets and key entry are still config-file only.
| S2e | Final step: a real test (ask the agent, speak the answer) and a 3-line tour (peel, click, approve) | folded into S2 or later | Covered in part by the lean card; provider presets and key entry are still config-file only.
| S2f | 3D lessons step: choose **On: ask me first** (default) / **On: build automatically** / **Off** (same `explainers` setting as the panel); shows the qt6-quick3d and claude-CLI checks from `doctor.py` with their hints (`sudo pacman -S qt6-quick3d`); the deno check (`sudo pacman -S deno`, required for lessons), a **Play a sample lesson** button (`goopctl explain3d jet_engine`) and one line on privacy (the topic and notes go to the model after you approve a card) | folded into S2 or later | Covered in part by the lean card; provider presets and key entry are still config-file only.
| Q3 | **Multi-monitor support** | done (virtual-monitor tested) | The overlay follows the focused monitor and shifts positions by its origin. Tested on a Hyprland headless output; not yet on a real second display. A goop on a window of the other monitor is hidden until you are there; peeling a goop across monitors is untested.
| Q4 | Config version + migrations for `omarchy plugin update` | done | `config_version` + `goop/migrate.py` + `settings.py migrate`; nothing to migrate yet (v1).
| Q5 | Friendly first-run errors: a missing CLI/key opens the wizard at the right step instead of a bare message | partly | The setup card shows the exact fix for every missing piece; the agent's own bare error message when `claude` is missing is still raw.
| Q6 | Offer (never force) a Hyprland keybinding to summon the ask box on the focused window | todo | A snippet to copy; goop does not edit the user's bindings. |
| Q7 | Languages: voice and agent language (today English voice only) | todo | Needs a voice per language and a prompt language hint. |

## Next

| ID | Item | Status | Notes |
|---|---|---|---|
| L7 | Create the public repo `Magonox/omarchy-goop`, push, enable Issues | todo | Needs L1/L2. Outward-facing: ask first. |
| L8 | Submit to the marketplace with `gh issue create` (`[Plugin]: Goop`) | todo | Category **Productivity**, tags `ai` `hyprland` `quickshell`. Only with explicit approval. |
| M1 | Marketing videos with `latent-spaces/brag` | todo | Evaluate first in a scratch dir (needs Node 22+, ffmpeg, `npx hyperframes`). One run = one ~20 s video, so one run per feature: peel, voice, approvals. |
| V3 | Squash and stretch on pick-up and landing; jelly settle | todo | |
| A1 | Test the OpenAI-compatible provider against a real model | blocked | Needs an API key or a local Ollama. |
| A2 | Per-goop provider: peel a copy and make it a different LLM, color-coded | todo | `agent.py --provider` exists; the shell must remember one per goop. |
| P1 | Browser adapter (Chromium debug port, read pages via CDP) | todo | |

## 3D explainers (owner idea 2026-10-30; research in `docs/design/3d-explainer.md`)

Goop explains something from an article ("how a water dam works") by voice **and** a windowless 3D animation floating in the middle
of the screen: the model is built up, exploded into components and the flow followed, narrated step by step. Recommended renderer:
**Qt Quick 3D** (optional system package `qt6-quick3d`, 7 MiB, not installed here yet). The model writes a storyboard as data, never code.

| ID | Item | Status | Notes |
|---|---|---|---|
| E1 | ~~Feasibility spike~~ | **done 2026-10-30** | Works. Qt Quick 3D in its own process: 11-24% of a core, about 260 MB while playing; the pure-JS canvas version needed 67-87%. It must run **outside** the shell (an in-shell test aborted the Omarchy shell). Details in the design doc. Try it: `bin/goopctl explain3d dam` (needs `qt6-quick3d`). |
| E2 | **Vocabulary proof**: storyboard JSON schema, parametric parts library, layout templates (axis, stack, radial, network, scene, assembly), camera director, animation verbs; proven with **three hand-written lessons in unrelated styles** (jet engine, Wi-Fi in a room, spacecraft) before any model is involved | done | Three templates (axis, network, assembly) proven by jet engine, Wi-Fi and spacecraft lessons; `bin/goop-explain <lesson>` plays them. Stack/radial/scene templates not needed yet. Dam is still the legacy renderer (to become lesson #4). Spacecraft close-ups may still want a final look. |
| E3 | **Planner** `daemon/explain.py`: source (screenshot/page text) + schema + examples -> validated storyboard via the existing providers, with a repair loop; fixtures and tests | done (tool-driven) | The model never writes coordinates or code. Uses the strongest configured model. |
| E4 | Playback: the renderer reads a storyboard file; Piper narration per step; steps end with their audio | partly |  |
| E7 | Offer + launch from goop ("Want me to show you in 3D?" as quick replies; setting Never/Offer/Auto): "Explain visually" in the ask box/bubble starts the explainer process with a storyboard path, goop narrates, a key or click dismisses | done (card, not pills) | The shell only spawns the separate process (see E1). Fall back to voice-only when `qt6-quick3d` is missing (the setup checklist already reports it). |
| E8 | Soft edges so close-ups never show a window boundary | todo | `MultiEffect` mask and built-in vignette both failed (see design doc); the ground-sinks trick covers the dam. Other ideas: shader fade, smaller frame. |
| E9 | **Finale + blueprint layout + teardown order** | done (first cut) | Monster truck tested end to end: assembled first, apart while explained, snaps together, drives off with dust. Open: wheels do not spin (a spinner needs the axle axis and a single-wheel part), a vision check of the assembled machine (does it look like the real thing?), drive direction assumes the machine faces +x, `fly` and `sink` untested with real planned lessons, sound effects, a rocket and a submarine run through the planner. |
| T4 | **Talk to goops**: Talk/Type buttons beside the goop, Moonshine small on-device speech-to-text, live captions, auto-send countdown | done (first cut) | Needs a real-voice test, ideally a child's. Open: speak-the-page-context into `set_context` once the page reader exists (P1), push-to-talk key, wake word (no: mic stays closed by default), Parakeet as an optional more accurate engine, quality of kids' speech (no Moonshine data), a spoken "did you mean" for low-confidence results, multiple microphones. |
| P1 | **Page reader** (Chromium extension + native host + `read_page`) | done, needs a Chromium restart to load | Installed 2026-11-01 (flags backup `~/.config/chromium-flags.conf.bak.*`). Open: Firefox, a reader for PDFs/YouTube transcripts, text of the visible part only, clicking and form-filling (acting, needs cards), checking the real browser after restart. |
| T5 | Voices at an even pace | done | Pace table for every Piper speaker; `tts.speed` scales the common pace. Open: a panel speed slider, a per-goop speed. |
| E3 | Planner: article/screen -> plan -> storyboard with validation, a layout engine (semantics, not coordinates) and a repair loop | todo | LLMs are weak at 3D placement, so they never write coordinates. Uses the existing agent providers. |
| E4 | Experience: "Explain visually" trigger, pause/skip/close/replay, captions, saved explainers in `~/.local/share/goop/explainers/` | todo | |
| E9 | **Teacher mode**: after the lesson the model stays on screen, paused; the user asks, goop answers by voice and drives the model (highlight, zoom, explode, label) over a control channel (JSON lines on the renderer's stdin); a check question at the end | todo | The point of the feature: understanding, then more questions. |
| E10 | Page text for grounding (browser adapter, see P1) | todo | Screenshot-only sees just the visible slice of an article. |
| E11 | Vision critic: render a frame, have a vision model review framing, overlaps and labels, repair | later | |
| E12 | Streaming: start playing as soon as the first steps are planned | later | Hides the planner's latency. |
| E5 | Parametric parts library, glTF models, vision critique of rendered frames | later | Blender only to author curated assets, never at runtime. |
| E5a | ~~Custom parts (composed pieces + lathe/extrude)~~ | removed | Replaced by code parts (E5b); `lathe` and `extrude` live on as helpers the model's code can call. |
| E5b | **Code parts: the only way lessons make shapes** (model-written geometry, Deno sandbox) | done | Open: trim the 3.6 MB scene size, cache generated parts by topic, a vision check of rendered frames, relation words for placement (a laser below a disc), curved/organic helpers (loft, skin). Wizard step S2f must check for deno. |
| E8 | **Parallel parts + early start** | done | Outline about 27-40 s (medium effort), parts 8-29 s each in parallel, window opens after about 50 s. Open: outline is now the long pole (try low effort or a short first pass that names the first parts), progress line in the goop bubble, cache generated parts by label, a vision check of the first frames, speak a short intro while waiting. |
| E6 | Flat animated-diagram fallback (Qt Quick Shapes) when Quick 3D is not installed | later | Plus a doctor/wizard hint with the pacman command. |

## Later

| ID | Item | Notes |
|---|---|---|
| V4 | Metaball split when peeling (a true liquid bridge instead of the current neck) | Refines the existing tether. |
| V5 | Mood-specific deformation (sad droops, happy bounces, thinking ripples) | Builds on V1. |
| P2 | Control other apps, e.g. Kdenlive: project files + `melt`/`ffmpeg` first, then AT-SPI, pixel clicking last | Approval cards, confined to the window, screenshot check after each step. AT-SPI bindings are installed; no virtual-pointer tool yet. |
| A3 | Write actions for project windows (Claude Code edit tools through the approval card, `--permission-prompt-tool`) | |
| A4 | Remember goops across shell restarts | Today only the first window gets one again. |
| T1 | Voice input (quick-reply buttons already send what a spoken "yes" would) | |
| T2 | `goopctl speed` live control | |
| Q1 | First-run setup inside the plugin (offer to run `setup.sh`) | Omarchy never runs install hooks, so setup is a manual step today. |
| Q2 | Manual click-through of the approval card and quick replies on a clean install | Backend verified; mouse path is owner-tested only. |

## Ideas (not yet judged)

- Goop sounds (soft squelch on peel, plop on landing).
- A goop that sleeps when its window is idle.
- Goops react to what is on screen (wave when a build finishes, worry on an error).
- Sharing a goop's personality seed so a favorite goop can be restored.
