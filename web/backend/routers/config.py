from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from dotenv import dotenv_values, set_key
import os
import socket
import json
import urllib.request
import urllib.error
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from app.integrations import heartbeat
from app.integrations.mcp_client import get_mcp_manager
from ..shared import shared

router = APIRouter()

_CONFIG_SCHEMA_CACHE: Optional[Dict[str, Dict[str, Any]]] = None

_GROUP_ORDER = [
    "Web 控制台",
    "Agent",
    "模型/LLM",
    "DeepSeek",
    "Qwen",
    "OpenAI",
    "火山方舟/豆包",
    "NVIDIA NIM",
    "本地模型",
    "Playwright",
    "WhatsApp",
    "MCP",
    "日志与调试",
    "安全/密钥",
    "其他",
]

_SCHEMA_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "WEB_HOST": {"label": "Web 监听地址", "desc": "Web 服务绑定的 host（通常 0.0.0.0 或 127.0.0.1）", "group": "Web 控制台", "common": True},
    "WEB_PORT": {"label": "Web 端口", "desc": "Web 服务端口（默认 5010）", "group": "Web 控制台", "common": True},
    "PUBLIC_URL": {"label": "访问地址", "desc": "用于生成二维码/分享的访问地址（可填局域网或公网地址）", "group": "Web 控制台", "common": True},
    "LLM_PROVIDER": {"label": "模型提供方", "desc": "选择模型提供方（deepseek/qwen/openai/local/nim_* 等）", "group": "模型/LLM", "common": True},
    "DEEPSEEK_API_KEY": {"label": "DeepSeek API Key", "desc": "DeepSeek 密钥", "group": "DeepSeek", "common": True, "secret": True},
    "DEEPSEEK_BASE_URL": {"label": "DeepSeek Base URL", "desc": "DeepSeek API 地址", "group": "DeepSeek", "common": True},
    "DEEPSEEK_MODEL_NAME": {"label": "DeepSeek 模型名", "desc": "对话模型名称", "group": "DeepSeek", "common": True},
    "QWEN_API_KEY": {"label": "Qwen API Key", "desc": "Qwen/DashScope 密钥", "group": "Qwen", "common": True, "secret": True},
    "QWEN_CODING_PLAN_API_KEY": {"label": "Coding Plan API Key", "desc": "通义千问 Coding Plan 密钥", "group": "Qwen", "common": False, "secret": True},
    "DASHSCOPE_API_KEY": {"label": "DashScope API Key", "desc": "通义千问 DashScope 密钥（可替代 QWEN_API_KEY）", "group": "Qwen", "common": False, "secret": True},
    "QWEN_BASE_URL": {"label": "Qwen Base URL", "desc": "Qwen API 地址", "group": "Qwen", "common": False},
    "QWEN_MODEL_NAME": {"label": "Qwen 模型名", "desc": "对话模型名称", "group": "Qwen", "common": True},
    "OPENAI_API_KEY": {"label": "OpenAI API Key", "desc": "OpenAI 密钥（也可能被部分集成作为兼容密钥使用）", "group": "OpenAI", "common": True, "secret": True},
    "OPENAI_BASE_URL": {"label": "OpenAI Base URL", "desc": "OpenAI API 地址", "group": "OpenAI", "common": False},
    "OPENAI_MODEL_NAME": {"label": "OpenAI 模型名", "desc": "对话模型名称", "group": "OpenAI", "common": True},
    "DOUBAO_API_KEY": {"label": "豆包/方舟 API Key", "desc": "火山方舟/豆包密钥（部分能力可与 ARK_API_KEY 互换）", "group": "火山方舟/豆包", "common": True, "secret": True},
    "ARK_API_KEY": {"label": "ARK API Key", "desc": "火山方舟密钥（兼容项）", "group": "火山方舟/豆包", "common": False, "secret": True},
    "DOUBAO_BASE_URL": {"label": "豆包/方舟 Base URL", "desc": "火山方舟 API 地址", "group": "火山方舟/豆包", "common": False},
    "ARK_BASE_URL": {"label": "ARK Base URL", "desc": "火山方舟 API 地址（兼容项）", "group": "火山方舟/豆包", "common": False},
    "DOUBAO_VISION_MODEL_NAME": {"label": "视觉模型名", "desc": "视觉理解/图片相关能力使用的模型名称", "group": "火山方舟/豆包", "common": True},
    "NIM_API_KEY": {"label": "NIM API Key", "desc": "NVIDIA NIM / API Catalog 密钥", "group": "NVIDIA NIM", "common": False, "secret": True},
    "NIM_BASE_URL": {"label": "NIM Base URL", "desc": "NVIDIA NIM / API Catalog 地址", "group": "NVIDIA NIM", "common": False},
    "NIM_MINIMAX_M2_MODEL_NAME": {"label": "NIM Minimax-M2 模型名", "desc": "minimaxai/minimax-m2", "group": "NVIDIA NIM", "common": False},
    "NIM_GLM47_MODEL_NAME": {"label": "NIM GLM4.7 模型名", "desc": "z-ai/glm4.7", "group": "NVIDIA NIM", "common": False},
    "LOCAL_MODEL_PATH": {"label": "本地模型路径", "desc": "本地模型文件路径", "group": "本地模型", "common": False},
    "LOCAL_CTX_SIZE": {"label": "本地上下文长度", "desc": "ctx size", "group": "本地模型", "common": False},
    "LOCAL_GPU_LAYERS": {"label": "本地 GPU Layers", "desc": "GPU 加速层数", "group": "本地模型", "common": False},
    "LOCAL_THREADS": {"label": "本地线程数", "desc": "推理线程数", "group": "本地模型", "common": False},
    "LOCAL_BATCH_SIZE": {"label": "本地 Batch Size", "desc": "批大小", "group": "本地模型", "common": False},
    "LOCAL_TEMPERATURE": {"label": "本地 Temperature", "desc": "采样温度", "group": "本地模型", "common": False},
    "PLAYWRIGHT_USER_DATA_DIR": {"label": "Playwright 用户数据目录", "desc": "浏览器用户数据目录", "group": "Playwright", "common": True},
    "PLAYWRIGHT_EXTENSION_DIR": {"label": "Playwright 扩展目录", "desc": "用于 Cookie 同步等扩展", "group": "Playwright", "common": True},
    "PLAYWRIGHT_AUTO_LOAD_COOKIES": {"label": "自动载入 Cookie", "desc": "启动浏览器时自动载入 Cookie（1/0）", "group": "Playwright", "common": True},
    "WA_GATEWAY_HOST": {"label": "WA Gateway Host", "desc": "WhatsApp 网关地址", "group": "WhatsApp", "common": True},
    "WA_GATEWAY_PORT": {"label": "WA Gateway 端口", "desc": "WhatsApp 网关端口", "group": "WhatsApp", "common": True},
    "WA_GATEWAY_TOKEN": {"label": "WA Gateway Token", "desc": "WhatsApp 网关鉴权 Token", "group": "WhatsApp", "common": True, "secret": True},
    "WA_PROVIDER": {"label": "WhatsApp Provider", "desc": "接入方式：baileys 或 cloud（官方）", "group": "WhatsApp", "common": True},
    "WA_GATEWAY_AUTOSTART": {"label": "自动启动 WA Gateway", "desc": "是否自动启动 WhatsApp 网关（1/0）", "group": "WhatsApp", "common": False},
    "WA_NODE_BIN": {"label": "Node 可执行文件", "desc": "启动 WA Gateway 使用的 node 路径/命令", "group": "WhatsApp", "common": False},
    "WA_AUTH_DIR": {"label": "WA 登录态目录", "desc": "WhatsApp 登录态（auth）保存目录", "group": "WhatsApp", "common": False},
    "WA_DM_ENABLED": {"label": "允许私聊消息", "desc": "是否允许 WhatsApp 私聊消息进入（1/0）", "group": "WhatsApp", "common": True},
    "WA_ALLOW_FROM": {"label": "允许的手机号白名单", "desc": "允许的 E164 号码（逗号分隔），或 * 放行全部", "group": "WhatsApp", "common": True},
    "WA_WEBHOOK_URL": {"label": "WhatsApp Webhook 地址", "desc": "网关收到消息后的回调地址", "group": "WhatsApp", "common": True},
    "WA_WEBHOOK_TOKEN": {"label": "WhatsApp Webhook Token", "desc": "回调鉴权 Token（Bearer）", "group": "WhatsApp", "common": False, "secret": True},
    "WA_CLOUD_VERIFY_TOKEN": {"label": "WA Cloud Verify Token", "desc": "Cloud API webhook 校验 token", "group": "WhatsApp", "common": False, "secret": True},
    "WA_CLOUD_ACCESS_TOKEN": {"label": "WA Cloud Access Token", "desc": "Cloud API Graph 访问令牌", "group": "WhatsApp", "common": False, "secret": True},
    "WA_CLOUD_PHONE_NUMBER_ID": {"label": "WA Cloud Phone Number ID", "desc": "Cloud API phone_number_id", "group": "WhatsApp", "common": False},
    "WA_CLOUD_API_VERSION": {"label": "WA Cloud API Version", "desc": "Graph API 版本（如 v19.0）", "group": "WhatsApp", "common": False},
    "WA_CLOUD_APP_SECRET": {"label": "WA Cloud App Secret", "desc": "用于校验 X-Hub-Signature-256", "group": "WhatsApp", "common": False, "secret": True},
    "WA_PROXY_ENABLED": {"label": "启用代理", "desc": "网关是否启用代理（1/0）", "group": "WhatsApp", "common": False},
    "WA_PROXY_URL": {"label": "代理地址", "desc": "代理 URL（如 http://127.0.0.1:7890）", "group": "WhatsApp", "common": False},
    "WA_TEXT_CHUNK_LIMIT": {"label": "消息分片长度", "desc": "发送长消息时的分片长度（默认 4000）", "group": "WhatsApp", "common": False},
    "WA_PRINT_QR": {"label": "控制台打印二维码", "desc": "网关是否在控制台打印二维码（1/0）", "group": "WhatsApp", "common": False},
    "MCP_SERVERS": {"label": "MCP Servers", "desc": "MCP 服务器列表（JSON）", "group": "MCP", "common": True},
    "AGENT_MAX_ITERATIONS": {"label": "最大执行步数", "desc": "Agent 单次任务最多执行步数", "group": "Agent", "common": True},
    "AGENT_MAX_EXECUTION_TIME": {"label": "最大执行时间（秒）", "desc": "Agent 单次任务最多执行时间", "group": "Agent", "common": True},
    "AGENT_LIMITS_DISABLED": {"label": "解除执行限制", "desc": "是否解除步数/时间限制（1/0）", "group": "Agent", "common": True},
    "DEVOPS_ENC_KEY": {"label": "变更日志加密密钥", "desc": "用于加密变更日志/快照", "group": "安全/密钥", "common": False, "secret": True},
    "AUDIT_LOG_KEY": {"label": "审计日志加密密钥", "desc": "用于加密审计日志", "group": "安全/密钥", "common": False, "secret": True},
}

