from langchain_core.tools import tool
import os
from typing import Optional, Dict, Any

def _pick_encoding(file_path: str, encoding: str):
    candidates = []
    if encoding:
        candidates.append(str(encoding).strip())
    candidates.extend(["utf-8-sig", "utf-8", "gb18030", "gbk", "cp936", "latin-1"])
    seen = set()
    with open(file_path, "rb") as f:
        sample = f.read(65536)
    for enc in candidates:
        if not enc or enc in seen:
            continue
        seen.add(enc)
        try:
            sample.decode(enc)
            return enc, "strict"
        except Exception:
            continue
    return "utf-8", "replace"

@tool
def extract_document_section(file_path: str, section_marker: str, 
                           include_marker: bool = True, next_section_marker: Optional[str] = None,
                           encoding: str = "utf-8") -> Dict[str, Any]:
    """
    提取文档中特定章节或标记的内容
    
    Args:
        file_path: 文档文件路径
        section_marker: 章节标记（如## 功能说明、### 接口说明等）
        include_marker: 是否包含标记行本身
        next_section_marker: 下一章节标记，用于确定提取范围
        encoding: 文件编码
    
    Returns:
        包含提取内容的字典
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在: {file_path}",
                "content": "",
                "stats": {}
            }
        
        # 检查文件是否为文本文件
        if not os.path.isfile(file_path):
            return {
                "success": False,
                "error": f"路径不是文件: {file_path}",
                "content": "",
                "stats": {}
            }
        
        encoding_used, error_mode = _pick_encoding(file_path, encoding)
        section_start = -1
        section_end = -1
        extract_start = -1
        extracted_lines = []
        extracted_line_count = 0
        collecting = False
        total_lines = 0

        with open(file_path, "r", encoding=encoding_used, errors=error_mode, newline="") as f:
            for line in f:
                line_index = total_lines
                total_lines += 1
                if section_start == -1:
                    if section_marker in line:
                        section_start = line_index
                        extract_start = section_start if include_marker else section_start + 1
                        if include_marker:
                            extracted_lines.append(line)
                            extracted_line_count += 1
                        collecting = True
                    continue

                if collecting:
                    if next_section_marker and next_section_marker in line:
                        section_end = line_index - 1
                        collecting = False
                        continue
                    extracted_lines.append(line)
                    extracted_line_count += 1

        if section_start == -1:
            return {
                "success": False,
                "error": f"未找到章节标记: '{section_marker}'",
                "content": "",
                "stats": {"total_lines": total_lines, "section_marker": section_marker}
            }

        if section_end == -1:
            section_end = total_lines - 1

        if extract_start > section_end:
            return {
                "success": False,
                "error": "提取范围无效（起始位置超过结束位置）",
                "content": "",
                "stats": {
                    "total_lines": total_lines,
                    "section_marker": section_marker,
                    "section_start": section_start,
                    "section_end": section_end,
                    "extract_start": extract_start
                }
            }

        content = "".join(extracted_lines)
        
        stats = {
            "total_lines": total_lines,
            "section_marker": section_marker,
            "section_start": section_start,
            "section_end": section_end,
            "extract_start": extract_start,
            "extracted_lines": extracted_line_count,
            "include_marker": include_marker,
            "next_section_marker": next_section_marker,
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "encoding": encoding_used
        }
        
        return {
            "success": True,
            "content": content,
            "stats": stats,
            "message": f"成功提取 {extracted_line_count} 行内容 (行 {extract_start}-{section_end})"
        }
        
    except UnicodeDecodeError as e:
        return {
            "success": False,
            "error": f"编码错误: {str(e)}，请尝试不同的编码",
            "content": "",
            "stats": {}
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"提取文档章节时出错: {str(e)}",
            "content": "",
            "stats": {}
        }
