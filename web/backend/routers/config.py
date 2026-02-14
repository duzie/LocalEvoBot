from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from dotenv import dotenv_values, set_key
import os
import socket
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from app.integrations import heartbeat
from app.integrations.mcp_client import get_mcp_manager
from ..shared import shared

router = APIRouter()

class ConfigUpdate(BaseModel):
    key: str
    value: str

class AccessUrlUpdate(BaseModel):
    url: str

class HeartbeatUpdate(BaseModel):
    name: str
    interval: Optional[float] = None
    paused: Optional[bool] = None

class TemplateUpdate(BaseModel):
    template: Dict[str, Any]
    tags: Optional[List[str]] = None

class ExperienceUpdate(BaseModel):
    content: Optional[str] = None
    system: Optional[str] = None
    tags: Optional[Any] = None
    scope: Optional[str] = None
    project_id: Optional[str] = None
    user_id: Optional[str] = None
    memory_type: Optional[str] = None
    url: Optional[str] = None

class McpServerUpsert(BaseModel):
    id: str
    name: Optional[str] = None
    command: str
    args: Optional[Any] = None
    env: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = True

def _read_mcp_servers_raw() -> List[dict]:
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    raw = (os.getenv("MCP_SERVERS") or env.get("MCP_SERVERS") or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]

def _write_mcp_servers_raw(servers: List[dict]):
    env_path = _get_env_path()
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("")
    payload = json.dumps(servers, ensure_ascii=False)
    try:
        set_key(env_path, "MCP_SERVERS", payload)
        os.environ["MCP_SERVERS"] = payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _get_template_store():
    try:
        from app.skills.system_skill.scripts.experience_tools import _init_components
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"无法加载模板存储: {e}")
    store = _init_components()
    if not store:
        raise HTTPException(status_code=500, detail="模板存储不可用")
    return store

def _normalize_tags(tags):
    if tags is None:
        return []
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(",") if t.strip()]
    if isinstance(tags, list):
        cleaned = []
        for t in tags:
            s = str(t).strip()
            if s:
                cleaned.append(s)
        return cleaned
    return []

def _build_page_content(metadata, content):
    return (
        f"System: {metadata.get('system', '')}\n"
        f"Content: {content}\n"
        f"Tags: {metadata.get('tags', '')}\n"
        f"Scope: {metadata.get('scope', '')}\n"
        f"Project: {metadata.get('project_id', '')}\n"
        f"User: {metadata.get('user_id', '')}\n"
        f"Type: {metadata.get('memory_type', '')}"
    )

def _get_experience_items(query: Optional[str], system_name: Optional[str], tags: Optional[str], scope: Optional[str], project_id: Optional[str], user_id: Optional[str], memory_type: Optional[str], limit: int, offset: int):
    try:
        from app.skills.system_skill.scripts.experience_tools import list_operation_experiences
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"无法加载经验库: {e}")
    tag_list = _normalize_tags(tags)
    items = list_operation_experiences(
        query=query,
        system_filter=system_name,
        scope=scope,
        project_id=project_id,
        user_id=user_id,
        memory_type=memory_type,
        tags=tag_list,
        limit=limit,
        offset=offset,
    )
    return items

def _get_env_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(base_dir, ".env")

def _wa_gateway_config():
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    host = (os.getenv("WA_GATEWAY_HOST") or env.get("WA_GATEWAY_HOST") or "127.0.0.1").strip()
    port_raw = (os.getenv("WA_GATEWAY_PORT") or env.get("WA_GATEWAY_PORT") or "8787").strip()
    try:
        port = int(port_raw)
    except Exception:
        port = 8787
    token = (os.getenv("WA_GATEWAY_TOKEN") or env.get("WA_GATEWAY_TOKEN") or "").strip()
    base = f"http://{host}:{port}"
    return base, token

def _wa_gateway_request_json(path: str, method: str = "GET", body: Optional[dict] = None, require_auth: bool = False):
    base, token = _wa_gateway_config()
    url = base + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if require_auth:
        if not token:
            raise HTTPException(status_code=400, detail="WA_GATEWAY_TOKEN 未配置")
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        raise HTTPException(status_code=int(getattr(e, "code", 502) or 502), detail=raw or str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"无法连接 WA Gateway: {e}")

