"""Claude Code provider: runs `claude -p` headless and maps its stream-json output to goop events."""
import json, shutil, subprocess

from .. import access
from . import events
from .base import AgentRequest, Provider

TOOL_PREFIX = "mcp__goop__"
GOOP_TOOLS = [TOOL_PREFIX + t for t in ("screenshot", "window_info", "read_context", "read_file", "list_files", "type_in_terminal", "move_files", "undo_last_move")]
READ_TOOLS = ["Read", "Glob", "Grep"]
# Claude's own file and shell tools stay off: everything the goop does goes through the approval-gated goop tools.
DENIED = ["Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch", "Task"]


def parse_line(line, state):
    """One stream-json line -> goop events. `state` remembers whether the run already finished."""
    try:
        d = json.loads(line)
    except ValueError:
        return []
    t = d.get("type")
    if state.get("finished"):
        return []
    if t == "system" and d.get("subtype") == "init":
        return [events.thinking()]
    if t == "assistant":
        out = []
        for block in d.get("message", {}).get("content", []):
            kind = block.get("type")
            if kind == "text" and block.get("text", "").strip():
                out.append(events.text(block["text"].strip()))
            elif kind == "tool_use":
                name = block.get("name", "")
                # Claude's own tool-loading step is plumbing, not something to show in a bubble
                out.append(events.tool_use(name.removeprefix(TOOL_PREFIX)) if name.startswith(TOOL_PREFIX) else events.thinking())
            elif kind == "thinking":
                out.append(events.thinking())
        return out
    if t == "result":
        state["finished"] = True
        if d.get("is_error"):
            return [events.error(d.get("result") or d.get("terminal_reason") or "the agent failed")]
        return [events.done(d.get("result", ""), session=d.get("session_id"), cost=d.get("total_cost_usd"))]
    return []


class ClaudeProvider(Provider):
    name = "claude"
    capabilities = {"vision": True, "mcp": True}

    def available(self):
        return shutil.which("claude") is not None

    def command(self, req: AgentRequest):
        # the prompt goes over stdin, so window contents never appear in `ps`
        cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--append-system-prompt", req.system]
        if req.model:
            cmd += ["--model", req.model]
        if req.mcp_config:
            cmd += ["--mcp-config", req.mcp_config, "--strict-mcp-config"]
        offered = set(access.allowed([t.removeprefix(TOOL_PREFIX) for t in GOOP_TOOLS]))
        allowed = [t for t in GOOP_TOOLS if t.removeprefix(TOOL_PREFIX) in offered] + (READ_TOOLS if req.read_paths else [])
        withheld = [t for t in GOOP_TOOLS if t.removeprefix(TOOL_PREFIX) not in offered]     # Look only: also deny them by name
        # Outside a project Claude's own Read/Glob/Grep are removed entirely, so it uses goop's read_file instead of
        # trying a tool that would be refused.
        denied = DENIED + withheld + ([] if req.read_paths else READ_TOOLS)
        cmd += ["--allowedTools", *allowed, "--disallowedTools", *denied]
        if req.session:
            cmd += ["--resume", req.session]
        return cmd

    def run(self, req: AgentRequest):
        if not self.available():
            yield events.error("the claude CLI was not found on PATH")
            return
        try:
            proc = subprocess.Popen(self.command(req), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, cwd=req.cwd)
        except OSError as e:
            yield events.error(f"could not start claude: {e}")
            return
        proc.stdin.write(req.prompt)
        proc.stdin.close()
        state = {}
        for line in proc.stdout:
            yield from parse_line(line, state)
        proc.wait()
        if not state.get("finished"):
            err = (proc.stderr.read() or "").strip().splitlines()
            yield events.error(err[-1] if err else f"claude exited with code {proc.returncode}")
