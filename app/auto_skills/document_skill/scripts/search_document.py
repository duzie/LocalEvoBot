from langchain_core.tools import tool
import os
from typing import List, Dict, Any
from collections import deque

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
        
        if not keyword:
            return {
                "success": False,
                "error": "keyword 不能为空",
                "results": [],
                "stats": {}
            }

        encoding_used, error_mode = _pick_encoding(file_path, encoding)
        safe_context = max(0, int(context_lines or 0))
        safe_max_results = max(1, int(max_results or 10))
        search_keyword = keyword if case_sensitive else keyword.lower()
        results = []
        prev_lines = deque(maxlen=safe_context)
        ahead_queue = deque()
        total_lines = 0
        line_num = -1
        reached_max = False

        with open(file_path, "r", encoding=encoding_used, errors=error_mode, newline="") as f:
            while True:
                if ahead_queue:
                    line_num, line = ahead_queue.popleft()
                else:
                    line = f.readline()
                    if not line:
                        break
                    line_num += 1
                if line_num + 1 > total_lines:
                    total_lines = line_num + 1

                if not reached_max:
                    line_to_search = line if case_sensitive else line.lower()
                    if search_keyword in line_to_search:
                        context_items = list(prev_lines)
                        context_items.append((line_num, line))

                        next_items = []
                        if safe_context > 0:
                            while len(next_items) < safe_context:
                                if ahead_queue:
                                    nxt = ahead_queue.popleft()
                                else:
                                    next_line = f.readline()
                                    if not next_line:
                                        break
                                    line_num += 1
                                    nxt = (line_num, next_line)
                                    if line_num + 1 > total_lines:
                                        total_lines = line_num + 1
                                next_items.append(nxt)
                            if next_items:
                                for item in reversed(next_items):
                                    ahead_queue.appendleft(item)

                        context_items.extend(next_items)
                        context_start = context_items[0][0] if context_items else line_num
                        context_end = context_items[-1][0] if context_items else line_num

                        marked_context = []
                        for ctx_line_num, ctx_line in context_items:
                            if ctx_line_num == line_num:
                                marked_context.append(f">>> 行 {ctx_line_num}: {ctx_line.rstrip()}")
                            else:
                                marked_context.append(f"    行 {ctx_line_num}: {ctx_line.rstrip()}")

                        context_text = "\n".join(marked_context)
                        results.append({
                            "line_number": line_num,
                            "matched_line": line.rstrip(),
                            "context": context_text,
                            "context_start": context_start,
                            "context_end": context_end
                        })
                        if len(results) >= safe_max_results:
                            reached_max = True

                prev_lines.append((line_num, line))
        
        # 计算统计信息
        stats = {
            "total_lines": total_lines,
            "keyword": keyword,
            "case_sensitive": case_sensitive,
            "context_lines": safe_context,
            "max_results": safe_max_results,
            "matches_found": len(results),
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "encoding": encoding_used
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
