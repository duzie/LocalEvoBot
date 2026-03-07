"""文件系统路由 - 提供文件搜索和列表功能"""
import os
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

router = APIRouter()

@router.get("/list")
async def list_files(
    path: str = Query(default=".", description="搜索根目录"),
    recursive: bool = Query(default=True, description="是否递归搜索"),
    max_depth: int = Query(default=10, description="最大搜索深度"),
    max_results: int = Query(default=1000, description="最大返回结果数")
):
    """
    列出指定目录下的所有文件
    返回文件路径列表，用于前端拖拽文件时匹配完整路径
    """
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"路径不存在: {path}")
    
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"不是目录: {path}")
    
    items = []
    count = 0
    
    def scan_dir(current_path: str, depth: int = 0):
        nonlocal count
        if depth > max_depth or count >= max_results:
            return
        
        try:
            for entry in os.scandir(current_path):
                if count >= max_results:
                    break
                
                # 跳过隐藏文件和目录
                if entry.name.startswith('.'):
                    continue
                
                # 跳过常见的排除目录
                if entry.is_dir() and entry.name in {'node_modules', '__pycache__', '.git', 'venv', 'env', '.venv', 'dist', 'build'}:
                    continue
                
                if entry.is_file():
                    # 计算相对路径
                    abs_path = entry.path
                    rel_path = os.path.relpath(abs_path, path)
                    
                    items.append({
                        "name": entry.name,
                        "path": abs_path.replace('\\', '/'),
                        "rel_path": rel_path.replace('\\', '/'),
                        "size": entry.stat().st_size,
                        "is_file": True
                    })
                    count += 1
                elif entry.is_dir() and recursive:
                    scan_dir(entry.path, depth + 1)
        except PermissionError:
            pass  # 跳过无权限的目录
        except Exception as e:
            pass  # 跳过其他错误
    
    scan_dir(path)
    
    return {
        "success": True,
        "root": path,
        "count": len(items),
        "items": items
    }


@router.get("/search")
async def search_files(
    path: str = Query(default=".", description="搜索根目录"),
    name: str = Query(default="", description="文件名关键词"),
    extension: str = Query(default="", description="文件扩展名"),
    max_results: int = Query(default=100, description="最大返回结果数")
):
    """
    搜索指定目录下匹配的文件
    """
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"路径不存在: {path}")
    
    items = []
    name_lower = name.lower() if name else ""
    ext_lower = extension.lower().lstrip('.') if extension else ""
    
    for root, dirs, files in os.walk(path):
        # 跳过隐藏目录和排除目录
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'node_modules', '__pycache__', '.git', 'venv', 'env', '.venv', 'dist', 'build'}]
        
        for file in files:
            if len(items) >= max_results:
                break
            
            # 文件名过滤
            if name_lower and name_lower not in file.lower():
                continue
            
            # 扩展名过滤
            if ext_lower and not file.lower().endswith('.' + ext_lower):
                continue
            
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, path)
            
            items.append({
                "name": file,
                "path": abs_path.replace('\\', '/'),
                "rel_path": rel_path.replace('\\', '/'),
                "size": os.path.getsize(abs_path),
                "is_file": True
            })
    
    return {
        "success": True,
        "root": path,
        "count": len(items),
        "items": items
    }