@router.get("")
async def get_config():
    """Get all environment variables from .env file"""
    env_path = _get_env_path()
    if not os.path.exists(env_path):
        return {}
    return dotenv_values(env_path)

@router.post("")
async def update_config(config: ConfigUpdate):
    """Update a specific environment variable"""
    env_path = _get_env_path()

    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                f.write("")
        
        set_key(env_path, config.key, config.value)
        os.environ[config.key] = config.value
        return {"status": "success", "key": config.key, "value": config.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/access-url")
async def get_access_url():
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    url = (os.getenv("PUBLIC_URL") or env.get("PUBLIC_URL") or "").strip()
    return {"url": url}

@router.post("/access-url")
async def set_access_url(payload: AccessUrlUpdate):
    env_path = _get_env_path()
    try:
        if not os.path.exists(env_path):
            with open(env_path, "w", encoding="utf-8") as f:
                f.write("")
        url = (payload.url or "").strip()
        set_key(env_path, "PUBLIC_URL", url)
        os.environ["PUBLIC_URL"] = url
        return {"status": "success", "url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hosts")
async def get_hosts():
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    port = int(os.getenv("WEB_PORT") or env.get("WEB_PORT") or 5010)

    candidates = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                candidates.append(ip)
        finally:
            s.close()
    except Exception:
        pass

    try:
        host_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        for ip in host_ips:
            if ip and not ip.startswith("127.") and ip not in candidates:
                candidates.append(ip)
    except Exception:
        pass

    urls = [f"http://{ip}:{port}/" for ip in candidates]
    return {"port": port, "ips": candidates, "urls": urls}

@router.get("/whatsapp/status")
async def whatsapp_status():
    return _wa_gateway_request_json("/health", method="GET", require_auth=False)

@router.get("/whatsapp/qr")
async def whatsapp_qr():
    return _wa_gateway_request_json("/qr", method="GET", require_auth=True)

@router.get("/whatsapp/qr-ascii")
async def whatsapp_qr_ascii():
    return _wa_gateway_request_json("/qr-ascii", method="GET", require_auth=True)

@router.post("/whatsapp/reset")
async def whatsapp_reset():
    return _wa_gateway_request_json("/reset", method="POST", body={}, require_auth=True)

@router.get("/mcp/servers")
async def mcp_list_servers():
    manager = get_mcp_manager()
    return {"servers": manager.list_servers(), "status": manager.status()}

@router.post("/mcp/servers")
async def mcp_upsert_server(payload: McpServerUpsert):
    sid = (payload.id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="缺少 id")
    command = (payload.command or "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="缺少 command")
    args: List[str] = []
    if isinstance(payload.args, list):
        args = [str(x) for x in payload.args if str(x).strip()]
    elif isinstance(payload.args, str) and payload.args.strip():
        args = [s for s in payload.args.strip().split(" ") if s]
    env = payload.env if isinstance(payload.env, dict) else {}
    env = {str(k): str(v) for k, v in env.items() if str(k).strip()}
    servers = _read_mcp_servers_raw()
    replaced = False
    for s in servers:
        if str(s.get("id") or "").strip() == sid:
            s.update(
                {
                    "id": sid,
                    "name": (payload.name or sid).strip(),
                    "transport": "stdio",
                    "command": command,
                    "args": args,
                    "env": env,
                    "enabled": bool(payload.enabled) if payload.enabled is not None else True,
                }
            )
            replaced = True
            break
    if not replaced:
        servers.append(
            {
                "id": sid,
                "name": (payload.name or sid).strip(),
                "transport": "stdio",
                "command": command,
                "args": args,
                "env": env,
                "enabled": bool(payload.enabled) if payload.enabled is not None else True,
            }
        )
    _write_mcp_servers_raw(servers)
    return {"ok": True, "id": sid}

@router.delete("/mcp/servers/{server_id}")
async def mcp_delete_server(server_id: str):
    sid = (server_id or "").strip()
    servers = _read_mcp_servers_raw()
    kept = [s for s in servers if str(s.get("id") or "").strip() != sid]
    if len(kept) == len(servers):
        raise HTTPException(status_code=404, detail="server 不存在")
    _write_mcp_servers_raw(kept)
    return {"ok": True, "id": sid}

@router.post("/mcp/servers/{server_id}/test")
async def mcp_test_server(server_id: str):
    manager = get_mcp_manager()
    try:
        return manager.test(server_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="server 不存在")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.get("/mcp/servers/{server_id}/tools")
async def mcp_list_tools(server_id: str, refresh: bool = False):
    manager = get_mcp_manager()
    try:
        tools = manager.list_tools(server_id, refresh=bool(refresh))
    except KeyError:
        raise HTTPException(status_code=404, detail="server 不存在")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "ok": True,
        "serverId": server_id,
        "tools": [{"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in tools],
    }

@router.post("/mcp/reload")
async def mcp_reload_agent_tools():
    shared.put_input("__RELOAD_SKILLS__")
    return {"ok": True}

@router.get("/heartbeat/tasks")
async def list_heartbeat_tasks():
    return {"tasks": heartbeat.list_tasks()}

@router.post("/heartbeat/update")
async def update_heartbeat_task(payload: HeartbeatUpdate):
    tasks = heartbeat.list_tasks()
    names = [t.get("name") for t in tasks]
    if payload.name not in names:
        raise HTTPException(status_code=404, detail="心跳任务不存在")
    ok = heartbeat.update_task(payload.name, payload.interval, payload.paused)
    if not ok:
        raise HTTPException(status_code=400, detail="更新失败")
    return {"status": "success", "name": payload.name}

@router.get("/templates")
async def list_templates(limit: int = 100, offset: int = 0):
    safe_limit = max(1, min(int(limit or 100), 500))
    safe_offset = max(0, int(offset or 0))
    store = _get_template_store()
    try:
        result = store.get(where={"memory_type": {"$eq": "task_template"}})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取模板失败: {e}")
    ids = result.get("ids") or []
    metadatas = result.get("metadatas") or []
    documents = result.get("documents") or []
    templates = []
    for i, template_id in enumerate(ids):
        meta = metadatas[i] if i < len(metadatas) else {}
        doc = documents[i] if i < len(documents) else ""
        raw_content = meta.get("original_content") or doc or ""
        template_obj = None
        name = ""
        try:
            template_obj = json.loads(raw_content)
            if isinstance(template_obj, dict):
                name = str(template_obj.get("name") or "").strip()
        except Exception:
            template_obj = None
        tags = _normalize_tags(meta.get("tags") or meta.get("tags_list"))
        templates.append({
            "id": template_id,
            "name": name or "未命名模板",
            "template": template_obj,
            "raw": raw_content,
            "tags": tags,
            "scope": meta.get("scope") or "",
            "project_id": meta.get("project_id") or "",
            "user_id": meta.get("user_id") or "",
            "created_at": meta.get("created_at") or ""
        })
    templates.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    templates = templates[safe_offset:safe_offset + safe_limit]
    return {"templates": templates}

@router.get("/experiences")
async def list_experiences(query: Optional[str] = None, system: Optional[str] = None, tags: Optional[str] = None, scope: Optional[str] = None, project_id: Optional[str] = None, user_id: Optional[str] = None, memory_type: Optional[str] = None, limit: int = 200, offset: int = 0):
    safe_limit = max(1, min(int(limit or 200), 500))
    safe_offset = max(0, int(offset or 0))
    items = _get_experience_items(query, system, tags, scope, project_id, user_id, memory_type, safe_limit, safe_offset)
    return {"items": items}

@router.get("/experiences/export")
async def export_experiences(format: str = "json", query: Optional[str] = None, system: Optional[str] = None, tags: Optional[str] = None, scope: Optional[str] = None, project_id: Optional[str] = None, user_id: Optional[str] = None, memory_type: Optional[str] = None, limit: int = 500, offset: int = 0):
    safe_limit = max(1, min(int(limit or 500), 500))
    safe_offset = max(0, int(offset or 0))
    items = _get_experience_items(query, system, tags, scope, project_id, user_id, memory_type, safe_limit, safe_offset)
    fmt = (format or "json").strip().lower()
    if fmt == "csv":
        headers = ["created_at", "system", "memory_type", "tags", "scope", "project_id", "user_id", "url", "content"]
        rows = [",".join(headers)]
        for item in items:
            values = []
            for key in headers:
                value = item.get(key) if isinstance(item, dict) else ""
                text = "" if value is None else str(value)
                text = text.replace('"', '""')
                values.append(f"\"{text}\"")
            rows.append(",".join(values))
        data = "\n".join(rows)
        return Response(content=data, media_type="text/csv; charset=utf-8")
    payload = json.dumps(items, ensure_ascii=False, indent=2)
    return Response(content=payload, media_type="application/json")

@router.put("/experiences/{experience_id}")
async def update_experience(experience_id: str, payload: ExperienceUpdate):
    store = _get_template_store()
    existing = store.get(ids=[experience_id])
    ids = existing.get("ids") or []
    if not ids:
        raise HTTPException(status_code=404, detail="记忆不存在")
    meta = (existing.get("metadatas") or [{}])[0]
    doc = (existing.get("documents") or [""])[0]
    current_content = meta.get("original_content") or doc or ""
    content = payload.content if payload.content is not None else current_content
    tags_list = _normalize_tags(payload.tags if payload.tags is not None else (meta.get("tags") or meta.get("tags_list")))
    tags_str = ", ".join(tags_list)
    metadata = {
        "system": payload.system if payload.system is not None else (meta.get("system") or ""),
        "tags": tags_str,
        "tags_list": tags_str,
        "url": payload.url if payload.url is not None else (meta.get("url") or ""),
        "scope": payload.scope if payload.scope is not None else (meta.get("scope") or ""),
        "project_id": payload.project_id if payload.project_id is not None else (meta.get("project_id") or ""),
        "user_id": payload.user_id if payload.user_id is not None else (meta.get("user_id") or ""),
        "memory_type": payload.memory_type if payload.memory_type is not None else (meta.get("memory_type") or ""),
        "created_at": meta.get("created_at") or datetime.now(timezone.utc).isoformat(),
        "original_content": content
    }
    page_content = _build_page_content(metadata, content)
    try:
        store.delete(ids=[experience_id])
        from langchain_core.documents import Document
        new_ids = store.add_documents([Document(page_content=page_content, metadata=metadata)])
        new_id = new_ids[0] if new_ids else experience_id
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新记忆失败: {e}")
    return {"status": "success", "id": new_id}

@router.delete("/experiences/{experience_id}")
async def delete_experience(experience_id: str):
    store = _get_template_store()
    try:
        store.delete(ids=[experience_id])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除记忆失败: {e}")
    return {"status": "deleted", "id": experience_id}

@router.put("/templates/{template_id}")
async def update_template(template_id: str, payload: TemplateUpdate):
    store = _get_template_store()
    existing = store.get(ids=[template_id])
    ids = existing.get("ids") or []
    if not ids:
        raise HTTPException(status_code=404, detail="模板不存在")
    meta = (existing.get("metadatas") or [{}])[0]
    tags = payload.tags
    if tags is None and isinstance(payload.template, dict):
        tags = payload.template.get("tags")
    tags_list = _normalize_tags(tags) or _normalize_tags(meta.get("tags") or meta.get("tags_list"))
    tags_str = ", ".join(tags_list)
    raw_content = json.dumps(payload.template, ensure_ascii=False)
    metadata = {
        "system": meta.get("system") or "task_template",
        "tags": tags_str,
        "tags_list": tags_str,
        "url": meta.get("url") or "",
        "scope": meta.get("scope") or "project",
        "project_id": meta.get("project_id") or "",
        "user_id": meta.get("user_id") or "",
        "memory_type": meta.get("memory_type") or "task_template",
        "created_at": meta.get("created_at") or datetime.now(timezone.utc).isoformat(),
        "original_content": raw_content
    }
    page_content = _build_page_content(metadata, raw_content)
    try:
        store.delete(ids=[template_id])
        from langchain_core.documents import Document
        new_ids = store.add_documents([Document(page_content=page_content, metadata=metadata)])
        new_id = new_ids[0] if new_ids else template_id
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新模板失败: {e}")
    return {"status": "success", "id": new_id}

@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    store = _get_template_store()
    try:
        store.delete(ids=[template_id])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除模板失败: {e}")
    return {"status": "deleted", "id": template_id}
