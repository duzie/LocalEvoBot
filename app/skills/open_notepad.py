from langchain_core.tools import tool
import subprocess
import platform

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
