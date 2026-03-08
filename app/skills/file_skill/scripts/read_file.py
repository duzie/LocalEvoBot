"""
read_file - 读取文件内容

支持自动编码检测、大文件分块读取、内容摘要。
"""

from langchain_core.tools import tool
import os
import chardet
from typing import Dict, Any, Optional
from app.skills.common import ok_payload, error_payload, SkillException


@tool
def read_file(
    file_path: str,
    max_chars: int = 50000,
    encoding: Optional[str] = None,
    return_summary: bool = False
) -> Dict[str, Any]:
    """
    读取文件内容
    
    Args:
        file_path: 文件路径
        max_chars: 最大读取字符数，默认 50000
        encoding: 文件编码（可选，自动检测如果未指定）
        return_summary: 是否返回摘要（默认 False）
    
    Returns:
        dict: 包含 ok 字段的字典
        - ok: True/False
        - content: 文件内容（如果成功）
        - summary: 文件摘要（如果 return_summary=True）
        - lines: 行数
        - size: 文件大小（字节）
    
    Example:
        result = read_file.invoke({"file_path": "test.py", "max_chars": 10000})
        if result.get("ok"):
            print(result.get("content"))
    """
    tool_name = "read_file"
    
    try:
        # 验证文件存在
        if not os.path.exists(file_path):
            raise SkillException("file_not_found", f"文件不存在：{file_path}")
        
        if not os.path.isfile(file_path):
            raise SkillException("not_a_file", f"路径不是文件：{file_path}")
        
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        
        # 检测编码
        if not encoding:
            try:
                with open(file_path, 'rb') as f:
                    raw = f.read(10000)  # 读取前 10KB 用于检测
                detected = chardet.detect(raw)
                encoding = detected.get('encoding', 'utf-8')
            except Exception:
                encoding = 'utf-8'
        
        # 读取文件
        try:
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read(max_chars)
        except UnicodeDecodeError:
            # 如果指定编码失败，尝试 utf-8
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(max_chars)
        
        # 计算行数
        lines = content.count('\n') + 1
        
        # 生成摘要（可选）
        summary = None
        if return_summary:
            summary = _generate_summary(file_path, content)
        
        result = {
            "content": content,
            "lines": lines,
            "size": file_size,
            "encoding": encoding,
            "truncated": len(content) >= max_chars
        }
        
        if summary:
            result["summary"] = summary
        
        return ok_payload(f"成功读取 {lines} 行", **result)
        
    except SkillException:
        raise  # 重新抛出，让 StandardizedTool 处理
    
    except Exception as e:
        return error_payload("read_error", f"读取失败：{e}", file=file_path)


def _generate_summary(file_path: str, content: str) -> str:
    """生成文件摘要"""
    ext = os.path.splitext(file_path)[1].lower()
    
    # 按文件类型生成摘要
    if ext == '.py':
        return _summarize_python(content)
    elif ext in ['.md', '.txt']:
        return _summarize_text(content)
    else:
        return f"文件类型：{ext}, 大小：{len(content)} 字符"


def _summarize_python(content: str) -> str:
    """Python 文件摘要"""
    import re
    
    # 提取类
    classes = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)[:5]
    
    # 提取函数
    functions = re.findall(r'^def\s+(\w+)', content, re.MULTILINE)[:10]
    
    summary_parts = ["Python 文件"]
    if classes:
        summary_parts.append(f"类：{', '.join(classes)}")
    if functions:
        summary_parts.append(f"函数：{', '.join(functions)}")
    
    return " | ".join(summary_parts)


def _summarize_text(content: str) -> str:
    """文本文件摘要"""
    lines = content.strip().split('\n')
    
    # 提取前 5 行非空行作为摘要
    non_empty = [l.strip() for l in lines if l.strip()][:5]
    
    return f"文本文件，{len(lines)} 行，前 5 行：{' | '.join(non_empty[:3])}"