def _get_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def _is_secret_key(key: str) -> bool:
    up = (key or "").upper()
    if not up:
        return False
    if up in _SCHEMA_OVERRIDES and bool(_SCHEMA_OVERRIDES[up].get("secret")):
        return True
    for token in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "PASS", "COOKIE", "KEY"):
        if token in up and up not in {"PUBLIC_KEY"}:
            return True
    return False

def _guess_group(key: str) -> str:
    up = (key or "").upper()
    if up in _SCHEMA_OVERRIDES and _SCHEMA_OVERRIDES[up].get("group"):
        return str(_SCHEMA_OVERRIDES[up]["group"])
    if up.startswith(("WEB_", "PUBLIC_")):
        return "Web 控制台"
    if up.startswith("AGENT_"):
        return "Agent"
    if up.startswith(("DEEPSEEK_",)):
        return "DeepSeek"
    if up.startswith(("QWEN_", "DASHSCOPE_")):
        return "Qwen"
    if up.startswith(("OPENAI_",)):
        return "OpenAI"
    if up.startswith(("DOUBAO_", "ARK_")):
        return "火山方舟/豆包"
    if up.startswith(("NIM_",)):
        return "NVIDIA NIM"
    if up.startswith(("LOCAL_",)):
        return "本地模型"
    if up.startswith(("PLAYWRIGHT_", "TESSDATA_", "TESSERACT_")):
        return "Playwright"
    if up.startswith(("WA_", "WHATSAPP_")):
        return "WhatsApp"
    if up.startswith(("MCP_",)):
        return "MCP"
    if up.startswith(("LOG_", "DEBUG_", "TRACE_")):
        return "日志与调试"
    if any(t in up for t in ("ENC_KEY", "AUDIT", "KEY")):
        return "安全/密钥"
    if up in {"LLM_PROVIDER"}:
        return "模型/LLM"
    return "其他"

