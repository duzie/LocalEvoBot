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

@tool
def eyes_find_text(window_title: str, target_text: str, return_normalized: bool = True) -> str:
    """
    在指定窗口截图中定位文字，返回坐标（眼睛：视觉定位）。
    """
    if platform.system() != "Windows":
        return "Error: Only Windows supported"
    client, model, err = _create_client()
    if err:
        return err
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        window = desktop.window(title_re=window_title)
        if not window.exists(timeout=2):
            msg = f"未找到窗口: {window_title}"
            if not _is_admin():
                msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
            return msg
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
        return json.dumps(data if data is not None else {"raw": content}, ensure_ascii=False)
    except Exception as e:
        msg = f"眼睛定位文字失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
        return msg

@tool
def eyes_find_ui(window_title: str, description: str, return_normalized: bool = True) -> str:
    """
    在指定窗口截图中按描述定位 UI 元素，返回坐标（眼睛：视觉定位）。
    """
    if platform.system() != "Windows":
        return "Error: Only Windows supported"
    client, model, err = _create_client()
    if err:
        return err
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        window = desktop.window(title_re=window_title)
        if not window.exists(timeout=2):
            msg = f"未找到窗口: {window_title}"
            if not _is_admin():
                msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
            return msg
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
        return json.dumps(data if data is not None else {"raw": content}, ensure_ascii=False)
    except Exception as e:
        msg = f"眼睛定位UI失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
        return msg

@tool
def eyes_find_multiple(window_title: str, descriptions: list, return_normalized: bool = True) -> str:
    """
    在指定窗口截图中批量定位多个目标，返回坐标列表（眼睛：视觉定位）。
    """
    if platform.system() != "Windows":
        return "Error: Only Windows supported"
    client, model, err = _create_client()
    if err:
        return err
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        window = desktop.window(title_re=window_title)
        if not window.exists(timeout=2):
            msg = f"未找到窗口: {window_title}"
            if not _is_admin():
                msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
            return msg
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
        return json.dumps(data if data is not None else {"raw": content}, ensure_ascii=False)
    except Exception as e:
        msg = f"眼睛批量定位失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
        return msg

@tool
def eyes_map_ui(window_title: str, functions: list, return_normalized: bool = True) -> str:
    """
    在指定窗口截图中按“功能描述”批量返回 UI 坐标（眼睛：视觉定位）。
    """
    if platform.system() != "Windows":
        return "Error: Only Windows supported"
    client, model, err = _create_client()
    if err:
        return err
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        window = desktop.window(title_re=window_title)
        if not window.exists(timeout=2):
            msg = f"未找到窗口: {window_title}"
            if not _is_admin():
                msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
            return msg
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
        return json.dumps(data if data is not None else {"raw": content}, ensure_ascii=False)
    except Exception as e:
        msg = f"眼睛功能映射失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
        return msg

@tool
def eyes_click_ui(window_title: str, description: str, min_conf: float = 0.3, offset_x: int = 0, offset_y: int = 0, double_click: bool = False) -> str:
    """
    视觉 → 坐标 → 自动点击：在指定窗口内按功能描述定位并点击（眼睛：视觉点击）。
    """
    if platform.system() != "Windows":
        return "Error: Only Windows supported"
    api_key = os.getenv("ARK_API_KEY")
    model = os.getenv("DOUBAO_VISION_MODEL_NAME")
    if not api_key or not model:
        return "Error: Missing ARK_API_KEY or DOUBAO_VISION_MODEL_NAME"
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        window = desktop.window(title_re=window_title)
        if not window.exists(timeout=2):
            msg = f"未找到窗口: {window_title}"
            if not _is_admin():
                msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
            return msg
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
            return f"未找到元素: {description}"
        if isinstance(data, list) and data:
            data = data[0]
        bbox = data.get("bbox") if isinstance(data, dict) else None
        conf = data.get("confidence")
        if conf is not None:
            try:
                if float(conf) < min_conf:
                    return f"置信度过低: {conf}"
            except Exception:
                pass
        if not bbox:
            return f"未获取到坐标: {data}"
        try:
            left = float(bbox.get("left")); top = float(bbox.get("top")); right = float(bbox.get("right")); bottom = float(bbox.get("bottom"))
        except Exception:
            return f"坐标格式错误: {bbox}"
        w, h = img.size
        cx = int(((left+right)/2) * w) + offset_x
        cy = int(((top+bottom)/2) * h) + offset_y
        if double_click:
            window.double_click_input(coords=(cx, cy))
            act = "双击"
        else:
            window.click_input(coords=(cx, cy))
            act = "点击"
        return f"已通过视觉模型{act} '{description}' at ({cx}, {cy})"
    except Exception as e:
        msg = f"眼睛视觉点击失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 可能为管理员权限窗口，请以管理员身份运行 Agent。"
        return msg
