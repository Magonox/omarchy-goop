"""Provider lookup. Add a provider by writing a Provider subclass and listing it here."""
from .. import config
from .claude import ClaudeProvider

PROVIDERS = {"claude": ClaudeProvider}


def get(name=None):
    name = name or config.load().get("provider", "claude")
    try:
        return PROVIDERS[name]()
    except KeyError:
        raise ValueError(f"unknown provider {name!r}; available: {', '.join(PROVIDERS)}")


def available():
    return [n for n, cls in PROVIDERS.items() if cls().available()]
