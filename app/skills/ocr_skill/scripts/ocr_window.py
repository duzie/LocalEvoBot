from langchain_core.tools import tool
import platform
import os
import shutil

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

@tool
def ocr_window(window_title: str, language: str = "chi_sim+eng"):
    """
    对指定窗口进行 OCR 文本识别。

    Args:
        window_title: 窗口标题或正则，例如 "微信" 或 ".*WeChat.*"
        language: 识别语言，例如 "chi_sim+eng"
    """
    if platform.system() != "Windows":
        return "当前仅支持 Windows OCR 窗口识别"
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
                     return f"OCR 识别失败: 缺少中文语言包。请检查 {lang_file} 是否存在。\n解决方法: 重新安装 Tesseract 并勾选 'Additional language data -> Chinese (Simplified)'。"

        desktop = Desktop(backend="uia")
        win = desktop.window(title_re=window_title)
        if not win.exists(timeout=1):
            return f"未找到窗口: {window_title}"
        img = win.capture_as_image()
        text = pytesseract.image_to_string(img, lang=language)
        return text.strip()
    except Exception as e:
        msg = str(e)
        if "tesseract is not installed" in msg or "not in your PATH" in msg:
             return f"OCR 识别失败: 未找到 Tesseract。请安装 Tesseract-OCR (https://github.com/UB-Mannheim/tesseract/wiki) 并添加到 PATH，或确保安装在默认路径 (C:\\Program Files\\Tesseract-OCR)。"
        return f"OCR 窗口识别失败: {e}"
