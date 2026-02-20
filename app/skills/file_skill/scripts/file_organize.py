from langchain_core.tools import tool
import os
import shutil
import glob
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
def file_organize(source_dir: str, target_dir: str, file_extension: str):
    """
    整理文件：将源文件夹中指定后缀名的文件移动到目标文件夹。
    
    Args:
        source_dir: 源文件夹路径 (例如 "Desktop")
        target_dir: 目标文件夹路径 (例如 "D:/screenshots")
        file_extension: 文件后缀名，不带点 (例如 "png", "txt")
    """
    tool_name = "file_organize"
    if not source_dir or not target_dir or not file_extension:
        return _error_payload("invalid_args", "source_dir、target_dir、file_extension 不能为空", tool=tool_name)
    if source_dir.lower() == "desktop" or source_dir.lower() == "桌面":
        source_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    
    if not os.path.exists(source_dir):
        return _error_payload("source_not_found", f"源目录不存在 {source_dir}", tool=tool_name)

    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir)
        except Exception as e:
            return _error_payload("target_create_failed", f"无法创建目标目录 {target_dir}: {e}", tool=tool_name)
            
    try:
        pattern = os.path.join(source_dir, f"*.{file_extension}")
        files = glob.glob(pattern)
        
        if not files:
            _emit_event(tool_name, "no_files", source_dir=source_dir, extension=file_extension)
            return _ok_payload("未找到匹配文件", moved_count=0, source_dir=source_dir, target_dir=target_dir, extension=file_extension)
            
        moved_count = 0
        for file_path in files:
            file_name = os.path.basename(file_path)
            dest_path = os.path.join(target_dir, file_name)
            shutil.move(file_path, dest_path)
            moved_count += 1
            
        _emit_event(tool_name, "moved", moved_count=moved_count, source_dir=source_dir, target_dir=target_dir, extension=file_extension)
        return _ok_payload("整理完成", moved_count=moved_count, source_dir=source_dir, target_dir=target_dir, extension=file_extension)
        
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("file_organize_failed", str(e), tool=tool_name)
