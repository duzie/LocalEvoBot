from langchain_core.tools import tool
import json
import ast
import re
from datetime import datetime
from typing import Dict, Any
from web.backend.shared import shared


def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload


def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload


def _emit_event(tool_name: str, event: str, **fields):
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))


@tool
def ast_parse_replace(file_path: str, target_node: str, new_code: str, node_type: str = "function"):
    """
    基于AST解析的代码替换，保持代码结构完整性
    Args:
        file_path: 文件路径
        target_node: 目标节点标识（函数名、类名等）
        new_code: 新的代码内容
        node_type: 节点类型：function, class, import
    """
    tool_name = "ast_parse_replace"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_code = f.read()
        
        # 解析原始代码为AST
        try:
            tree = ast.parse(original_code)
        except SyntaxError as e:
            return _error_payload("syntax_error", f"原始代码存在语法错误: {e}", tool=tool_name)
        
        # 根据节点类型进行不同的处理
        if node_type == "function":
            modified_code = replace_function_in_ast(original_code, target_node, new_code)
        elif node_type == "class":
            modified_code = replace_class_in_ast(original_code, target_node, new_code)
        elif node_type == "import":
            modified_code = replace_import_in_ast(original_code, target_node, new_code)
        else:
            return _error_payload("invalid_type", f"不支持的节点类型: {node_type}", tool=tool_name)
        
        if modified_code is None:
            return _error_payload("not_found", f"未找到 {node_type}: {target_node}", tool=tool_name)
        
        # 验证修改后的代码语法
        try:
            ast.parse(modified_code)
        except SyntaxError as e:
            return _error_payload("syntax_error", f"修改后的代码存在语法错误: {e}", tool=tool_name)
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_code)
        
        result = {
            "file_path": file_path,
            "target_node": target_node,
            "node_type": node_type,
            "replacement_successful": True
        }
        
        _emit_event(tool_name, "completed", result=result)
        return _ok_payload(f"成功替换 {node_type} '{target_node}'", **result)
    
    except FileNotFoundError:
        err = _error_payload("file_not_found", f"文件不存在: {file_path}", tool=tool_name)
        _emit_event(tool_name, "error", error=f"文件不存在: {file_path}")
        return err
    except Exception as e:
        err = _error_payload("unknown_error", f"AST解析替换时发生错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err


def replace_function_in_ast(original_code: str, func_name: str, new_func_code: str) -> str:
    """
    在AST中替换函数定义
    """
    # 解析新函数代码
    try:
        new_tree = ast.parse(new_func_code)
    except SyntaxError:
        raise ValueError(f"新函数代码存在语法错误: {new_func_code}")
    
    # 查找新代码中的函数定义
    new_func_def = None
    for node in ast.walk(new_tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            new_func_def = node
            break
    
    if not new_func_def:
        raise ValueError(f"在新代码中找不到函数: {func_name}")
    
    # 将AST节点转换回代码
    new_func_source = ast.unparse(new_func_def) if hasattr(ast, 'unparse') else new_func_code
    
    # 在原始代码中查找并替换函数
    lines = original_code.split('\n')
    
    # 找到函数定义的开始行
    func_pattern = rf'(?:async\s+)?def\s+{re.escape(func_name)}\s*\('
    start_line_idx = -1
    for i, line in enumerate(lines):
        if re.match(r'\s*' + func_pattern, line):  # 检查行首可能的缩进
            start_line_idx = i
            break
    
    if start_line_idx == -1:
        return None  # 未找到函数
    
    # 找到函数定义的结束行（通过缩进判断）
    start_indent = len(lines[start_line_idx]) - len(lines[start_line_idx].lstrip())
    end_line_idx = start_line_idx
    for i in range(start_line_idx + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= start_indent and not line.isspace():
            end_line_idx = i
            break
    else:
        # 如果到达文件末尾仍未找到结束，则认为直到文件末尾
        end_line_idx = len(lines)
    
    # 构建新代码：函数之前的代码 + 新函数代码 + 函数之后的代码
    # 需要保持适当的缩进
    before_code = lines[:start_line_idx]
    after_code = lines[end_line_idx:]
    
    # 获取原函数的缩进
    original_indent = lines[start_line_idx][:len(lines[start_line_idx])-len(lines[start_line_idx].lstrip())]
    
    # 应用相同的缩进到新函数的每一行
    new_func_indented = []
    for i, line in enumerate(new_func_source.split('\n')):
        if i == 0:
            # 第一行使用原始缩进
            new_func_indented.append(original_indent + line)
        else:
            # 后续行需要根据与第一行的相对缩进来调整
            original_line_indent_len = len(line) - len(line.lstrip())
            if line.strip():  # 非空行
                new_func_indented.append(original_indent + line)
            else:  # 空行保持原样
                new_func_indented.append(line)
    
    # 组合所有部分
    result_lines = before_code + new_func_indented + after_code
    return '\n'.join(result_lines)


def replace_class_in_ast(original_code: str, class_name: str, new_class_code: str) -> str:
    """
    在AST中替换类定义
    """
    # 解析新类代码
    try:
        new_tree = ast.parse(new_class_code)
    except SyntaxError:
        raise ValueError(f"新类代码存在语法错误: {new_class_code}")
    
    # 查找新代码中的类定义
    new_class_def = None
    for node in ast.walk(new_tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            new_class_def = node
            break
    
    if not new_class_def:
        raise ValueError(f"在新代码中找不到类: {class_name}")
    
    # 将AST节点转换回代码
    new_class_source = ast.unparse(new_class_def) if hasattr(ast, 'unparse') else new_class_code
    
    # 在原始代码中查找并替换类
    lines = original_code.split('\n')
    
    # 找到类定义的开始行
    class_pattern = rf'class\s+{re.escape(class_name)}\s*[:\(]'
    start_line_idx = -1
    for i, line in enumerate(lines):
        if re.match(r'\s*' + class_pattern, line):  # 检查行首可能的缩进
            start_line_idx = i
            break
    
    if start_line_idx == -1:
        return None  # 未找到类
    
    # 找到类定义的结束行（通过缩进判断）
    start_indent = len(lines[start_line_idx]) - len(lines[start_line_idx].lstrip())
    end_line_idx = start_line_idx
    for i in range(start_line_idx + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= start_indent and not line.isspace():
            end_line_idx = i
            break
    else:
        # 如果到达文件末尾仍未找到结束，则认为直到文件末尾
        end_line_idx = len(lines)
    
    # 构建新代码：类之前的代码 + 新类代码 + 类之后的代码
    before_code = lines[:start_line_idx]
    after_code = lines[end_line_idx:]
    
    # 获取原类的缩进
    original_indent = lines[start_line_idx][:len(lines[start_line_idx])-len(lines[start_line_idx].lstrip())]
    
    # 应用相同的缩进到新类的每一行
    new_class_indented = []
    for i, line in enumerate(new_class_source.split('\n')):
        if i == 0:
            # 第一行使用原始缩进
            new_class_indented.append(original_indent + line)
        else:
            # 后续行需要根据与第一行的相对缩进来调整
            original_line_indent_len = len(line) - len(line.lstrip())
            if line.strip():  # 非空行
                new_class_indented.append(original_indent + line)
            else:  # 空行保持原样
                new_class_indented.append(line)
    
    # 组合所有部分
    result_lines = before_code + new_class_indented + after_code
    return '\n'.join(result_lines)


def replace_import_in_ast(original_code: str, import_name: str, new_import_code: str) -> str:
    """
    在AST中替换导入语句
    """
    lines = original_code.split('\n')
    
    # 找到导入语句
    import_patterns = [
        rf'import\s+{re.escape(import_name)}(?:\s|,|$)',
        rf'from\s+{re.escape(import_name)}\s+import',
        rf'from\s+\w+\s+import\s+.*\b{re.escape(import_name)}\b'
    ]
    
    for i, line in enumerate(lines):
        for pattern in import_patterns:
            if re.search(pattern, line):
                # 替换这一行
                lines[i] = new_import_code
                return '\n'.join(lines)
    
    return None  # 未找到导入语句


if __name__ == "__main__":
    # 示例使用
    result = ast_parse_replace("example.py", "my_function", "def my_function(): pass", "function")
    print(result)