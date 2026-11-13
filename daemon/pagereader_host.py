#!/usr/bin/env python3
"""The native-messaging host of the Goop page reader. Chromium starts it when the extension connects, and it stays up for as long as the browser does.
It stands between two things that cannot talk to each other directly: the extension (over Chromium's native-messaging pipe on stdin/stdout) and Goop (over a private
Unix socket, ~/.cache/goop/page.sock, readable only by this user). Goop sends one JSON line {"cmd": "read", "title": ..., "max_chars": ...}; the host forwards it to the
extension, waits for the page text, and answers with one JSON line. Nothing is stored and nothing leaves this computer."""
import json, os, socket, struct, sys, threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import private  # noqa: E402

SOCK = os.path.expanduser("~/.cache/goop/page.sock")
TIMEOUT = 5.0

out_lock = threading.Lock()
pending, pending_lock = {}, threading.Lock()
counter = [0]


def send_to_extension(msg):
    data = json.dumps(msg).encode()
    with out_lock:
        sys.stdout.buffer.write(struct.pack("=I", len(data)) + data)
        sys.stdout.buffer.flush()


def read_from_extension():
    head = sys.stdin.buffer.read(4)
    if len(head) < 4:
        return None
    n = struct.unpack("=I", head)[0]
    return json.loads(sys.stdin.buffer.read(n))


def ask_extension(req):
    """Forward one request and wait for its answer; always returns a dict."""
    with pending_lock:
        counter[0] += 1
        rid = counter[0]
        slot = pending[rid] = {"event": threading.Event(), "reply": None}
    send_to_extension({**req, "id": rid})
    slot["event"].wait(TIMEOUT)
    with pending_lock:
        pending.pop(rid, None)
    return slot["reply"] or {"ok": False, "error": "the browser did not answer in time"}


def serve_client(conn):
    try:
        conn.settimeout(3)
        data = b""
        while b"\n" not in data and len(data) < 65536:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
        req = json.loads(data.split(b"\n")[0] or b"{}")
        if req.get("cmd") not in ("ping", "read"):
            reply = {"ok": False, "error": "unknown command"}
        else:
            reply = ask_extension({k: req.get(k) for k in ("cmd", "title", "max_chars") if k in req})
        conn.sendall((json.dumps(reply) + "\n").encode())
    except Exception as e:
        try:
            conn.sendall((json.dumps({"ok": False, "error": f"page reader error: {e}"}) + "\n").encode())
        except OSError:
            pass
    finally:
        conn.close()


def listen():
    private.makedirs(os.path.dirname(SOCK))
    try:
        os.unlink(SOCK)                      # a stale socket from an earlier browser session
    except FileNotFoundError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old = os.umask(0o177)                    # created readable and writable by this user only
    try:
        srv.bind(SOCK)
    finally:
        os.umask(old)
    srv.listen(4)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=serve_client, args=(conn,), daemon=True).start()


def main():
    threading.Thread(target=listen, daemon=True).start()
    while True:
        msg = read_from_extension()
        if msg is None:                      # the browser closed the pipe: we are done
            break
        with pending_lock:
            slot = pending.get(msg.get("id"))
        if slot:
            slot["reply"] = {k: v for k, v in msg.items() if k != "id"}
            slot["event"].set()
    try:
        os.unlink(SOCK)
    except OSError:
        pass


if __name__ == "__main__":
    main()
