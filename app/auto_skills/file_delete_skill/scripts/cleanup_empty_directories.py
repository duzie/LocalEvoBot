from langchain_core.tools import tool
import os
import json
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
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
def cleanup_empty_directories(
    root_path: str = ".",
    dry_run: bool = False
):
    """
    清理空目录（递归删除所有空子目录）
    
    Args:
        root_path: 根目录路径，默认当前目录
        dry_run: 预览模式，不实际删除，默认 False
    
    Returns:
        包含清理结果的字典
    """
    tool_name = "cleanup_empty_directories"
    
    try:
        root = Path(root_path)
        
        if not root.exists():
            return _error_payload("directory_not_found", f"目录不存在：{root_path}", tool=tool_name)
        
        if not root.is_dir():
            return _error_payload("not_a_directory", f"路径不是目录：{root_path}", tool=tool_name)
        
        # 收集所有空目录（从内到外）
        empty_dirs: List[Path] = []
        
        # 自底向上遍历，先检查深层目录
        for dirpath, dirnames, filenames in os.walk(root, topdown=False):
            current_dir = Path(dirpath)
            # 检查是否为空目录（无文件且无子目录）
            try:
                if not any(current_dir.iterdir()):
                    # 不删除根目录本身
                    if current_dir != root:
                        empty_dirs.append(current_dir)
            except PermissionError:
                continue
        
        stats = {
            "root_path": str(root.absolute()),
            "empty_directories_found": len(empty_dirs),
            "empty_directories_list": [str(d) for d in empty_dirs[:100]],  # 限制列表长度
            "dry_run": dry_run
        }
        
        if dry_run:
            return _ok_payload("预览模式：未执行删除", **stats)
        
        # 执行删除
        deleted_count = 0
        errors = []
        
        for empty_dir in empty_dirs:
            try:
                if empty_dir.exists() and empty_dir.is_dir():
                    empty_dir.rmdir()
                    deleted_count += 1
            except Exception as e:
                errors.append(f"{empty_dir}: {str(e)}")
        
        stats["directories_deleted"] = deleted_count
        stats["errors"] = errors[:20]  # 限制错误数量
        
        _emit_event(tool_name, "success", **stats)
        return _ok_payload(f"清理完成，删除 {deleted_count} 个空目录", **stats)
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误：{e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err