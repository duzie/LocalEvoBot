"""
incremental_file_edit - 增量文件编辑

使用正则表达式定位，支持插入/替换/删除操作。
"""

from langchain_core.tools import tool
import os
import re
import shutil
from datetime import datetime
from typing import Dict, Any


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


@tool
def incremental_file_edit(file_path: str, operation: str, target_pattern: str, content: str, create_backup: bool = True) -> Dict[str, Any]:
    """
    增量编辑文件，只修改指定部分（使用正则表达式定位）
    
    Args:
        file_path: 目标文件路径
        operation: 操作类型：insert_before/insert_after/replace/delete
        target_pattern: 目标位置模式（正则表达式）
        content: 要插入或替换的内容
        create_backup: 是否创建备份
    
    Returns:
        dict: 包含 ok 字段的字典
        - ok: True/False
        - matches: 匹配到的次数
        - backup_path: 备份文件路径（如果创建了备份）
    
    Example:
        # 在某个函数后插入新函数
        incremental_file_edit.invoke({
            "file_path": "utils.py",
            "operation": "insert_after",
            "target_pattern": r"def helper_function\\(\\):.*?(?=\\ndef|$)",
            "content": "\\n\\ndef new_function():\\n    pass\\n"
        })
    """
    tool_name = "incremental_file_edit"
    
    try:
        # 验证操作类型
        valid_operations = ["insert_before", "insert_after", "replace", "delete"]
        if operation not in valid_operations:
            return _error_payload("invalid_operation", 
                f"无效的操作类型：{operation}，支持：{', '.join(valid_operations)}",
                tool=tool_name)
        
        # 验证文件存在
        if not os.path.exists(file_path):
            return _error_payload("file_not_found", f"文件不存在：{file_path}", tool=tool_name)
        
        # 备份文件
        backup_path = None
        if create_backup:
            backup_path = _create_backup(file_path)
        
        # 读取文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content_lines = f.readlines()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='gbk') as f:
                content_lines = f.readlines()
        
        full_content = ''.join(content_lines)
        
        # 执行正则匹配
        try:
            matches = list(re.finditer(target_pattern, full_content, re.MULTILINE | re.DOTALL))
        except re.error as e:
            return _error_payload("invalid_regex", f"正则表达式错误：{e}", tool=tool_name)
        
        if not matches:
            return _error_payload("no_matches", 
                f"未找到匹配的模式：{target_pattern}", 
                tool=tool_name, pattern=target_pattern)
        
        # 执行操作（从后向前处理，避免位置偏移）
        modified = False
        for match in reversed(matches):
            modified = True
            
            if operation == "delete":
                # 删除匹配内容
                full_content = full_content[:match.start()] + full_content[match.end():]
            
            elif operation == "replace":
                # 替换匹配内容
                full_content = full_content[:match.start()] + content + full_content[match.end():]
            
            elif operation == "insert_before":
                # 在匹配内容前插入
                full_content = full_content[:match.start()] + content + full_content[match.start():]
            
            elif operation == "insert_after":
                # 在匹配内容后插入
                full_content = full_content[:match.end()] + content + full_content[match.end():]
        
        if not modified:
            return _error_payload("no_modifications", "未执行任何修改", tool=tool_name)
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(full_content)
        
        result = {
            "matches": len(matches),
            "operation": operation
        }
        
        if backup_path:
            result["backup_path"] = backup_path
        
        return _ok_payload(f"成功执行 {operation} 操作，影响 {len(matches)} 处", **result)
        
    except Exception as e:
        return _error_payload("edit_error", f"编辑失败：{e}", tool=tool_name, file=file_path)


def _create_backup(file_path: str) -> str:
    """创建文件备份"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(file_path)
    backup_path = f"{base}.{timestamp}.bak{ext}"
    
    try:
        shutil.copy2(file_path, backup_path)
        return backup_path
    except Exception as e:
        print(f"[WARN] 备份失败：{e}")
        return None
