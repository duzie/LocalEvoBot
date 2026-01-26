from langchain_core.tools import tool
import subprocess
import platform
import os
import time

@tool
def open_notepad():
    """
    打开 Windows 记事本程序。无需参数。
    如果是 macOS，则尝试打开 TextEdit。
    """
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen("notepad.exe")
            return "已启动记事本 (notepad.exe)"
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", "TextEdit"])
            return "已启动 TextEdit"
        else:
            return f"不支持的操作系统: {system}"
    except Exception as e:
        return f"启动失败: {e}"

@tool
def read_notepad_text(window_title: str = None, file_path: str = None, try_open: bool = True):
    """
    读取记事本中的文本内容或直接读取文件内容。

    Args:
        window_title: 记事本窗口标题正则，未提供时自动匹配包含“记事本/Notepad”的窗口
        file_path: 文件路径，若提供且存在则直接读取文件内容
        try_open: 当未找到窗口但提供了 file_path 时，尝试用记事本打开并读取
    """
    system = platform.system()
    if system != "Windows":
        return "当前仅支持 Windows"
    if file_path and os.path.exists(file_path):
        try:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                with open(file_path, "r", encoding="gbk", errors="ignore") as f:
                    return f.read()
        except Exception as e:
            return f"读取文件失败: {e}"
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        pattern = window_title or r".*(记事本|Notepad).*"
        win = desktop.window(title_re=pattern)
        if not win.exists(timeout=2):
            if file_path and try_open:
                try:
                    subprocess.Popen(["notepad.exe", file_path])
                    time.sleep(1.5)
                    base = os.path.basename(file_path)
                    alt = rf".*{base}.*"
                    win = desktop.window(title_re=alt)
                    if not win.exists(timeout=3):
                        win = desktop.window(title_re=r".*(记事本|Notepad).*")
                except Exception:
                    pass
            else:
                return f"未找到记事本窗口: {pattern}"
        try:
            win.set_focus()
        except Exception:
            pass
        try:
            edit = win.child_window(control_type="Edit")
            if edit.exists(timeout=1):
                return edit.window_text()
        except Exception:
            pass
        try:
            edit_list = win.descendants(control_type="Edit")
            if edit_list:
                return edit_list[0].window_text()
        except Exception:
            pass
        return "未找到可读取的文本控件"
    except Exception as e:
        return f"读取失败: {e}"
