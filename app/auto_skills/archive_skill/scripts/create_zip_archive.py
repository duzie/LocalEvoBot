from langchain_core.tools import tool
import os
import zipfile
import fnmatch
from pathlib import Path
from typing import List, Optional


@tool
def create_zip_archive(
    source_dir: str,
    output_path: Optional[str] = None,
    exclude_patterns: Optional[List[str]] = None,
    include_hidden: bool = False
) -> dict:
    """
    创建zip压缩文件，将指定目录打包成zip文件
    
    Args:
        source_dir: 源目录路径
        output_path: 输出zip文件路径，如果为None则使用source_dir名称
        exclude_patterns: 排除模式列表，如['__pycache__', '*.pyc']
        include_hidden: 是否包含隐藏文件
    
    Returns:
        包含操作结果的字典
    """
    try:
        # 验证源目录
        source_path = Path(source_dir)
        if not source_path.exists():
            return {"success": False, "error": f"源目录不存在: {source_dir}"}
        if not source_path.is_dir():
            return {"success": False, "error": f"路径不是目录: {source_dir}"}
        
        # 设置默认输出路径
        if output_path is None:
            output_path = str(source_path.parent / f"{source_path.name}.zip")
        else:
            output_path = str(Path(output_path))
        
        # 确保输出目录存在
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 默认排除模式
        if exclude_patterns is None:
            exclude_patterns = ['__pycache__', '*.pyc', '*.pyo', '*.pyd', '.git', '.svn', '.DS_Store']
        
        # 统计信息
        total_files = 0
        total_size = 0
        
        # 创建zip文件
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                # 过滤排除的目录
                dirs[:] = [d for d in dirs if not any(
                    fnmatch.fnmatch(d, pattern) for pattern in exclude_patterns
                )]
                
                # 过滤排除的文件
                filtered_files = []
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, source_dir)
                    
                    # 检查是否隐藏文件
                    if not include_hidden and file.startswith('.'):
                        continue
                    
                    # 检查是否匹配排除模式
                    exclude = False
                    for pattern in exclude_patterns:
                        if fnmatch.fnmatch(file, pattern) or fnmatch.fnmatch(rel_path, pattern):
                            exclude = True
                            break
                    
                    if not exclude:
                        filtered_files.append(file)
                
                # 添加文件到zip
                for file in filtered_files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, source_dir)
                    
                    try:
                        # 获取文件信息
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        total_files += 1
                        
                        # 添加到zip
                        zipf.write(file_path, rel_path)
                        
                    except Exception as e:
                        # 如果单个文件失败，继续处理其他文件
                        print(f"警告: 无法添加文件 {file_path}: {e}")
                        continue
        
        # 检查是否成功添加了文件
        if total_files == 0:
            return {
                "success": False,
                "error": "没有文件被添加到压缩包中，可能是所有文件都被排除或目录为空",
                "output_path": output_path
            }
        
        # 获取输出文件大小
        output_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        
        return {
            "success": True,
            "output_path": output_path,
            "output_size": output_size,
            "total_files": total_files,
            "total_size": total_size,
            "compression_ratio": f"{output_size/total_size:.1%}" if total_size > 0 else "N/A",
            "message": f"成功打包 {total_files} 个文件到 {output_path}，压缩率: {output_size/total_size:.1%}" if total_size > 0 else f"成功打包 {total_files} 个文件到 {output_path}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"创建zip文件时出错: {str(e)}",
            "output_path": output_path if 'output_path' in locals() else None
        }