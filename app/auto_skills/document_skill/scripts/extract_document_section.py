from langchain_core.tools import tool
import os
from typing import Optional, Dict, Any

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
        
        # 读取文件内容
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # 查找章节标记
        section_start = -1
        for i, line in enumerate(lines):
            if section_marker in line:
                section_start = i
                break
        
        if section_start == -1:
            return {
                "success": False,
                "error": f"未找到章节标记: '{section_marker}'",
                "content": "",
                "stats": {"total_lines": total_lines, "section_marker": section_marker}
            }
        
        # 确定提取结束位置
        section_end = total_lines - 1  # 默认到文件末尾
        
        if next_section_marker:
            # 查找下一章节标记
            for i in range(section_start + 1, total_lines):
                if next_section_marker in lines[i]:
                    section_end = i - 1
                    break
        
        # 调整起始位置（是否包含标记行）
        extract_start = section_start if include_marker else section_start + 1
        
        # 确保起始位置不超过结束位置
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
        
        # 提取内容
        extracted_lines = lines[extract_start:section_end + 1]
        content = ''.join(extracted_lines)
        
        # 计算统计信息
        extracted_line_count = len(extracted_lines)
        
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
            "file_size": os.path.getsize(file_path)
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