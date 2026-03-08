"""
validate_js - JavaScript 语法校验工具

使用 Python 的 jsbeautifier 或 subprocess 调用 node 来验证 JS 语法。
"""

from langchain_core.tools import tool
import os
import subprocess
import sys
from typing import Dict, Any


@tool
def validate_js(file_path: str, use_eslint: bool = False) -> Dict[str, Any]:
    """
    JavaScript 语法校验工具
    
    Args:
        file_path: JS 文件路径
        use_eslint: 是否使用 ESLint（默认 False，仅语法检查）
    
    Returns:
        {
            "success": True/False,
            "message": "校验通过/失败",
            "errors": [
                {
                    "line": 行号，
                    "col": 列号，
                    "message": "错误信息",
                    "code": "错误代码"
                }
            ]
        }
    """
    tool_name = "validate_js"
    
    try:
        # 1. 检查文件
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在：{file_path}"
            }
        
        # 2. 检查扩展名
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ['.js', '.jsx', '.mjs', '.cjs']:
            return {
                "success": False,
                "error": f"不是 JavaScript 文件：{ext}"
            }
        
        # 3. 读取文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception:
                return {
                    "success": False,
                    "error": "无法读取文件（编码不支持）"
                }
        
        errors = []
        
        # 4. 方法 1: 使用 Node.js 检查（如果可用）
        if use_eslint:
            # 尝试使用 ESLint
            try:
                result = subprocess.run(
                    ['node', '-e', f'require("eslint").CLIEngine.executeOnFiles(["{file_path}"])'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    # 解析 ESLint 输出
                    for line in result.stdout.split('\n') + result.stderr.split('\n'):
                        if ':' in line and ('error' in line.lower() or 'warning' in line.lower()):
                            parts = line.split(':')
                            if len(parts) >= 3:
                                try:
                                    errors.append({
                                        "line": int(parts[0].strip()),
                                        "col": int(parts[1].strip()),
                                        "message": ':'.join(parts[2:]).strip(),
                                        "code": "ESLint"
                                    })
                                except ValueError:
                                    pass
            except Exception:
                # ESLint 不可用，降级到基本检查
                pass
        
        # 5. 方法 2: 使用 Node.js 语法检查
        if not errors:
            try:
                # 使用 Node.js 的 --check 参数（Node 12+）
                result = subprocess.run(
                    ['node', '--check', file_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    # 解析 Node.js 错误输出
                    for line in result.stderr.split('\n'):
                        if ':' in line and ('SyntaxError' in line or 'Error' in line):
                            # 尝试提取行号
                            import re
                            match = re.search(r':(\d+):(\d+)', line)
                            if match:
                                errors.append({
                                    "line": int(match.group(1)),
                                    "col": int(match.group(2)),
                                    "message": line.strip(),
                                    "code": "SyntaxError"
                                })
                            else:
                                errors.append({
                                    "line": 0,
                                    "col": 0,
                                    "message": line.strip(),
                                    "code": "SyntaxError"
                                })
            except FileNotFoundError:
                # Node.js 不可用，使用 Python 基本检查
                pass
            except Exception as e:
                errors.append({
                    "line": 0,
                    "col": 0,
                    "message": f"Node.js 检查失败：{e}",
                    "code": "NodeCheckError"
                })
        
        # 6. 方法 3: Python 基本语法检查（降级方案）
        if not errors:
            # 检查明显的语法错误
            lines = content.split('\n')
            
            # 括号匹配检查
            paren_count = 0
            brace_count = 0
            bracket_count = 0
            
            for line_num, line in enumerate(lines, 1):
                # 跳过注释和字符串
                in_string = False
                string_char = None
                
                for i, char in enumerate(line):
                    if char in ['"', "'"] and (i == 0 or line[i-1] != '\\'):
                        if not in_string:
                            in_string = True
                            string_char = char
                        elif char == string_char:
                            in_string = False
                    
                    if not in_string:
                        if char == '(':
                            paren_count += 1
                        elif char == ')':
                            paren_count -= 1
                        elif char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                        elif char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                
                # 检查是否负数
                if paren_count < 0:
                    errors.append({
                        "line": line_num,
                        "col": 0,
                        "message": "多余的闭合括号 )",
                        "code": "EXTRA_PAREN"
                    })
                    paren_count = 0
                elif brace_count < 0:
                    errors.append({
                        "line": line_num,
                        "col": 0,
                        "message": "多余的闭合大括号 }}",
                        "code": "EXTRA_BRACE"
                    })
                    brace_count = 0
                elif bracket_count < 0:
                    errors.append({
                        "line": line_num,
                        "col": 0,
                        "message": "多余的闭合中括号 ]",
                        "code": "EXTRA_BRACKET"
                    })
                    bracket_count = 0
            
            # 检查未闭合的括号
            if paren_count > 0:
                errors.append({
                    "line": len(lines),
                    "col": 0,
                    "message": f"未闭合的括号 ( 共{paren_count}个",
                    "code": "UNCLOSED_PAREN"
                })
            
            if brace_count > 0:
                errors.append({
                    "line": len(lines),
                    "col": 0,
                    "message": f"未闭合的大括号 {{ 共{brace_count}个",
                    "code": "UNCLOSED_BRACE"
                })
            
            if bracket_count > 0:
                errors.append({
                    "line": len(lines),
                    "col": 0,
                    "message": f"未闭合的中括号 [ 共{bracket_count}个",
                    "code": "UNCLOSED_BRACKET"
                })
            
            # 检查分号（可选，仅警告）
            # 这个检查可能过于严格，因为现代 JS 允许省略分号
            # 所以不加入错误列表
        
        # 7. 返回结果
        if errors:
            return {
                "success": False,
                "file_path": file_path,
                "error_count": len(errors),
                "errors": errors
            }
        else:
            return {
                "success": True,
                "message": "JavaScript 语法校验通过"
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"校验失败：{e}"
        }


@tool
def check_js_compatibility(file_path: str, target_es_version: str = "es6") -> Dict[str, Any]:
    """
    检查 JavaScript 代码的 ECMAScript 版本兼容性
    
    Args:
        file_path: JS 文件路径
        target_es_version: 目标 ES 版本（es5, es6, es2017, 等）
    
    Returns:
        {
            "success": True/False,
            "target_version": "es6",
            "incompatible_features": [...]
        }
    """
    tool_name = "check_js_compatibility"
    
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在：{file_path}"
            }
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        incompatible = []
        
        # ES5 不支持的特性
        if target_es_version.lower() == 'es5':
            es5_features = {
                r'let\s+\w+': 'let 关键字（ES6）',
                r'const\s+\w+': 'const 关键字（ES6）',
                r'=>': '箭头函数（ES6）',
                r'class\s+\w+': 'class 类（ES6）',
                r'import\s+.*from': 'import 模块（ES6）',
                r'export\s+': 'export 模块（ES6）',
                r'async\s+function': 'async 函数（ES8）',
                r'await\s+': 'await（ES8）',
            }
            
            import re
            for pattern, feature in es5_features.items():
                if re.search(pattern, content):
                    incompatible.append({
                        "feature": feature,
                        "pattern": pattern
                    })
        
        return {
            "success": True,
            "target_version": target_es_version,
            "incompatible_features": incompatible,
            "message": f"发现 {len(incompatible)} 个不兼容 {target_es_version} 的特性" if incompatible else f"代码兼容 {target_es_version}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"检查失败：{e}"
        }
