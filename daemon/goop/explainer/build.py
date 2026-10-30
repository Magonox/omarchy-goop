"""storyboard (what the model writes) -> resolved scene (what the renderer plays): validate, lay out, schedule."""
import copy, json

from . import codegen, layout, schema, timeline, vocab


class StoryboardError(ValueError):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def build(story):
    errors = schema.validate(story)
    if errors:
        raise StoryboardError(errors)
    story = copy.deepcopy(story)                 # code parts get their sandbox results attached; the caller's storyboard stays clean
    try:
        codegen.resolve(story)
    except codegen.CodeError as e:
        raise StoryboardError([str(e)])
    lay = layout.layout(story)
    tl = timeline.build(story, lay)
    if tl["duration"] > vocab.LIMITS["duration"]:
        raise StoryboardError([f"the lesson would run {tl['duration']:.0f}s; keep it under {vocab.LIMITS['duration']}s (fewer or shorter steps)"])
    parts = []
    for pid, p in lay["placed"].items():
        mat = vocab.MATERIALS[p["material"]]
        palette = {name: vocab.MATERIALS[name] for name in {m["material"] for m in p["shape"].get("meshes", [])}}
        parts.append({k: p[k] for k in ("id", "group", "kind", "label", "shape", "pos", "rot", "explode", "radius") if k in p}
                     | {"material": {"name": p["material"], **mat}, "context": bool(p.get("context")), "spanning": p["spanning"]}
                     | ({"palette": palette} if palette else {})
                     | ({"signal": p["signal"], "distance": p["distance"]} if "signal" in p else {}))
    return {"version": 1, "title": story["title"], "template": story["layout"]["template"], "parts": parts, "bounds": lay["bounds"],
            "question": story.get("question", ""), **tl}


def load(path):
    with open(path) as f:
        return build(json.load(f))
