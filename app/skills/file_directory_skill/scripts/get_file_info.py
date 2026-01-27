from langchain_core.tools import tool
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


@tool
def get_file_info(
    path: Optional[str] = None,
    include_stats: bool = True
) -> Dict[str, Any]:
    """
    获取文件或目录的详细信息
    
    Args:
        path: 文件或目录路径
        include_stats: 是否包含统计信息（大小、修改时间等）
        
    Returns:
        包含文件/目录信息的字典
    """
    try:
        # 检查路径是否提供
        if path is None:
            return {
                "success": False,
                "error": "未提供路径参数"
            }
        
        # 检查路径是否存在
        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"路径不存在: {path}",
                "path": path
            }
        
        # 基本路径信息
        path_obj = Path(path)
        absolute_path = str(path_obj.absolute())
        is_dir = os.path.isdir(path)
        is_file = os.path.isfile(path)
        
        result = {
            "success": True,
            "path": path,
            "absolute_path": absolute_path,
            "name": path_obj.name,
            "parent": str(path_obj.parent),
            "is_directory": is_dir,
            "is_file": is_file,
            "exists": True
        }
        
        # 如果包含统计信息
        if include_stats:
            try:
                stat = os.stat(path)
                
                # 文件大小（如果是目录，计算总大小）
                if is_file:
                    size = stat.st_size
                else:
                    # 计算目录大小（递归）
                    total_size = 0
                    for dirpath, dirnames, filenames in os.walk(path):
                        for filename in filenames:
                            filepath = os.path.join(dirpath, filename)
                            try:
                                total_size += os.path.getsize(filepath)
                            except OSError:
                                pass
                    size = total_size
                
                # 获取扩展名（如果是文件）
                if is_file:
                    suffix = path_obj.suffix
                    stem = path_obj.stem
                else:
                    suffix = ""
                    stem = ""
                
                # 统计信息
                stats_info = {
                    "size_bytes": size,
                    "size_human": _format_size(size),
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "accessed_time": datetime.fromtimestamp(stat.st_atime).isoformat(),
                    "permissions": oct(stat.st_mode)[-3:],
                    "inode": stat.st_ino,
                    "device": stat.st_dev
                }
                
                if is_file:
                    stats_info.update({
                        "extension": suffix,
                        "filename_without_extension": stem
                    })
                
                result["stats"] = stats_info
                
                # 如果是目录，获取子项目数量
                if is_dir:
                    try:
                        items = os.listdir(path)
                        dir_items = []
                        file_items = []
                        
                        for item in items:
                            item_path = os.path.join(path, item)
                            if os.path.isdir(item_path):
                                dir_items.append(item)
                            else:
                                file_items.append(item)
                        
                        result["directory_info"] = {
                            "total_items": len(items),
                            "directories": len(dir_items),
                            "files": len(file_items),
                            "hidden_items": sum(1 for item in items if item.startswith('.'))
                        }
                    except Exception as e:
                        result["directory_info_error"] = str(e)
                
            except Exception as e:
                result["stats_error"] = str(e)
        
        # 检查是否为符号链接
        try:
            if os.path.islink(path):
                result["is_symlink"] = True
                result["symlink_target"] = os.readlink(path)
        except (OSError, AttributeError):
            pass
        
        # 检查是否为挂载点
        try:
            if os.path.ismount(path):
                result["is_mount_point"] = True
        except (OSError, AttributeError):
            pass
        
        result["timestamp"] = datetime.now().isoformat()
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "path": path if path else "unknown"
        }


def _format_size(size_bytes: int) -> str:
    """格式化文件大小为人类可读的格式"""
    if size_bytes == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    
    while size_bytes >= 1024 and unit_index < len(units) - 1:
        size_bytes /= 1024.0
        unit_index += 1
    
    return f"{size_bytes:.2f} {units[unit_index]}"