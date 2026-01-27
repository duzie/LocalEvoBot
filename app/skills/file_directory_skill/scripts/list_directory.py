from langchain_core.tools import tool
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


@tool
def list_directory(
    directory_path: Optional[str] = None,
    show_hidden: bool = False,
    sort_by: str = "name",
    reverse: bool = False,
    max_items: int = 100
) -> Dict[str, Any]:
    """
    列出指定目录下的文件和子目录
    
    Args:
        directory_path: 目录路径，默认为当前目录
        show_hidden: 是否显示隐藏文件和目录
        sort_by: 排序方式：name（按名称）、size（按大小）、modified（按修改时间）
        reverse: 是否反向排序
        max_items: 最大返回项目数
        
    Returns:
        包含目录信息的字典
    """
    try:
        # 设置默认目录
        if directory_path is None:
            directory_path = os.getcwd()
        
        # 检查目录是否存在
        if not os.path.exists(directory_path):
            return {
                "success": False,
                "error": f"目录不存在: {directory_path}",
                "directory": directory_path
            }
        
        if not os.path.isdir(directory_path):
            return {
                "success": False,
                "error": f"路径不是目录: {directory_path}",
                "directory": directory_path
            }
        
        # 获取目录内容
        items = []
        for item_name in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item_name)
            
            # 跳过隐藏文件（如果需要）
            if not show_hidden and item_name.startswith('.'):
                continue
            
            # 获取项目信息
            try:
                stat = os.stat(item_path)
                is_dir = os.path.isdir(item_path)
                
                item_info = {
                    "name": item_name,
                    "path": item_path,
                    "is_directory": is_dir,
                    "is_file": not is_dir,
                    "size": stat.st_size if not is_dir else 0,
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "permissions": oct(stat.st_mode)[-3:],
                    "hidden": item_name.startswith('.')
                }
                
                items.append(item_info)
            except Exception as e:
                # 如果无法获取某个项目的详细信息，只添加基本信息
                items.append({
                    "name": item_name,
                    "path": item_path,
                    "error": str(e)
                })
        
        # 排序
        if sort_by == "name":
            items.sort(key=lambda x: x.get("name", "").lower(), reverse=reverse)
        elif sort_by == "size":
            items.sort(key=lambda x: x.get("size", 0), reverse=reverse)
        elif sort_by == "modified":
            items.sort(key=lambda x: x.get("modified_time", ""), reverse=reverse)
        
        # 限制返回数量
        if len(items) > max_items:
            items = items[:max_items]
        
        # 统计信息
        dir_count = sum(1 for item in items if item.get("is_directory", False))
        file_count = sum(1 for item in items if item.get("is_file", False))
        
        return {
            "success": True,
            "directory": directory_path,
            "absolute_path": os.path.abspath(directory_path),
            "total_items": len(items),
            "directories": dir_count,
            "files": file_count,
            "items": items,
            "parent_directory": os.path.dirname(directory_path) if directory_path != os.path.sep else None,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "directory": directory_path if directory_path else "current directory"
        }