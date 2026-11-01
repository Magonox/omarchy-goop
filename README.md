# Goop

**A small gooey creature that lives on your windows.** Click it, then *talk* or *type*: it looks at what's in that window and helps. It can explain a web page with a **3D model it builds for you**, read your terminal, sort your files (with your OK), and answer out loud.

An [Omarchy](https://omarchy.org) plugin: a Quickshell overlay and a small Python daemon. Everything about voice runs on your machine.

- **Talk or type.** Click a goop and two buttons appear beside it: **Talk** (microphone) and **Type** (pencil). Speak, pause, and your words show on screen for a moment before they are sent, so you can fix them.
- **It understands the window.** A terminal (which shell, which project, git state), a file manager (which folder, what is in it), a web page in Chromium (the actual text, not a screenshot), anything else (a screenshot it takes itself).
- **3D lessons.** Reading about how something works? Goop offers to build a narrated 3D model: the finished machine appears, comes apart while each part is explained, then snaps back together and does what it is for (a truck drives off, a balloon floats away, a rocket lifts off). About a minute to build.
- **Acts only with your OK.** Typing a command, moving files (undoable): each shows a card with exactly what will happen. You choose how careful it is.
- **Speaks.** An on-device voice, a different one for each goop, with a small wave bar for a mouth.
- **Lives on every window and every monitor.** Drag a goop onto another window to peel off a copy. The overlay follows the monitor you are using.

## Install

```bash
omarchy plugin add https://github.com/Magonox/omarchy-goop.git --enable
```

The **setup card opens by itself** the first time a goop appears. It checks what you have, installs the voice with one button, and lets you choose how careful Goop is. Skip it any time, and run it again from the ghost icon in the bar (**Run setup again**).

### What it needs

| | |
|---|---|
| **Required** | Omarchy with Hyprland, the [Claude Code](https://claude.com/claude-code) CLI (`claude`, logged in), `grim` |
| **Voice and talking** (optional, one button in the setup card) | `python3` and about 450 MB: the voice (about 75 MB) and the speech recognizer (about 140 MB) plus their libraries, in a private folder `~/.local/share/goop`. Needs `paplay` and `parecord` (PipeWire's pulse layer, already on Omarchy). |
| **3D lessons** (optional) | `sudo pacman -S qt6-quick3d deno`. `deno` runs the model's shape code in a sandbox with no file, network or process access. |
| **Typing into terminals, reading PDFs** (optional) | `wtype`, `poppler` (`pdftotext`) |
| **Reading web pages** (optional) | Chromium, plus one command: `bin/goop-install-pagereader` (below) |

`omarchy plugin validate .` passes, and the setup card shows exactly which of these you have and the fix for each one you do not.

## Using it

| Do this | To get this |
|---|---|
| Click a goop | **Talk** and **Type** buttons appear beside it. |
| Talk | Speak; about a second of quiet ends the question. Your words show with a bar running down, then it is asked. Type or click to edit instead. |
| Type | A small box opens. Enter sends, Esc closes. |
| Drag a goop onto another window | A copy peels off with its own color and voice. |
| Press **Approve** on a card | The action runs. **Deny**, or ignore it for 90 seconds, and nothing happens. |
| Ask for a model: *"explain how this page works with a 3D model"* | A card asks first, then the lesson builds and plays, narrated. **Close lesson** (top right of it) or `bin/goopctl explain3d stop` ends it. |
| Click the ghost icon in the bar | Settings: animations, voice, talking, access level, 3D lessons, agent, a setup checklist. |

`bin/goopctl` talks to the running goop: `list`, `say <addr> "..."`, `speak`, `mute`, `hush`, `explain3d <name>`, `config get|set`.

## Privacy and permissions

**What leaves your computer.**
- **Your agent.** When you ask, Goop sends the question and that window's context (the terminal's project and recent output, the folder listing, the page text, or a screenshot) to your **Claude Code CLI**, the same as if you had pasted it yourself. Goop never looks at a window in the background.
- **3D lessons.** After you approve a card, the topic and a short summary of the page go to a Claude model that plans the lesson (about 20 to 40 cents on the API, or counted against your plan). Set **3D lessons: Off** and nothing is ever sent for this.
- Nothing else. There is no telemetry, no account, no server of ours.

**Voice.** Speaking (Piper) and listening (Moonshine) run on your CPU. The microphone opens only while you are talking, is never recorded to disk, and its audio is never sent anywhere.

**Access level** (setup card or panel): *Ask first* (default) shows a card before any action; *Ask for everything* adds a card for every file read and screenshot; *Look only* cannot change anything. A privacy block list (password managers, anything titled "bank", "password"...) is never read or captured.

**The page reader (Chromium extension).** It needs permission to read pages (`tabs`, `scripting`, access to all sites) because Chromium offers no narrower way to read the page you ask about. It does nothing until a goop asks for the page you are on, sends that one tab's text to Goop over a private socket on this computer, and keeps nothing. It is off in incognito windows. Read its entire source in `browser/pagereader/` (one 62-line script). The installer adds it to the `--load-extension` list in `~/.config/chromium-flags.conf` (after backing that file up) and writes a native-messaging host file. Remove it with `bin/goop-install-pagereader --uninstall`.

**Files Goop writes:** `~/.config/goop/` (settings), `~/.local/share/goop/` (voice and the Python environment), `~/.cache/goop/` (logs, screenshots, built lessons; safe to delete).

## Choosing the agent

Goop talks to Claude Code by default (3D lessons are planned with the `claude` CLI for now). To use another LLM, add any **OpenAI-compatible** endpoint (OpenAI, xAI Grok, Gemini's
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

Goops cost about 7% of one CPU core in the default **Full** mode (liquid wobble, drips), 1.7% in **Reduced** (plain round, still blinking) and 1% in **Off**. Pick a level in the bar panel on an older machine. The speech recognizer holds about 400 MB while loaded and lets go three minutes after you last used it; a playing 3D lesson uses about 10% of a core and 260 MB.

## Configuration

Everything in the panel and the setup card is saved to `~/.config/goop/config.json` and applies instantly. Other keys: `tts.speed`, `stt.model` (`tiny`, `small`, `medium`), `stt.auto_send_ms`, `explain_model`, `explain_part_effort`, `deny_classes`, `deny_title_regex`. `bin/goopctl config get [key]` and `config set <key> <value>` read and write it.

## Troubleshooting

| | |
|---|---|
| The setup card says the agent is missing | Install Claude Code and run `claude` once to log in. |
| No voice / no Talk button | Setup card, step 2: **Install voice and talking**. |
| A web page is only read by screenshot | Run `bin/goop-install-pagereader` and **restart Chromium**. |
| 3D lessons say they need something | `sudo pacman -S qt6-quick3d deno`. |
| Goop disappears after a theme change | Some theme tools rewrite `~/.config/omarchy/shell.json` and drop third-party plugins; re-add `{"id": "io.github.magonox.goop"}` to `.plugins` in your post-theme hook (see `docs/DEVELOPMENT.md`). |

## Uninstall

```bash
bin/goop-install-pagereader --uninstall      # only if you installed the page reader
omarchy plugin remove io.github.magonox.goop
rm -rf ~/.local/share/goop ~/.cache/goop ~/.config/goop
```

## Development

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md). Tests (no GPU, audio or network needed): `python3 -I -m unittest discover -s daemon/tests`. Roadmap: [`docs/BACKLOG.md`](docs/BACKLOG.md). Changes: [`CHANGELOG.md`](CHANGELOG.md).

## Third-party software

Goop's own code is MIT. `setup.sh` installs these into a private folder on your machine; none of them is bundled or redistributed by Goop:
**Piper** text-to-speech (GPL-3.0-or-later) with the default voice trained on LibriTTS-R (CC BY 4.0), **Moonshine** speech recognition and its English models (MIT), and `onnxruntime` and `numpy` (permissive). The optional `deno` (MIT) and `qt6-quick3d` (LGPL) come from your package manager.

## License

[MIT](LICENSE). Goop's page reader and 3D lessons were shaped by ideas from [Teardown](https://github.com/elvarofficial/teardown) (MIT).
