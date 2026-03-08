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
def validate_code_changes(file_path: str, start_line: int, end_line: int):
    """
    验证代码修改的语法正确性和完整性
    Args:
        file_path: 文件路径
        start_line: 起始行号
        end_line: 结束行号
    """
    tool_name = "validate_code_changes"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 获取指定行范围的代码
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            return _error_payload("invalid_range", f"无效的行号范围: {start_line}-{end_line} (文件共{len(lines)}行)", tool=tool_name)
        
        # 获取验证范围的代码（稍微扩大范围以包含上下文）
        validation_start = max(0, start_line - 5)  # 包含前后几行上下文
        validation_end = min(len(lines), end_line + 5)
        
        # 验证整个文件的语法
        content = ''.join(lines)
        try:
            tree = ast.parse(content)
            file_syntax_valid = True
        except SyntaxError as e:
            file_syntax_valid = False
            syntax_error = str(e)
        
        # 验证指定范围的语法
        target_content = ''.join(lines[start_line-1:end_line])
        target_syntax_valid = True
        target_syntax_error = None
        try:
            ast.parse(target_content)
        except SyntaxError as e:
            target_syntax_valid = False
            target_syntax_error = str(e)
        
        # 额外检查：括号、引号等是否匹配
        bracket_balance = check_bracket_balance(target_content)
        quote_balance = check_quote_balance(target_content)
        
        # 生成验证报告
        validation_report = {
            "file_path": file_path,
            "validated_range": f"{start_line}-{end_line}",
            "file_syntax_valid": file_syntax_valid,
            "target_syntax_valid": target_syntax_valid,
            "bracket_balance_ok": bracket_balance["ok"],
            "quote_balance_ok": quote_balance["ok"],
            "issues": []
        }
        
        if not file_syntax_valid:
            validation_report["issues"].append({
                "type": "syntax_error",
                "severity": "critical",
                "message": f"整个文件存在语法错误: {syntax_error}"
            })
        
        if not target_syntax_valid:
            validation_report["issues"].append({
                "type": "target_syntax_error",
                "severity": "high",
                "message": f"目标范围存在语法错误: {target_syntax_error}"
            })
        
        if not bracket_balance["ok"]:
            validation_report["issues"].append({
                "type": "bracket_mismatch",
                "severity": "medium",
                "message": f"括号不匹配: {bracket_balance['details']}"
            })
        
        if not quote_balance["ok"]:
            validation_report["issues"].append({
                "type": "quote_mismatch", 
                "severity": "medium",
                "message": f"引号不匹配: {quote_balance['details']}"
            })
        
        # 判断总体验证结果
        overall_valid = (
            file_syntax_valid and 
            target_syntax_valid and 
            bracket_balance["ok"] and 
            quote_balance["ok"]
        )
        
        result = {
            "validation_report": validation_report,
            "overall_valid": overall_valid
        }
        
        status_msg = f"验证完成 - 整体{'通过' if overall_valid else '失败'}"
        if overall_valid:
            _emit_event(tool_name, "completed", result=result)
            return _ok_payload(status_msg, **result)
        else:
            _emit_event(tool_name, "warning", result=result)
            return _ok_payload(status_msg, **result)
    
    except FileNotFoundError:
        err = _error_payload("file_not_found", f"文件不存在: {file_path}", tool=tool_name)
        _emit_event(tool_name, "error", error=f"文件不存在: {file_path}")
        return err
    except Exception as e:
        err = _error_payload("unknown_error", f"验证代码时发生错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err


def check_bracket_balance(content: str) -> Dict[str, Any]:
    """
    检查括号平衡
    """
    stack = []
    brackets_map = {')': '(', ']': '[', '}': '{'}
    opening_brackets = set(['(', '[', '{'])
    closing_brackets = set([')', ']', '}'])
    
    # 遍历内容，只考虑非字符串内的括号
    in_string = False
    string_char = None
    escaped = False
    
    for i, char in enumerate(content):
        if escaped:
            escaped = False
            continue
        
        if char in ['"', "'"] and not escaped:
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
        elif char == '\\':
            escaped = True
        elif not in_string:  # 只在字符串外检查括号
            if char in opening_brackets:
                stack.append(char)
            elif char in closing_brackets:
                if not stack or stack[-1] != brackets_map[char]:
                    return {
                        "ok": False,
                        "details": f"位置 {i} 发现不匹配的括号: {char}"
                    }
                stack.pop()
    
    if stack:
        return {
            "ok": False,
            "details": f"存在未闭合的括号: {stack}"
        }
    
    return {
        "ok": True,
        "details": "括号平衡"
    }


def check_quote_balance(content: str) -> Dict[str, Any]:
    """
    检查引号平衡
    """
    # 简单检查单引号和双引号
    single_quotes = 0
    double_quotes = 0
    triple_single_quotes = 0  # '''
    triple_double_quotes = 0  # """
    
    i = 0
    while i < len(content):
        char = content[i]
        
        # 检查三引号
        if content[i:i+3] == "'''" and not (i > 0 and content[i-1] == '\\'):
            triple_single_quotes += 1
            i += 3
            continue
        elif content[i:i+3] == '"""' and not (i > 0 and content[i-1] == '\\'):
            triple_double_quotes += 1
            i += 3
            continue
        
        # 检查普通引号
        if char == "'" and not (i > 0 and content[i-1] == '\\'):
            single_quotes += 1
        elif char == '"' and not (i > 0 and content[i-1] == '\\'):
            double_quotes += 1
        
        i += 1
    
    issues = []
    if single_quotes % 2 != 0:
        issues.append(f"单引号不平衡: {single_quotes}个")
    if double_quotes % 2 != 0:
        issues.append(f"双引号不平衡: {double_quotes}个")
    if triple_single_quotes % 2 != 0:
        issues.append(f"三单引号不平衡: {triple_single_quotes}个")
    if triple_double_quotes % 2 != 0:
        issues.append(f"三双引号不平衡: {triple_double_quotes}个")
    
    if issues:
        return {
            "ok": False,
            "details": ", ".join(issues)
        }
    
    return {
        "ok": True,
        "details": "引号平衡"
    }


if __name__ == "__main__":
    # 示例使用
    result = validate_code_changes("example.py", 10, 20)
    print(result)