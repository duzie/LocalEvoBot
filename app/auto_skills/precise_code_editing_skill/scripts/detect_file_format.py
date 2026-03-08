"""
文件格式检测工具
自动检测文件的编码、换行符、语言等格式信息
"""
from langchain_core.tools import tool
import json
import os
from datetime import datetime
from typing import Dict, Any
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


def detect_encoding(file_path: str) -> Dict[str, Any]:
    """检测文件编码"""
    try:
        import chardet
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            return {
                "encoding": result.get('encoding', 'utf-8'),
                "confidence": result.get('confidence', 0.0),
                "language": result.get('language', '')
            }
    except Exception as e:
        return {
            "encoding": "utf-8",
            "confidence": 0.0,
            "language": "",
            "error": str(e)
        }


def detect_line_ending(content: str) -> Dict[str, Any]:
    """检测换行符类型"""
    crlf_count = content.count('\r\n')
    lf_count = content.count('\n') - crlf_count
    cr_count = content.count('\r') - crlf_count
    
    total = crlf_count + lf_count + cr_count
    
    if total == 0:
        return {
            "type": "none",
            "description": "无换行符",
            "char": ""
        }
    
    if crlf_count > lf_count and crlf_count > cr_count:
        return {
            "type": "crlf",
            "description": "Windows风格 (\\r\\n)",
            "char": "\r\n",
            "count": crlf_count
        }
    elif lf_count > cr_count:
        return {
            "type": "lf",
            "description": "Unix/Linux风格 (\\n)",
            "char": "\n",
            "count": lf_count
        }
    else:
        return {
            "type": "cr",
            "description": "Mac经典风格 (\\r)",
            "char": "\r",
            "count": cr_count
        }


def detect_language(file_path: str) -> Dict[str, Any]:
    """检测编程语言"""
    ext = os.path.splitext(file_path)[1].lower()
    
    language_map = {
        '.py': {'name': 'Python', 'version': '3'},
        '.js': {'name': 'JavaScript', 'version': 'ES6+'},
        '.jsx': {'name': 'JavaScript (React)', 'version': 'ES6+'},
        '.ts': {'name': 'TypeScript', 'version': ''},
        '.tsx': {'name': 'TypeScript (React)', 'version': ''},
        '.vue': {'name': 'Vue', 'version': ''},
        '.html': {'name': 'HTML', 'version': '5'},
        '.css': {'name': 'CSS', 'version': '3'},
        '.scss': {'name': 'SCSS', 'version': ''},
        '.less': {'name': 'Less', 'version': ''},
        '.json': {'name': 'JSON', 'version': ''},
        '.xml': {'name': 'XML', 'version': ''},
        '.yaml': {'name': 'YAML', 'version': ''},
        '.yml': {'name': 'YAML', 'version': ''},
        '.md': {'name': 'Markdown', 'version': ''},
        '.java': {'name': 'Java', 'version': ''},
        '.c': {'name': 'C', 'version': ''},
        '.cpp': {'name': 'C++', 'version': ''},
        '.h': {'name': 'C/C++ Header', 'version': ''},
        '.go': {'name': 'Go', 'version': ''},
        '.rs': {'name': 'Rust', 'version': ''},
        '.rb': {'name': 'Ruby', 'version': ''},
        '.php': {'name': 'PHP', 'version': ''},
        '.swift': {'name': 'Swift', 'version': ''},
        '.kt': {'name': 'Kotlin', 'version': ''},
        '.scala': {'name': 'Scala', 'version': ''},
        '.sh': {'name': 'Shell', 'version': ''},
        '.bat': {'name': 'Batch', 'version': ''},
        '.ps1': {'name': 'PowerShell', 'version': ''},
        '.sql': {'name': 'SQL', 'version': ''},
    }
    
    return language_map.get(ext, {'name': 'Unknown', 'version': ''})


def detect_indent_style(content: str) -> Dict[str, Any]:
    """检测缩进风格"""
    lines = content.splitlines()
    tab_count = 0
    space_count = 0
    space_sizes = []
    
    for line in lines:
        if line.startswith('\t'):
            tab_count += 1
        elif line.startswith(' '):
            # 计算空格数
            space_len = len(line) - len(line.lstrip())
            if space_len > 0:
                space_count += 1
                space_sizes.append(space_len)
    
    total = tab_count + space_count
    
    if total == 0:
        return {
            "type": "unknown",
            "description": "无法确定缩进风格"
        }
    
    if tab_count > space_count:
        return {
            "type": "tab",
            "description": "使用Tab缩进",
            "count": tab_count
        }
    else:
        # 计算最常见的空格数
        if space_sizes:
            from collections import Counter
            most_common = Counter(space_sizes).most_common(1)[0][0]
            return {
                "type": "space",
                "description": f"使用空格缩进（{most_common}个空格）",
                "count": space_count,
                "size": most_common
            }
        
        return {
            "type": "space",
            "description": "使用空格缩进",
            "count": space_count
        }


@tool
def detect_file_format(file_path: str) -> Dict[str, Any]:
    """
    检测文件格式信息，包括编码、换行符、语言、缩进风格等
    
    Args:
        file_path: 文件路径
    """
    tool_name = "detect_file_format"
    
    try:
        if not os.path.exists(file_path):
            return _error_payload("file_not_found", f"文件不存在: {file_path}", tool=tool_name)
        
        # 检测编码
        encoding_info = detect_encoding(file_path)
        
        # 读取文件内容
        with open(file_path, 'r', encoding=encoding_info['encoding']) as f:
            content = f.read()
        
        # 检测换行符
        line_ending_info = detect_line_ending(content)
        
        # 检测语言
        language_info = detect_language(file_path)
        
        # 检测缩进风格
        indent_info = detect_indent_style(content)
        
        # 统计信息
        lines = content.splitlines()
        file_size = os.path.getsize(file_path)
        
        result = {
            "file_path": file_path,
            "encoding": encoding_info,
            "line_ending": line_ending_info,
            "language": language_info,
            "indent_style": indent_info,
            "statistics": {
                "file_size": file_size,
                "file_size_human": format_file_size(file_size),
                "line_count": len(lines),
                "char_count": len(content),
                "non_empty_lines": sum(1 for line in lines if line.strip())
            }
        }
        
        _emit_event(tool_name, "completed", result=result)
        return _ok_payload(f"文件格式检测完成: {language_info['name']}", **result)
    
    except Exception as e:
        err = _error_payload("unknown_error", f"检测文件格式时发生错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err


def format_file_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


if __name__ == "__main__":
    print("文件格式检测工具已加载")
