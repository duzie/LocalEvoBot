from langchain_core.tools import tool
import os
import re
from typing import Dict, Any
from datetime import datetime

@tool
def get_document_stats(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """
    获取文档统计信息（行数、字符数、大小等）
    
    Args:
        file_path: 文档文件路径
        encoding: 文件编码
    
    Returns:
        包含文档统计信息的字典
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在: {file_path}",
                "stats": {}
            }
        
        # 检查文件是否为文本文件
        if not os.path.isfile(file_path):
            return {
                "success": False,
                "error": f"路径不是文件: {file_path}",
                "stats": {}
            }
        
        # 获取文件基本信息
        file_size = os.path.getsize(file_path)
        modified_time = os.path.getmtime(file_path)
        modified_date = datetime.fromtimestamp(modified_time).strftime('%Y-%m-%d %H:%M:%S')
        
        # 读取文件内容进行分析
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            content = f.read()
            lines = content.splitlines()
        
        # 计算各种统计信息
        total_lines = len(lines)
        total_chars = len(content)
        total_words = len(re.findall(r'\b\w+\b', content))
        
        # 计算非空行数
        non_empty_lines = sum(1 for line in lines if line.strip())
        
        # 分析常见文档结构（针对Markdown）
        markdown_headers = {
            "#": len(re.findall(r'^#\s', content, re.MULTILINE)),
            "##": len(re.findall(r'^##\s', content, re.MULTILINE)),
            "###": len(re.findall(r'^###\s', content, re.MULTILINE)),
            "####": len(re.findall(r'^####\s', content, re.MULTILINE)),
        }
        
        # 分析代码块
        code_blocks = len(re.findall(r'```', content))
        
        # 分析列表项
        bullet_points = len(re.findall(r'^\s*[-*+]\s', content, re.MULTILINE))
        numbered_lists = len(re.findall(r'^\s*\d+\.\s', content, re.MULTILINE))
        
        # 分析表格
        tables = len(re.findall(r'^\|.*\|$', content, re.MULTILINE))
        
        # 计算平均行长度
        avg_line_length = total_chars / total_lines if total_lines > 0 else 0
        
        # 文件类型判断
        file_ext = os.path.splitext(file_path)[1].lower()
        common_extensions = {
            '.md': 'Markdown',
            '.txt': 'Text',
            '.py': 'Python',
            '.js': 'JavaScript',
            '.java': 'Java',
            '.cs': 'C#',
            '.cpp': 'C++',
            '.html': 'HTML',
            '.css': 'CSS',
            '.json': 'JSON',
            '.xml': 'XML',
            '.sql': 'SQL',
            '.yml': 'YAML',
            '.yaml': 'YAML',
            '.ini': 'INI',
            '.cfg': 'Config',
            '.conf': 'Config',
            '.log': 'Log',
            '.csv': 'CSV'
        }
        
        file_type = common_extensions.get(file_ext, 'Unknown')
        
        # 构建统计信息
        stats = {
            "file_info": {
                "path": file_path,
                "name": os.path.basename(file_path),
                "directory": os.path.dirname(file_path),
                "size_bytes": file_size,
                "size_human": f"{file_size / 1024:.2f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.2f} MB",
                "modified": modified_date,
                "extension": file_ext,
                "type": file_type
            },
            "content_stats": {
                "total_lines": total_lines,
                "non_empty_lines": non_empty_lines,
                "empty_lines": total_lines - non_empty_lines,
                "total_characters": total_chars,
                "total_words": total_words,
                "avg_line_length": round(avg_line_length, 2)
            },
            "structure_analysis": {
                "markdown_headers": markdown_headers,
                "code_blocks": code_blocks,
                "bullet_points": bullet_points,
                "numbered_lists": numbered_lists,
                "tables": tables
            },
            "readability": {
                "lines_per_kb": round(total_lines / (file_size / 1024), 2) if file_size > 0 else 0,
                "chars_per_line": round(total_chars / total_lines, 2) if total_lines > 0 else 0,
                "words_per_line": round(total_words / total_lines, 2) if total_lines > 0 else 0
            }
        }
        
        return {
            "success": True,
            "stats": stats,
            "message": f"文档分析完成: {os.path.basename(file_path)} ({file_type}, {total_lines} 行, {total_chars} 字符)"
        }
        
    except UnicodeDecodeError as e:
        return {
            "success": False,
            "error": f"编码错误: {str(e)}，请尝试不同的编码",
            "stats": {}
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取文档统计信息时出错: {str(e)}",
            "stats": {}
        }