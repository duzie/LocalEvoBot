from langchain_core.tools import tool
import os
import shutil
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
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
def safe_delete_files(
    file_paths: Optional[List[str]] = None,
    backup_dir: Optional[str] = None,
    dry_run: bool = False
):
    """
    安全删除文件（支持备份后删除）
    
    Args:
        file_paths: 要删除的文件路径列表
        backup_dir: 备份目录，为空则不备份
        dry_run: 预览模式，不实际删除，默认 False
    
    Returns:
        包含删除结果的字典
    """
    tool_name = "safe_delete_files"
    
    try:
        if not file_paths:
            return _error_payload("missing_parameter", "file_paths 参数不能为空", tool=tool_name)
        
        # 转换为 Path 对象并验证
        files_to_delete: List[Path] = []
        not_found_files = []
        not_file_paths = []
        
        for file_path in file_paths:
            p = Path(file_path)
            if not p.exists():
                not_found_files.append(file_path)
            elif not p.is_file():
                not_file_paths.append(file_path)
            else:
                files_to_delete.append(p)
        
        stats = {
            "total_requested": len(file_paths),
            "files_found": len(files_to_delete),
            "files_not_found": len(not_found_files),
            "not_files": len(not_file_paths),
            "dry_run": dry_run,
            "backup_enabled": backup_dir is not None
        }
        
        if not_found_files:
            stats["not_found_list"] = not_found_files[:20]
        if not_file_paths:
            stats["not_file_list"] = not_file_paths[:20]
        
        if not files_to_delete:
            return _error_payload("no_files_to_delete", "没有找到可删除的文件", **stats, tool=tool_name)
        
        # 备份（如果需要）
        backup_path = None
        if backup_dir and not dry_run:
            backup_root = Path(backup_dir)
            backup_root.mkdir(parents=True, exist_ok=True)
            backup_path = backup_root / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_path.mkdir(parents=True, exist_ok=True)
            
            backed_up = 0
            for file_path in files_to_delete:
                try:
                    # 保持相对路径结构
                    rel_path = file_path.relative_to(file_path.anchor)
                    dest = backup_path / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, dest)
                    backed_up += 1
                except Exception as e:
                    stats[f"backup_error_{file_path.name}"] = str(e)
            
            stats["files_backed_up"] = backed_up
            stats["backup_location"] = str(backup_path)
        
        if dry_run:
            stats["files_to_delete"] = [str(f) for f in files_to_delete[:50]]
            return _ok_payload("预览模式：未执行删除", **stats)
        
        # 执行删除
        deleted_count = 0
        errors = []
        
        for file_path in files_to_delete:
            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted_count += 1
            except Exception as e:
                errors.append(f"{file_path}: {str(e)}")
        
        stats["files_deleted"] = deleted_count
        stats["errors"] = errors[:20]
        
        _emit_event(tool_name, "success", **stats)
        return _ok_payload(f"删除完成，成功删除 {deleted_count}/{len(files_to_delete)} 个文件", **stats)
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误：{e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err