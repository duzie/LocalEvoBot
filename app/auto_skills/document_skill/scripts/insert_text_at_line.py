from langchain_core.tools import tool
import os
import re
from typing import Dict, Any


def _normalize_newlines(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _ensure_trailing_newline(text: str) -> str:
    if not text:
        return "\n"
    return text if text.endswith("\n") else (text + "\n")


def _stream_contains_normalized(file_path: str, needle: str, encoding: str) -> bool:
    if not needle:
        return False
    tail = ""
    needle_len = len(needle)
    with open(file_path, "r", encoding=encoding, errors="ignore") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            data = (tail + chunk).replace("\r\n", "\n").replace("\r", "\n")
            if needle in data:
                return True
            if needle_len > 1:
                tail = data[-(needle_len - 1):]
            else:
                tail = ""
    return False


def _detect_newline_style(file_path: str, encoding: str) -> str:
    with open(file_path, "r", encoding=encoding, errors="ignore", newline="") as f:
        chunk = f.read(8192)
    if "\r\n" in chunk:
        return "\r\n"
    if "\n" in chunk:
        return "\n"
    return "\n"


def _read_prefix_from_line(file_path: str, start_line: int, max_chars: int, encoding: str) -> str:
    if max_chars <= 0:
        return ""
    collected = []
    collected_len = 0
    line_num = 0
    with open(file_path, "r", encoding=encoding, errors="ignore", newline="") as f:
        for line in f:
            line_num += 1
            if line_num < start_line:
                continue
            part = line.replace("\r\n", "\n").replace("\r", "\n")
            remaining = max_chars - collected_len
            if remaining <= 0:
                break
            collected.append(part[:remaining])
            collected_len += len(collected[-1])
            if collected_len >= max_chars:
                break
    return "".join(collected)


@tool
def insert_text_at_line(
    file_path: str,
    line_number: int,
    text: str,
    position: str = "before",
    encoding: str = "utf-8",
    expected_pattern: str = "",
    skip_if_present: bool = True,
    dedupe_overlap: bool = True,
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

    try:
        total_lines = 0
        target_line_text = ""
        with open(path, "r", encoding=encoding, errors="ignore", newline="") as f:
            for line in f:
                total_lines += 1
                if total_lines == ln:
                    target_line_text = line.rstrip("\r\n")

        normalized_insert = _normalize_newlines(text).strip()
        if skip_if_present and normalized_insert and _stream_contains_normalized(path, normalized_insert, encoding):
            return {
                "success": True,
                "file_path": path,
                "skipped": True,
                "reason": "内容已存在",
                "old_total_lines": total_lines,
                "new_total_lines": total_lines,
            }

        if ln > total_lines + 1:
            ln = total_lines + 1

        if expected_pattern and total_lines > 0 and ln <= total_lines:
            line_text = target_line_text
            if not re.search(expected_pattern, line_text):
                return {
                    "success": False,
                    "error": "行内容校验失败",
                    "expected_pattern": expected_pattern,
                    "actual_line": line_text,
                    "line_number": ln,
                }

        insert_text_value = _ensure_trailing_newline(_normalize_newlines(text))
        if dedupe_overlap and normalized_insert:
            follow_start_line = ln if pos == "before" else ln + 1
            if follow_start_line <= total_lines:
                prefix = _read_prefix_from_line(path, follow_start_line, len(normalized_insert), encoding)
            else:
                prefix = ""
            if prefix:
                max_overlap = min(len(normalized_insert), len(prefix))
                overlap_size = 0
                for size in range(max_overlap, 0, -1):
                    if normalized_insert.endswith(prefix[:size]):
                        overlap_size = size
                        break
                if overlap_size > 0 and overlap_size < len(normalized_insert):
                    insert_text_value = normalized_insert[:len(normalized_insert) - overlap_size]
                    if insert_text_value:
                        insert_text_value = _ensure_trailing_newline(insert_text_value)
                elif overlap_size == len(normalized_insert):
                    return {
                        "success": True,
                        "file_path": path,
                        "skipped": True,
                        "reason": "内容与后续重叠，已跳过",
                        "old_total_lines": total_lines,
                        "new_total_lines": total_lines,
                    }

        newline_style = _detect_newline_style(path, encoding)
        insert_text_write = insert_text_value.replace("\n", newline_style)
        insert_before_line = ln if pos == "before" else ln + 1

        tmp_file = path + ".tmp"
        inserted = False
        with open(path, "r", encoding=encoding, errors="ignore", newline="") as src, open(tmp_file, "w", encoding=encoding, newline="") as dst:
            line_num = 0
            for line in src:
                line_num += 1
                if not inserted and line_num == insert_before_line:
                    dst.write(insert_text_write)
                    inserted = True
                dst.write(line)
            if not inserted:
                dst.write(insert_text_write)
                inserted = True

        os.replace(tmp_file, path)
        inserted_lines = _normalize_newlines(insert_text_value).count("\n")
        new_total_lines = total_lines + inserted_lines

        return {
            "success": True,
            "file_path": path,
            "inserted_at_line": ln,
            "position": pos,
            "old_total_lines": total_lines,
            "new_total_lines": new_total_lines,
            "message": f"已插入到 {os.path.basename(path)} 第 {ln} 行（{pos}），当前共 {new_total_lines} 行",
        }
    except Exception as e:
        return {"success": False, "error": f"插入失败: {str(e)}"}

