from langchain_core.tools import tool
import os
import re
from typing import Dict, Any, List, Optional, Tuple

def _remove_comments_and_strings(content: str) -> str:
    """
    Removes comments and strings from C# code to safely analyze braces.
    Preserves newlines to keep line numbers consistent.
    """
    # This is a simplified state machine or regex approach. 
    # Since regex for nested structures and C# strings (@"...", $"...", "...") is complex,
    # we'll use a careful regex approach that replaces content with spaces but keeps newlines.
    
    # 1. Replace strings with placeholders (spaces)
    # Handle verbatim strings @"..."
    pattern_verbatim = r'@"[^"]*"' 
    # Handle interpolated strings $"..." and normal strings "..."
    # Note: This is a basic approximation. C# string parsing is complex.
    # For structural brace counting, we mainly need to avoid { } inside strings.
    
    # Let's iterate character by character for robustness
    result = []
    i = 0
    n = len(content)
    in_string = False
    in_verbatim_string = False
    in_char = False
    in_single_line_comment = False
    in_multi_line_comment = False
    
    while i < n:
        c = content[i]
        
        # Handle newlines (always preserve)
        if c == '\n':
            result.append('\n')
            in_single_line_comment = False
            i += 1
            continue
            
        # If in comment, skip until end
        if in_single_line_comment:
            result.append(' ')
            i += 1
            continue
            
        if in_multi_line_comment:
            if c == '*' and i + 1 < n and content[i+1] == '/':
                in_multi_line_comment = False
                result.append('  ')
                i += 2
            else:
                result.append(' ')
                i += 1
            continue
            
        # If in string/char, skip until end
        if in_verbatim_string:
            if c == '"':
                if i + 1 < n and content[i+1] == '"': # escaped quote ""
                    result.append('  ')
                    i += 2
                else:
                    in_verbatim_string = False
                    result.append(' ')
                    i += 1
            else:
                result.append(' ')
                i += 1
            continue
            
        if in_string:
            if c == '\\': # escape
                result.append('  ')
                i += 2
            elif c == '"':
                in_string = False
                result.append(' ')
                i += 1
            else:
                result.append(' ')
                i += 1
            continue
            
        if in_char:
            if c == '\\':
                result.append('  ')
                i += 2
            elif c == "'":
                in_char = False
                result.append(' ')
                i += 1
            else:
                result.append(' ')
                i += 1
            continue
            
        # Start of comment?
        if c == '/' and i + 1 < n:
            if content[i+1] == '/':
                in_single_line_comment = True
                result.append('  ')
                i += 2
                continue
            elif content[i+1] == '*':
                in_multi_line_comment = True
                result.append('  ')
                i += 2
                continue
                
        # Start of string?
        if c == '@' and i + 1 < n and content[i+1] == '"':
            in_verbatim_string = True
            result.append('  ')
            i += 2
            continue
        if c == '"':
            in_string = True
            result.append(' ')
            i += 1
            continue
        if c == '\'':
            in_char = True
            result.append(' ')
            i += 1
            continue
            
        # Normal character
        result.append(c)
        i += 1
        
    return "".join(result)

