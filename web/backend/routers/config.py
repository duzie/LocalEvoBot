from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import dotenv_values, set_key
import os
import socket

router = APIRouter()

class ConfigUpdate(BaseModel):
    key: str
    value: str

class AccessUrlUpdate(BaseModel):
    url: str

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
