from langchain_core.tools import tool
import subprocess
import platform
import json

@tool
def list_processes(keyword: str = None, as_json: bool = False):
    """
    列出当前系统的进程清单，并可按关键词过滤。
    
    Args:
        keyword: (可选) 关键词筛选，忽略大小写
        as_json: (可选) 是否以 JSON 数组返回
    """
    system = platform.system()
    try:
        if system == "Windows":
            output = subprocess.check_output("tasklist", shell=True).decode("gbk", errors="ignore")
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            lines = [line for line in lines if not line.lower().startswith("image name") and not set(line) == {"="}]
            if keyword:
                kw = keyword.lower()
                lines = [line for line in lines if kw in line.lower()]
            if as_json:
                return json.dumps(lines, ensure_ascii=False)
            return "\n".join(lines)
        if system in ["Darwin", "Linux"]:
            output = subprocess.check_output(["ps", "-A", "-o", "pid,comm"], text=True)
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            if keyword:
                kw = keyword.lower()
                lines = [line for line in lines if kw in line.lower()]
            if as_json:
                return json.dumps(lines, ensure_ascii=False)
            return "\n".join(lines)
        return f"不支持的操作系统: {system}"
    except Exception as e:
        return f"列出进程失败: {e}"
