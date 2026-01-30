from langchain_core.tools import tool
import os
from typing import List, Dict, Any

@tool
def search_document(file_path: str, keyword: str, context_lines: int = 3, 
                   case_sensitive: bool = False, max_results: int = 10, 
                   encoding: str = "utf-8") -> Dict[str, Any]:
    """
    在文档中搜索关键词，返回包含关键词的行或段落
    
    Args:
        file_path: 文档文件路径
        keyword: 搜索关键词
        context_lines: 返回关键词前后多少行上下文
        case_sensitive: 是否区分大小写
        max_results: 最大返回结果数
        encoding: 文件编码
    
    Returns:
        包含搜索结果的字典
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在: {file_path}",
                "results": [],
                "stats": {}
            }
        
        # 检查文件是否为文本文件
        if not os.path.isfile(file_path):
            return {
                "success": False,
                "error": f"路径不是文件: {file_path}",
                "results": [],
                "stats": {}
            }
        
        # 读取文件内容
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # 准备搜索
        search_keyword = keyword if case_sensitive else keyword.lower()
        results = []
        
        # 遍历所有行进行搜索
        for line_num, line in enumerate(lines):
            line_to_search = line if case_sensitive else line.lower()
            
            if search_keyword in line_to_search:
                # 计算上下文范围
                start_context = max(0, line_num - context_lines)
                end_context = min(total_lines - 1, line_num + context_lines)
                
                # 获取上下文内容
                context = lines[start_context:end_context + 1]
                
                # 标记匹配行
                marked_context = []
                for i, ctx_line in enumerate(context):
                    ctx_line_num = start_context + i
                    if ctx_line_num == line_num:
                        # 标记匹配行
                        marked_context.append(f">>> 行 {ctx_line_num}: {ctx_line.rstrip()}")
                    else:
                        marked_context.append(f"    行 {ctx_line_num}: {ctx_line.rstrip()}")
                
                context_text = '\n'.join(marked_context)
                
                # 添加到结果
                results.append({
                    "line_number": line_num,
                    "matched_line": line.rstrip(),
                    "context": context_text,
                    "context_start": start_context,
                    "context_end": end_context
                })
                
                # 如果达到最大结果数，停止搜索
                if len(results) >= max_results:
                    break
        
        # 计算统计信息
        stats = {
            "total_lines": total_lines,
            "keyword": keyword,
            "case_sensitive": case_sensitive,
            "context_lines": context_lines,
            "max_results": max_results,
            "matches_found": len(results),
            "file_path": file_path,
            "file_size": os.path.getsize(file_path)
        }
        
        return {
            "success": True,
            "results": results,
            "stats": stats,
            "message": f"找到 {len(results)} 个匹配项" if results else "未找到匹配项"
        }
        
    except UnicodeDecodeError as e:
        return {
            "success": False,
            "error": f"编码错误: {str(e)}，请尝试不同的编码",
            "results": [],
            "stats": {}
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"搜索文件时出错: {str(e)}",
            "results": [],
            "stats": {}
        }