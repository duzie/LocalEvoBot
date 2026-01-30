from langchain_core.tools import tool
import os
from typing import Optional, Dict, Any

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
        
        # 读取文件内容
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # 验证起始行号
        if start_line < 0:
            start_line = 0
        elif start_line >= total_lines:
            return {
                "success": False,
                "error": f"起始行号 {start_line} 超出文件范围 (总行数: {total_lines})",
                "content": "",
                "stats": {"total_lines": total_lines}
            }
        
        # 确定结束行号
        if end_line is None:
            end_line = total_lines - 1
        elif end_line >= total_lines:
            end_line = total_lines - 1
        
        if end_line < start_line:
            return {
                "success": False,
                "error": f"结束行号 {end_line} 小于起始行号 {start_line}",
                "content": "",
                "stats": {"total_lines": total_lines}
            }
        
        # 截取指定行范围
        selected_lines = lines[start_line:end_line + 1]
        
        # 合并为字符串
        content = ''.join(selected_lines)
        
        # 检查字符数限制
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[内容已截断，超过最大字符限制]"
        
        # 计算统计信息
        selected_line_count = len(selected_lines)
        char_count = len(content)
        
        stats = {
            "total_lines": total_lines,
            "selected_lines": selected_line_count,
            "start_line": start_line,
            "end_line": end_line,
            "char_count": char_count,
            "max_chars": max_chars,
            "file_size": os.path.getsize(file_path),
            "file_path": file_path
        }
        
        return {
            "success": True,
            "content": content,
            "stats": stats,
            "message": f"成功读取 {selected_line_count} 行内容 (行 {start_line}-{end_line})"
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