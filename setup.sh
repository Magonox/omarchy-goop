#!/usr/bin/env bash
# Optional one-time setup for goop's voice: a private Python venv with Piper (on-device TTS) plus the voice model.
# Safe to re-run. Goop works without it, just silently.
#
#   ~/.config/omarchy/plugins/<goop-id>/setup.sh
set -euo pipefail

DATA="${XDG_DATA_HOME:-$HOME/.local/share}/goop"
VENV="$DATA/venv"
VOICES="$DATA/voices"
VOICE="en_US-libritts_r-medium"

say() { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m! %s\033[0m\n' "$*"; }

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

say "Voice: Piper venv in $VENV"
mkdir -p "$DATA"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip piper-tts moonshine-voice

say "Voice model: $VOICE (about 75 MB)"
mkdir -p "$VOICES"
if [ ! -f "$VOICES/$VOICE.onnx" ]; then
  "$VENV/bin/python" -m piper.download_voices --download-dir "$VOICES" "$VOICE"
fi

say "Voice input: Moonshine speech model (about 140 MB)"
"$VENV/bin/python" - <<'PY' || warn "could not download the speech model (voice input will try again when first used)"
import moonshine_voice as mv
mv.get_model_for_language("en", mv.ModelArch.SMALL_STREAMING)
PY

say "Page reader (optional): run  $(cd "$(dirname "$0")" && pwd)/bin/goop-install-pagereader  so goops can read web pages in Chromium"

say "Checking what goop uses"
for tool in claude wtype grim paplay parecord pdftotext hyprctl; do
  command -v "$tool" >/dev/null || warn "$tool not found${tool/claude/ (the agent needs the Claude Code CLI)}"
done
say "Done. Restart the shell (omarchy restart shell) or run: omarchy plugin enable <goop-id>"
