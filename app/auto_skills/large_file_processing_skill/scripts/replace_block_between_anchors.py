from langchain_core.tools import tool
import os
import re
import shutil
from typing import Dict, Any


def _stream_contains(file_path: str, needle: str, encoding: str) -> bool:
    if not needle:
        return False
    tail = ""
    needle_len = len(needle)
    with open(file_path, "r", encoding=encoding, errors="ignore") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            data = tail + chunk
            if needle in data:
                return True
            if needle_len > 1:
                tail = data[-(needle_len - 1):]
            else:
                tail = ""
    return False


def _update_contains_state(buffer: str, text: str, needle: str, found: bool) -> (str, bool):
    if found or not needle:
        return buffer, found
    data = buffer + text
    if needle in data:
        return data[-(len(needle) - 1):] if len(needle) > 1 else "", True
    if len(needle) > 1:
        return data[-(len(needle) - 1):], False
    return "", False


def _stream_contains_in_range(file_path: str, start_line: int, end_line: int, needle: str, encoding: str) -> bool:
    if not needle:
        return False
    buffer = ""
    found = False
    line_num = 0
    with open(file_path, "r", encoding=encoding, errors="ignore") as f:
        for line in f:
            line_num += 1
            if line_num < start_line:
                continue
            if line_num > end_line:
                break
            buffer, found = _update_contains_state(buffer, line, needle, found)
            if found:
                return True
    return False


