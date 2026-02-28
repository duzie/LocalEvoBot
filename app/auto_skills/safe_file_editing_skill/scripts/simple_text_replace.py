from langchain_core.tools import tool
import os
import shutil
import re
from typing import Dict, Any

@tool
def simple_text_replace(
    file_path: str,
    old_text: str,
    new_text: str,
    is_regex: bool = False,
    backup: bool = True
) -> Dict[str, Any]:
    """
    对文件进行简单的文本替换（全局或单次），适用于端口号、版本号、变量名等简单修改。
    
    Args:
        file_path: 目标文件路径
        old_text: 要被替换的旧文本（或正则模式）
        new_text: 替换后的新文本
        is_regex: 是否将 old_text 视为正则表达式，默认为 False (纯文本匹配)
        backup: 是否创建备份，默认为 True
        
    Returns:
        执行结果，包含替换次数
    """
    try:
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
            
        # 读取文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception:
                return {"success": False, "error": "无法读取文件（可能是二进制文件或编码不支持）"}
            
        # 执行替换
        if is_regex:
            # 正则替换
            try:
                new_content, count = re.subn(old_text, new_text, content)
            except re.error as e:
                return {"success": False, "error": f"正则表达式错误: {str(e)}"}
        else:
            # 纯文本替换
            count = content.count(old_text)
            if count > 0:
                new_content = content.replace(old_text, new_text)
            else:
                new_content = content
                
        if count == 0:
            return {
                "success": True, 
                "message": f"未找到匹配项: '{old_text}'",
                "replaced_count": 0
            }
            
        # 创建备份
        if backup:
            shutil.copy2(file_path, file_path + ".bak")
            
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return {
            "success": True,
            "message": f"成功替换 {count} 处匹配项",
            "replaced_count": count
        }
        
    except Exception as e:
        return {"success": False, "error": f"执行出错: {str(e)}"}
