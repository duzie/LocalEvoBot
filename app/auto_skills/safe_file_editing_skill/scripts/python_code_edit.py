from langchain_core.tools import tool
import os
import ast
import shutil
from typing import Dict, Any, Optional
import re

def _find_node(tree, name, node_type):
    for node in ast.walk(tree):
        if isinstance(node, node_type) and node.name == name:
            return node
    return None

def _get_node_source_range(content: str, node):
    """
    获取节点在源代码中的准确字节范围。
    为了安全替换（包括缩进），我们扩展到整行范围。
    """
    lines = content.splitlines(keepends=True)
    
    # 确保行号有效
    if node.lineno < 1 or node.lineno > len(lines):
        return None, None
        
    start_line_idx = node.lineno - 1
    
    # 计算起始位置：从该行行首开始
    # 注意：这会包含该行的缩进
    start_byte = 0
    for i in range(start_line_idx):
        start_byte += len(lines[i])
    
    # 计算结束位置
    if node.end_lineno is None:
        return None, None
        
    end_line_idx = node.end_lineno - 1
    if end_line_idx >= len(lines):
        end_line_idx = len(lines) - 1
        
    end_byte = 0
    for i in range(end_line_idx + 1): # +1 因为包含结束行
        end_byte += len(lines[i])
    
    return start_byte, end_byte

import subprocess
import sys
import json

@tool
def python_code_edit(
    file_path: str,
    edit_type: str,
    name: str,
    new_code: str,
    backup: bool = True
) -> Dict[str, Any]:
    """
    基于 AST 的 Python 代码精准编辑工具。
    
    Args:
        file_path: Python 文件路径
        edit_type: 编辑类型，支持 'replace_function', 'replace_class'
        name: 要替换的函数名或类名
        new_code: 新的代码块（完整的函数或类定义）
        backup: 是否创建备份
        
    Returns:
        执行结果
    """
    try:
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 1. 验证原始内容语法
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return {"success": False, "error": f"原文件存在语法错误，无法解析: {e}"}
            
        # 2. 验证新代码语法
        try:
            ast.parse(new_code)
        except SyntaxError as e:
            return {"success": False, "error": f"新代码存在语法错误: {e}"}

        # 3. 查找目标节点
        target_node = None
        if edit_type == 'replace_function':
            target_node = _find_node(tree, name, ast.FunctionDef)
            # 同时也查找 AsyncFunctionDef
            if not target_node:
                 target_node = _find_node(tree, name, ast.AsyncFunctionDef)
        elif edit_type == 'replace_class':
            target_node = _find_node(tree, name, ast.ClassDef)
        else:
            return {"success": False, "error": f"不支持的编辑类型: {edit_type}"}
            
        if not target_node:
            return {"success": False, "error": f"未找到目标 {edit_type}: {name}"}
            
        # 4. 获取替换范围
        start, end = _get_node_source_range(content, target_node)
        if start is None or end is None:
            return {"success": False, "error": "无法定位目标代码块的结束位置"}
            
        # 5. 执行替换
        # 智能处理缩进
        target_indent = target_node.col_offset
        
        # 检查新代码的第一行缩进
        new_lines = new_code.splitlines()
        if not new_lines:
            return {"success": False, "error": "新代码为空"}
            
        first_line = new_lines[0]
        current_indent = len(first_line) - len(first_line.lstrip())
        
        if current_indent < target_indent:
            # 需要增加缩进
            indent_diff = target_indent - current_indent
            indent_str = " " * indent_diff
            new_code_adjusted = "\n".join([indent_str + line if line.strip() else line for line in new_lines])
            if new_code.endswith('\n'):
                new_code_adjusted += '\n'
            new_code = new_code_adjusted
            
        # 检查新代码是否以 newline 结尾，如果没有，补一个，保持格式整洁
        if not new_code.endswith('\n'):
            new_code += '\n'
            
        new_content = content[:start] + new_code + content[end:]
        
        # 6. 再次验证完整内容的语法
        try:
            ast.parse(new_content)
        except SyntaxError as e:
             return {"success": False, "error": f"替换后导致语法错误 (可能是缩进或上下文问题): {e}"}

        # 7. 写入文件
        if backup:
            shutil.copy2(file_path, file_path + ".bak")
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # 8. 运行轻量级 Linter 检查 (Ruff)
        linter_warnings = []
        try:
            # 尝试调用 ruff
            cmd = [sys.executable, "-m", "ruff", "check", file_path, "--output-format", "json", "--select", "E,F,W"]
            result_proc = subprocess.run(cmd, capture_output=True, text=True)
            if result_proc.stdout:
                try:
                    errors = json.loads(result_proc.stdout)
                    for err in errors:
                        # 只关注替换区域附近的错误，或者严重的语法/未定义错误
                        err_line = err.get("location", {}).get("row", 0)
                        # 简单起见，返回所有错误，让 Agent 自己判断
                        linter_warnings.append({
                            "line": err_line,
                            "message": err.get("message", ""),
                            "code": err.get("code", "")
                        })
                except:
                    pass
        except Exception:
            pass
            
        result = {
            "success": True, 
            "message": f"成功替换 {name}",
            "original_range": [start, end],
            "new_length": len(new_code)
        }
        
        if linter_warnings:
            result["linter_warnings"] = linter_warnings
            result["message"] += f" (注意: Linter 发现 {len(linter_warnings)} 个潜在问题，请检查是否引入了错误)"
            
        return result

        
    except Exception as e:
        return {"success": False, "error": f"执行出错: {str(e)}"}
