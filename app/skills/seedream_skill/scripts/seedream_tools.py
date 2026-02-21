from langchain_core.tools import tool
import os
import base64
import time
import urllib.request
from typing import Dict, Any, List
from openai import OpenAI
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
env_path = os.path.join(project_root, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

def _resolve_api_key():
    return os.getenv("DOUBAO_API_KEY") or os.getenv("ARK_API_KEY") or os.getenv("OPENAI_API_KEY")

def _resolve_base_url():
    return os.getenv("DOUBAO_BASE_URL") or os.getenv("ARK_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"

def _resolve_model(default_model: str):
    return os.getenv("DOUBAO_IMAGE_MODEL_NAME") or default_model

def _default_save_dir():
    base = os.path.join(project_root, "app", "data", "images", "seedream")
    os.makedirs(base, exist_ok=True)
    return base

def _write_file(path: str, data: bytes):
    with open(path, "wb") as f:
        f.write(data)

def _download_to_file(url: str, path: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    _write_file(path, data)

@tool
def seedream_generate_image(prompt: str, negative_prompt: str = "", size: str = "1024x1024", n: int = 1, quality: str = "", save_dir: str = "", model: str = "") -> Dict[str, Any]:
    """
    使用豆包 Seedream 模型生成图片并保存到本地。
    """
    text = str(prompt or "").strip()
    if not text:
        return {"ok": False, "error": "prompt 不能为空"}
    api_key = _resolve_api_key()
    if not api_key:
        return {"ok": False, "error": "未配置 DOUBAO_API_KEY 或 ARK_API_KEY"}
    base_url = _resolve_base_url()
    model_name = _resolve_model(model or "doubao-seedream-4-5-251128")
    try:
        count = max(1, min(int(n or 1), 4))
    except Exception:
        count = 1
    target_dir = os.path.abspath(save_dir) if save_dir else _default_save_dir()
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir, exist_ok=True)
    client = OpenAI(api_key=api_key, base_url=base_url)
    params: Dict[str, Any] = {"model": model_name, "prompt": text, "n": count, "size": size}
    if quality:
        params["quality"] = quality
    if negative_prompt:
        params["extra_body"] = {"negative_prompt": negative_prompt}
    try:
        response = client.images.generate(**params)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    images: List[Dict[str, Any]] = []
    errors: List[str] = []
    data_list = getattr(response, "data", None) or []
    ts = int(time.time())
    for idx, item in enumerate(data_list):
        url = None
        b64 = None
        if isinstance(item, dict):
            url = item.get("url")
            b64 = item.get("b64_json")
        else:
            url = getattr(item, "url", None)
            b64 = getattr(item, "b64_json", None)
        filename = f"seedream_{ts}_{idx+1}.png"
        path = os.path.join(target_dir, filename)
        try:
            if b64:
                _write_file(path, base64.b64decode(b64))
                images.append({"file_path": path, "url": url})
            elif url:
                _download_to_file(url, path)
                images.append({"file_path": path, "url": url})
            else:
                errors.append(f"第{idx+1}张图片缺少内容")
        except Exception as e:
            errors.append(f"第{idx+1}张图片保存失败: {e}")
    return {
        "ok": len(images) > 0,
        "model": model_name,
        "images": images,
        "errors": errors
    }
