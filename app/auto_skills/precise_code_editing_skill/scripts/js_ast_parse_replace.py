"""
JavaScript AST 解析和替换工具
支持 ES6+ 语法，包括箭头函数、类、async/await 等
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


def detect_line_ending(content: str) -> str:
    """检测文件的换行符类型"""
    if '\r\n' in content:
        return '\r\n'
    elif '\n' in content:
        return '\n'
    else:
        return '\n'


def find_js_function_range(lines: List[str], func_name: str, start_idx: int) -> Tuple[int, int]:
    """
    查找 JavaScript 函数的行号范围
    支持：普通函数、箭头函数、类方法、async 函数
    """
    brace_count = 0
    in_function = False
    end_idx = start_idx
    
    for i in range(start_idx, len(lines)):
        line = lines[i]
        
        # 统计花括号
        for char in line:
            if char == '{':
                brace_count += 1
                in_function = True
            elif char == '}':
                brace_count -= 1
                
                # 当花括号计数回到初始值时，函数结束
                if in_function and brace_count == 0:
                    end_idx = i
                    return (start_idx, end_idx)
    
    return (start_idx, len(lines) - 1)


def find_js_class_range(lines: List[str], class_name: str, start_idx: int) -> Tuple[int, int]:
    """查找 JavaScript 类的行号范围"""
    brace_count = 0
    in_class = False
    end_idx = start_idx
    
    for i in range(start_idx, len(lines)):
        line = lines[i]
        
        for char in line:
            if char == '{':
                brace_count += 1
                in_class = True
            elif char == '}':
                brace_count -= 1
                
                if in_class and brace_count == 0:
                    end_idx = i
                    return (start_idx, end_idx)
    
    return (start_idx, len(lines) - 1)


@tool
def js_ast_parse_replace(
    file_path: str,
    target_name: str,
    new_code: str,
    node_type: str = "function",
    preserve_indent: bool = True
) -> Dict[str, Any]:
    """
    基于 AST 风格的 JavaScript 代码替换，支持 ES6+ 语法
    Args:
        file_path: 文件路径
        target_name: 目标节点名称（函数名、类名、变量名等）
        new_code: 新的代码内容
        node_type: 节点类型：function, class, variable, const, let, export
        preserve_indent: 是否保持原始缩进
    """
    tool_name = "js_ast_parse_replace"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.splitlines()
        line_ending = detect_line_ending(content)
        
        # 根据节点类型查找目标
        if node_type == "function":
            result = replace_js_function(lines, target_name, new_code, preserve_indent)
        elif node_type == "class":
            result = replace_js_class(lines, target_name, new_code, preserve_indent)
        elif node_type in ["variable", "const", "let", "var"]:
            result = replace_js_variable(lines, target_name, new_code, node_type, preserve_indent)
        elif node_type == "export":
            result = replace_js_export(lines, target_name, new_code, preserve_indent)
        else:
            return _error_payload("invalid_type", f"不支持的节点类型: {node_type}", tool=tool_name)
        
        if not result["success"]:
            return _error_payload("not_found", result.get("error", f"未找到 {node_type}: {target_name}"), tool=tool_name)
        
        # 构建新内容
        new_content = line_ending.join(result["lines"])
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            f.write(new_content)
        
        response = {
            "file_path": file_path,
            "target_name": target_name,
            "node_type": node_type,
            "start_line": result.get("start_line"),
            "end_line": result.get("end_line"),
            "replacement_successful": True
        }
        
        _emit_event(tool_name, "completed", result=response)
        return _ok_payload(f"成功替换 {node_type} '{target_name}'", **response)
    
    except FileNotFoundError:
        err = _error_payload("file_not_found", f"文件不存在: {file_path}", tool=tool_name)
        _emit_event(tool_name, "error", error=f"文件不存在: {file_path}")
        return err
    except Exception as e:
        err = _error_payload("unknown_error", f"JS AST 解析替换时发生错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err


def replace_js_function(
    lines: List[str],
    func_name: str,
    new_func_code: str,
    preserve_indent: bool
) -> Dict[str, Any]:
    """替换 JavaScript 函数"""
    # 匹配各种函数定义形式
    patterns = [
        rf'(?:export\s+)?(?:async\s+)?function\s+{re.escape(func_name)}\s*\(',  # 普通函数
        rf'(?:export\s+)?(?:const|let|var)\s+{re.escape(func_name)}\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=])*=>',  # 箭头函数
        rf'(?:export\s+)?(?:async\s+)?{re.escape(func_name)}\s*\([^)]*\)\s*{{',  # 简写方法
    ]
    
    start_idx = -1
    matched_pattern = None
    
    for i, line in enumerate(lines):
        for pattern in patterns:
            if re.search(pattern, line):
                start_idx = i
                matched_pattern = pattern
                break
        if start_idx != -1:
            break
    
    if start_idx == -1:
        return {"success": False, "error": f"未找到函数: {func_name}", "lines": lines}
    
    # 查找函数结束位置
    start_line, end_line = find_js_function_range(lines, func_name, start_idx)
    
    # 获取原始缩进
    original_indent = ""
    if preserve_indent and start_line < len(lines):
        original_line = lines[start_line]
        original_indent = original_line[:len(original_line) - len(original_line.lstrip())]
    
    # 应用缩进到新代码
    new_lines = []
    for i, line in enumerate(new_func_code.splitlines()):
        if i == 0:
            new_lines.append(original_indent + line.lstrip())
        else:
            if line.strip():
                new_lines.append(original_indent + line.lstrip())
            else:
                new_lines.append("")
    
    # 替换代码
    result_lines = lines[:start_line] + new_lines + lines[end_line + 1:]
    
    return {
        "success": True,
        "lines": result_lines,
        "start_line": start_line + 1,
        "end_line": end_line + 1
    }


def replace_js_class(
    lines: List[str],
    class_name: str,
    new_class_code: str,
    preserve_indent: bool
) -> Dict[str, Any]:
    """替换 JavaScript 类"""
    pattern = rf'(?:export\s+)?class\s+{re.escape(class_name)}\s*(?:extends\s+\w+\s*)?{{'
    
    start_idx = -1
    for i, line in enumerate(lines):
        if re.search(pattern, line):
            start_idx = i
            break
    
    if start_idx == -1:
        return {"success": False, "error": f"未找到类: {class_name}", "lines": lines}
    
    # 查找类结束位置
    start_line, end_line = find_js_class_range(lines, class_name, start_idx)
    
    # 获取原始缩进
    original_indent = ""
    if preserve_indent and start_line < len(lines):
        original_line = lines[start_line]
        original_indent = original_line[:len(original_line) - len(original_line.lstrip())]
    
    # 应用缩进到新代码
    new_lines = []
    for i, line in enumerate(new_class_code.splitlines()):
        if i == 0:
            new_lines.append(original_indent + line.lstrip())
        else:
            if line.strip():
                new_lines.append(original_indent + line.lstrip())
            else:
                new_lines.append("")
    
    # 替换代码
    result_lines = lines[:start_line] + new_lines + lines[end_line + 1:]
    
    return {
        "success": True,
        "lines": result_lines,
        "start_line": start_line + 1,
        "end_line": end_line + 1
    }


def replace_js_variable(
    lines: List[str],
    var_name: str,
    new_code: str,
    var_type: str,
    preserve_indent: bool
) -> Dict[str, Any]:
    """替换 JavaScript 变量声明"""
    # 匹配变量声明
    if var_type == "const":
        pattern = rf'(?:export\s+)?const\s+{re.escape(var_name)}\s*='
    elif var_type == "let":
        pattern = rf'(?:export\s+)?let\s+{re.escape(var_name)}\s*='
    else:  # var
        pattern = rf'(?:export\s+)?var\s+{re.escape(var_name)}\s*='
    
    start_idx = -1
    for i, line in enumerate(lines):
        if re.search(pattern, line):
            start_idx = i
            break
    
    if start_idx == -1:
        return {"success": False, "error": f"未找到变量: {var_name}", "lines": lines}
    
    # 查找变量声明的结束（分号或换行）
    end_idx = start_idx
    for i in range(start_idx, len(lines)):
        if ';' in lines[i]:
            end_idx = i
            break
    
    # 获取原始缩进
    original_indent = ""
    if preserve_indent and start_idx < len(lines):
        original_line = lines[start_idx]
        original_indent = original_line[:len(original_line) - len(original_line.lstrip())]
    
    # 应用缩进
    new_line = original_indent + new_code.lstrip()
    
    # 替换代码
    result_lines = lines[:start_idx] + [new_line] + lines[end_idx + 1:]
    
    return {
        "success": True,
        "lines": result_lines,
        "start_line": start_idx + 1,
        "end_line": end_idx + 1
    }


def replace_js_export(
    lines: List[str],
    export_name: str,
    new_code: str,
    preserve_indent: bool
) -> Dict[str, Any]:
    """替换 JavaScript 导出语句"""
    patterns = [
        rf'export\s+(?:default\s+)?(?:function|class|const|let|var)\s+{re.escape(export_name)}',
        rf'export\s+{{\s*{re.escape(export_name)}\s*}}',
    ]
    
    start_idx = -1
    for i, line in enumerate(lines):
        for pattern in patterns:
            if re.search(pattern, line):
                start_idx = i
                break
        if start_idx != -1:
            break
    
    if start_idx == -1:
        return {"success": False, "error": f"未找到导出: {export_name}", "lines": lines}
    
    # 简单处理：只替换这一行
    original_indent = ""
    if preserve_indent and start_idx < len(lines):
        original_line = lines[start_idx]
        original_indent = original_line[:len(original_line) - len(original_line.lstrip())]
    
    new_line = original_indent + new_code.lstrip()
    result_lines = lines[:start_idx] + [new_line] + lines[start_idx + 1:]
    
    return {
        "success": True,
        "lines": result_lines,
        "start_line": start_idx + 1,
        "end_line": start_idx + 1
    }


if __name__ == "__main__":
    # 测试示例
    test_js = """
function hello() {
    console.log("Hello");
}

const add = (a, b) => {
    return a + b;
};

class MyClass {
    constructor() {
        this.value = 0;
    }
}
"""
    
    print("JavaScript AST 解析工具已加载")
