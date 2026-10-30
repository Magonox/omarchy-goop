"""storyboard (what the model writes) -> resolved scene (what the renderer plays): validate, lay out, schedule."""
import json

from . import layout, schema, timeline, vocab


class StoryboardError(ValueError):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def build(story):
    errors = schema.validate(story)
    if errors:
        raise StoryboardError(errors)
    lay = layout.layout(story)
    tl = timeline.build(story, lay)
    if tl["duration"] > vocab.LIMITS["duration"]:
        raise StoryboardError([f"the lesson would run {tl['duration']:.0f}s; keep it under {vocab.LIMITS['duration']}s (fewer or shorter steps)"])
    parts = []
    for pid, p in lay["placed"].items():
        mat = vocab.MATERIALS[p["material"]]
        palette = {name: vocab.MATERIALS[name] for name in {pc.get("material", p["material"]) for pc in p["shape"].get("pieces", [])}}
        parts.append({k: p[k] for k in ("id", "group", "kind", "label", "shape", "pos", "rot", "explode", "radius") if k in p}
                     | {"material": {"name": p["material"], **mat}, "context": bool(p.get("context")), "spanning": p["spanning"]}
                     | ({"palette": palette} if palette else {})
                     | ({"signal": p["signal"], "distance": p["distance"]} if "signal" in p else {}))
    return {"version": 1, "title": story["title"], "template": story["layout"]["template"], "parts": parts, "bounds": lay["bounds"],
            "question": story.get("question", ""), **tl}


def load(path):
    with open(path) as f:
        return build(json.load(f))
