import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


def _env_flag(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _get_env_path() -> str:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(app_dir)
    return os.path.join(project_root, ".env")


def _load_mcp_servers_from_env() -> List[dict]:
    raw = (os.getenv("MCP_SERVERS") or "").strip()
    if not raw:
        try:
            from dotenv import dotenv_values

            env_path = _get_env_path()
            if os.path.exists(env_path):
                env = dotenv_values(env_path)
                raw = (env.get("MCP_SERVERS") or "").strip()
        except Exception:
            raw = ""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if isinstance(item, dict):
            out.append(item)
    return out


def _normalize_server(server: dict) -> dict:
    sid = str(server.get("id") or server.get("name") or "").strip()
    name = str(server.get("name") or sid or "").strip()
    command = server.get("command")
    args = server.get("args")
    env = server.get("env")
    enabled = server.get("enabled")
    transport = str(server.get("transport") or "stdio").strip().lower()
    if transport not in {"stdio"}:
        transport = "stdio"
    if isinstance(args, str):
        args = [s for s in args.split(" ") if s]
    if not isinstance(args, list):
        args = []
    args = [str(x) for x in args if str(x).strip()]
    if not isinstance(env, dict):
        env = {}
    env = {str(k): str(v) for k, v in env.items() if str(k).strip()}
    enabled_flag = True
    if isinstance(enabled, bool):
        enabled_flag = enabled
    elif enabled is not None:
        enabled_flag = str(enabled).strip().lower() in {"1", "true", "yes", "on"}
    return {
        "id": sid,
        "name": name or sid,
        "transport": transport,
        "command": str(command or "").strip(),
        "args": args,
        "env": env,
        "enabled": enabled_flag,
    }


@dataclass
class MCPToolDef:
    name: str
    description: str
    input_schema: dict


class _MCPArguments(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPRemoteTool(BaseTool):
    server_id: str
    remote_tool_name: str
    _manager: "MCPManager"

    args_schema: type[BaseModel] = _MCPArguments

    def _run(self, arguments: Dict[str, Any]) -> str:
        result = self._manager.call_tool(self.server_id, self.remote_tool_name, arguments or {})
        if isinstance(result, dict):
            if result.get("isError") is True:
                raise RuntimeError(str(result.get("content") or result))
            content = result.get("content")
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        t = str(item.get("text") or "")
                        if t:
                            texts.append(t)
                    else:
                        texts.append(json.dumps(item, ensure_ascii=False))
                joined = "\n".join([t for t in texts if t]).strip()
                if joined:
                    return joined
        return json.dumps(result, ensure_ascii=False)


class MCPClient:
    def __init__(
        self,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        init_timeout_s: float = 10.0,
    ):
        self._command = command
        self._env = env or {}
        self._cwd = cwd
        self._init_timeout_s = init_timeout_s

        self._proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._next_id = 1
        self._pending: Dict[int, Tuple[threading.Event, Dict[str, Any]]] = {}
        self._rx_buffer = bytearray()
        self._initialized = False
        self._last_error: Optional[str] = None

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc is not None else None

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def _write_message(self, payload: dict):
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("MCP process not started")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        self._proc.stdin.write(header + data)
        self._proc.stdin.flush()

    def _read_one_message(self) -> Optional[bytes]:
        buf = self._rx_buffer
        marker = b"\r\n\r\n"
        header_end = buf.find(marker)
        if header_end == -1:
            return None
        header_bytes = bytes(buf[:header_end]).decode("ascii", errors="replace")
        content_length = None
        for line in header_bytes.split("\r\n"):
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            if k.strip().lower() == "content-length":
                try:
                    content_length = int(v.strip())
                except Exception:
                    content_length = None
        if content_length is None:
            del buf[: header_end + len(marker)]
            return None
        total_len = header_end + len(marker) + content_length
        if len(buf) < total_len:
            return None
        body = bytes(buf[header_end + len(marker) : total_len])
        del buf[:total_len]
        return body

    def _reader_loop(self):
        try:
            assert self._proc is not None
            assert self._proc.stdout is not None
            while True:
                chunk = self._proc.stdout.read(4096)
                if not chunk:
                    break
                with self._lock:
                    self._rx_buffer.extend(chunk)
                    while True:
                        body = self._read_one_message()
                        if body is None:
                            break
                        try:
                            msg = json.loads(body.decode("utf-8", errors="replace"))
                        except Exception:
                            continue
                        if not isinstance(msg, dict):
                            continue
                        msg_id = msg.get("id")
                        if isinstance(msg_id, int) and msg_id in self._pending:
                            ev, slot = self._pending[msg_id]
                            slot["msg"] = msg
                            ev.set()
        except Exception as e:
            self._last_error = str(e)
        finally:
            with self._lock:
                for ev, _slot in self._pending.values():
                    ev.set()

    def start(self):
        if self._proc is not None:
            return
        if not self._command:
            raise RuntimeError("Missing MCP command")
        env = os.environ.copy()
        env.update(self._env)
        self._proc = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self._cwd,
            env=env,
        )
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def stop(self):
        proc = self._proc
        self._proc = None
        self._initialized = False
        if proc is None:
            return
        try:
            proc.terminate()
        except Exception:
            return

    def request(self, method: str, params: Optional[dict] = None, timeout_s: float = 10.0) -> dict:
        self.start()
        with self._lock:
            req_id = self._next_id
            self._next_id += 1
            ev = threading.Event()
            slot: Dict[str, Any] = {}
            self._pending[req_id] = (ev, slot)
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._write_message(payload)
        ok = ev.wait(timeout_s)
        with self._lock:
            _ev, slot = self._pending.pop(req_id, (None, {}))
        if not ok:
            raise TimeoutError(f"MCP request timeout: {method}")
        msg = slot.get("msg")
        if not isinstance(msg, dict):
            raise RuntimeError(f"MCP invalid response: {method}")
        if "error" in msg and isinstance(msg["error"], dict):
            raise RuntimeError(str(msg["error"].get("message") or msg["error"]))
        return msg.get("result") if isinstance(msg.get("result"), dict) else {"result": msg.get("result")}

    def notify(self, method: str, params: Optional[dict] = None):
        self.start()
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._write_message(payload)

    def ensure_initialized(self):
        if self._initialized:
            return
        result = self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "localevobot", "version": "0.1"},
            },
            timeout_s=self._init_timeout_s,
        )
        if not isinstance(result, dict):
            raise RuntimeError("MCP initialize failed")
        self.notify("notifications/initialized", {})
        self._initialized = True

    def list_tools(self) -> List[MCPToolDef]:
        self.ensure_initialized()
        result = self.request("tools/list", {}, timeout_s=self._init_timeout_s)
        tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list):
            return []
        out: List[MCPToolDef] = []
        for t in tools:
            if not isinstance(t, dict):
                continue
            name = str(t.get("name") or "").strip()
            if not name:
                continue
            out.append(
                MCPToolDef(
                    name=name,
                    description=str(t.get("description") or "").strip(),
                    input_schema=t.get("inputSchema") if isinstance(t.get("inputSchema"), dict) else {},
                )
            )
        return out

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> dict:
        self.ensure_initialized()
        result = self.request(
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
            timeout_s=float(os.getenv("MCP_CALL_TIMEOUT_S") or 30),
        )
        return result if isinstance(result, dict) else {"result": result}


class MCPManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._clients: Dict[str, MCPClient] = {}
        self._tool_cache: Dict[str, Tuple[float, List[MCPToolDef]]] = {}

    def list_servers(self) -> List[dict]:
        servers = [_normalize_server(s) for s in _load_mcp_servers_from_env()]
        return [s for s in servers if s.get("id") and s.get("command")]

    def _get_client(self, server_id: str) -> MCPClient:
        servers = {s["id"]: s for s in self.list_servers()}
        cfg = servers.get(server_id)
        if not cfg:
            raise KeyError("unknown_server")
        cmd = [cfg["command"], *cfg.get("args", [])]
        init_timeout = float(os.getenv("MCP_INIT_TIMEOUT_S") or 10)
        with self._lock:
            client = self._clients.get(server_id)
            if client is None:
                client = MCPClient(cmd, env=cfg.get("env") or {}, init_timeout_s=init_timeout)
                self._clients[server_id] = client
        return client

    def test(self, server_id: str) -> dict:
        client = self._get_client(server_id)
        tools = client.list_tools()
        return {
            "ok": True,
            "serverId": server_id,
            "pid": client.pid,
            "toolCount": len(tools),
        }

    def list_tools(self, server_id: str, refresh: bool = False) -> List[MCPToolDef]:
        ttl = float(os.getenv("MCP_TOOLS_CACHE_TTL_S") or 30)
        now = time.time()
        if not refresh:
            cached = self._tool_cache.get(server_id)
            if cached and now - cached[0] <= ttl:
                return cached[1]
        client = self._get_client(server_id)
        tools = client.list_tools()
        self._tool_cache[server_id] = (now, tools)
        return tools

    def call_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> dict:
        client = self._get_client(server_id)
        return client.call_tool(tool_name, arguments)

    def status(self) -> List[dict]:
        servers = self.list_servers()
        out = []
        with self._lock:
            for s in servers:
                sid = s["id"]
                c = self._clients.get(sid)
                out.append(
                    {
                        "id": sid,
                        "name": s.get("name") or sid,
                        "enabled": bool(s.get("enabled")),
                        "pid": c.pid if c else None,
                        "initialized": bool(c.initialized) if c else False,
                        "lastError": c.last_error if c else None,
                    }
                )
        return out


_manager_singleton: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    global _manager_singleton
    if _manager_singleton is None:
        _manager_singleton = MCPManager()
    return _manager_singleton


def load_mcp_tools() -> List[BaseTool]:
    if _env_flag("MCP_ENABLED", True) is False:
        return []
    manager = get_mcp_manager()
    servers = [s for s in manager.list_servers() if s.get("enabled")]
    tools: List[BaseTool] = []
    for s in servers:
        sid = s["id"]
        try:
            remote_tools = manager.list_tools(sid, refresh=False)
        except Exception:
            remote_tools = []
        for t in remote_tools:
            tool = MCPRemoteTool()
            tool.server_id = sid
            tool.remote_tool_name = t.name
            tool._manager = manager
            tool.name = f"mcp_{sid}__{t.name}".replace("/", "__").replace(" ", "_")
            tool.description = (t.description or "").strip() or f"MCP tool {t.name} from {sid}"
            tools.append(tool)
    return tools

