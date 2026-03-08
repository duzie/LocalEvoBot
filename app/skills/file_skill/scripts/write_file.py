"""
write_file - 写入文件内容

支持自动创建目录、备份现有文件、编码处理。
"""

from langchain_core.tools import tool
import os
import shutil
from datetime import datetime
from typing import Dict, Any, Optional
from app.skills.common import ok_payload, error_payload, SkillException


@tool
def write_file(
    file_path: str,
    content: str,
    encoding: str = 'utf-8',
    create_backup: bool = True,
    create_dirs: bool = True
) -> Dict[str, Any]:
    """
    写入文件内容
    
    Args:
        file_path: 文件路径
        content: 要写入的内容
        encoding: 文件编码，默认 utf-8
        create_backup: 如果文件存在，是否创建备份，默认 True
        create_dirs: 是否自动创建父目录，默认 True
    
    Returns:
        dict: 包含 ok 字段的字典
        - ok: True/False
        - backup_path: 备份文件路径（如果创建了备份）
        - size: 写入的字节数
    
    Example:
        result = write_file.invoke({
            "file_path": "test.py",
            "content": "print('hello')",
            "create_backup": True
        })
        if result.get("ok"):
            print("写入成功")
    """
    tool_name = "write_file"
    
    try:
        # 验证路径
        if not file_path:
            raise SkillException("invalid_path", "文件路径不能为空")
        
        # 自动创建父目录
        if create_dirs:
            parent_dir = os.path.dirname(file_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
        
        # 备份现有文件
        backup_path = None
        if create_backup and os.path.exists(file_path):
            backup_path = _create_backup(file_path)
        
        # 写入文件
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
        
        file_size = os.path.getsize(file_path)
        
        result = {
            "size": file_size,
            "encoding": encoding
        }
        
        if backup_path:
            result["backup_path"] = backup_path
        
        return ok_payload(f"成功写入 {file_size} 字节", **result)
        
    except SkillException:
        raise
    
    except Exception as e:
        return error_payload("write_error", f"写入失败：{e}", file=file_path)


def _create_backup(file_path: str) -> str:
    """创建文件备份"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(file_path)
    backup_path = f"{base}.{timestamp}.bak{ext}"
    
    try:
        shutil.copy2(file_path, backup_path)
        return backup_path
    except Exception as e:
        # 备份失败不影响主流程，记录警告
        print(f"[WARN] 备份失败：{e}")
        return None


@tool
def append_file(
    file_path: str,
    content: str,
    encoding: str = 'utf-8',
    add_newline: bool = True
) -> Dict[str, Any]:
    """
    追加内容到文件末尾
    
    Args:
        file_path: 文件路径
        content: 要追加的内容
        encoding: 文件编码，默认 utf-8
        add_newline: 是否在追加前添加换行，默认 True
    
    Returns:
        dict: 包含 ok 字段的字典
        - ok: True/False
        - size: 追加后的总大小
    """
    tool_name = "append_file"
    
    try:
        # 验证文件存在
        if not os.path.exists(file_path):
            raise SkillException("file_not_found", f"文件不存在：{file_path}")
        
        # 追加内容
        with open(file_path, 'a', encoding=encoding) as f:
            if add_newline:
                f.write('\n')
            f.write(content)
        
        file_size = os.path.getsize(file_path)
        
        return ok_payload(f"成功追加内容，总大小 {file_size} 字节", size=file_size)
        
    except SkillException:
        raise
    
    except Exception as e:
        return error_payload("append_error", f"追加失败：{e}", file=file_path)