@tool
def replace_block_between_anchors(
    file_path: str,
    start_pattern: str,
    end_pattern: str,
    new_block: str,
    backup_suffix: str = ".bak",
    require_unique: bool = True,
    start_line: int = 0,
    end_line: int = 0,
    allow_fallback: bool = False,
    ensure_present: bool = True,
    expected_old: str = "",
    skip_if_present: bool = True
) -> Dict[str, Any]:
    """
    按锚点区间替换内容，避免重复与错位插入。
    """
    try:
        if not file_path:
            return {"success": False, "error": "file_path 不能为空"}
        if not start_pattern or not end_pattern:
            if not (allow_fallback and start_line and end_line):
                return {"success": False, "error": "start_pattern 与 end_pattern 不能为空"}
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        if not os.path.isfile(file_path):
            return {"success": False, "error": f"路径不是文件: {file_path}"}

        encoding = "utf-8"
        if skip_if_present and new_block and _stream_contains(file_path, new_block, encoding):
            return {
                "success": True,
                "message": "内容已存在，已跳过",
                "file_path": file_path,
                "used_fallback": False,
                "skipped": True
            }
        used_fallback = False
        start_matches = 0
        end_matches = 0
        found_start_line = 0
        found_end_line = 0
        total_lines = 0
        segment_expected_found = False
        segment_new_found = False
        expected_buffer = ""
        new_buffer = ""
        start_re = re.compile(start_pattern) if start_pattern else None
        end_re = re.compile(end_pattern) if end_pattern else None

        with open(file_path, "r", encoding=encoding, errors="ignore") as f:
            for line in f:
                total_lines += 1
                start_hit = bool(start_re.search(line)) if start_re else False
                end_hit = bool(end_re.search(line)) if end_re else False
                if start_hit:
                    start_matches += 1
                    if found_start_line == 0:
                        found_start_line = total_lines
                        if end_hit and found_end_line == 0:
                            end_matches += 1
                            found_end_line = total_lines
                            continue
                if end_hit:
                    end_matches += 1
                    if found_start_line > 0 and found_end_line == 0:
                        found_end_line = total_lines
                        continue
                if found_start_line > 0 and found_end_line == 0 and total_lines != found_start_line and not end_hit:
                    expected_buffer, segment_expected_found = _update_contains_state(
                        expected_buffer, line, expected_old, segment_expected_found
                    )
                    new_buffer, segment_new_found = _update_contains_state(
                        new_buffer, line, new_block, segment_new_found
                    )

        anchor_usable = (
            found_start_line > 0
            and found_end_line > 0
            and (not require_unique or (start_matches == 1 and end_matches == 1))
        )
        
        # 增加对锚点行号的校验 (如果用户提供了行号提示)
        if anchor_usable and start_line > 0:
            # 允许 5 行以内的偏差
            if abs(found_start_line - start_line) > 5:
                return {
                    "success": False,
                    "error": f"锚点匹配行 ({found_start_line}) 与预期行 ({start_line}) 偏差过大 (>5行)，为安全起见已拒绝。请确认锚点是否正确或更新预期行号。",
                    "found_line": found_start_line,
                    "expected_line": start_line
                }

        if anchor_usable:
            if skip_if_present and new_block and segment_new_found:
                return {
                    "success": True,
                    "message": "区间已包含内容，已跳过",
                    "file_path": file_path,
                    "used_fallback": False,
                    "skipped": True
                }
            if expected_old and not segment_expected_found:
                return {"success": False, "error": "锚点命中但内容校验失败", "used_fallback": False}
        else:
            if not allow_fallback:
                return {
                    "success": False,
                    "error": "锚点未匹配" if start_matches == 0 or end_matches == 0 else "锚点不唯一",
                    "start_matches": start_matches,
                    "end_matches": end_matches
                }
            if not (allow_fallback and start_line and end_line):
                return {"success": False, "error": "锚点未匹配且未启用行号兜底"}
            if allow_fallback and not expected_old:
                return {"success": False, "error": "行号兜底必须提供 expected_old"}
            s = max(1, int(start_line))
            e = max(1, int(end_line))
            if s > e:
                s, e = e, s
            if s > total_lines or e > total_lines:
                return {"success": False, "error": "行号范围超出文件长度", "total_lines": total_lines}
            if expected_old and not _stream_contains_in_range(file_path, s, e, expected_old, encoding):
                return {"success": False, "error": "行号兜底内容校验失败", "total_lines": total_lines}
            if skip_if_present and new_block and _stream_contains_in_range(file_path, s, e, new_block, encoding):
                return {
                    "success": True,
                    "message": "区间已包含内容，已跳过",
                    "file_path": file_path,
                    "used_fallback": True,
                    "skipped": True
                }
            used_fallback = True

        backup_file = file_path + backup_suffix
        shutil.copy2(file_path, backup_file)
        tmp_file = file_path + ".tmp"
        inserted = False
        if anchor_usable:
            start_line_num = found_start_line
            end_line_num = found_end_line
            with open(file_path, "r", encoding=encoding, errors="ignore") as src, open(tmp_file, "w", encoding=encoding) as dst:
                line_num = 0
                for line in src:
                    line_num += 1
                    if line_num < start_line_num:
                        dst.write(line)
                        continue
                    if line_num == start_line_num:
                        dst.write(line)
                        if new_block:
                            dst.write(new_block)
                            if not new_block.endswith("\n"):
                                dst.write("\n")
                        inserted = True if new_block else False
                        continue
                    if line_num < end_line_num:
                        continue
                    if line_num == end_line_num:
                        dst.write(line)
                        continue
                    dst.write(line)
        else:
            s = max(1, int(start_line))
            e = max(1, int(end_line))
            if s > e:
                s, e = e, s
            with open(file_path, "r", encoding=encoding, errors="ignore") as src, open(tmp_file, "w", encoding=encoding) as dst:
                line_num = 0
                for line in src:
                    line_num += 1
                    if line_num < s:
                        dst.write(line)
                        continue
                    if line_num == s:
                        if new_block:
                            dst.write(new_block)
                            if not new_block.endswith("\n"):
                                dst.write("\n")
                            inserted = True
                        continue
                    if line_num <= e:
                        continue
                    dst.write(line)

        if ensure_present and new_block and not inserted:
            shutil.copy2(backup_file, file_path)
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
            return {
                "success": False,
                "error": "替换内容校验失败，已回滚",
                "backup_file": backup_file
            }

        os.replace(tmp_file, file_path)
        new_size = os.path.getsize(file_path)
        original_size = os.path.getsize(backup_file)

        if new_size < original_size and not new_block:
            return {
                "success": True,
                "message": "已清空锚点区间内容",
                "file_path": file_path,
                "backup_file": backup_file,
                "original_size": original_size,
                "new_size": new_size,
                "used_fallback": used_fallback
            }

        return {
            "success": True,
            "message": "已按锚点区间替换内容",
            "file_path": file_path,
            "backup_file": backup_file,
            "original_size": original_size,
            "new_size": new_size,
            "used_fallback": used_fallback
        }
    except Exception as e:
        return {"success": False, "error": f"替换失败: {str(e)}"}
