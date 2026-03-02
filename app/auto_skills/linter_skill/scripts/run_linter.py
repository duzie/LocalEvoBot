from langchain_core.tools import tool
import subprocess
import json
import os
import sys
from typing import Dict, Any, List

@tool
def run_linter(file_path: str) -> Dict[str, Any]:
    """
    运行代码检查工具 (Linter) 来发现代码中的错误。
    优先使用 ruff，如果不可用则使用 python 自带的编译检查。
    
    Args:
        file_path: 要检查的文件路径
        
    Returns:
        包含检查结果的字典。如果发现错误，success 为 False 并包含 errors 列表。
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"文件不存在: {file_path}"}
        
    ext = os.path.splitext(file_path)[1].lower()
    if ext != '.py':
        return {"success": True, "message": f"暂不支持非 Python 文件检查: {ext}"}
        
    errors = []
    
    # 1. 尝试使用 ruff (极速 linter)
    try:
        # 使用 --output-format json 获取结构化输出
        # 使用 --select E,F,W 来检查错误、未定义变量等
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", file_path, "--output-format", "json", "--select", "E,F,W"],
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            try:
                ruff_errors = json.loads(result.stdout)
                for err in ruff_errors:
                    errors.append({
                        "line": err.get("location", {}).get("row", 0),
                        "col": err.get("location", {}).get("column", 0),
                        "message": err.get("message", ""),
                        "code": err.get("code", ""),
                        "source": "ruff"
                    })
            except json.JSONDecodeError:
                # Fallback if json parsing fails
                pass
                
    except Exception as e:
        # 如果 ruff 运行失败，忽略并尝试下一个方法
        pass
        
    # 2. 如果 ruff 没发现严重错误（或者没运行），尝试使用 compile() 进行基本的语法检查
    # ruff 可能没装，或者配置不对。compile() 是最后的防线。
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        compile(content, file_path, 'exec')
    except SyntaxError as e:
        # 避免重复报告
        if not any(err['line'] == e.lineno and 'SyntaxError' in err['message'] for err in errors):
            errors.append({
                "line": e.lineno,
                "col": e.offset,
                "message": f"SyntaxError: {e.msg}",
                "code": "SyntaxError",
                "source": "python_compile"
            })
    except Exception as e:
        errors.append({
            "line": 0,
            "col": 0,
            "message": str(e),
            "code": "CompileError",
            "source": "python_compile"
        })

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
            "message": "代码检查通过，未发现明显错误。"
        }
