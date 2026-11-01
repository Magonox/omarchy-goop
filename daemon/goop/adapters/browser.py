"""Browser windows. The page text comes from the Goop page reader extension (browser/pagereader/) through its native host's private socket, only when asked.
Everything here fails quietly into {"ok": False, "error": ...}: no extension, no browser, a page that cannot be read."""
import json, os, re, socket

SOCK = os.path.expanduser("~/.cache/goop/page.sock")
NOT_AVAILABLE = ("the page reader is not available (it needs the Goop extension installed in Chromium and the browser restarted: run bin/goop-install-pagereader); "
                 "take a screenshot instead")
TITLE_SUFFIX = re.compile(r" - (Chromium|Google Chrome|Brave|Microsoft Edge|Vivaldi)$")


def request(msg, timeout=4.0, sock=None):
    """Send one request to the page reader host; always returns a dict."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(sock or SOCK)
        s.sendall((json.dumps(msg) + "\n").encode())
        data = b""
        while b"\n" not in data:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
        return json.loads(data.split(b"\n")[0])
    except (FileNotFoundError, ConnectionRefusedError):
        return {"ok": False, "error": NOT_AVAILABLE}
    except socket.timeout:
        return {"ok": False, "error": "the browser did not answer in time"}
    except (OSError, ValueError) as e:
        return {"ok": False, "error": f"page reader error: {e}"}
    finally:
        s.close()


def available(sock=None):
    return bool(request({"cmd": "ping"}, timeout=1.0, sock=sock).get("ok"))


def read(window_title="", max_chars=12000, timeout=4.0, sock=None):
    return request({"cmd": "read", "title": TITLE_SUFFIX.sub("", window_title or ""), "max_chars": max_chars}, timeout, sock)


def render(r):
    """The page as text for the agent: where it is, what it is about, the selection, then the readable text."""
    lines = [f"PAGE: {r.get('title') or r.get('tab_title') or '(untitled)'}", f"URL: {r.get('url', '')}"]
    if r.get("description"):
        lines.append(f"DESCRIPTION: {r['description']}")
    if r.get("selection"):
        lines.append(f"THE USER HAS SELECTED THIS TEXT: {r['selection']}")
    if r.get("headings"):
        lines.append("HEADINGS: " + " | ".join(r["headings"]))
    lines += ["", r.get("text", "")]
    if r.get("truncated"):
        lines.append(f"\n[cut after {len(r.get('text', ''))} of {r.get('chars')} characters; ask for more with max_chars]")
    return "\n".join(lines)


def collect(window, sock=None):
    """(context, confidence) for the packet: the page text if the reader is there, else the old screenshot-only note."""
    r = read(window.get("title") or "", 6000, timeout=1.5, sock=sock)
    if not r.get("ok"):
        return {"notes": ["no page text (" + r.get("error", "reader unavailable") + "); screenshot only"]}, "low"
    return {"page": {"title": r.get("title"), "url": r.get("url"), "text": r.get("text", ""), "selection": r.get("selection", ""),
                     "headings": r.get("headings", []), "truncated": r.get("truncated", False)}}, "high"
