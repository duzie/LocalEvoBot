from langchain_core.tools import tool
import pyautogui
import os
import datetime

@tool
def take_screenshot(save_path: str = None):
    """
    截取当前屏幕并保存。
    
    Args:
        save_path: (可选) 保存路径。
                   如果是目录，会自动生成文件名 (screenshot_YYYYMMDD_HHMMSS.png)。
                   如果未提供，默认保存到当前运行目录的 images 文件夹。
    """
    try:
        if not save_path:
            save_path = os.path.join(os.getcwd(), "images")
        
        if os.path.isdir(save_path) or not os.path.splitext(save_path)[1]:
            os.makedirs(save_path, exist_ok=True)
            filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            final_path = os.path.join(save_path, filename)
        else:
            parent_dir = os.path.dirname(save_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            final_path = save_path

        pyautogui.screenshot(final_path)
        
        return f"截图已保存至: {final_path}"
        
    except Exception as e:
        return f"截图失败: {e}"