def _extract_env_keys_from_source() -> List[str]:
    root = _get_project_root()
    targets = [os.path.join(root, "app"), os.path.join(root, "web", "backend"), os.path.join(root, "gateway")]
    patterns = [
        re.compile(r'os\.getenv\(\s*[\'"]([A-Z0-9_]+)[\'"]\s*\)'),
        re.compile(r'env\.get\(\s*[\'"]([A-Z0-9_]+)[\'"]\s*\)'),
        re.compile(r'_env_flag\(\s*[\'"]([A-Z0-9_]+)[\'"]\s*[,)]'),
        re.compile(r'_read_(?:int|bool)_env\(\s*[\'"]([A-Z0-9_]+)[\'"]\s*,'),
        re.compile(r'process\.env\[\s*[\'"]([A-Z0-9_]+)[\'"]\s*\]'),
        re.compile(r'env(?:Str|Flag|Int)\(\s*[\'"]([A-Z0-9_]+)[\'"]'),
    ]
    found: set[str] = set()
    for base in targets:
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for name in filenames:
                low = name.lower()
                if not (low.endswith(".py") or low.endswith(".js") or low.endswith(".mjs")):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                except Exception:
                    continue
                for pat in patterns:
                    for m in pat.finditer(text):
                        k = (m.group(1) or "").strip().upper()
                        if k:
                            found.add(k)
    return sorted(found)

def _read_env_file_map() -> Dict[str, str]:
    env_path = _get_env_path()
    if not os.path.exists(env_path):
        return {}
    raw = dotenv_values(env_path)
    out: Dict[str, str] = {}
    for k, v in (raw or {}).items():
        key = str(k or "").strip()
        if not key:
            continue
        out[key] = "" if v is None else str(v)
    return out

def _append_missing_env_keys(keys: List[str]) -> Dict[str, Any]:
    env_path = _get_env_path()
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("")

    existing = _read_env_file_map()
    existing_upper = {str(k).upper() for k in existing.keys()}
    to_add = []
    for k in keys:
        key = str(k or "").strip().upper()
        if not key:
            continue
        if key in existing_upper:
            continue
        to_add.append(key)

    if not to_add:
        return {"added": [], "skipped": []}

    try:
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            tail = f.read()[-1:] if os.path.getsize(env_path) > 0 else ""
    except Exception:
        tail = ""

    defaults: Dict[str, str] = {
        "WEB_HOST": "0.0.0.0",
        "WEB_PORT": "5010",
        "WA_PROVIDER": "baileys",
        "WA_GATEWAY_HOST": "127.0.0.1",
        "WA_GATEWAY_PORT": "8787",
        "WA_AUTH_DIR": "./gateway/auth",
        "WA_TEXT_CHUNK_LIMIT": "4000",
        "WA_PRINT_QR": "1",
        "WA_DM_ENABLED": "1",
        "WA_PROXY_ENABLED": "0",
        "WA_GATEWAY_AUTOSTART": "0",
        "WA_CLOUD_API_VERSION": "v19.0",
    }

    with open(env_path, "a", encoding="utf-8") as f:
        if tail and tail not in ("\n", "\r"):
            f.write("\n")
        f.write("\n")
        for k in sorted(set(to_add)):
            f.write(f"{k}={defaults.get(k, '')}\n")

    return {"added": sorted(set(to_add)), "skipped": []}

def _get_config_schema() -> Dict[str, Dict[str, Any]]:
    global _CONFIG_SCHEMA_CACHE
    if _CONFIG_SCHEMA_CACHE is not None:
        return _CONFIG_SCHEMA_CACHE
    schema: Dict[str, Dict[str, Any]] = {}
    for key in _extract_env_keys_from_source():
        schema[key] = {
            "label": key,
            "desc": "",
            "group": _guess_group(key),
            "common": False,
            "secret": _is_secret_key(key),
        }
    for key, meta in _SCHEMA_OVERRIDES.items():
        k = (key or "").upper()
        existing = schema.get(k) or {
            "label": k,
            "desc": "",
            "group": _guess_group(k),
            "common": False,
            "secret": _is_secret_key(k),
        }
        merged = {**existing, **meta}
        merged["group"] = merged.get("group") or _guess_group(k)
        merged["secret"] = bool(merged.get("secret")) or _is_secret_key(k)
        merged["common"] = bool(merged.get("common"))
        merged["label"] = str(merged.get("label") or k)
        merged["desc"] = str(merged.get("desc") or "")
        schema[k] = merged
    _CONFIG_SCHEMA_CACHE = schema
    return schema

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

