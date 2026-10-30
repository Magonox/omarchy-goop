"""Provider lookup. "claude" is built in; any other name is an OpenAI-compatible endpoint from the user's config:

  {"provider": "grok", "providers": {"grok": {"base_url": "https://api.x.ai/v1", "model": "...", "api_key_env": "XAI_API_KEY"}}}

To add a different kind of provider, write a Provider subclass and handle its `type` in get()."""
from .. import config
from .claude import ClaudeProvider
from .openai_compat import OpenAICompatProvider


def _configured():
    return config.load().get("providers") or {}


def names():
    return ["claude"] + [n for n in _configured() if n != "claude"]


def get(name=None):
    cfg = config.load()
    name = name or cfg.get("provider", "claude")
    if name == "claude":
        return ClaudeProvider()
    entry = (cfg.get("providers") or {}).get(name)
    if isinstance(entry, dict):
        if entry.get("type", "openai-compat") == "openai-compat":
            return OpenAICompatProvider(name, entry)
        raise ValueError(f"provider {name!r} has an unknown type {entry.get('type')!r}")
    raise ValueError(f"unknown provider {name!r}; available: {', '.join(names())}")


def available():
    return [n for n in names() if get(n).available()]
