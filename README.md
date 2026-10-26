# Goop

A small animated creature that lives on your windows. Click it to ask about what's in that window, peel copies of it onto other
windows, and let it act for you, always with your approval. It talks, with an on-device voice.

An [Omarchy](https://omarchy.org) plugin (Quickshell overlay + a small Python daemon).

- **Lives on windows.** The first window gets one goop. Drag any goop onto another window to peel off a copy (new color, new
  personality, new voice). It works across workspaces.
- **Understands the window.** A terminal (which shell, which project, git state), a file manager (which folder, what's in it),
  anything else (a screenshot it takes itself). It can read files in the folder the window shows, including PDFs.
- **Acts, with your OK.** Typing a command into a terminal, sorting files into folders (undoable). Plain read-only commands
  (`ls`, `cd`, `pwd`, `git status`) run right away; everything else shows a card with the exact action and waits for Approve.
- **Talks.** Piper TTS runs on your CPU (first audio in about 70 ms). The speaking goop shows a small wave bar as its mouth.
- **Quick replies.** When it asks "Want me to keep going?" you get a button instead of typing.
- **Provider-agnostic design.** Today the agent is Claude Code (`claude -p`); the provider interface and the tool layer (an MCP
  server) are built so other LLMs can be added.

## Install

```bash
omarchy plugin add https://github.com/<you>/goop.git --enable
~/.config/omarchy/plugins/shawn.goop/setup.sh        # optional: on-device voice (Piper venv + ~75 MB voice)
```

Requirements: Omarchy / Hyprland, the [Claude Code](https://claude.com/claude-code) CLI (`claude`, logged in), `python3`,
`grim`, `wtype`, `poppler` (`pdftotext`), `paplay` (PipeWire/PulseAudio). `setup.sh` reports anything missing.

Goop loads with the Omarchy shell, so it is running whenever you are logged in.

> If a theme tool rewrites `~/.config/omarchy/shell.json` (Omagen does, on every theme change), it drops third-party plugins from
> the enabled list. Re-add `{"id": "shawn.goop"}` to `.plugins` in your post-theme hook (see `docs/DEVELOPMENT.md`).

## Using it

| Do this | To get this |
|---|---|
| Click a goop | Opens a small box under it. Type, Enter to send, Esc or click elsewhere to close. |
| Drag a goop onto another window | A copy peels off and lands there. Dropping on a window that has one springs back. |
| Press **Approve** on a card | The action runs. **Deny** or ignore it for 90 s and nothing happens. |
| Press **Keep going / Yes** under a reply | Answers "yes" for you; the goop continues. |

`bin/goopctl` talks to the running goop: `goopctl list | say <addr> "..." | speak <addr> "..." | mute true | hush | reload`.

## What it can and cannot do

- Reads only what the window shows: its screenshot, its terminal's working directory, its folder. Secret-looking files
  (`.env`, keys, `id_rsa`, `*token*`, `.ssh/`...) and your whole home directory are refused.
- Never deletes or overwrites files. Moves stay inside the folder shown, and the last sort can be undone.
- Won't type into a terminal running `claude`, `nvim`, `ssh`..., or when it can't tell which shell the window is.
- Windows matching a deny list (password managers, titles containing "bank"/"password"...) are never read or captured.
- Text from windows and files is treated as data, never as instructions.
- Every tool call is logged to `~/.cache/goop/audit.log`. Voice and tool logic run locally; the only thing sent out is the
  conversation with your chosen LLM.

## Configuration

`~/.config/goop/config.json` (all optional):

```json
{
  "auto_approve_safe": true,
  "read_files": "folder",
  "model": "haiku",
  "tts": { "enabled": true, "speed": 0.94, "pause_ms": 220, "speakers": [0, 112, 233, 358, 471, 590, 702, 815] },
  "deny_classes": ["1password", "bitwarden", "keepassxc"],
  "deny_title_regex": ["password", "bank"]
}
```

`read_files`: `"folder"` (read inside the window's own folder), `"ask"` (a card per file), `"off"`.
Audition voices: `~/.local/share/goop/venv/bin/python daemon/voices.py --random 12`.

## Uninstall

```bash
omarchy plugin remove shawn.goop
rm -rf ~/.local/share/goop ~/.cache/goop ~/.config/goop
```

## Development

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md). Tests: `python3 -I -m unittest discover -s daemon/tests` (no GPU, audio, or
network needed).
