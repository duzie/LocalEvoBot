"""
JavaScript 代码结构分析工具
分析 JS 文件中的函数、类、变量、导入导出等结构
"""
from langchain_core.tools import tool
import json
import re
from datetime import datetime
from typing import Dict, Any, List
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


def find_js_functions(content: str) -> List[Dict[str, Any]]:
    """查找 JavaScript 函数"""
    functions = []
    lines = content.splitlines()
    
    # 匹配模式
    patterns = [
        # 普通函数: function name() {}
        (r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)', 'function'),
        # 箭头函数: const name = () => {}
        (r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=])*=>', 'arrow'),
        # 方法简写: name() {}
        (r'(\w+)\s*\([^)]*\)\s*{', 'method'),
    ]
    
    for i, line in enumerate(lines):
        for pattern, func_type in patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                name = match.group(1)
                
                # 跳过关键字
                if name in ['if', 'for', 'while', 'switch', 'catch', 'class', 'function']:
                    continue
                
                functions.append({
                    "name": name,
                    "type": func_type,
                    "line": i + 1,
                    "column": match.start() + 1,
                    "code": line.strip()
                })
    
    return functions


def find_js_classes(content: str) -> List[Dict[str, Any]]:
    """查找 JavaScript 类"""
    classes = []
    lines = content.splitlines()
    
    pattern = r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?\s*{'
    
    for i, line in enumerate(lines):
        match = re.search(pattern, line)
        if match:
            class_name = match.group(1)
            parent_class = match.group(2) if match.group(2) else None
            
            classes.append({
                "name": class_name,
                "extends": parent_class,
                "line": i + 1,
                "column": match.start() + 1,
                "code": line.strip()
            })
    
    return classes


def find_js_variables(content: str) -> List[Dict[str, Any]]:
    """查找 JavaScript 变量声明"""
    variables = []
    lines = content.splitlines()
    
    patterns = [
        (r'(?:export\s+)?const\s+(\w+)\s*=', 'const'),
        (r'(?:export\s+)?let\s+(\w+)\s*=', 'let'),
        (r'(?:export\s+)?var\s+(\w+)\s*=', 'var'),
    ]
    
    for i, line in enumerate(lines):
        for pattern, var_type in patterns:
            match = re.search(pattern, line)
            if match:
                name = match.group(1)
                variables.append({
                    "name": name,
                    "type": var_type,
                    "line": i + 1,
                    "column": match.start() + 1,
                    "code": line.strip()
                })
    
    return variables


def find_js_imports(content: str) -> List[Dict[str, Any]]:
    """查找 JavaScript 导入语句"""
    imports = []
    lines = content.splitlines()
    
    patterns = [
        # import defaultExport from 'module'
        (r"import\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]", 'default'),
        # import { export1, export2 } from 'module'
        (r"import\s+{([^}]+)}\s+from\s+['\"]([^'\"]+)['\"]", 'named'),
        # import * as name from 'module'
        (r"import\s+\*\s+as\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]", 'namespace'),
        # import 'module'
        (r"import\s+['\"]([^'\"]+)['\"]", 'side-effect'),
    ]
    
    for i, line in enumerate(lines):
        for pattern, import_type in patterns:
            match = re.search(pattern, line)
            if match:
                if import_type == 'side-effect':
                    imports.append({
                        "type": import_type,
                        "module": match.group(1),
                        "line": i + 1,
                        "code": line.strip()
                    })
                else:
                    imports.append({
                        "type": import_type,
                        "name": match.group(1),
                        "module": match.group(2),
                        "line": i + 1,
                        "code": line.strip()
                    })
    
    return imports


def find_js_exports(content: str) -> List[Dict[str, Any]]:
    """查找 JavaScript 导出语句"""
    exports = []
    lines = content.splitlines()
    
    patterns = [
        # export default name
        (r'export\s+default\s+(\w+)', 'default'),
        # export { name1, name2 }
        (r'export\s+{([^}]+)}', 'named'),
        # export const/let/var/function/class name
        (r'export\s+(?:const|let|var|function|class)\s+(\w+)', 'declaration'),
    ]
    
    for i, line in enumerate(lines):
        for pattern, export_type in patterns:
            match = re.search(pattern, line)
            if match:
                exports.append({
                    "type": export_type,
                    "name": match.group(1) if match.lastindex else None,
                    "line": i + 1,
                    "code": line.strip()
                })
    
    return exports


def analyze_js_complexity(content: str) -> Dict[str, Any]:
    """分析 JavaScript 代码复杂度"""
    lines = content.splitlines()
    
    # 统计代码行数
    total_lines = len(lines)
    blank_lines = sum(1 for line in lines if not line.strip())
    comment_lines = sum(1 for line in lines if line.strip().startswith('//') or line.strip().startswith('/*'))
    code_lines = total_lines - blank_lines - comment_lines
    
    # 统计函数和类
    functions = find_js_functions(content)
    classes = find_js_classes(content)
    
    return {
        "total_lines": total_lines,
        "code_lines": code_lines,
        "blank_lines": blank_lines,
        "comment_lines": comment_lines,
        "function_count": len(functions),
        "class_count": len(classes),
        "average_function_length": code_lines / len(functions) if functions else 0
    }


@tool
def analyze_js_structure(file_path: str) -> Dict[str, Any]:
    """
    分析 JavaScript 文件的代码结构
    
    Args:
        file_path: JavaScript 文件路径
    """
    tool_name = "analyze_js_structure"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 分析各种结构
        functions = find_js_functions(content)
        classes = find_js_classes(content)
        variables = find_js_variables(content)
        imports = find_js_imports(content)
        exports = find_js_exports(content)
        complexity = analyze_js_complexity(content)
        
        result = {
            "file_path": file_path,
            "structures": {
                "functions": functions,
                "classes": classes,
                "variables": variables,
                "imports": imports,
                "exports": exports
            },
            "statistics": {
                "function_count": len(functions),
                "class_count": len(classes),
                "variable_count": len(variables),
                "import_count": len(imports),
                "export_count": len(exports),
                **complexity
            },
            "summary": {
                "has_default_export": any(e["type"] == "default" for e in exports),
                "main_exports": [e["name"] for e in exports if e.get("name")],
                "dependencies": [i["module"] for i in imports if i.get("module")]
            }
        }
        
        _emit_event(tool_name, "completed", result=result)
        return _ok_payload(
            f"分析完成: 找到 {len(functions)} 个函数, {len(classes)} 个类",
            **result
        )
    
    except FileNotFoundError:
        err = _error_payload("file_not_found", f"文件不存在: {file_path}", tool=tool_name)
        _emit_event(tool_name, "error", error=f"文件不存在: {file_path}")
        return err
    except Exception as e:
        err = _error_payload("unknown_error", f"分析 JavaScript 结构时发生错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err


if __name__ == "__main__":
    print("JavaScript 代码结构分析工具已加载")
