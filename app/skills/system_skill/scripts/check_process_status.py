from langchain_core.tools import tool
import subprocess
import platform
import os
import json
from datetime import datetime
from typing import Any, Dict
from web.backend.shared import shared

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
def check_process_status(process_name: str):
    """
    检查指定名称的进程是否正在运行。
    
    Args:
        process_name: 进程名称，例如 "Weixin.exe", "notepad.exe", "chrome.exe"
    """
    tool_name = "check_process_status"
    name = str(process_name or "").strip()
    if not name:
        return _error_payload("invalid_args", "process_name 不能为空", tool=tool_name)
    system = platform.system()
    try:
        if system == "Windows":
            output = subprocess.check_output(
                f'tasklist /FI "IMAGENAME eq {name}"',
                shell=True
            ).decode('gbk', errors='ignore')
            if name.lower() in output.lower():
                _emit_event(tool_name, "running", process=name)
                return _ok_payload("进程正在运行", process=name, running=True)
            _emit_event(tool_name, "not_found", process=name)
            return _ok_payload("未找到进程", process=name, running=False)
        return _error_payload("unsupported_platform", "当前仅支持 Windows 进程检查", tool=tool_name)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("check_failed", str(e), tool=tool_name, process=name)

def _default_shell_encoding():
    return "gbk" if platform.system() == "Windows" else "utf-8"

def _decode_bytes(data: bytes):
    if data is None:
        return ""
    candidates = ["utf-8-sig", "utf-8", "gb18030", "gbk", "cp936", "latin-1"]
    for enc in candidates:
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")

@tool
def run_shell_command(command: str, cwd: str = None, timeout: int = 60, as_json: bool = False):
    """
    直接执行终端命令并返回输出。
    """
    tool_name = "run_shell_command"
    cmd = str(command or "").strip()
    if not cmd:
        return _error_payload("invalid_args", "command 不能为空", tool=tool_name)
    if cwd:
        cwd_path = os.path.abspath(str(cwd))
        if not os.path.isdir(cwd_path):
            return _error_payload("invalid_args", f"cwd 不存在: {cwd_path}", tool=tool_name)
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd if cwd else None,
            capture_output=True,
            text=False,
            timeout=max(1, int(timeout or 60))
        )
        output = _decode_bytes(result.stdout).strip()
        stderr = _decode_bytes(result.stderr).strip()
        combined = output
        if stderr:
            combined = (combined + "\n" if combined else "") + stderr
        payload = _ok_payload("命令执行完成", returncode=result.returncode, output=combined, ok=(result.returncode == 0))
        if result.returncode != 0:
            payload["ok"] = False
            payload["error"] = combined or "命令执行失败"
            payload["error_info"] = {"code": "command_failed", "message": payload["error"]}
        _emit_event(tool_name, "done", returncode=result.returncode)
        return json.dumps(payload, ensure_ascii=False) if as_json else payload
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("command_failed", str(e), tool=tool_name)
