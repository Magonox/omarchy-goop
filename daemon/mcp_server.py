#!/usr/bin/env python3
"""Minimal MCP server (stdio, newline-delimited JSON-RPC) exposing goop's tools for ONE window.

The window is fixed by the GOOP_WINDOW env var, so an agent can only ever look at the window it was dropped on.
"""
import base64, json, mimetypes, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import tools  # noqa: E402

ADDRESS = os.environ.get("GOOP_WINDOW", "")


def reply(id_, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": id_}
    msg.update({"error": error} if error else {"result": result})
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def handle(msg):
    method, id_, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if id_ is None:  # notification (e.g. notifications/initialized): no reply
        return
    if method == "initialize":
        reply(id_, {"protocolVersion": params.get("protocolVersion", "2024-11-05"),
                    "capabilities": {"tools": {}}, "serverInfo": {"name": "goop", "version": "0.1"}})
    elif method == "ping":
        reply(id_, {})
    elif method == "tools/list":
        reply(id_, {"tools": [
            {"name": n, "description": d, "inputSchema": schema}
            for n, (_, d, schema) in tools.TOOLS.items()]})
    elif method == "tools/call":
        try:
            r = tools.call(params.get("name", ""), ADDRESS, params.get("arguments"))
            if "image" in r:
                with open(r["image"], "rb") as f:
                    content = [{"type": "image", "data": base64.b64encode(f.read()).decode(), "mimeType": mimetypes.guess_type(r["image"])[0] or "image/png"}]
            else:
                content = [{"type": "text", "text": r["text"]}]
            reply(id_, {"content": content})
        except tools.ToolError as e:
            reply(id_, {"content": [{"type": "text", "text": str(e)}], "isError": True})
    else:
        reply(id_, error={"code": -32601, "message": f"method not found: {method}"})


for line in sys.stdin:
    line = line.strip()
    if line:
        try:
            handle(json.loads(line))
        except ValueError:
            pass
