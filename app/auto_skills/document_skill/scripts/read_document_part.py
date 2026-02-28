from langchain_core.tools import tool
import os
from typing import Optional, Dict, Any

def _pick_encoding(file_path: str, encoding: Optional[str]):
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
def read_document_part(file_path: str, start_line: int = 0, end_line: Optional[int] = None, 
                      max_chars: int = 5000, encoding: str = "utf-8") -> Dict[str, Any]:
    """
    读取文档的部分内容，支持按行数、字符数或百分比截取
    
    Args:
        file_path: 文档文件路径
        start_line: 起始行号（从0开始）
        end_line: 结束行号（包含），如果为None则读取到文件末尾
        max_chars: 最大字符数限制
        encoding: 文件编码
    
    Returns:
        包含文档内容的字典
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
        if start_line < 0:
            start_line = 0
        if end_line is not None and end_line < start_line:
            return {
                "success": False,
                "error": f"结束行号 {end_line} 小于起始行号 {start_line}",
                "content": "",
                "stats": {}
            }

        total_lines = 0
        selected_line_count = 0
        collected = []
        collected_chars = 0
        truncated = False
        with open(file_path, "r", encoding=encoding_used, errors=error_mode, newline="") as f:
            for line in f:
                line_index = total_lines
                total_lines += 1
                in_range = line_index >= start_line and (end_line is None or line_index <= end_line)
                if in_range:
                    selected_line_count += 1
                    if not truncated:
                        if collected_chars + len(line) <= max_chars:
                            collected.append(line)
                            collected_chars += len(line)
                        else:
                            remaining = max_chars - collected_chars
                            if remaining > 0:
                                collected.append(line[:remaining])
                            collected.append("\n\n[内容已截断，超过最大字符限制]")
                            truncated = True

        if start_line >= total_lines:
            return {
                "success": False,
                "error": f"起始行号 {start_line} 超出文件范围 (总行数: {total_lines})",
                "content": "",
                "stats": {"total_lines": total_lines}
            }

        if end_line is None:
            end_line_effective = total_lines - 1
        else:
            end_line_effective = min(end_line, total_lines - 1)

        content = "".join(collected)
        char_count = len(content)
        
        stats = {
            "total_lines": total_lines,
            "selected_lines": selected_line_count,
            "start_line": start_line,
            "end_line": end_line_effective,
            "char_count": char_count,
            "max_chars": max_chars,
            "file_size": os.path.getsize(file_path),
            "file_path": file_path,
            "encoding": encoding_used
        }
        
        return {
            "success": True,
            "content": content,
            "stats": stats,
            "message": f"成功读取 {selected_line_count} 行内容 (行 {start_line}-{end_line_effective})"
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
            "error": f"读取文件时出错: {str(e)}",
            "content": "",
            "stats": {}
        }
