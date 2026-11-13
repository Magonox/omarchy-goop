"""OpenAI-compatible provider: any server that speaks /chat/completions with function calling (OpenAI, xAI Grok, Gemini's
compatible endpoint, Ollama, LM Studio, OpenRouter, Groq, Together...). Standard library only.

Tools run in this process through goop.tools, so the approval cards and every safety limit are exactly the ones the Claude
provider uses. The API is stateless, so each goop's conversation is kept in a small history file (the "session")."""
import base64, json, mimetypes, os, re, socket, time, urllib.error, urllib.request, uuid

from .. import access, private, tools
from . import events
from .base import AgentRequest, Provider

SESSION_DIR = os.path.expanduser("~/.cache/goop/sessions")
MAX_STEPS = 8                 # model/tool round trips per question
HISTORY_MESSAGES = 24         # how much of an earlier conversation is sent back
SESSION_DAYS = 7
MAX_IMAGE_BYTES = 5_000_000
_SESSION_ID = re.compile(r"^[0-9a-f]{32}$")


class ProviderError(Exception):
    pass


def tool_definitions():
    offered = access.allowed(list(tools.TOOLS))
    return [{"type": "function", "function": {"name": n, "description": d, "parameters": schema}}
            for n, (_, d, schema) in tools.TOOLS.items() if n in offered]


# ---- sessions: the conversation so far, so "yes, keep going" has context ----

def load_session(sid):
    if not sid or not _SESSION_ID.match(sid):
        return []
    try:
        with open(os.path.join(SESSION_DIR, sid + ".json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def trim(messages):
    """Keep the most recent messages, starting at a user turn (a tool message without its assistant call is invalid)."""
    msgs = messages[-HISTORY_MESSAGES:]
    for i, m in enumerate(msgs):
        if m.get("role") == "user":
            return msgs[i:]
    return []


def save_session(sid, messages):
    sid = sid if sid and _SESSION_ID.match(sid) else uuid.uuid4().hex
    private.makedirs(SESSION_DIR)
    tmp = os.path.join(SESSION_DIR, sid + ".tmp")
    with private.open_file(tmp) as f:
        json.dump(trim(messages), f)
    os.replace(tmp, os.path.join(SESSION_DIR, sid + ".json"))
    cutoff = time.time() - SESSION_DAYS * 86400
    for n in os.listdir(SESSION_DIR):
        p = os.path.join(SESSION_DIR, n)
        try:
            if os.path.getmtime(p) < cutoff:
                os.remove(p)
        except OSError:
            pass
    return sid


class OpenAICompatProvider(Provider):
    capabilities = {"vision": False, "mcp": False}

    def __init__(self, name, cfg):
        self.name = name
        self.base_url = (cfg.get("base_url") or "").rstrip("/")
        self.model = cfg.get("model") or ""
        self.key_env, self.key_file = cfg.get("api_key_env"), cfg.get("api_key_file")
        self.vision = bool(cfg.get("vision", False))
        self.timeout = float(cfg.get("timeout", 120))
        self.capabilities = {"vision": self.vision, "mcp": False}

    # a key is required only if one is configured; a local server (Ollama...) needs none
    def api_key(self):
        if self.key_env:
            return os.environ.get(self.key_env) or None
        if self.key_file:
            try:
                with open(os.path.expanduser(self.key_file)) as f:
                    return f.read().strip() or None
            except OSError:
                return None
        return None

    def problem(self):
        if not self.base_url or not self.model:
            return f"provider {self.name!r} needs base_url and model in the goop config"
        if (self.key_env or self.key_file) and not self.api_key():
            where = f"the {self.key_env} environment variable" if self.key_env else self.key_file
            return f"no API key for {self.name!r}: set {where} (the shell must be restarted to see new environment variables)"
        return None

    def available(self):
        return self.problem() is None

    # ---- HTTP ----
    def _post(self, messages):
        body = {"model": self.model, "messages": messages, "tools": tool_definitions(), "tool_choice": "auto"}
        headers = {"Content-Type": "application/json"}
        if self.api_key():
            headers["Authorization"] = "Bearer " + self.api_key()
        req = urllib.request.Request(self.base_url + "/chat/completions", data=json.dumps(body).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise ProviderError(self._http_message(e))
        except urllib.error.URLError as e:
            raise ProviderError(f"cannot reach {self.base_url}: {e.reason}")
        except (socket.timeout, TimeoutError):
            raise ProviderError("the model took too long to answer")
        except ValueError:
            raise ProviderError("the server sent something that is not JSON")

    @staticmethod
    def _http_message(e):
        try:
            detail = json.load(e).get("error", {})
            detail = detail.get("message") if isinstance(detail, dict) else str(detail)
        except (ValueError, AttributeError):
            detail = ""
        base = {401: "the API key was rejected (HTTP 401)", 403: "access denied (HTTP 403)", 404: "model or endpoint not found (HTTP 404)",
                429: "rate limited or out of quota (HTTP 429)"}.get(e.code, f"the server returned HTTP {e.code}")
        return f"{base}: {detail[:200]}" if detail else base

    # ---- tools ----
    def _run_tool(self, req, name, args):
        """-> (text for the model, image path or None). Refusals go back to the model as text, like the MCP path."""
        try:
            r = tools.call(name, req.window_address, args)
        except tools.ToolError as e:
            return f"Error: {e}", None
        if "image" in r:
            if not self.vision:
                return "Error: this model cannot look at images, so no screenshot is available. Use read_context instead.", None
            if os.path.getsize(r["image"]) > MAX_IMAGE_BYTES:
                return "Error: that image is too large to send.", None
            return "The image is attached in the next message.", r["image"]
        return r["text"], None

    @staticmethod
    def _image_message(path):
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        mime = mimetypes.guess_type(path)[0] or "image/png"
        return {"role": "user", "content": [{"type": "text", "text": "Here is the image you asked for."},
                                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}]}

    # ---- the loop ----
    def run(self, req: AgentRequest):
        problem = self.problem()
        if problem:
            yield events.error(problem)
            return
        user = {"role": "user", "content": req.prompt}
        messages = [{"role": "system", "content": req.system}] + load_session(req.session) + [user]
        new = [user]                       # what gets remembered (images are not: they are large and rarely needed again)
        yield events.thinking()
        for _ in range(MAX_STEPS):
            try:
                resp = self._post(messages)
                msg = resp["choices"][0]["message"]
            except ProviderError as e:
                yield events.error(str(e))
                return
            except (KeyError, IndexError, TypeError):
                yield events.error("the server's reply was not in the expected format")
                return
            content, calls = (msg.get("content") or "").strip(), msg.get("tool_calls") or []
            assistant = {"role": "assistant", "content": content or None}
            if calls:
                assistant["tool_calls"] = calls
            messages.append(assistant)
            new.append(assistant)
            if not calls:
                sid = save_session(req.session, load_session(req.session) + new)
                yield events.done(content, session=sid)
                return
            if content:
                yield events.text(content)
            for call in calls:
                fn = call.get("function") or {}
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                    args = args if isinstance(args, dict) else {}
                except ValueError:
                    args = {}
                yield events.tool_use(name)
                text, image = self._run_tool(req, name, args)
                tool_msg = {"role": "tool", "tool_call_id": call.get("id", ""), "content": text}
                messages.append(tool_msg)
                new.append(tool_msg)
                if image:
                    messages.append(self._image_message(image))
            yield events.thinking()
        yield events.error("I used too many steps without finishing; try asking in a smaller piece")
