from langchain_core.tools import tool
import pyautogui
import os
import shutil
import platform
import json
from datetime import datetime
from typing import Any, Dict
from web.backend.shared import shared

def get_tesseract_cmd():
    # 1. 检查 PATH
    if shutil.which("tesseract"):
        return None  # pytesseract 默认会用 PATH
    
    # 2. 检查常见 Windows 路径
    paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"D:\Program Files\Tesseract-OCR\tesseract.exe",
        r"E:\Program Files\Tesseract-OCR\tesseract.exe"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

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
def ocr_screen(image_path: str = None, language: str = "chi_sim+eng"):
    """
    对当前屏幕进行 OCR 文本识别。

    Args:
        image_path: (可选) 图片文件的绝对路径。如果不传，则截取当前屏幕。
        language: 识别语言，例如 "chi_sim+eng"
    """
    tool_name = "ocr_screen"
    temp_screenshot = False
    if not image_path:
        image_path = "temp_ocr_screenshot.png"
        pyautogui.screenshot(image_path)
        temp_screenshot = True
    try:
        import pytesseract
        from PIL import Image
        
        # 自动配置 Tesseract 路径
        cmd = get_tesseract_cmd()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        else:
            cmd = shutil.which("tesseract")
        
        # 检查语言包 (仅当能找到 tesseract 时检查)
        if cmd:
            tessdata_dir = os.path.join(os.path.dirname(cmd), "tessdata")
            # 有些安装可能在 share/tessdata
            if not os.path.exists(tessdata_dir):
                alt_dir = os.path.join(os.path.dirname(cmd), "share", "tessdata")
                if os.path.exists(alt_dir):
                    tessdata_dir = alt_dir
            
            # 设置环境变量，防止找不到 data
            # TESSDATA_PREFIX 应指向 tessdata 文件夹的父目录
            os.environ["TESSDATA_PREFIX"] = os.path.dirname(tessdata_dir)

            if "chi_sim" in language:
                lang_file = os.path.join(tessdata_dir, "chi_sim.traineddata")
                if not os.path.exists(lang_file):
                    return _error_payload(
                        "language_pack_missing",
                        "缺少中文语言包",
                        tool=tool_name,
                        path=lang_file
                    )

        text = pytesseract.image_to_string(Image.open(image_path), lang=language)
        result_text = text.strip()
        _emit_event(tool_name, "recognized", chars=len(result_text))
        return _ok_payload("OCR 识别完成", text=result_text)
    except Exception as e:
        msg = str(e)
        if "tesseract is not installed" in msg or "not in your PATH" in msg:
            _emit_event(tool_name, "error", error=msg)
            return _error_payload(
                "tesseract_not_found",
                "未找到 Tesseract",
                tool=tool_name
            )
        _emit_event(tool_name, "error", error=msg)
        return _error_payload("ocr_failed", msg, tool=tool_name)
    finally:
        if temp_screenshot and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass
