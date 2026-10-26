"""The one event vocabulary every provider translates into. The shell drives moods and the speech bubble from these."""


def start(provider, app_type):
    return {"type": "start", "provider": provider, "app_type": app_type}


def thinking():
    return {"type": "thinking"}


def text(t):
    """The latest assistant text so far (replaces the previous one, it is not a delta)."""
    return {"type": "text", "text": t}


def tool_use(name):
    return {"type": "tool_use", "name": name}


def done(t, session=None, cost=None):
    return {"type": "done", "text": t, "session": session, "cost": cost}


def error(message):
    return {"type": "error", "message": message}
