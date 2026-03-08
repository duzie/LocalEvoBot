"""
改进的代码块查找工具
支持 Python 和 JavaScript，提供更精确的行号定位
"""
from langchain_core.tools import tool
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from web.backend.shared import shared


def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is not None:
            payload[str(k)] = v
    return payload


def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is not None:
            payload[str(k)] = v
    return payload


def _emit_event(tool_name: str, event: str, **fields):
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is not None:
            payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))


def detect_file_type(file_path: str) -> str:
    """检测文件类型"""
    if file_path.endswith('.py'):
        return 'python'
    elif file_path.endswith(('.js', '.jsx', '.mjs', '.cjs')):
        return 'javascript'
    elif file_path.endswith('.ts'):
        return 'typescript'
    elif file_path.endswith('.vue'):
        return 'vue'
    else:
        return 'unknown'


def find_python_block_range(lines: List[str], start_idx: int, block_type: str) -> Tuple[int, int]:
    """查找 Python 代码块的结束位置（基于缩进）"""
    if start_idx >= len(lines):
        return (start_idx, start_idx)
    
    start_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
    end_idx = start_idx
    
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()
        
        if not stripped or stripped.startswith('#'):
            continue
        
        current_indent = len(line) - len(line.lstrip())
        
        if current_indent <= start_indent:
            end_idx = i - 1
            break
    else:
        end_idx = len(lines) - 1
    
    return (start_idx, end_idx)


def find_js_block_range(lines: List[str], start_idx: int) -> Tuple[int, int]:
    """查找 JavaScript 代码块的结束位置（基于花括号）"""
    if start_idx >= len(lines):
        return (start_idx, start_idx)
    
    brace_count = 0
    in_block = False
    end_idx = start_idx
    
    for i in range(start_idx, len(lines)):
        line = lines[i]
        
        for char in line:
            if char == '{':
                brace_count += 1
                in_block = True
            elif char == '}':
                brace_count -= 1
                
                if in_block and brace_count == 0:
                    end_idx = i
                    return (start_idx, end_idx)
    
    return (start_idx, len(lines) - 1)


def find_js_function_patterns(func_name: str) -> List[str]:
    """生成 JavaScript 函数的匹配模式"""
    return [
        rf'(?:export\s+)?(?:async\s+)?function\s+{re.escape(func_name)}\s*\(',
        rf'(?:export\s+)?(?:const|let|var)\s+{re.escape(func_name)}\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=])*=>',
        rf'(?:export\s+)?(?:async\s+)?{re.escape(func_name)}\s*\([^)]*\)\s*{{',
        rf'{re.escape(func_name)}\s*:\s*(?:async\s+)?function\s*\(',
        rf'{re.escape(func_name)}\s*\([^)]*\)\s*{{',
    ]


def find_js_class_patterns(class_name: str) -> List[str]:
    """生成 JavaScript 类的匹配模式"""
    return [
        rf'(?:export\s+)?class\s+{re.escape(class_name)}\s*(?:extends\s+\w+\s*)?{{',
        rf'(?:export\s+)?class\s+{re.escape(class_name)}\s*{{',
    ]


def find_js_variable_patterns(var_name: str, var_type: str = None) -> List[str]:
    """生成 JavaScript 变量的匹配模式"""
    if var_type:
        return [rf'(?:export\s+)?{var_type}\s+{re.escape(var_name)}\s*=']
    else:
        return [
            rf'(?:export\s+)?const\s+{re.escape(var_name)}\s*=',
            rf'(?:export\s+)?let\s+{re.escape(var_name)}\s*=',
            rf'(?:export\s+)?var\s+{re.escape(var_name)}\s*=',
        ]