def _find_namespace_insertion_point(content: str) -> Tuple[int, str]:
    """
    Analyzes C# structure to find the closing brace of the main namespace.
    Returns (line_index, reason). line_index is 0-based.
    """
    clean_content = _remove_comments_and_strings(content)
    lines = clean_content.split('\n')
    
    # 1. Find the namespace declaration
    namespace_start_line = -1
    namespace_brace_level = -1
    
    current_brace_level = 0
    brace_stack = [] # stores (level, type, start_line)
    
    namespace_found = False
    target_close_line = -1
    
    # Regex to detect namespace
    # namespace My.Name.Space {  OR  namespace My.Name.Space; (file scoped)
    ns_pattern = re.compile(r'\bnamespace\s+[\w\.]+')
    
    for i, line in enumerate(lines):
        # Check for namespace definition if not found yet
        if not namespace_found:
            match = ns_pattern.search(line)
            if match:
                # Check if it is file-scoped (ends with ;)
                if ';' in line[match.end():]:
                    return -1, "file_scoped_namespace" # Just append to end of file
                namespace_found = True
                namespace_start_line = i
                namespace_brace_level = current_brace_level
                # The brace might be on this line or next
        
        for char in line:
            if char == '{':
                brace_stack.append(current_brace_level)
                current_brace_level += 1
            elif char == '}':
                current_brace_level -= 1
                if brace_stack:
                    brace_stack.pop()
                
                # If we are closing the namespace brace
                if namespace_found and current_brace_level == namespace_brace_level:
                    # This is likely the closing brace of the namespace
                    # We want to keep updating this, because we want the *last* matching closing brace
                    # (in case of weird formatting, though usually there's only one)
                    target_close_line = i
                    
    if not namespace_found:
        return -1, "no_namespace"
        
    if target_close_line != -1:
        return target_close_line, "found_namespace_close"
        
    return -1, "error_parsing"

@tool
def csharp_code_edit(file_path: str, new_code: str, backup: bool = True) -> Dict[str, Any]:
    """
    智能 C# 代码编辑器。
    专门解决 C# 文件嵌套结构（Namespace/Class）插入困难的问题。
    它会自动分析文件结构，将新代码插入到最后一个 Namespace 的结束大括号之前。
    
    Args:
        file_path: C# 文件路径 (.cs)
        new_code: 要插入的新代码（类、接口等）
        backup: 是否创建备份 (.bak)，默认为 True
        
    Returns:
        执行结果字典
    """
    try:
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
            
        # 1. 读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 2. 备份
        if backup:
            backup_path = file_path + ".bak"
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
        # 3. 分析结构寻找插入点
        insert_line_index, reason = _find_namespace_insertion_point(content)
        
        lines = content.split('\n')
        
        if reason == "file_scoped_namespace" or reason == "no_namespace":
            # 文件范围命名空间或无命名空间，直接追加到末尾
            # 但要确保在最后一个 } 之后（如果有的话，可能是类的结束）
            # 其实如果无命名空间，直接追加即可
            # 如果是文件范围命名空间，也是直接追加
            new_lines = lines + ["", new_code, ""]
            insertion_desc = "文件末尾 (无命名空间或文件级命名空间)"
            
        elif reason == "found_namespace_close":
            # 在 namespace 结束括号前插入
            # insert_line_index 是包含 '}' 的那一行
            # 我们要在该行之前插入
            
            # 检查缩进，保持一致
            target_line = lines[insert_line_index]
            indent = ""
            match = re.match(r'^(\s*)', target_line)
            if match:
                indent = match.group(1)
                
            # 如果是只有 } 的行，通常缩进是正确的，我们应该用比它多一级的缩进？
            # 或者新代码自己带了缩进？
            # 通常新代码是整块的。
            # 简单起见，直接插入。
            
            new_lines = lines[:insert_line_index] + ["", new_code, ""] + lines[insert_line_index:]
            insertion_desc = f"Namespace 结束括号前 (行 {insert_line_index + 1})"
            
        else:
            # 解析失败，回退到 safe_file_merge 的逻辑或直接报错？
            # 这里的 safe fallback 是追加到文件末尾，但这正是用户说的问题所在。
            # 所以最好是报错让用户人工介入，或者尝试“最后一个 } 之前”
            return {
                "success": False, 
                "error": "无法解析 C# 文件结构，未找到明确的 Namespace 结束位置。",
                "reason": reason
            }
            
        # 4. 写入文件
        final_content = "\n".join(new_lines)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
            
        return {
            "success": True,
            "message": f"成功插入代码。位置: {insertion_desc}",
            "file_path": file_path,
            "backup_path": file_path + ".bak" if backup else None
        }
        
    except Exception as e:
        return {"success": False, "error": f"编辑 C# 文件失败: {str(e)}"}
