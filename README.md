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
| Click the ghost icon in the bar | Goop's settings: animation level, voice on/off, which agent, and a setup checklist. |

`bin/goopctl` talks to the running goop: `goopctl list | say <addr> "..." | speak <addr> "..." | mute true | hush | reload`.

## Access level

One setting decides how much goop may do. Change it in the settings panel (ghost icon in the bar, ACCESS) or with
`bin/goopctl config set access look|ask|ask_all`. It applies at once.

| Level | Goop can | Goop asks first |
|---|---|---|
| **Look only** | see windows, read files in the folder a window shows | never acts: typing and moving files are refused (and not even offered to the agent) |
| **Ask first** (default) | do the above, plus run plain read-only commands (`ls`, `cd`, `pwd`...) at once | every other action: an approval card shows the exact command or file moves |
| **Ask for everything** | read what is already in the window's context | every screenshot, file read, command and move |

The level is enforced in the tools themselves, not just suggested to the agent, and the agent is told its level so it can explain it.

## What it can and cannot do

- Reads only what the window shows: its screenshot, its terminal's working directory, its folder. Secret-looking files
  (`.env`, keys, `id_rsa`, `*token*`, `.ssh/`...) and your whole home directory are refused.
- Never deletes or overwrites files. Moves stay inside the folder shown, and the last sort can be undone.
- Won't type into a terminal running `claude`, `nvim`, `ssh`..., or when it can't tell which shell the window is.
- Windows matching a deny list (password managers, titles containing "bank"/"password"...) are never read or captured.
- Text from windows and files is treated as data, never as instructions.
- Every tool call is logged to `~/.cache/goop/audit.log`. Voice and tool logic run locally; the only thing sent out is the
  conversation with your chosen LLM.

## Choosing the agent

Goop talks to Claude Code by default. To use another LLM, add any **OpenAI-compatible** endpoint (OpenAI, xAI Grok, Gemini's
compatible endpoint, Ollama, LM Studio, OpenRouter, Groq, Together...) to `~/.config/goop/config.json`:

```json
{
  "provider": "grok",
  "providers": {
    "grok":   { "base_url": "https://api.x.ai/v1", "model": "<model id>", "api_key_file": "~/.config/goop/keys/xai", "vision": true },
    "ollama": { "base_url": "http://localhost:11434/v1", "model": "<model id>" }
  }
}
```

- **Keys never go in the config.** Use `api_key_file` (a file containing only the key; `chmod 600` it; takes effect immediately) or
  `api_key_env` (a variable in `~/.config/uwsm/env.d/*`; needs a re-login). A local server like Ollama needs neither.
- `vision: true` only if the model can read images; otherwise the goop uses text context instead of screenshots.
- The model must support **tool calling**. Tools, approval cards and every safety limit are the same for every provider.
- Check setup: `python3 daemon/providers.py` (what is ready) and `python3 daemon/providers.py --test grok` (sends one tiny request).
- A conversation is remembered per goop for a week (`~/.cache/goop/sessions/`), so "yes, keep going" works with any provider.

## Animations and performance

The quickest way is the **Goop button in the top bar** (a ghost icon): pick Full, Reduced or Off. Or from a terminal:

Goops are animated, and the animation level is yours to choose. It applies instantly, no restart:

```bash
bin/goopctl animations full       # liquid wobble, jelly breathing, drips, blinking, eyes follow the cursor
bin/goopctl animations reduced    # plain round goops; blinking and eye-tracking only
bin/goopctl animations off        # static goops; no blinking, and the cursor-tracking process stops
```

Measured on an Intel i7-8559U laptop (4 cores, 2018), the whole Omarchy shell with goops showing: **full about 7% of one core,
reduced about 1.7%, off about 1.0%**. Animations cost CPU, not memory: the shell's memory stays at about 450 MB at every level.
(Also in `~/.config/goop/config.json` as `"animations"`.)

## Configuration

`~/.config/goop/config.json` (all optional):

```json
{
  "access": "ask",
  "model": "haiku",
  "tts": { "enabled": true, "speed": 0.94, "pause_ms": 220, "speakers": [0, 112, 233, 358, 471, 590, 702, 815] },
  "deny_classes": ["1password", "bitwarden", "keepassxc"],
  "deny_title_regex": ["password", "bank"]
}
```

`access` is explained under *Access level*. `read_files` (`"folder"`, `"ask"`, `"off"`) and `auto_approve_safe` (`true`/`false`) are optional
overrides of the level, for people who want one exception.
Audition voices: `~/.local/share/goop/venv/bin/python daemon/voices.py --random 12`.

## Uninstall

```bash
omarchy plugin remove shawn.goop
rm -rf ~/.local/share/goop ~/.cache/goop ~/.config/goop
```

## Development

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md). Tests: `python3 -I -m unittest discover -s daemon/tests` (no GPU, audio, or
network needed).
