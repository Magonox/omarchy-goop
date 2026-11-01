# Changelog

Format: [Keep a Changelog](https://keepachangelog.com). Versions follow the manifest `version`.
Work is planned in [`docs/BACKLOG.md`](docs/BACKLOG.md).

## [Unreleased]

### Changed
- E8: **lessons build in parallel and start early.** The agent tool now starts a detached builder (`daemon/explain_run.py`) and returns at once. Stage 1: one model call writes
  the outline (steps, narration, and for each part a brief and a target size, so the layout is final before any code exists). Stage 2: one call per part, all at the same
  time, each writing only that part's code; every part's geometry goes to its own file the moment it passes the sandbox, and a part that cannot be made to work becomes a
  glass stand-in. The lesson window opens as soon as the first step's parts exist and the renderer loads the others as their files appear. New `--scene` mode in
  `goop-explain`; the finished lesson is saved with all its code for replay. Settings `explain_outline_effort` (medium) and `explain_part_effort` (low): thinking was
  most of the waiting, and `--effort low` writes a part in about 10 s instead of 27-35 s. Measured on the Blu-ray topic: window open after 50 s (was 100+), all parts after
  67 s. A first parallel version without effort settings took 112 s (bigger parts, thinking on). A bug found by the tests: the last repair's error message was lost.

- E5c: **lessons are made entirely from model-written code.** The planner no longer offers ready-made shapes or the basic-pieces recipe (both removed: `custom`
  kind, `custom.py`, the `explain_parts` setting); every part is `kind: "code"` and a plan that uses anything else is sent back for repair. 3D lessons now need
  `deno` (the sandbox); without it the tool says how to install it. The network layout works with code parts: one part with `"sender": true`, blockers
  are any part with `"between"`. The hand-written jet engine, Wi-Fi, spacecraft and antenna lessons stay as demos and tests (they use the old library).
  Measured: a code-built lesson plays at about 10% of one core and 257 MB, the same as the library lessons.

### Fixed
- Voices that talk too fast: every Piper speaker has its own natural pace (on the voices in use, 20 to 29 characters of speech per second; speaker 358 was 40% faster than speaker 233) and one
  global speed left the fast ones fast. `goop/tts/pace.py` measures each speaker's pace on a fixed paragraph and the engine stretches fast talkers and tightens slow ones to the median pace;
  `tts.speed` still scales it. Piper's `length_scale` turned out to be a weak lever (pace changes roughly as length_scale to the power -0.45: doubling it slows a voice by only about a quarter), so each speaker's stretch is solved, not assumed: predicted from that curve, measured, and corrected once from the voice's own response (`--refine`). A table for every speaker of the default voice ships in `goop/tts/pace_<model>.json` (made by `daemon/calibrate_voices.py --all`, then `--refine`); any other model measures a
  speaker the first time it talks and remembers it in `~/.cache/goop/voice_pace.json`. Switch off with the engine's `even_pace`. 10 tests.
- Wheels turned about the vertical axis (the `spin` verb always did). Blueprint parts now carry a spin axis taken from their box (a disc or rod turns about its odd side: a
  wheel about its axle) or from an optional `spin_axis`; the driving finale rolls the wheels one circumference per circumference travelled; a demonstration spin stops when
  the finale begins. A node-based test runs the renderer's own `state()` to check this.

### Added
- P1: **the page reader.** A tiny Chromium extension (`browser/pagereader/`, pinned id, permissions tabs/scripting/nativeMessaging, not allowed in incognito) plus a native-messaging host
  (`daemon/pagereader_host.py`, a private 0600 Unix socket `~/.cache/goop/page.sock`) lets a goop read the text of the page you are on, only when asked: title, address, headings, your selection
  and the readable text without menus, footers and sidebars. New agent tool `read_page` (untrusted-data marking, the privacy deny list also checks the page's title and address, a card at
  Ask-for-everything), the page text now arrives in the packet for browser windows, and it feeds Moonshine as speech context so names on the page are heard right. `bin/goop-install-pagereader`
  (backs up and merges into the `--load-extension` list of `~/.config/chromium-flags.conf`, writes the host file; `--uninstall` reverses it); the browser must be restarted. Chrome 136+ ignores a
  debugging port on the real profile, which is why this is an extension. Tested end to end in a throwaway headless Chromium. 21 tests.
- E9: **the finale, and machines that really fit together.** A lesson can end with `finale: {say, motion, emitter}`: the machine is put together and does its job, then
  everything vanishes. `launch` (rocket: ignition shake, flame and smoke on a pad, climbs away), `drive` (truck: dust, road, drives off), `sink` (submarine: water surface,
  sways down with bubbles, fades), `fly` (contrail). The whole assembled body moves as one group; effects stream from the `emitter` part. New **blueprint** layout: the
  outline draws every part as a box (`size` [w,h,d], `at` one centre per copy) in one shared machine frame (front at +x, ground at y=0), the part's code is scaled to fill
  its box, so the assembled machine is right by construction (four wheels are one part with four centres). Boxes that pass through each other or float loose are rejected
  with numbers so the model fixes them (an idea taken from Teardown: real dimensions in one frame, collisions fixed with numbers). Blueprint lessons play as a teardown:
  step 1 shows the finished machine, then it hangs apart while each part is explained (the camera aims where the part hangs), and it snaps back together for the finale.
  The window opens once most of the machine's parts exist. `GOOP_START=<seconds>` starts playback partway in (for testing endings). 24 new tests.
- T4: **talk to goops.** Clicking a goop shows two round buttons beside it, **Talk** (microphone) and **Type** (pencil); the microphone stays closed until Talk is
  chosen. Talk opens the ask box already listening: a pulsing mic button, your words appearing live, a pause of about a second ends the question, the text stays
  on screen for 1.5 s with a bar running down (type or click to edit, Enter sends at once), then it is asked. Speech-to-text is Moonshine small streaming (142 MB,
  on-device, 5.5x real time on this laptop; tiny/medium selectable as `stt.model`), run by `daemon/stt_server.py` with the microphone read through `parecord`
  (PipeWire), nothing recorded or sent anywhere. The window title is passed as context so names come out right. The model unloads 3 minutes after the last use
  (it holds about 400 MB). Settings: panel toggle "Talk to goops", config `stt`; setup.sh installs it; the checklist has a "Talk to goops" line. 17 tests (fake mic and
  engine, plus one with the real model). A noise estimate that only learned during quiet would have let a humming fan keep a question open forever; found by the tests.
- E5b: **model-written code parts** (`kind: "code"`, `goop/explainer/codegen.py`): the model writes each part's geometry as a small JavaScript function using the renderer's
  own mesh helpers (box, lathe, extrude, torus, raw triangles, loops). It runs in **Deno with no permissions** (no files, network, environment or subprocesses), a 256 MB
  memory cap, a 6 s limit and output checks; errors go back to the model for repair. Lessons use it by default when `deno` is installed (setting `explain_parts`:
  auto/code/pieces) and fall back to basic pieces if code cannot be made to work. Blu-ray test: 8 parts, 101 s to plan, 3.6 MB scene (the pieces version took 40 s).
  `daemon/plan_lesson.py` plans from the command line. 7 new tests, including hostile code.
- E5: **custom parts**: the model can now describe a part it has no ready-made shape for as a recipe of up to 24 basic pieces (box, cylinder, cone, sphere,
  ring, disc with a hole, `lathe` = a profile revolved into a bottle/bowl/disc, `extrude` = an outline pushed into a gear/bracket), with material, look (glass,
  glow...), turn and repeat (a circle of bolts or pits). Data only, validated with repairable errors (`goop/explainer/custom.py`); the engine measures and places the
  part like any other. The planner is told never to borrow a ready-made kind for something else. Test: a hand-written Blu-ray lesson and one planned by opus.
- E4: a **Close lesson** pill in the lesson window (the only part that takes clicks) and `goopctl explain3d stop`.
- E3/E7: **Goop can build a 3D lesson itself.** New agent tool `explain_in_3d(topic, notes)`: a card asks first (the offer), then a strong model
  (`explain_model`, default opus, a bare `claude` call of a fraction of a cent of input) writes the storyboard (`goop/explainer/planner.py`), the validator's exact
  errors go back for up to two repairs, and the lesson plays narrated by the goop that was asked (`goop/explainer/play.py`, `bin/goop-explain --stop`).
  New setting `explainers`: Offer first (default) / Build automatically / Never (panel section 3D LESSONS, `goopctl config set explainers ...`); Never also
  withholds the tool. Network lessons now place every non-wall part around the sender. 17 new tests.
- E2: **explainer vocabulary**: storyboard JSON schema with repair-friendly errors (`goop/explainer/`), a parts library (fans, compressors, chambers, routers, capsules, tanks...),
  three layout templates (axis, network, assembly), a timeline/camera director, and a generic Quick 3D renderer (`shell/explainer3d/Lesson3D.qml`).
  Proven by three hand-written kid-level lessons (`bin/goop-explain jet_engine|wifi|spacecraft`, about 90-120 s each, 11-24% CPU). 21 new tests.
- E1: **3D explainer spike**: `bin/goopctl explain3d dam` plays a 30 s windowless 3D animation of a hydroelectric dam (built up, taken apart,
  water followed through) as its own short-lived Quick 3D process (`shell/explainer3d/`); geometry is generated by code, no assets. Needs the
  optional package `qt6-quick3d`, now checked in the setup list. A canvas-only version (`shell/Explainer.qml`, `goopctl explain dam`) exists as a
  zero-dependency fallback but costs far more CPU. Not in the shell process: loading Quick 3D there once crashed the Omarchy shell.
- S2c: **access level** (`goop/access.py`): Look only / Ask first (default) / Ask for everything, one switch in the settings panel (ACCESS) and
  `goopctl config set access ...`. Enforced in `tools.call` (acting tools refused at Look only), withheld from the tool lists the models see
  (Claude's allowed/denied lists, the MCP `tools/list`, the OpenAI-compatible provider), and stated in the system prompt so the agent explains its
  limits. At Ask for everything, screenshots and file reads also show a card. `read_files` and `auto_approve_safe` remain as explicit overrides.
  Tests no longer depend on the developer's own config. 14 new tests.
- S1: **settings button in the bar** (`shell/GoopPanel.qml`, manifest kind `bar-widget`): animations, voice mute (now saved in config), agent picker,
  and a setup checklist from `daemon/doctor.py` (`goop/doctor.py`, 6 tests). Changing the agent is validated against the configured providers.
- V2: drips. A bulge forms at the bottom of a goop, stretches on a thin neck, lets go and falls (`shell/Drip.qml`).
- Animation levels `full` / `reduced` / `off`, switchable live (`goopctl animations ...`, `~/.config/goop/config.json`). Measured CPU for the
  whole shell: about 7% / 1.7% / 1.0% of one core. `off` also stops the cursor-tracking process. `daemon/settings.py` and `goopctl config`
  read and change settings safely (validated, atomic writes).
- V1 (first pass): liquid goop bodies. A smooth closed curve whose rim moves with slow waves and a travelling slosh bump, a heavier bottom,
  jelly squash-and-stretch breathing, and livelier motion while speaking, thinking or startled. The peel blobs use the same shape.
- Tracking: `docs/BACKLOG.md`, this changelog, `docs/PUBLISHING.md` (marketplace research).

## [0.1.0] - 2026-10-30 (first working version, not yet published)

### Added
- Animated goops that live on windows: the first window gets one; drag a goop onto another window to peel off a copy with its own
  color, eyes (spacing, size, tilt), blink rhythm and voice. Works across workspaces.
- Eyes that blink and follow the cursor; moods (idle, startled, thinking, happy, error).
- Click a goop to ask it about its window. Agent runs through a provider interface; Claude Code first, then any
  OpenAI-compatible endpoint (OpenAI, Grok, Gemini, Ollama, ...), with per-goop conversation memory.
- Window understanding: terminal (shell, project, git), file manager (folder and listing), screenshots for anything else.
- Tools behind one MCP server: screenshot, window_info, read_context, read_file (text, PDF, images), list_files,
  type_in_terminal, move_files, undo_last_move. All safety rules live in `goop/actions.py` and are unit-tested.
- Approval cards for every action that changes something; a strict allowlist of read-only terminal commands runs without one.
- On-device voice (Piper `en_US-libritts_r-medium`): first audio in about 70 ms, a different speaker per goop, a small wave-bar
  mouth on the goop that is talking.
- Speech bubble that grows to fit; replies kept short and spoken; quick-reply buttons (Keep going / Enough, Yes / No thanks).
- Shrink-wrapping ask box with click-away close.
- Omarchy plugin packaging (`manifest.json`, overlay, keepLoaded), `setup.sh` for the voice runtime, `bin/goopctl`.
- Privacy deny list, audit log, 87 tests.

### Fixed
- The overlay re-assigned its goop list on every window poll even when nothing changed, causing needless recomputation (and starving a debounce timer).

### Fixed during development
- Workspace switches mid-drag no longer cancel the peel.
- Window focus uses Hyprland 0.56's Lua dispatch, with a fallback for older versions.
- Terminals sharing one process (Ghostty) are matched to their shell by title.
- Ask box flicker (fixed-size surface) and click-away (full-screen modal surface).
