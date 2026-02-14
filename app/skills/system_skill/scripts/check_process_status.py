from langchain_core.tools import tool
import subprocess
import platform
import os
import json

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

def _default_shell_encoding():
    return "gbk" if platform.system() == "Windows" else "utf-8"

@tool
def run_shell_command(command: str, cwd: str = None, timeout: int = 60, as_json: bool = False):
    """
    直接执行终端命令并返回输出。
    """
    cmd = str(command or "").strip()
    if not cmd:
        return {"ok": False, "error": "command 不能为空"}
    if cwd:
        cwd_path = os.path.abspath(str(cwd))
        if not os.path.isdir(cwd_path):
            return {"ok": False, "error": f"cwd 不存在: {cwd_path}"}
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd if cwd else None,
            capture_output=True,
            text=True,
            encoding=_default_shell_encoding(),
            errors="ignore",
            timeout=max(1, int(timeout or 60))
        )
        output = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        combined = output
        if stderr:
            combined = (combined + "\n" if combined else "") + stderr
        payload = {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "output": combined
        }
        return json.dumps(payload, ensure_ascii=False) if as_json else payload
    except Exception as e:
        return {"ok": False, "error": str(e)}
