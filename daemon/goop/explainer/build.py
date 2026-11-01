"""storyboard (what the model writes) -> resolved scene (what the renderer plays): validate, lay out, schedule."""
import copy, json, os

from . import codegen, layout, schema, timeline, vocab


class StoryboardError(ValueError):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def build(story, parts_dir=None):
    """Validate, lay out and schedule. With `parts_dir` the story is an outline (code parts have a brief and a size but no code yet): each code part's geometry
    will be written to <parts_dir>/<id>.json later and the renderer loads it as it appears. Without it, every code part's code is run now and embedded."""
    errors = schema.validate(story, outline=parts_dir is not None)
    if errors:
        raise StoryboardError(errors)
    story = copy.deepcopy(story)                 # code parts get their sandbox results attached; the caller's storyboard stays clean
    if parts_dir is not None:
        for p in story["parts"]:
            if p["kind"] == "code":
                p["_file"] = os.path.join(parts_dir, p["id"] + ".json")
    else:
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
        palette = dict(vocab.MATERIALS) if p["kind"] == "code" else {}
        parts.append({k: p[k] for k in ("id", "group", "kind", "label", "shape", "pos", "rot", "explode", "radius", "spin_axis") if k in p}
                     | {"material": {"name": p["material"], **mat}, "context": bool(p.get("context")), "spanning": p["spanning"]}
                     | ({"palette": palette} if palette else {})
                     | ({"signal": p["signal"], "distance": p["distance"]} if "signal" in p else {}))
    return {"version": 1, "title": story["title"], "template": story["layout"]["template"], "parts": parts, "bounds": lay["bounds"],
            "question": story.get("question", ""), **tl}


def load(path):
    with open(path) as f:
        return build(json.load(f))