@router.get("/ui")
async def get_config_ui():
    env_path = _get_env_path()
    env_raw = dotenv_values(env_path) if os.path.exists(env_path) else {}
    schema = _get_config_schema()
    keys = sorted(set([str(k).upper() for k in (env_raw or {}).keys()]) | set(schema.keys()))
    env: Dict[str, Any] = {}
    items: List[Dict[str, Any]] = []
    for key in keys:
        raw_value = env_raw.get(key)
        value = "" if raw_value is None else str(raw_value)
        has_value = bool(str(value).strip())
        meta = schema.get(key) or {
            "label": key,
            "desc": "",
            "group": _guess_group(key),
            "common": False,
            "secret": _is_secret_key(key),
        }
        secret = bool(meta.get("secret"))
        env[key] = "" if secret else value
        items.append(
            {
                "key": key,
                "label": meta.get("label") or key,
                "desc": meta.get("desc") or "",
                "group": meta.get("group") or "其他",
                "common": bool(meta.get("common")),
                "secret": secret,
                "hasValue": has_value,
                "value": "" if secret else value,
            }
        )
    return {"groups": _GROUP_ORDER, "items": items, "env": env}

@router.get("/ui/diff")
async def get_config_ui_diff():
    env_map = _read_env_file_map()
    env_keys_upper = {str(k).upper() for k in env_map.keys()}
    schema = _get_config_schema()
    schema_keys = set(schema.keys())
    missing_in_env = sorted([k for k in schema_keys if k not in env_keys_upper])
    extra_in_env = sorted([k for k in env_keys_upper if k not in schema_keys])
    return {"missingInEnv": missing_in_env, "extraInEnv": extra_in_env, "schemaKeys": len(schema_keys), "envKeys": len(env_keys_upper)}

@router.post("/ui/fill-missing")
async def fill_missing_env_keys():
    schema = _get_config_schema()
    env_map = _read_env_file_map()
    env_keys_upper = {str(k).upper() for k in env_map.keys()}
    missing = [k for k in schema.keys() if k not in env_keys_upper]
    result = _append_missing_env_keys(missing)
    return {"ok": True, **result}

@router.post("")
async def update_config(config: ConfigUpdate):
    """Update a specific environment variable"""
    env_path = _get_env_path()

    try:
        if not os.path.exists(env_path):
            with open(env_path, "w", encoding="utf-8") as f:
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
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    provider = (os.getenv("WA_PROVIDER") or env.get("WA_PROVIDER") or "baileys").strip().lower()
    if provider in {"cloud", "official", "business"}:
        return {
            "ok": True,
            "provider": "cloud",
            "webhookPath": "/api/chat/whatsapp/cloud/webhook",
            "configured": {
                "verifyToken": bool((os.getenv("WA_CLOUD_VERIFY_TOKEN") or env.get("WA_CLOUD_VERIFY_TOKEN") or "").strip()),
                "accessToken": bool((os.getenv("WA_CLOUD_ACCESS_TOKEN") or env.get("WA_CLOUD_ACCESS_TOKEN") or "").strip()),
                "phoneNumberId": bool((os.getenv("WA_CLOUD_PHONE_NUMBER_ID") or env.get("WA_CLOUD_PHONE_NUMBER_ID") or "").strip()),
            },
        }
    return _wa_gateway_request_json("/health", method="GET", require_auth=False)

@router.get("/whatsapp/qr")
async def whatsapp_qr():
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    provider = (os.getenv("WA_PROVIDER") or env.get("WA_PROVIDER") or "baileys").strip().lower()
    if provider in {"cloud", "official", "business"}:
        raise HTTPException(status_code=400, detail="Cloud API 不需要二维码")
    return _wa_gateway_request_json("/qr", method="GET", require_auth=True)

@router.get("/whatsapp/qr-ascii")
async def whatsapp_qr_ascii():
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    provider = (os.getenv("WA_PROVIDER") or env.get("WA_PROVIDER") or "baileys").strip().lower()
    if provider in {"cloud", "official", "business"}:
        raise HTTPException(status_code=400, detail="Cloud API 不需要二维码")
    return _wa_gateway_request_json("/qr-ascii", method="GET", require_auth=True)

@router.post("/whatsapp/reset")
async def whatsapp_reset():
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    provider = (os.getenv("WA_PROVIDER") or env.get("WA_PROVIDER") or "baileys").strip().lower()
    if provider in {"cloud", "official", "business"}:
        raise HTTPException(status_code=400, detail="Cloud API 无需 reset")
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
