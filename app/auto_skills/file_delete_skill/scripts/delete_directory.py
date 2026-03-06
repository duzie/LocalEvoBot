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
def delete_directory(
    directory_path: Optional[str] = None,
    recursive: bool = True,
    pattern: Optional[str] = None,
    dry_run: bool = False,
    backup_before_delete: bool = False
):
    """
    删除指定目录（支持递归删除、模式过滤、预览模式）
    
    Args:
        directory_path: 要删除的目录路径
        recursive: 是否递归删除子目录，默认 True
        pattern: 文件匹配模式（如 *.tmp），为空则删除所有
        dry_run: 预览模式，不实际删除，默认 False
        backup_before_delete: 删除前是否备份，默认 False
    
    Returns:
        包含删除结果的字典
    """
    tool_name = "delete_directory"
    
    try:
        if not directory_path:
            return _error_payload("missing_parameter", "directory_path 参数不能为空", tool=tool_name)
        
        dir_path = Path(directory_path)
        
        if not dir_path.exists():
            return _error_payload("directory_not_found", f"目录不存在：{directory_path}", tool=tool_name)
        
        if not dir_path.is_dir():
            return _error_payload("not_a_directory", f"路径不是目录：{directory_path}", tool=tool_name)
        
        # 收集要删除的文件和目录
        to_delete_files: List[Path] = []
        to_delete_dirs: List[Path] = []
        
        if pattern:
            # 按模式匹配文件
            import fnmatch
            for root, dirs, files in os.walk(dir_path):
                root_path = Path(root)
                for file in files:
                    if fnmatch.fnmatch(file, pattern):
                        to_delete_files.append(root_path / file)
                if not recursive:
                    break
        else:
            # 删除所有
            if recursive:
                for root, dirs, files in os.walk(dir_path, topdown=False):
                    root_path = Path(root)
                    for file in files:
                        to_delete_files.append(root_path / file)
                    for dir_name in dirs:
                        to_delete_dirs.append(root_path / dir_name)
            else:
                # 仅删除顶层文件
                for item in dir_path.iterdir():
                    if item.is_file():
                        to_delete_files.append(item)
                    elif item.is_dir():
                        to_delete_dirs.append(item)
        
        # 统计信息
        stats = {
            "directory": str(dir_path.absolute()),
            "files_to_delete": len(to_delete_files),
            "dirs_to_delete": len(to_delete_dirs),
            "recursive": recursive,
            "pattern": pattern,
            "dry_run": dry_run,
            "backup": backup_before_delete
        }
        
        if dry_run:
            stats["files_list"] = [str(f) for f in to_delete_files[:50]]  # 限制列表长度
            stats["dirs_list"] = [str(d) for d in to_delete_dirs[:50]]
            return _ok_payload("预览模式：未执行删除", **stats)
        
        # 备份（如果需要）
        if backup_before_delete and not dry_run:
            backup_dir = dir_path.parent / f"{dir_path.name}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copytree(dir_path, backup_dir)
            stats["backup_path"] = str(backup_dir)
        
        # 执行删除
        deleted_files = 0
        deleted_dirs = 0
        
        # 先删除文件
        for file_path in to_delete_files:
            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted_files += 1
            except Exception as e:
                stats[f"file_delete_error_{file_path.name}"] = str(e)
        
        # 再删除目录（从内到外）
        if recursive and not pattern:
            # 递归模式下，删除整个目录树
            try:
                shutil.rmtree(dir_path)
                deleted_dirs = len(to_delete_dirs) + 1  # +1 是根目录
                stats["root_dir_deleted"] = True
            except Exception as e:
                return _error_payload("delete_failed", f"删除目录失败：{e}", tool=tool_name, **stats)
        else:
            # 非递归或模式匹配，只删除空子目录
            for dir_path_item in sorted(to_delete_dirs, key=lambda x: len(str(x)), reverse=True):
                try:
                    if dir_path_item.exists() and dir_path_item.is_dir():
                        # 只删除空目录
                        if not any(dir_path_item.iterdir()):
                            dir_path_item.rmdir()
                            deleted_dirs += 1
                except Exception as e:
                    stats[f"dir_delete_error_{dir_path_item.name}"] = str(e)
        
        stats["files_deleted"] = deleted_files
        stats["dirs_deleted"] = deleted_dirs
        
        _emit_event(tool_name, "success", **stats)
        return _ok_payload("删除完成", **stats)
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误：{e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err