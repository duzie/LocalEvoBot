from langchain_core.tools import tool
import os
import shutil
import re
from typing import Dict, Any, Optional
from langchain.tools import tool


def _stream_contains(file_path: str, needle: str, encoding: str) -> bool:
    if not needle:
        return False
    tail = ""
    needle_len = len(needle)
    with open(file_path, "r", encoding=encoding, errors="ignore") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            data = tail + chunk
            if needle in data:
                return True
            if needle_len > 1:
                tail = data[-(needle_len - 1):]
            else:
                tail = ""
    return False


def _iter_lines(file_path: str, encoding: str):
    with open(file_path, "r", encoding=encoding, errors="ignore") as f:
        for line in f:
            yield line


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
        
        encoding = "utf-8"
        if skip_if_present and new_content and _stream_contains(target_file, new_content, encoding):
            return {
                "success": True,
                "action": "skipped",
                "file_path": target_file,
                "backup_file": backup_file,
                "message": "内容已存在，已跳过"
            }
        
        # 根据插入位置处理
        if insert_position == "beginning":
            tmp_file = target_file + ".tmp"
            with open(tmp_file, "w", encoding=encoding) as dst:
                if new_content:
                    dst.write(new_content)
                if not new_content.endswith("\n"):
                    dst.write("\n")
                dst.write("\n")
                for line in _iter_lines(target_file, encoding):
                    dst.write(line)
            os.replace(tmp_file, target_file)
        elif insert_position == "end":
            tmp_file = target_file + ".tmp"
            with open(tmp_file, "w", encoding=encoding) as dst:
                for line in _iter_lines(target_file, encoding):
                    dst.write(line)
                dst.write("\n")
                dst.write("\n")
                if new_content:
                    dst.write(new_content)
            os.replace(tmp_file, target_file)
        elif insert_position == "after_last_class":
            last_class_end = 0
            total_lines = 0
            for line in _iter_lines(target_file, encoding):
                total_lines += 1
                if line.strip() == "}":
                    last_class_end = total_lines
            if last_class_end == 0:
                last_class_end = total_lines
            tmp_file = target_file + ".tmp"
            with open(tmp_file, "w", encoding=encoding) as dst:
                line_num = 0
                for line in _iter_lines(target_file, encoding):
                    line_num += 1
                    dst.write(line)
                    if line_num == last_class_end:
                        dst.write("\n")
                        dst.write("\n")
                        if new_content:
                            dst.write(new_content)
                        dst.write("\n")
                if total_lines == 0:
                    dst.write("\n")
                    dst.write("\n")
                    if new_content:
                        dst.write(new_content)
                    dst.write("\n")
            os.replace(tmp_file, target_file)
            
        elif insert_position.startswith("after_line:"):
            try:
                line_num = int(insert_position.split(":")[1])
                total_lines = 0
                for _ in _iter_lines(target_file, encoding):
                    total_lines += 1
                if line_num < 0 or line_num > total_lines:
                    return {
                        "success": False,
                        "error": f"行号 {line_num} 超出范围 (1-{total_lines})"
                    }
                tmp_file = target_file + ".tmp"
                with open(tmp_file, "w", encoding=encoding) as dst:
                    current = 0
                    for line in _iter_lines(target_file, encoding):
                        current += 1
                        dst.write(line)
                        if current == line_num:
                            dst.write("\n")
                            if new_content:
                                dst.write(new_content)
                            dst.write("\n")
                    if line_num == 0:
                        dst.write("\n")
                        if new_content:
                            dst.write(new_content)
                        dst.write("\n")
                os.replace(tmp_file, target_file)
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
            anchor_re = re.compile(anchor_pattern)
            matches = 0
            match_line = 0
            line_num = 0
            for line in _iter_lines(target_file, encoding):
                line_num += 1
                if anchor_re.search(line):
                    matches += 1
                    if match_line == 0:
                        match_line = line_num
            if matches == 0:
                return {
                    "success": False,
                    "error": "未找到锚点匹配行",
                    "anchor_pattern": anchor_pattern
                }
            if require_unique and matches != 1:
                return {
                    "success": False,
                    "error": "锚点匹配行不唯一",
                    "anchor_pattern": anchor_pattern,
                    "match_count": matches
                }
            tmp_file = target_file + ".tmp"
            with open(tmp_file, "w", encoding=encoding) as dst:
                line_num = 0
                for line in _iter_lines(target_file, encoding):
                    line_num += 1
                    dst.write(line)
                    if line_num == match_line:
                        dst.write("\n")
                        if new_content:
                            dst.write(new_content)
                        dst.write("\n")
            os.replace(tmp_file, target_file)
        elif insert_position == "before_pattern":
            if not anchor_pattern:
                return {
                    "success": False,
                    "error": "before_pattern 需要提供 anchor_pattern"
                }
            anchor_re = re.compile(anchor_pattern)
            matches = 0
            match_line = 0
            line_num = 0
            for line in _iter_lines(target_file, encoding):
                line_num += 1
                if anchor_re.search(line):
                    matches += 1
                    if match_line == 0:
                        match_line = line_num
            if matches == 0:
                return {
                    "success": False,
                    "error": "未找到锚点匹配行",
                    "anchor_pattern": anchor_pattern
                }
            if require_unique and matches != 1:
                return {
                    "success": False,
                    "error": "锚点匹配行不唯一",
                    "anchor_pattern": anchor_pattern,
                    "match_count": matches
                }
            tmp_file = target_file + ".tmp"
            with open(tmp_file, "w", encoding=encoding) as dst:
                current = 0
                for line in _iter_lines(target_file, encoding):
                    current += 1
                    if current == match_line:
                        dst.write("\n")
                        if new_content:
                            dst.write(new_content)
                        dst.write("\n")
                    dst.write(line)
            os.replace(tmp_file, target_file)
        else:
            return {
                "success": False,
                "error": f"不支持的插入位置: {insert_position}"
            }

        original_size = os.path.getsize(backup_file)
        merged_size = os.path.getsize(target_file)
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
        if ensure_present and new_content and not _stream_contains(target_file, new_content, encoding):
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
