from langchain_core.tools import tool
import os
import base64
import io
import json
import re
import platform
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
from web.backend.shared import shared

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
env_path = os.path.join(project_root, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

def _extract_json(text: str):
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    match = re.search(r"\[[\s\S]*\]", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None

def _create_client():
    api_key = os.getenv("ARK_API_KEY")
    model = os.getenv("DOUBAO_VISION_MODEL_NAME")
    if not api_key or not model:
        return None, None, "Error: Missing ARK_API_KEY or DOUBAO_VISION_MODEL_NAME"
    client = OpenAI(
        api_key=api_key,
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )
    return client, model, None

def _encode_image_bytes(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def _is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _emit_event(tool_name: str, event: str, **fields):
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))

@tool
def eyes_find_text(window_title: str, target_text: str, return_normalized: bool = True) -> str:
    """
    在指定窗口截图中定位文字，返回坐标（眼睛：视觉定位）。
    """
    tool_name = "eyes_find_text"
    if platform.system() != "Windows":
        return _error_payload("unsupported_platform", "仅支持 Windows", tool=tool_name)
    client, model, err = _create_client()
    if err:
        return _error_payload("missing_config", err, tool=tool_name)
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        window = desktop.window(title_re=window_title)
        if not window.exists(timeout=2):
            msg = f"未找到窗口: {window_title}"
            if not _is_admin():
                msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
            return _error_payload("window_not_found", msg, tool=tool_name, is_admin=_is_admin())
        img = window.capture_as_image()
        base64_image = _encode_image_bytes(img)
        fmt = "normalized between 0 and 1" if return_normalized else "pixel coordinates"
        prompt = (
            f"Find the bounding box of the text '{target_text}' in the image. "
            "Return JSON only in this format: "
            "{\"text\":\"...\",\"bbox\":{\"left\":0.0,\"top\":0.0,\"right\":0.0,\"bottom\":0.0},\"confidence\":0.0}. "
            f'Coordinates must be {fmt}. If not found, return {{"error":"not_found"}}.'
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:image/png;base64,{base64_image}"}}]}],
        )
        content = response.choices[0].message.content
        data = _extract_json(content)
        payload = data if data is not None else {"raw": content}
        _emit_event(tool_name, "find_text")
        return _ok_payload("定位完成", data=payload)
    except Exception as e:
        msg = f"眼睛定位文字失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("find_text_failed", msg, tool=tool_name, is_admin=_is_admin())

@tool
def eyes_find_ui(window_title: str, description: str, return_normalized: bool = True) -> str:
    """
    在指定窗口截图中按描述定位 UI 元素，返回坐标（眼睛：视觉定位）。
    """
    tool_name = "eyes_find_ui"
    if platform.system() != "Windows":
        return _error_payload("unsupported_platform", "仅支持 Windows", tool=tool_name)
    client, model, err = _create_client()
    if err:
        return _error_payload("missing_config", err, tool=tool_name)
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        window = desktop.window(title_re=window_title)
        if not window.exists(timeout=2):
            msg = f"未找到窗口: {window_title}"
            if not _is_admin():
                msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
            return _error_payload("window_not_found", msg, tool=tool_name, is_admin=_is_admin())
        img = window.capture_as_image()
        base64_image = _encode_image_bytes(img)
        fmt = "normalized between 0 and 1" if return_normalized else "pixel coordinates"
        prompt = (
            f"Find the UI element described as '{description}' in the image. "
            "Return JSON only in this format: "
            "{\"desc\":\"...\",\"bbox\":{\"left\":0.0,\"top\":0.0,\"right\":0.0,\"bottom\":0.0},\"confidence\":0.0}. "
            f'Coordinates must be {fmt}. If not found, return {{"error":"not_found"}}.'
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:image/png;base64,{base64_image}"}}]}],
        )
        content = response.choices[0].message.content
        data = _extract_json(content)
        payload = data if data is not None else {"raw": content}
        _emit_event(tool_name, "find_ui")
        return _ok_payload("定位完成", data=payload)
    except Exception as e:
        msg = f"眼睛定位UI失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("find_ui_failed", msg, tool=tool_name, is_admin=_is_admin())

@tool
def eyes_find_multiple(window_title: str, descriptions: list, return_normalized: bool = True) -> str:
    """
    在指定窗口截图中批量定位多个目标，返回坐标列表（眼睛：视觉定位）。
    """
    tool_name = "eyes_find_multiple"
    if platform.system() != "Windows":
        return _error_payload("unsupported_platform", "仅支持 Windows", tool=tool_name)
    client, model, err = _create_client()
    if err:
        return _error_payload("missing_config", err, tool=tool_name)
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        window = desktop.window(title_re=window_title)
        if not window.exists(timeout=2):
            msg = f"未找到窗口: {window_title}"
            if not _is_admin():
                msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
            return _error_payload("window_not_found", msg, tool=tool_name, is_admin=_is_admin())
        img = window.capture_as_image()
        base64_image = _encode_image_bytes(img)
        fmt = "normalized between 0 and 1" if return_normalized else "pixel coordinates"
        prompt = (
            f"Find the UI elements described as {descriptions} in the image. "
            "Return JSON only as an array of items in this format: "
            "{\"desc\":\"...\",\"bbox\":{\"left\":0.0,\"top\":0.0,\"right\":0.0,\"bottom\":0.0},\"confidence\":0.0}. "
            f"Coordinates must be {fmt}. If not found, return an empty list []."
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:image/png;base64,{base64_image}"}}]}],
        )
        content = response.choices[0].message.content
        data = _extract_json(content)
        payload = data if data is not None else {"raw": content}
        _emit_event(tool_name, "find_multiple")
        return _ok_payload("定位完成", data=payload)
    except Exception as e:
        msg = f"眼睛批量定位失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("find_multiple_failed", msg, tool=tool_name, is_admin=_is_admin())

@tool
def eyes_map_ui(window_title: str, functions: list, return_normalized: bool = True) -> str:
    """
    在指定窗口截图中按“功能描述”批量返回 UI 坐标（眼睛：视觉定位）。
    """
    tool_name = "eyes_map_ui"
    if platform.system() != "Windows":
        return _error_payload("unsupported_platform", "仅支持 Windows", tool=tool_name)
    client, model, err = _create_client()
    if err:
        return _error_payload("missing_config", err, tool=tool_name)
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        window = desktop.window(title_re=window_title)
        if not window.exists(timeout=2):
            msg = f"未找到窗口: {window_title}"
            if not _is_admin():
                msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
            return _error_payload("window_not_found", msg, tool=tool_name, is_admin=_is_admin())
        img = window.capture_as_image()
        base64_image = _encode_image_bytes(img)
        fmt = "normalized between 0 and 1" if return_normalized else "pixel coordinates"
        prompt = (
            "You are an expert UI locator. "
            f"Given the software window screenshot, find the UI elements for these functions: {functions}. "
            "Return JSON only as an array of items in this format: "
            "{\"function\":\"...\",\"bbox\":{\"left\":0.0,\"top\":0.0,\"right\":0.0,\"bottom\":0.0},\"confidence\":0.0,\"note\":\"\"}. "
            f"Coordinates must be {fmt}. "
            "If a function cannot be found, still return an item with empty bbox and note 'not_found'."
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:image/png;base64,{base64_image}"}}]}],
        )
        content = response.choices[0].message.content
        data = _extract_json(content)
        payload = data if data is not None else {"raw": content}
        _emit_event(tool_name, "map_ui")
        return _ok_payload("映射完成", data=payload)
    except Exception as e:
        msg = f"眼睛功能映射失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("map_ui_failed", msg, tool=tool_name, is_admin=_is_admin())

@tool
def eyes_click_ui(window_title: str, description: str, min_conf: float = 0.3, offset_x: int = 0, offset_y: int = 0, double_click: bool = False) -> str:
    """
    视觉 → 坐标 → 自动点击：在指定窗口内按功能描述定位并点击（眼睛：视觉点击）。
    """
    tool_name = "eyes_click_ui"
    if platform.system() != "Windows":
        return _error_payload("unsupported_platform", "仅支持 Windows", tool=tool_name)
    api_key = os.getenv("ARK_API_KEY")
    model = os.getenv("DOUBAO_VISION_MODEL_NAME")
    if not api_key or not model:
        return _error_payload("missing_config", "缺少 ARK_API_KEY 或 DOUBAO_VISION_MODEL_NAME", tool=tool_name)
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        window = desktop.window(title_re=window_title)
        if not window.exists(timeout=2):
            msg = f"未找到窗口: {window_title}"
            if not _is_admin():
                msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
            return _error_payload("window_not_found", msg, tool=tool_name, is_admin=_is_admin())
        img = window.capture_as_image()
        base64_image = _encode_image_bytes(img)
        client = OpenAI(api_key=api_key, base_url="https://ark.cn-beijing.volces.com/api/v3")
        prompt = (
            f"Find the UI element described as '{description}' in the image. "
            "Return JSON only in this format: "
            "{\"desc\":\"...\",\"bbox\":{\"left\":0.0,\"top\":0.0,\"right\":0.0,\"bottom\":0.0},\"confidence\":0.0}. "
            "Coordinates must be normalized between 0 and 1. If not found, return {\"error\":\"not_found\"}."
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:image/png;base64,{base64_image}"}}]}],
        )
        content = response.choices[0].message.content
        data = _extract_json(content)
        if not data or isinstance(data, dict) and data.get("error"):
            return _error_payload("element_not_found", f"未找到元素: {description}", tool=tool_name)
        if isinstance(data, list) and data:
            data = data[0]
        bbox = data.get("bbox") if isinstance(data, dict) else None
        conf = data.get("confidence")
        if conf is not None:
            try:
                if float(conf) < min_conf:
                    return _error_payload("low_confidence", f"置信度过低: {conf}", tool=tool_name, confidence=conf, min_conf=min_conf)
            except Exception:
                pass
        if not bbox:
            return _error_payload("bbox_missing", f"未获取到坐标: {data}", tool=tool_name)
        try:
            left = float(bbox.get("left")); top = float(bbox.get("top")); right = float(bbox.get("right")); bottom = float(bbox.get("bottom"))
        except Exception:
            return _error_payload("bbox_invalid", f"坐标格式错误: {bbox}", tool=tool_name)
        w, h = img.size
        cx = int(((left+right)/2) * w) + offset_x
        cy = int(((top+bottom)/2) * h) + offset_y
        if double_click:
            window.double_click_input(coords=(cx, cy))
            act = "双击"
        else:
            window.click_input(coords=(cx, cy))
            act = "点击"
        _emit_event(tool_name, "click", action=act, x=cx, y=cy, description=description)
        return _ok_payload("视觉点击完成", action=act, x=cx, y=cy, description=description)
    except Exception as e:
        msg = f"眼睛视觉点击失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("click_failed", msg, tool=tool_name, is_admin=_is_admin())
