from langchain_core.tools import tool
import os
import ast
import json
import subprocess
import re
from typing import Dict, Any

def _remove_csharp_comments_and_strings(content: str) -> str:
    """
    Removes comments and strings from C# code to safely analyze braces.
    Preserves newlines to keep line numbers consistent.
    """
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
        
        if c == '\n':
            result.append('\n')
            in_single_line_comment = False
            i += 1
            continue
            
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
            
        if in_verbatim_string:
            if c == '"':
                if i + 1 < n and content[i+1] == '"': 
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
            if c == '\\': 
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
            
        result.append(c)
        i += 1
        
    return "".join(result)

@tool
def validate_code_syntax(
    file_path: str,
    language: str = "auto"
) -> Dict[str, Any]:
    """
    检查代码文件的语法是否正确。
    支持的语言：
    - Python (.py)
    - JavaScript (.js, .mjs, .cjs)
    - JSON (.json)
    - C# (.cs)
    
    Args:
        file_path: 要检查的文件路径
        language: 语言类型，默认为 "auto" (根据扩展名自动检测)
                  可选值: "python", "javascript", "json", "csharp"
                  
    Returns:
        检查结果，包含是否通过及错误详情
    """
    try:
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
            
        # 自动检测语言
        if language == "auto":
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".py":
                language = "python"
            elif ext in [".js", ".mjs", ".cjs"]:
                language = "javascript"
            elif ext == ".json":
                language = "json"
            elif ext == ".cs":
                language = "csharp"
            else:
                return {"success": False, "error": f"无法自动检测文件类型: {ext}，请手动指定语言"}
        
        language = language.lower()
        
        if language == "python":
            return _check_python_syntax(file_path)
        elif language == "javascript":
            return _check_javascript_syntax(file_path)
        elif language == "json":
            return _check_json_syntax(file_path)
        elif language == "csharp":
            return _check_csharp_syntax(file_path)
        else:
            return {"success": False, "error": f"不支持的语言: {language}"}
            
    except Exception as e:
        return {"success": False, "error": f"执行出错: {str(e)}"}

def _check_python_syntax(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        ast.parse(source)
        return {"success": True, "message": "Python 语法检查通过"}
    except SyntaxError as e:
        return {
            "success": False,
            "error": f"Python 语法错误: {e.msg}",
            "line": e.lineno,
            "offset": e.offset,
            "text": e.text
        }
    except Exception as e:
        return {"success": False, "error": f"Python 检查失败: {str(e)}"}

def _check_javascript_syntax(file_path: str) -> Dict[str, Any]:
    try:
        # 使用 node --check (-c) 检查语法
        # capture_output=True 需要 Python 3.7+
        result = subprocess.run(
            ["node", "--check", file_path],
            capture_output=True,
            text=True,
            encoding="utf-8"  # 显式指定编码，防止 Windows 下乱码
        )
        
        if result.returncode == 0:
            return {"success": True, "message": "JavaScript 语法检查通过"}
        else:
            # node --check 的错误输出通常在 stderr
            error_msg = result.stderr.strip() or result.stdout.strip()
            return {
                "success": False,
                "error": f"JavaScript 语法错误:\n{error_msg}"
            }
    except FileNotFoundError:
        return {"success": False, "error": "未找到 node 命令，无法检查 JavaScript 语法"}
    except Exception as e:
        return {"success": False, "error": f"JavaScript 检查失败: {str(e)}"}

def _check_json_syntax(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json.load(f)
        return {"success": True, "message": "JSON 语法检查通过"}
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"JSON 语法错误: {e.msg}",
            "line": e.lineno,
            "column": e.colno
        }
    except Exception as e:
        return {"success": False, "error": f"JSON 检查失败: {str(e)}"}

def _check_csharp_syntax(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 1. 基础括号匹配检查 (忽略注释和字符串)
        clean_content = _remove_csharp_comments_and_strings(content)
        open_braces = clean_content.count('{')
        close_braces = clean_content.count('}')
        
        if open_braces != close_braces:
            return {
                "success": False, 
                "error": f"C# 括号不匹配: {{ = {open_braces}, }} = {close_braces}. 请检查代码结构。"
            }
            
        # 2. 尝试使用 dotnet build (如果存在项目文件)
        # 向上查找 .csproj
        current_dir = os.path.dirname(file_path)
        project_file = None
        for _ in range(3): # check 3 levels up
            try:
                files = os.listdir(current_dir)
                for f in files:
                    if f.endswith('.csproj'):
                        project_file = os.path.join(current_dir, f)
                        break
                if project_file: break
                parent = os.path.dirname(current_dir)
                if parent == current_dir: break
                current_dir = parent
            except Exception:
                break
                
        if project_file:
            # 尝试构建
            try:
                # 只构建，不恢复依赖，不显示 logo，静默模式
                # 注意：这可能会因为环境缺失依赖而失败，不一定是因为语法错误
                # 所以如果 build 失败，我们只作为警告，或者只提取语法相关错误？
                # 简单起见，如果 build 失败，我们返回错误，但提示可能是环境问题。
                cmd = ["dotnet", "build", project_file, "--no-restore", "--nologo", "-v", "q"]
                result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
                
                if result.returncode == 0:
                    return {"success": True, "message": "C# 语法检查通过 (dotnet build 成功)"}
                else:
                    # 检查输出中是否有当前文件的错误
                    filename = os.path.basename(file_path)
                    if filename in result.stdout:
                        # 提取相关错误行
                        errors = []
                        for line in result.stdout.split('\n'):
                            if filename in line and "Error" in line:
                                errors.append(line.strip())
                        
                        if errors:
                            return {
                                "success": False, 
                                "error": f"C# 编译错误:\n" + "\n".join(errors[:5])
                            }
            except Exception:
                pass # dotnet build 失败忽略，只依赖括号检查
                
        return {"success": True, "message": "C# 基础语法检查通过 (括号匹配)"}
        
    except Exception as e:
        return {"success": False, "error": f"C# 检查失败: {str(e)}"}
