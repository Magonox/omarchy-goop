"""Check a storyboard before anything is built. Returns human-readable errors; the messages name the valid choices, so they can be handed
straight back to a model for a repair pass."""
import re

from . import codegen, vocab

_ID = re.compile(r"^[a-z][a-z0-9_]{0,23}$")


def _list(items):
    return ", ".join(sorted(items))


def validate(story):
    errs = []
    if not isinstance(story, dict):
        return ["the storyboard must be a JSON object"]
    if story.get("version") != 1:
        errs.append("version must be 1")
    title = story.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > vocab.LIMITS["title"]:
        errs.append(f"title must be 1-{vocab.LIMITS['title']} characters")
    layout = story.get("layout")
    template = layout.get("template") if isinstance(layout, dict) else None
    if template not in vocab.TEMPLATES:
        errs.append(f"layout.template must be one of: {_list(vocab.TEMPLATES)}")

    parts = story.get("parts")
    ids = {}
    lo, hi = vocab.LIMITS["parts"]
    if not isinstance(parts, list) or not lo <= len(parts) <= hi:
        errs.append(f"parts must be a list of {lo}-{hi} parts")
        parts = []
    for p in parts:
        if not isinstance(p, dict):
            errs.append("each part must be an object")
            continue
        pid = p.get("id")
        if not isinstance(pid, str) or not _ID.match(pid):
            errs.append(f"part id {pid!r} must be lowercase letters, digits or _ (start with a letter, max 24)")
            continue
        if pid in vocab.RESERVED_IDS:
            errs.append(f"part id {pid!r} is reserved")
        if pid in ids:
            errs.append(f"duplicate part id {pid!r}")
        ids[pid] = p
        if p.get("kind") not in vocab.KINDS:
            errs.append(f"part {pid!r}: kind {p.get('kind')!r} is not in the vocabulary; use one of: {_list(vocab.KINDS)}")
        label = p.get("label")
        if not isinstance(label, str) or not label.strip() or len(label) > vocab.LIMITS["label"]:
            errs.append(f"part {pid!r}: label must be 1-{vocab.LIMITS['label']} characters")
        if p.get("kind") == "code":
            lo_c, hi_c = codegen.LIMITS["code"]
            if not isinstance(p.get("code"), str) or not lo_c <= len(p["code"]) <= hi_c:
                errs.append(f"part {pid!r}: a code part needs code: a string of {lo_c}-{hi_c} characters defining function build(M) that returns [{{material, look, mesh}}]")
        if p.get("size", "medium") not in vocab.SIZES:
            errs.append(f"part {pid!r}: size must be one of: {_list(vocab.SIZES)}")
        if p.get("material", "steel") not in vocab.MATERIALS:
            errs.append(f"part {pid!r}: material must be one of: {_list(vocab.MATERIALS)}")

    def known(ref, where):
        if ref not in ids:
            errs.append(f"{where}: unknown part {ref!r}; parts are: {_list(ids)}")
            return False
        return True

    for pid, p in ids.items():
        kind = vocab.KINDS.get(p.get("kind"), {})
        if kind.get("spanning"):
            sp = p.get("spans")
            if not (isinstance(sp, list) and len(sp) == 2 and all(isinstance(x, str) for x in sp)):
                errs.append(f"part {pid!r}: a {p.get('kind')} needs spans: [first_part_id, last_part_id]")
            else:
                for r in sp:
                    known(r, f"part {pid!r} spans")
        if p.get("kind") == "device" and p.get("variant", "laptop") not in ("laptop", "phone", "tv", "speaker", "antenna"):
            errs.append(f"part {pid!r}: device variant must be one of: laptop, phone, tv, speaker, antenna")
        if template == "network":
            if not vocab.is_sender(p) and not vocab.is_blocker(p) and p.get("distance", "medium") not in vocab.DISTANCES:
                errs.append(f"part {pid!r}: distance must be one of: {_list(vocab.DISTANCES)}")
            if vocab.is_blocker(p):
                bt = p.get("between")
                if not (isinstance(bt, list) and len(bt) == 2):
                    errs.append(f"part {pid!r}: a wall (any part with between) needs between: [part_id, part_id]")
                else:
                    for r in bt:
                        known(r, f"wall {pid!r} between")
        if template == "assembly":
            att = p.get("attach")
            if att is not None:
                if not isinstance(att, dict) or att.get("at") not in vocab.ATTACH_AT:
                    errs.append(f"part {pid!r}: attach needs to (a part id) and at (one of: {_list(vocab.ATTACH_AT)})")
                else:
                    known(att.get("to"), f"part {pid!r} attach")
                    if not isinstance(att.get("count", 1), int) or not 1 <= att.get("count", 1) <= 8:
                        errs.append(f"part {pid!r}: attach.count must be 1-8")
            if p.get("inside") is not None:
                known(p.get("inside"), f"part {pid!r} inside")
    if template == "network" and not any(vocab.is_sender(p) for p in ids.values()):
        errs.append("a network lesson needs a sender: one part with \"sender\": true (the thing the signal spreads from)")

    steps = story.get("steps")
    slo, shi = vocab.LIMITS["steps"]
    if not isinstance(steps, list) or not slo <= len(steps) <= shi:
        errs.append(f"steps must be a list of {slo}-{shi} steps")
        steps = []
    for n, st in enumerate(steps, 1):
        where = f"step {n}"
        if not isinstance(st, dict):
            errs.append(f"{where} must be an object")
            continue
        say = st.get("say")
        if not isinstance(say, str) or not vocab.LIMITS["say"][0] <= len(say) <= vocab.LIMITS["say"][1]:
            errs.append(f"{where}: say must be {vocab.LIMITS['say'][0]}-{vocab.LIMITS['say'][1]} characters of friendly narration")
        if len(st.get("analogy", "") or "") > vocab.LIMITS["analogy"]:
            errs.append(f"{where}: analogy is too long")
        for verb in st.get("do", []) or []:
            if not isinstance(verb, dict) or len(verb) != 1 or next(iter(verb)) not in vocab.VERBS:
                errs.append(f"{where}: each action must be an object with exactly one of: {_list(vocab.VERBS)}")
                continue
            name, arg = next(iter(verb.items()))
            if name in ("reveal", "label", "highlight", "spin", "cutaway"):
                refs = arg if isinstance(arg, list) else [arg]
                if not refs or not all(isinstance(r, str) for r in refs):
                    errs.append(f"{where}: {name} needs a part id or a list of part ids")
                else:
                    for r in refs:
                        known(r, f"{where} {name}")
            elif name == "flow":
                ok = isinstance(arg, dict) and isinstance(arg.get("from"), str) and isinstance(arg.get("to"), str)
                if not ok:
                    errs.append(f"{where}: flow needs {{\"from\": part, \"to\": part, \"medium\": one of {_list(vocab.MEDIA)}}}")
                else:
                    known(arg["from"], f"{where} flow from")
                    known(arg["to"], f"{where} flow to")
                    if arg.get("medium", "air") not in vocab.MEDIA:
                        errs.append(f"{where}: flow medium must be one of: {_list(vocab.MEDIA)}")
            elif name == "pulse":
                if isinstance(arg, str):
                    known(arg, f"{where} pulse")
                else:
                    errs.append(f"{where}: pulse needs the id of the part the waves come from")
            elif name == "explode":
                if arg != "all" and not (isinstance(arg, list) and all(isinstance(r, str) for r in arg)):
                    errs.append(f"{where}: explode needs \"all\" or a list of part ids")
                elif isinstance(arg, list):
                    for r in arg:
                        known(r, f"{where} explode")
            elif name == "zoom":
                if arg != "all":
                    known(arg, f"{where} zoom")
    for key in ("recap", "question"):
        if key in story and not isinstance(story[key], str):
            errs.append(f"{key} must be text")
    return errs
