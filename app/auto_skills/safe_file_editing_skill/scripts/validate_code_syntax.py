from langchain_core.tools import tool
import os
import ast
import json
import subprocess
from typing import Dict, Any

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
    
    Args:
        file_path: 要检查的文件路径
        language: 语言类型，默认为 "auto" (根据扩展名自动检测)
                  可选值: "python", "javascript", "json"
                  
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
            else:
                return {"success": False, "error": f"无法自动检测文件类型: {ext}，请手动指定语言"}
        
        language = language.lower()
        
        if language == "python":
            return _check_python_syntax(file_path)
        elif language == "javascript":
            return _check_javascript_syntax(file_path)
        elif language == "json":
            return _check_json_syntax(file_path)
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
