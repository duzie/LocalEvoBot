from langchain_core.tools import tool
import subprocess
import platform

@tool
def check_process_status(process_name: str):
    """
    检查指定名称的进程是否正在运行。
    
    Args:
        process_name: 进程名称，例如 "Weixin.exe", "notepad.exe", "chrome.exe"
    """
    system = platform.system()
    try:
        if system == "Windows":
            output = subprocess.check_output(
                f'tasklist /FI "IMAGENAME eq {process_name}"',
                shell=True
            ).decode('gbk', errors='ignore')
            if process_name.lower() in output.lower():
                return f"进程 {process_name} 正在运行"
            else:
                return f"未找到进程 {process_name}"
        else:
            return "当前仅支持 Windows 进程检查"
    except Exception as e:
        return f"检查进程失败: {e}"
