#!/usr/bin/env python3
"""Ask the agent about a window. Streams goop events as JSON lines on stdout.

  agent.py --address 0x... --stdin [--session ID] [--provider claude]      (the shell: the question arrives as one JSON line)
  agent.py --address 0x... --command "what is this?" [--session ID]        (by hand in a terminal)

The shell must use --stdin: command-line arguments are readable by every local account (/proc/<pid>/cmdline), and the
question can be private. The stdin line is {"command": "..."}.

Context is built fresh from the window at ask time. A window on the privacy deny list is never sent anywhere.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import access, config, hypr, packet  # noqa: E402
from goop.agent import events, prompt, registry  # noqa: E402
from goop.agent.base import AgentRequest  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.expanduser("~/.cache/goop/run")
LAST = os.path.expanduser("~/.cache/goop/last_response.md")


def emit(ev):
    print(json.dumps(ev), flush=True)


def read_command(args, stdin):
    """The user's question, from --command or from one JSON line on stdin. Raises ValueError with a readable message."""
    if args.command is not None:
        return args.command
    line = stdin.readline()
    try:
        command = json.loads(line)["command"]
    except (ValueError, KeyError, TypeError):
        raise ValueError("the question did not arrive on stdin") from None
    if not isinstance(command, str) or not command.strip():
        raise ValueError("the question was empty")
    return command


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--command", help="the question (visible to other local users in the process list; prefer --stdin)")
    src.add_argument("--stdin", action="store_true", help='read the question as one JSON line: {"command": "..."}')
    ap.add_argument("--session")
    ap.add_argument("--provider")
    a = ap.parse_args()

    if not config.is_enabled():
        return emit(events.error("goop is turned off"))
    try:
        command = read_command(a, sys.stdin)
    except ValueError as e:
        return emit(events.error(str(e)))

    clients, _ = hypr.snapshot()
    window = next((c for c in clients if c["address"] == a.address and c["mapped"]), None)
    if not window:
        return emit(events.error("that window no longer exists"))
    if config.is_denied(window):
        return emit(events.error("this window is on the privacy deny list, so I did not look at it"))

    cfg = config.load()
    try:
        provider = registry.get(a.provider)
    except ValueError as e:
        return emit(events.error(str(e)))

    pkt = packet.build(window, shots=False)
    proj = (pkt.get("context") or {}).get("project") or {}
    project_cwd = proj.get("cwd") if proj.get("is_project") else None
    os.makedirs(RUN_DIR, exist_ok=True)

    mcp = os.path.join(RUN_DIR, f"mcp-{a.address}.json")
    with open(mcp, "w") as f:
        json.dump({"mcpServers": {"goop": {"command": sys.executable, "args": [os.path.join(HERE, "mcp_server.py")],
                                           "env": {"GOOP_WINDOW": a.address}}}}, f)

    req = AgentRequest(
        command=command, packet=pkt, window_address=a.address,
        system=prompt.system_for(access.level(cfg), lessons=access.explainers(cfg) != "never"), prompt=prompt.user_prompt(pkt, command),
        session=a.session, cwd=project_cwd or RUN_DIR, mcp_config=mcp,
        model=cfg.get("model"), read_paths=bool(project_cwd),
    )
    emit(events.start(provider.name, pkt["app_type"]))
    for ev in provider.run(req):
        emit(ev)
        if ev["type"] == "done":
            os.makedirs(os.path.dirname(LAST), exist_ok=True)
            with open(LAST, "w") as f:
                f.write(ev["text"] + "\n")


if __name__ == "__main__":
    main()
