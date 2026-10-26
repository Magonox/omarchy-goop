# Development handoff

State as of 2026-10-26. Everything below was built and verified live on an Intel i7-8559U laptop (Omarchy, Hyprland 0.56.2,
Quickshell 0.3.2, single 2x display).

## Run and develop

Goop is an **Omarchy plugin** (`manifest.json`: kind `overlay`, `keepLoaded: true`), so it starts with the Omarchy shell.

- Dev checkout lives in `~/ai_apps/goop`, symlinked into `~/.config/omarchy/plugins/shawn.goop` (Omarchy follows the symlink).
- After editing QML or Python: `bin/goopctl reload` (= `omarchy-shell shell rescanPlugins`). Python daemon scripts are started
  fresh per request, so most daemon edits apply immediately; the long-lived ones (`tts_server.py`, `cursor.py`) need a reload.
- Full restart, same as login: `omarchy-restart-shell`. Goops are ephemeral: after a restart the first window gets one again.
- Tests: `python3 -I -m unittest discover -s daemon/tests` (70, stdlib only, no hardware).
- Standalone (outside the plugin system): `quickshell -n -p shell`. Don't run it while the plugin is enabled: you get two overlays.
- Logs: `quickshell log -p /usr/share/omarchy/shell | grep -i goop`. Audit of tool calls: `~/.cache/goop/audit.log`.
- Voice runtime is outside the repo (plugins may not contain symlinks, and venvs do): `setup.sh` -> `~/.local/share/goop/{venv,voices}`.

**Gotcha: Omagen.** It rewrites `~/.config/omarchy/shell.json` on every theme change and drops third-party plugins. The user's
hook `~/.config/omarchy/hooks/theme-set.d/zz-shell-overrides.sh` re-adds `shawn.goop` (a `jq` line next to `shawn.idle`). Without
it the day/night theme timer would switch goop off at sunset.

## Architecture

```
shell/Goop.qml        overlay: goops, peel/drop, bubbles, quick replies, approval cards, ask box, mouth bar, voice client
shell/Eyes.qml        eyes: personality from a seed, blink, gaze, moods (idle/startled/thinking/happy/error)
daemon/state.py       window geometry + pending approvals, polled by the shell every 250 ms
daemon/drop.py        hit-test the window under the cursor, build its context packet
daemon/agent.py       one question about one window -> provider -> JSON-lines events (start/thinking/text/tool_use/done/error)
daemon/mcp_server.py  stdio MCP server exposing goop/tools.py for ONE window (fixed by env GOOP_WINDOW)
daemon/tts_server.py  warm Piper process; speaks sentence by sentence, emits mouth levels
daemon/cursor.py      cursor position stream for gaze
daemon/goop/          adapters/ (terminal, folder), agent/ (provider interface + claude), tts/, tools.py, actions.py (all safety
                      rules, pure and tested), approvals.py (file handshake with the shell), config.py, hypr.py, ...
```

Flow of a question: click goop -> ask box -> `agent.py` builds a packet, writes an MCP config, runs `claude -p` (prompt on stdin)
-> Claude calls tools through `mcp_server.py` -> acting tools block on an approval card (`approvals.py`) -> events stream back ->
bubble, mood, voice. Sessions resume per goop (`--resume`), so "yes, keep going" has context.

## Decisions worth remembering

- **Tools live behind MCP**, with one safety model for every provider. Claude's own Bash/Edit/Write stay disabled; Read/Glob/Grep
  are only on for real project windows. Outside projects it uses `read_file`/`list_files` (scoped to the window's folder).
- **TTS: Piper `en_US-libritts_r-medium`**, chosen by benchmark on this CPU (`docs/tts-benchmark/`): first audio ~70 ms, ~25x
  real time. Kokoro was too slow (~1.6 s), Kitten/Supertonic fine but not better. Speed 0.94, 220 ms sentence pauses.
- **Replies are short on purpose** (about 60 words, spoken style); a longer explanation ends in a question and the bubble shows
  Keep going / Enough pills.
- **Safe-command allowlist** (`actions.is_safe_command`): `ls cd pwd du df whoami uname uptime free`, `git status|log`, plain words only.
  The prompt line is cleared with Ctrl+U before typing so half-typed text can't merge into a command.

## Gotchas that cost time

- Hyprland 0.56 is Lua-configured: `hyprctl dispatch 'hl.dsp.focus({ window = "address:0x.." })'`; `hl.dsp.cursor.move({x=,y=})`.
  `hypr.focus_window` falls back to the classic dispatcher for older versions.
- Never hide a drag source mid-drag (Qt cancels its mouse grab). Never resize a layer surface per keystroke (flicker): keep it
  fixed and resize an inner item. An exclusive-keyboard layer is a modal in Hyprland: click-away needs a full-screen transparent
  exclusive surface with a MouseArea behind the box. `follow_mouse` makes on-demand keyboard focus unusable.
- Ghostty runs all windows under one pid: windows are mapped to shells by title (Claude Code titles start with a spinner glyph;
  an idle shell's title is `~`) and the result is `high` or `medium` confidence.
- A tool that raises an unexpected error must not kill the MCP server: `tools.call` converts it to a `ToolError`.
- Paths: the QML finds its own directory with `Qt.resolvedUrl("Goop.qml")`; `Quickshell.shellDir` would be Omarchy's.

## Backlog, in the order I'd do it

1. **File-sort live test** (only unit-tested so far): open Nautilus on a scratch folder, ask a goop to sort it, check the plan
   card, Approve, then undo.
2. **Second provider**: a generic OpenAI-compatible one (covers Grok, Gemini, Ollama, ...: base URL + model + key) to prove the
   provider interface before more code assumes Claude. `goop/agent/base.py` is the contract, `claude.py` the example.
3. **Browser adapter**: launch Chromium with a debug port and read pages via CDP instead of only screenshots.
4. Write actions for project windows (Claude Code's edit tools routed through the approval card via `--permission-prompt-tool`).
5. Voice input (the quick-reply buttons send the same message a spoken "yes" would).
6. A `goopctl speed` live control; per-goop provider (peel a copy and make it a different LLM).

## Before publishing to GitHub

- Choose a license (none yet) and set `manifest.json` `id`/`author`. The id is `shawn.goop` now; GitHub plugins usually use
  `io.github.<user>.goop`. If you rename it, update `README.md`, the hook above, `bin/goopctl`'s docs, and re-enable.
- Create the repo, then `git remote add origin <url> && git push -u origin main`.
- Run `omarchy plugin validate .` (no symlinks allowed inside the plugin folder; the venv is kept outside for that reason).
- Piper (GPL-3.0) is installed by `setup.sh` from PyPI, not bundled; voices have their own licenses.
