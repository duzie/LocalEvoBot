from langchain_core.tools import tool
import pyautogui
import os
import shutil
import platform

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
def ocr_screen(image_path: str = None, language: str = "chi_sim+eng"):
    """
    对当前屏幕进行 OCR 文本识别。

    Args:
        image_path: (可选) 图片文件的绝对路径。如果不传，则截取当前屏幕。
        language: 识别语言，例如 "chi_sim+eng"
    """
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
            os.environ["TESSDATA_PREFIX"] = tessdata_dir

            if "chi_sim" in language:
                lang_file = os.path.join(tessdata_dir, "chi_sim.traineddata")
                if not os.path.exists(lang_file):
                     return f"OCR 识别失败: 缺少中文语言包。请检查 {lang_file} 是否存在。\n解决方法: 重新安装 Tesseract 并勾选 'Additional language data -> Chinese (Simplified)'。"

        text = pytesseract.image_to_string(Image.open(image_path), lang=language)
        return text.strip()
    except Exception as e:
        msg = str(e)
        if "tesseract is not installed" in msg or "not in your PATH" in msg:
             return f"OCR 识别失败: 未找到 Tesseract。请安装 Tesseract-OCR (https://github.com/UB-Mannheim/tesseract/wiki) 并添加到 PATH，或确保安装在默认路径 (C:\\Program Files\\Tesseract-OCR)。"
        return f"OCR 识别失败: {e}"
    finally:
        if temp_screenshot and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass
