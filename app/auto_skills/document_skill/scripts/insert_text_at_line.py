from langchain_core.tools import tool
import os
from typing import Dict, Any


def _normalize_newlines(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _ensure_trailing_newline(text: str) -> str:
    if not text:
        return "\n"
    return text if text.endswith("\n") else (text + "\n")


@tool
def insert_text_at_line(
    file_path: str,
    line_number: int,
    text: str,
    position: str = "before",
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """
    按行号向文本文件插入内容（适用于将过长输出分段写入文件）。

    Args:
        file_path: 文件路径
        line_number: 目标行号（从 1 开始）。允许等于 total_lines+1 表示追加到末尾。
        text: 要插入的文本（可多行）
        position: "before" | "after"。before 表示插入到该行前；after 表示插入到该行后
        encoding: 文件编码

    Returns:
        包含插入结果与新行数的字典
    """
    path = str(file_path or "").strip()
    if not path:
        return {"success": False, "error": "file_path 不能为空"}
    if not os.path.exists(path):
        return {"success": False, "error": f"文件不存在: {path}"}
    if not os.path.isfile(path):
        return {"success": False, "error": f"路径不是文件: {path}"}

    try:
        ln = int(line_number)
    except Exception:
        return {"success": False, "error": "line_number 必须是整数（从 1 开始）"}
    if ln < 1:
        return {"success": False, "error": "line_number 必须 >= 1"}

    pos = (position or "before").strip().lower()
    if pos not in {"before", "after"}:
        return {"success": False, "error": 'position 仅支持 "before" 或 "after"'}

    insert_text = _ensure_trailing_newline(_normalize_newlines(text))

    try:
        with open(path, "r", encoding=encoding, errors="ignore") as f:
            content = f.read()
        normalized = _normalize_newlines(content)
        lines = normalized.splitlines(True)

        total_lines = len(lines)
        if ln > total_lines + 1:
            ln = total_lines + 1

        idx = ln - 1
        if pos == "after" and ln <= total_lines:
            idx = ln

        if not lines:
            lines = []
            idx = 0

        insert_lines = insert_text.splitlines(True)
        new_lines = lines[:idx] + insert_lines + lines[idx:]

        out = "".join(new_lines)
        out = out.replace("\n", "\r\n")
        with open(path, "w", encoding=encoding, newline="") as f:
            f.write(out)

        return {
            "success": True,
            "file_path": path,
            "inserted_at_line": ln,
            "position": pos,
            "old_total_lines": total_lines,
            "new_total_lines": len(new_lines),
            "message": f"已插入到 {os.path.basename(path)} 第 {ln} 行（{pos}），当前共 {len(new_lines)} 行",
        }
    except Exception as e:
        return {"success": False, "error": f"插入失败: {str(e)}"}

