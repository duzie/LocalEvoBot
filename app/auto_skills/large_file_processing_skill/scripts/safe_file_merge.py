from langchain_core.tools import tool
import os
import shutil
import re
from typing import Dict, Any, Optional
from langchain.tools import tool


@tool
def safe_file_merge(target_file: str, new_content: str, insert_position: str = "end", 
                   backup_suffix: str = ".bak", anchor_pattern: str = "", require_unique: bool = True, ensure_present: bool = True, skip_if_present: bool = True) -> Dict[str, Any]:
    """
    安全合并文件内容（读取原始内容，合并新内容，写入备份）
    
    Args:
        target_file: 目标文件路径
        new_content: 要合并的新内容
        insert_position: 插入位置：
            - "beginning": 文件开头
            - "end": 文件末尾（默认）
            - "after_last_class": 最后一个类定义之后
            - "after_line:X": 在第X行之后插入（X为行号）
            - "after_pattern": 在锚点模式命中行之后插入（配合 anchor_pattern）
            - "before_pattern": 在锚点模式命中行之前插入（配合 anchor_pattern）
        backup_suffix: 备份文件后缀，默认".bak"
        anchor_pattern: 锚点正则（用于 after_pattern）
        require_unique: 锚点是否要求唯一命中
        ensure_present: 写入后校验 new_content 是否存在
        skip_if_present: 内容已存在则跳过写入
        
    Returns:
        包含操作结果的字典
    """
    try:
        # 检查目标文件是否存在
        if not os.path.exists(target_file):
            # 如果文件不存在，直接创建新文件
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return {
                "success": True,
                "action": "created_new_file",
                "file_path": target_file,
                "content_size": len(new_content),
                "message": f"文件不存在，已创建新文件并写入内容"
            }
        
        # 创建备份
        backup_file = target_file + backup_suffix
        shutil.copy2(target_file, backup_file)
        
        # 读取原始内容
        with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
            original_content = f.read()
        
        if skip_if_present and new_content and new_content in original_content:
            return {
                "success": True,
                "action": "skipped",
                "file_path": target_file,
                "backup_file": backup_file,
                "message": "内容已存在，已跳过"
            }
        
        # 根据插入位置处理
        if insert_position == "beginning":
            merged_content = new_content + "\n\n" + original_content
        elif insert_position == "end":
            merged_content = original_content + "\n\n" + new_content
        elif insert_position == "after_last_class":
            # 查找最后一个类定义的结束位置
            lines = original_content.split('\n')
            last_class_end = len(lines)
            
            # 简单查找最后一个"}"的位置（C#类结束）
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == "}":
                    last_class_end = i + 1
                    break
            
            # 在最后一个类之后插入
            before = '\n'.join(lines[:last_class_end])
            after = '\n'.join(lines[last_class_end:])
            merged_content = before + "\n\n" + new_content + "\n" + after
            
        elif insert_position.startswith("after_line:"):
            try:
                line_num = int(insert_position.split(":")[1])
                lines = original_content.split('\n')
                
                if line_num < 0 or line_num > len(lines):
                    return {
                        "success": False,
                        "error": f"行号 {line_num} 超出范围 (1-{len(lines)})"
                    }
                
                before = '\n'.join(lines[:line_num])
                after = '\n'.join(lines[line_num:])
                merged_content = before + "\n" + new_content + "\n" + after
                
            except ValueError:
                return {
                    "success": False,
                    "error": f"无效的行号格式: {insert_position}"
                }
        elif insert_position == "after_pattern":
            if not anchor_pattern:
                return {
                    "success": False,
                    "error": "after_pattern 需要提供 anchor_pattern"
                }
            lines = original_content.split('\n')
            matches = [i for i, line in enumerate(lines) if re.search(anchor_pattern, line)]
            if not matches:
                return {
                    "success": False,
                    "error": "未找到锚点匹配行",
                    "anchor_pattern": anchor_pattern
                }
            if require_unique and len(matches) != 1:
                return {
                    "success": False,
                    "error": "锚点匹配行不唯一",
                    "anchor_pattern": anchor_pattern,
                    "match_count": len(matches)
                }
            idx = matches[0]
            before = '\n'.join(lines[:idx + 1])
            after = '\n'.join(lines[idx + 1:])
            merged_content = before + "\n" + new_content + "\n" + after
        elif insert_position == "before_pattern":
            if not anchor_pattern:
                return {
                    "success": False,
                    "error": "before_pattern 需要提供 anchor_pattern"
                }
            lines = original_content.split('\n')
            matches = [i for i, line in enumerate(lines) if re.search(anchor_pattern, line)]
            if not matches:
                return {
                    "success": False,
                    "error": "未找到锚点匹配行",
                    "anchor_pattern": anchor_pattern
                }
            if require_unique and len(matches) != 1:
                return {
                    "success": False,
                    "error": "锚点匹配行不唯一",
                    "anchor_pattern": anchor_pattern,
                    "match_count": len(matches)
                }
            idx = matches[0]
            before = '\n'.join(lines[:idx])
            after = '\n'.join(lines[idx:])
            merged_content = before + "\n" + new_content + "\n" + after
        else:
            return {
                "success": False,
                "error": f"不支持的插入位置: {insert_position}"
            }
        
        # 写入合并后的内容
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(merged_content)
        
        # 计算变化
        original_size = len(original_content)
        merged_size = len(merged_content)
        added_size = merged_size - original_size
        if merged_size <= original_size:
            shutil.copy2(backup_file, target_file)
            return {
                "success": False,
                "error": "合并后文件大小异常，已回滚",
                "backup_file": backup_file,
                "original_size": original_size,
                "merged_size": merged_size
            }
        if ensure_present and new_content and new_content not in merged_content:
            shutil.copy2(backup_file, target_file)
            return {
                "success": False,
                "error": "合并内容校验失败，已回滚",
                "backup_file": backup_file
            }
        
        return {
            "success": True,
            "action": "merged_content",
            "file_path": target_file,
            "backup_file": backup_file,
            "original_size": original_size,
            "merged_size": merged_size,
            "added_size": added_size,
            "insert_position": insert_position,
            "message": f"内容已安全合并，原始文件已备份到 {backup_file}"
        }
        
    except Exception as e:
        return {"success": False, "error": f"合并文件失败: {str(e)}"}
