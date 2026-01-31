from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import dotenv_values, set_key
import os
import socket
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

router = APIRouter()

class ConfigUpdate(BaseModel):
    key: str
    value: str

class AccessUrlUpdate(BaseModel):
    url: str

class TemplateUpdate(BaseModel):
    template: Dict[str, Any]
    tags: Optional[List[str]] = None

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

def _get_env_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(base_dir, ".env")

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

@router.get("/templates")
async def list_templates():
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
    return {"templates": templates}

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
