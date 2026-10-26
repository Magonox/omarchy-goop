"""Turn a chat reply into something that sounds right read aloud."""
import re

_EMOJI = re.compile("[\U0001F000-\U0001FFFF☀-➿️]")
# ~/Downloads, /home/user/Downloads/x.pdf, ../a/b: spoken as the last part, not "slash home slash user slash ..."
_PATH = re.compile(r"(?:~|\.{1,2})?(?:/[^\s/`'\"),;:!?]+)+/?|~(?=\s|$)")


def _say_path(m):
    parts = [p for p in m.group(0).split("/") if p and p not in (".", "..")]
    if not parts or parts == ["~"]:
        return "home"
    return parts[-1].lstrip("~") or "home"


def prepare(text, max_chars=420):
    t = re.sub(r"```.*?```", " ", text, flags=re.S)            # code blocks are not read aloud
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"https?://\S+", "a link", t)
    t = _PATH.sub(_say_path, t)
    t = _EMOJI.sub("", t)
    t = re.sub(r"^\s*[-*+>#]+\s+", "", t, flags=re.M)           # bullets, quotes, headings
    t = re.sub(r"[*#>|]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return cut(t, max_chars)


def cut(t, max_chars):
    """Shorten at the last sentence end that fits (or a word boundary if there is none)."""
    if len(t) <= max_chars:
        return t
    head = t[:max_chars]
    ends = [m.end() for m in re.finditer(r"[.!?](?=\s|$)", head)]
    if ends and ends[-1] > max_chars * 0.4:
        return head[:ends[-1]].strip()
    return head.rsplit(" ", 1)[0].strip() + "."
