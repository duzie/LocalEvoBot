from langchain_core.tools import tool
import platform
import os
import shutil
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
def ocr_window(window_title: str, language: str = "chi_sim+eng"):
    """
    对指定窗口进行 OCR 文本识别。

    Args:
        window_title: 窗口标题或正则，例如 "微信" 或 ".*WeChat.*"
        language: 识别语言，例如 "chi_sim+eng"
    """
    tool_name = "ocr_window"
    if platform.system() != "Windows":
        return _error_payload("unsupported_platform", "当前仅支持 Windows OCR 窗口识别", tool=tool_name)
    try:
        import pytesseract
        from pywinauto import Desktop
        
        # 自动配置 Tesseract 路径
        cmd = get_tesseract_cmd()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        else:
            cmd = shutil.which("tesseract")

        # 检查语言包
        if cmd:
            tessdata_dir = os.path.join(os.path.dirname(cmd), "tessdata")
            if not os.path.exists(tessdata_dir):
                alt_dir = os.path.join(os.path.dirname(cmd), "share", "tessdata")
                if os.path.exists(alt_dir):
                    tessdata_dir = alt_dir
            
            os.environ["TESSDATA_PREFIX"] = tessdata_dir

            if "chi_sim" in language:
                lang_file = os.path.join(tessdata_dir, "chi_sim.traineddata")
                if not os.path.exists(lang_file):
                    return _error_payload(
                        "language_pack_missing",
                        "缺少中文语言包",
                        tool=tool_name,
                        path=lang_file
                    )

        desktop = Desktop(backend="uia")
        win = desktop.window(title_re=window_title)
        if not win.exists(timeout=1):
            return _error_payload("window_not_found", f"未找到窗口: {window_title}", tool=tool_name)
        img = win.capture_as_image()
        text = pytesseract.image_to_string(img, lang=language)
        result_text = text.strip()
        _emit_event(tool_name, "recognized", chars=len(result_text), window_title=window_title)
        return _ok_payload("OCR 窗口识别完成", text=result_text, window_title=window_title)
    except Exception as e:
        msg = str(e)
        if "tesseract is not installed" in msg or "not in your PATH" in msg:
            _emit_event(tool_name, "error", error=msg)
            return _error_payload("tesseract_not_found", "未找到 Tesseract", tool=tool_name)
        _emit_event(tool_name, "error", error=msg)
        return _error_payload("ocr_window_failed", msg, tool=tool_name)
