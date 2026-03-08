"""
quick_edit - 快速文件编辑工具

⚠️ 警告：这个工具不会验证语法，不会记录经验
仅用于简单修改，复杂修改请用 safe_file_editing_skill
"""

from langchain_core.tools import tool
import os
import shutil
from datetime import datetime
from typing import Dict, Any


@tool
def quick_edit(file_path: str, old_text: str, new_text: str) -> Dict[str, Any]:
    """
    快速文件编辑工具
    
    ⚠️ 警告：这个工具不会验证语法，不会记录经验
    仅用于简单修改，复杂修改请用 safe_file_editing_skill
    
    Args:
        file_path: 文件路径
        old_text: 要替换的文本（必须完全匹配，包括空格和换行）
        new_text: 新文本
    
    Returns:
        {
            "ok": True/False,
            "message": "修改成功",
            "backup_path": "备份文件路径" (如果成功)
        }
    
    Example:
        quick_edit.invoke({
            "file_path": "config.py",
            "old_text": "DEBUG = True",
            "new_text": "DEBUG = False"
        })
    """
    tool_name = "quick_edit"
    
    try:
        # 1. 检查文件
        if not os.path.exists(file_path):
            return {
                "ok": False,
                "error": f"文件不存在：{file_path}"
            }
        
        if not os.path.isfile(file_path):
            return {
                "ok": False,
                "error": f"路径不是文件：{file_path}"
            }
        
        # 2. 读取文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception:
                return {
                    "ok": False,
                    "error": "无法读取文件（可能是二进制文件或编码不支持）"
                }
        
        # 3. 检查匹配
        if old_text not in content:
            # 尝试给出更友好的错误提示
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if old_text[:20] in line:  # 查找部分匹配
                    return {
                        "ok": False,
                        "error": f"找不到完全匹配的文本（在第{i+1}行找到相似内容）",
                        "suggestion": "请检查空格、换行和缩进是否完全匹配"
                    }
            
            return {
                "ok": False,
                "error": "找不到要替换的文本",
                "suggestion": "请检查 old_text 是否完全匹配（包括空格和换行）"
            }
        
        # 4. 创建备份
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base, ext = os.path.splitext(file_path)
        backup_path = f"{base}.{timestamp}.bak{ext}"
        
        try:
            shutil.copy2(file_path, backup_path)
        except Exception as e:
            # 备份失败不影响主流程，但记录警告
            backup_path = None
            print(f"[WARN] 备份失败：{e}")
        
        # 5. 替换
        new_content = content.replace(old_text, new_text)
        
        # 6. 写回
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            return {
                "ok": False,
                "error": f"写入失败：{e}"
            }
        
        # 7. 返回结果
        result = {
            "ok": True,
            "message": "修改成功",
            "replaced_count": content.count(old_text)
        }
        
        if backup_path:
            result["backup_path"] = backup_path
        
        return result
        
    except Exception as e:
        return {
            "ok": False,
            "error": f"编辑失败：{e}"
        }


@tool
def quick_append(file_path: str, text: str, add_newline: bool = True) -> Dict[str, Any]:
    """
    快速追加文本到文件末尾
    
    Args:
        file_path: 文件路径
        text: 要追加的文本
        add_newline: 是否在追加前添加换行（默认 True）
    
    Returns:
        {
            "ok": True/False,
            "message": "追加成功",
            "new_size": 新文件大小
        }
    """
    tool_name = "quick_append"
    
    try:
        # 检查文件
        if not os.path.exists(file_path):
            return {
                "ok": False,
                "error": f"文件不存在：{file_path}"
            }
        
        # 追加
        try:
            with open(file_path, 'a', encoding='utf-8') as f:
                if add_newline:
                    f.write('\n')
                f.write(text)
        except Exception as e:
            return {
                "ok": False,
                "error": f"写入失败：{e}"
            }
        
        # 获取新大小
        new_size = os.path.getsize(file_path)
        
        return {
            "ok": True,
            "message": "追加成功",
            "new_size": new_size
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": f"追加失败：{e}"
        }
