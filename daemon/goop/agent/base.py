"""Provider interface. A provider turns an AgentRequest into a stream of events (see events.py)."""
from dataclasses import dataclass, field
from typing import Iterator, Optional


@dataclass
class AgentRequest:
    command: str                      # what the user typed
    packet: dict                      # context packet for the window (see packet.py)
    window_address: str
    system: str = ""
    prompt: str = ""
    session: Optional[str] = None     # resume token from an earlier "done" event
    cwd: Optional[str] = None         # where the agent runs; the project dir for project windows
    mcp_config: Optional[str] = None  # path to an MCP config exposing the goop tools
    model: Optional[str] = None
    read_paths: bool = False          # allow read-only file tools inside cwd


class Provider:
    name = ""
    # vision: can read screenshots. mcp: can use the goop tool server directly.
    capabilities = {"vision": False, "mcp": False}

    def available(self) -> bool:
        raise NotImplementedError

    def run(self, req: AgentRequest) -> Iterator[dict]:
        raise NotImplementedError
