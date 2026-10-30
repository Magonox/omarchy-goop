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
| L3 | Rename the id everywhere (manifest, theme hook, plugin symlink, docs, `goopctl`) | decision | Blocked on L1. Re-enable the plugin after. |
| L4 | Marketplace-ready README: install, **removal**, external dependencies | todo | Required by the submission guide. Mostly written. |
| L5 | `preview.png` in the repo root | todo | Optional but it is the card image. Needs a good screenshot (see M1). |
| L6 | Self-check against the security baseline | todo | `setup.sh` is an installer (pip, model download) so it will be flagged `review-required`, not rejected. Keep: no `curl | sh`, no unpinned remote code. |
| V1 | Gooey outline: edges that wobble like liquid instead of a plain circle | doing | First pass in (2026-10-30): `shell/goo.js` + `GooBody.qml`, jelly squash-and-stretch breathing, livelier when speaking/thinking/startled, the peel blobs use the same shape. CPU unchanged (5-6% of a core for the whole shell). **Waiting on owner feedback**: more or less wobble? Knobs: amplitudes in `goo.js` (`a2/a3/a4/ab`, sag), breathing 0.05 in `Goop.qml`. |
| V2 | Drips: a small drop forms at the bottom, falls a few pixels, fades | todo | Random interval per goop; calmer while speaking. |

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