@tool
def find_code_block(
    file_path: str,
    block_name: str,
    block_type: str = "function",
    language: str = None
) -> Dict[str, Any]:
    """
    在代码文件中查找特定函数、类或其他代码块的精确行号范围
    支持 Python 和 JavaScript (ES6+)
    
    Args:
        file_path: 文件路径
        block_name: 代码块名称（函数名、类名、变量名等）
        block_type: 代码块类型：function, class, method, variable, const, let, var
        language: 编程语言（python, javascript, typescript），不指定则自动检测
    """
    tool_name = "find_code_block"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.splitlines()
        
        # 自动检测语言
        if not language:
            language = detect_file_type(file_path)
        
        # 根据语言和代码块类型查找
        if language == 'python':
            result = find_python_block(lines, block_name, block_type)
        elif language in ['javascript', 'typescript']:
            result = find_javascript_block(lines, block_name, block_type)
        else:
            # 尝试通用查找
            result = find_generic_block(lines, block_name, block_type)
        
        if not result["found"]:
            return _error_payload("not_found", result.get("error", f"未找到 {block_type}: {block_name}"), tool=tool_name)
        
        # 添加额外信息
        result["file_path"] = file_path
        result["language"] = language
        result["line_count"] = len(lines)
        
        # 提取代码块内容
        start_line = result["start_line"] - 1  # 转为0-based索引
        end_line = result["end_line"]
        result["code_snippet"] = '\n'.join(lines[start_line:end_line])
        
        _emit_event(tool_name, "completed", result=result)
        return _ok_payload(
            f"找到 {block_type} '{block_name}' 在第 {result['start_line']}-{result['end_line']} 行",
            **result
        )
    
    except FileNotFoundError:
        err = _error_payload("file_not_found", f"文件不存在: {file_path}", tool=tool_name)
        _emit_event(tool_name, "error", error=f"文件不存在: {file_path}")
        return err
    except Exception as e:
        err = _error_payload("unknown_error", f"查找代码块时发生错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err


def find_python_block(lines: List[str], block_name: str, block_type: str) -> Dict[str, Any]:
    """查找 Python 代码块"""
    patterns = []
    
    if block_type == "function":
        patterns = [rf'(?:async\s+)?def\s+{re.escape(block_name)}\s*\(']
    elif block_type == "class":
        patterns = [rf'class\s+{re.escape(block_name)}\s*[:\(]']
    elif block_type == "method":
        patterns = [rf'def\s+{re.escape(block_name)}\s*\(']
    elif block_type == "variable":
        patterns = [rf'^\s*{re.escape(block_name)}\s*=']
    else:
        return {"found": False, "error": f"不支持的代码块类型: {block_type}"}
    
    # 查找匹配的行
    start_idx = -1
    for i, line in enumerate(lines):
        for pattern in patterns:
            if re.search(pattern, line):
                start_idx = i
                break
        if start_idx != -1:
            break
    
    if start_idx == -1:
        return {"found": False, "error": f"未找到 {block_type}: {block_name}"}
    
    # 查找结束位置
    start_idx, end_idx = find_python_block_range(lines, start_idx, block_type)
    
    return {
        "found": True,
        "start_line": start_idx + 1,
        "end_line": end_idx + 1,
        "block_name": block_name,
        "block_type": block_type
    }


def find_javascript_block(lines: List[str], block_name: str, block_type: str) -> Dict[str, Any]:
    """查找 JavaScript 代码块"""
    patterns = []
    
    if block_type == "function":
        patterns = find_js_function_patterns(block_name)
    elif block_type == "class":
        patterns = find_js_class_patterns(block_name)
    elif block_type in ["variable", "const", "let", "var"]:
        var_type = block_type if block_type != "variable" else None
        patterns = find_js_variable_patterns(block_name, var_type)
    elif block_type == "method":
        patterns = [
            rf'{re.escape(block_name)}\s*\([^)]*\)\s*{{',
            rf'{re.escape(block_name)}\s*:\s*(?:async\s+)?function\s*\(',
        ]
    else:
        return {"found": False, "error": f"不支持的代码块类型: {block_type}"}
    
    # 查找匹配的行
    start_idx = -1
    for i, line in enumerate(lines):
        for pattern in patterns:
            if re.search(pattern, line):
                start_idx = i
                break
        if start_idx != -1:
            break
    
    if start_idx == -1:
        return {"found": False, "error": f"未找到 {block_type}: {block_name}"}
    
    # 查找结束位置
    if block_type in ["function", "class", "method"]:
        start_idx, end_idx = find_js_block_range(lines, start_idx)
    else:
        # 变量声明，查找分号或下一行
        end_idx = start_idx
        for i in range(start_idx, min(start_idx + 10, len(lines))):
            if ';' in lines[i]:
                end_idx = i
                break
    
    return {
        "found": True,
        "start_line": start_idx + 1,
        "end_line": end_idx + 1,
        "block_name": block_name,
        "block_type": block_type
    }


def find_generic_block(lines: List[str], block_name: str, block_type: str) -> Dict[str, Any]:
    """通用代码块查找（不依赖语言特性）"""
    pattern = rf'\b{re.escape(block_name)}\b'
    
    start_idx = -1
    for i, line in enumerate(lines):
        if re.search(pattern, line):
            start_idx = i
            break
    
    if start_idx == -1:
        return {"found": False, "error": f"未找到 {block_name}"}
    
    return {
        "found": True,
        "start_line": start_idx + 1,
        "end_line": start_idx + 1,
        "block_name": block_name,
        "block_type": block_type,
        "note": "使用通用查找，可能不够精确"
    }


if __name__ == "__main__":
    # 测试示例
    print("代码块查找工具已加载")
