from langchain_core.tools import tool
import os
import fnmatch
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


@tool
def search_files(
    directory_path: Optional[str] = None,
    pattern: Optional[str] = None,
    name_contains: Optional[str] = None,
    extension: Optional[str] = None,
    recursive: bool = False,
    max_results: int = 50
) -> Dict[str, Any]:
    """
    在目录中搜索文件
    
    Args:
        directory_path: 搜索目录路径
        pattern: 搜索模式（支持通配符）
        name_contains: 文件名包含的关键词
        extension: 文件扩展名
        recursive: 是否递归搜索子目录
        max_results: 最大返回结果数
        
    Returns:
        包含搜索结果的信息字典
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
        
        # 准备搜索条件
        search_conditions = []
        
        if pattern:
            search_conditions.append(f"模式: {pattern}")
        
        if name_contains:
            search_conditions.append(f"包含: {name_contains}")
        
        if extension:
            # 确保扩展名以点开头
            if not extension.startswith('.'):
                extension = '.' + extension
            search_conditions.append(f"扩展名: {extension}")
        
        # 搜索文件
        results = []
        searched_dirs = 0
        
        if recursive:
            # 递归搜索
            for root, dirs, files in os.walk(directory_path):
                searched_dirs += 1
                
                for filename in files:
                    filepath = os.path.join(root, filename)
                    
                    # 应用搜索条件
                    if _matches_search_criteria(filename, filepath, pattern, name_contains, extension):
                        try:
                            stat = os.stat(filepath)
                            relative_path = os.path.relpath(filepath, directory_path)
                            
                            results.append({
                                "name": filename,
                                "path": filepath,
                                "relative_path": relative_path,
                                "directory": root,
                                "size": stat.st_size,
                                "size_human": _format_size(stat.st_size),
                                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                                "extension": os.path.splitext(filename)[1]
                            })
                            
                            # 达到最大结果数时停止
                            if len(results) >= max_results:
                                break
                        except Exception as e:
                            # 跳过无法访问的文件
                            continue
                
                # 达到最大结果数时停止遍历
                if len(results) >= max_results:
                    break
        else:
            # 非递归搜索
            searched_dirs = 1
            try:
                for filename in os.listdir(directory_path):
                    filepath = os.path.join(directory_path, filename)
                    
                    # 只处理文件，跳过目录
                    if not os.path.isfile(filepath):
                        continue
                    
                    # 应用搜索条件
                    if _matches_search_criteria(filename, filepath, pattern, name_contains, extension):
                        try:
                            stat = os.stat(filepath)
                            
                            results.append({
                                "name": filename,
                                "path": filepath,
                                "relative_path": filename,
                                "directory": directory_path,
                                "size": stat.st_size,
                                "size_human": _format_size(stat.st_size),
                                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                                "extension": os.path.splitext(filename)[1]
                            })
                            
                            # 达到最大结果数时停止
                            if len(results) >= max_results:
                                break
                        except Exception as e:
                            # 跳过无法访问的文件
                            continue
            except Exception as e:
                return {
                    "success": False,
                    "error": f"无法读取目录内容: {str(e)}",
                    "directory": directory_path
                }
        
        # 准备返回结果
        result_data = {
            "success": True,
            "directory": directory_path,
            "absolute_path": os.path.abspath(directory_path),
            "search_conditions": search_conditions,
            "recursive": recursive,
            "searched_directories": searched_dirs,
            "total_results": len(results),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
        # 如果达到最大结果数，添加提示
        if len(results) >= max_results:
            result_data["note"] = f"达到最大结果数限制 ({max_results})，可能还有更多匹配文件"
        
        return result_data
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "directory": directory_path if directory_path else "current directory"
        }


def _matches_search_criteria(
    filename: str,
    filepath: str,
    pattern: Optional[str] = None,
    name_contains: Optional[str] = None,
    extension: Optional[str] = None
) -> bool:
    """检查文件是否匹配搜索条件"""
    # 检查是否为文件
    if not os.path.isfile(filepath):
        return False
    
    # 检查模式匹配
    if pattern and not fnmatch.fnmatch(filename, pattern):
        return False
    
    # 检查名称包含
    if name_contains and name_contains.lower() not in filename.lower():
        return False
    
    # 检查扩展名
    if extension:
        # 确保扩展名以点开头
        if not extension.startswith('.'):
            extension = '.' + extension
        
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext != extension.lower():
            return False
    
    return True


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