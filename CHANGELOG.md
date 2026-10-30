# Changelog

Format: [Keep a Changelog](https://keepachangelog.com). Versions follow the manifest `version`.
Work is planned in [`docs/BACKLOG.md`](docs/BACKLOG.md).

## [Unreleased]

### Added
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

### Fixed during development
- Workspace switches mid-drag no longer cancel the peel.
- Window focus uses Hyprland 0.56's Lua dispatch, with a fallback for older versions.
- Terminals sharing one process (Ghostty) are matched to their shell by title.
- Ask box flicker (fixed-size surface) and click-away (full-screen modal surface).
