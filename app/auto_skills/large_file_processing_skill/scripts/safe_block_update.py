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


def _stream_contains_in_range(file_path: str, start_line: int, end_line: int, needle: str, encoding: str, drop_last_incomplete: bool) -> bool:
    if not needle:
        return False
    buffer = ""
    found = False
    line_num = 0
    for line in _iter_lines(file_path, encoding, drop_last_incomplete):
        line_num += 1
        if line_num < start_line:
            continue
        if line_num > end_line:
            break
        buffer, found = _update_contains_state(buffer, line, needle, found)
        if found:
            return True
    return False


def _should_drop_last_incomplete(file_path: str) -> bool:
    try:
        with open(file_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size == 0:
                return False
            f.seek(-1, os.SEEK_END)
            return f.read(1) != b"\n"
    except Exception:
        return False


def _iter_lines(file_path: str, encoding: str, drop_last_incomplete: bool):
    with open(file_path, "r", encoding=encoding, errors="ignore") as f:
        prev = None
        for line in f:
            if prev is not None:
                yield prev
            prev = line
        if prev is not None:
            if drop_last_incomplete and not prev.endswith("\n"):
                return
            yield prev


@tool
def safe_block_update(
    file_path: str,
    new_block: str,
    start_pattern: str = "",
    end_pattern: str = "",
    anchor_pattern: str = "",
    insert_mode: str = "replace_between",
    backup_suffix: str = ".bak",
    require_unique: bool = True,
    ensure_present: bool = True,
    truncate_incomplete_tail: bool = True,
    expected_old: str = "",
    skip_if_present: bool = True,
    start_line: int = 0,
    end_line: int = 0
) -> Dict[str, Any]:
    """
    大文件安全更新：裁剪未完整尾行 + 锚点替换/插入 + 校验 + 回滚。
    """
    try:
        if not file_path:
            return {"success": False, "error": "file_path 不能为空"}
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        if not os.path.isfile(file_path):
            return {"success": False, "error": f"路径不是文件: {file_path}"}

        encoding = "utf-8"
        drop_last_incomplete = _should_drop_last_incomplete(file_path) if truncate_incomplete_tail else False

        backup_file = file_path + backup_suffix
        shutil.copy2(file_path, backup_file)

        mode = (insert_mode or "").strip().lower()
        if mode == "replace_between":
            if not start_pattern or not end_pattern:
                return {"success": False, "error": "replace_between 需要 start_pattern 与 end_pattern"}
            start_re = re.compile(start_pattern)
            end_re = re.compile(end_pattern)
            start_matches = 0
            end_matches = 0
            found_start_line = 0
            found_end_line = 0
            total_lines = 0
            segment_expected_found = False
            segment_new_found = False
            expected_buffer = ""
            new_buffer = ""
            for line in _iter_lines(file_path, encoding, drop_last_incomplete):
                total_lines += 1
                start_hit = bool(start_re.search(line))
                end_hit = bool(end_re.search(line))
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
            if start_matches == 0 or end_matches == 0:
                return {"success": False, "error": "锚点未匹配", "start_matches": start_matches, "end_matches": end_matches}
            if require_unique and (start_matches != 1 or end_matches != 1):
                return {"success": False, "error": "锚点不唯一", "start_matches": start_matches, "end_matches": end_matches}
            if found_start_line == 0 or found_end_line == 0:
                return {"success": False, "error": "未找到位于起始锚点之后的结束锚点"}

            # 行号偏差校验
            if start_line > 0:
                if abs(found_start_line - start_line) > 5:
                    return {
                        "success": False,
                        "error": f"锚点匹配行 ({found_start_line}) 与预期行 ({start_line}) 偏差过大 (>5行)，为安全起见已拒绝。请确认锚点是否正确或更新预期行号。",
                        "found_line": found_start_line,
                        "expected_line": start_line
                    }

            if skip_if_present and new_block and segment_new_found:
                return {
                    "success": True,
                    "message": "区间已包含内容，已跳过",
                    "file_path": file_path,
                    "backup_file": backup_file,
                    "original_size": os.path.getsize(backup_file),
                    "new_size": os.path.getsize(backup_file),
                    "insert_mode": mode,
                    "skipped": True
                }
            if expected_old and not segment_expected_found:
                return {"success": False, "error": "锚点命中但内容校验失败"}
            tmp_file = file_path + ".tmp"
            inserted = False
            with open(tmp_file, "w", encoding=encoding) as dst:
                line_num = 0
                for line in _iter_lines(file_path, encoding, drop_last_incomplete):
                    line_num += 1
                    if line_num < found_start_line:
                        dst.write(line)
                        continue
                    if line_num == found_start_line:
                        dst.write(line)
                        if new_block:
                            dst.write(new_block)
                            if not new_block.endswith("\n"):
                                dst.write("\n")
                            inserted = True
                        continue
                    if line_num < found_end_line:
                        continue
                    if line_num == found_end_line:
                        dst.write(line)
                        continue
                    dst.write(line)
            if ensure_present and new_block and not inserted:
                shutil.copy2(backup_file, file_path)
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
                return {"success": False, "error": "内容校验失败，已回滚", "backup_file": backup_file}
            os.replace(tmp_file, file_path)
        elif mode == "after_pattern":
            if not anchor_pattern:
                return {"success": False, "error": "after_pattern 需要 anchor_pattern"}
            anchor_re = re.compile(anchor_pattern)
            matches = 0
            anchor_line = 0
            total_lines = 0
            after_new_found = False
            buffer_new = ""
            for line in _iter_lines(file_path, encoding, drop_last_incomplete):
                total_lines += 1
                hit = bool(anchor_re.search(line))
                if hit:
                    matches += 1
                    if anchor_line == 0:
                        anchor_line = total_lines
                    continue
                if anchor_line > 0:
                    buffer_new, after_new_found = _update_contains_state(buffer_new, line, new_block, after_new_found)
            if matches == 0:
                return {"success": False, "error": "未找到锚点匹配行", "anchor_pattern": anchor_pattern}
            if require_unique and matches != 1:
                return {"success": False, "error": "锚点匹配行不唯一", "anchor_pattern": anchor_pattern, "match_count": matches}
            if skip_if_present and new_block and after_new_found:
                return {
                    "success": True,
                    "message": "锚点后已包含内容，已跳过",
                    "file_path": file_path,
                    "backup_file": backup_file,
                    "original_size": os.path.getsize(backup_file),
                    "new_size": os.path.getsize(backup_file),
                    "insert_mode": mode,
                    "skipped": True
                }
            tmp_file = file_path + ".tmp"
            inserted = False
            with open(tmp_file, "w", encoding=encoding) as dst:
                line_num = 0
                for line in _iter_lines(file_path, encoding, drop_last_incomplete):
                    line_num += 1
                    if line_num == anchor_line:
                        dst.write(line)
                        if new_block:
                            dst.write(new_block)
                            if not new_block.endswith("\n"):
                                dst.write("\n")
                            inserted = True
                        continue
                    dst.write(line)
            if ensure_present and new_block and not inserted:
                shutil.copy2(backup_file, file_path)
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
                return {"success": False, "error": "内容校验失败，已回滚", "backup_file": backup_file}
            os.replace(tmp_file, file_path)
        elif mode == "append":
            if skip_if_present and new_block and _stream_contains(file_path, new_block, encoding):
                return {
                    "success": True,
                    "message": "内容已存在，已跳过",
                    "file_path": file_path,
                    "backup_file": backup_file,
                    "original_size": os.path.getsize(backup_file),
                    "new_size": os.path.getsize(backup_file),
                    "insert_mode": mode,
                    "skipped": True
                }
            tmp_file = file_path + ".tmp"
            inserted = False
            with open(tmp_file, "w", encoding=encoding) as dst:
                wrote_any = False
                last_ended_newline = False
                for line in _iter_lines(file_path, encoding, drop_last_incomplete):
                    wrote_any = True
                    last_ended_newline = line.endswith("\n")
                    dst.write(line)
                if new_block:
                    if wrote_any and not last_ended_newline:
                        dst.write("\n")
                    dst.write(new_block)
                    if not new_block.endswith("\n"):
                        dst.write("\n")
                    inserted = True
            if ensure_present and new_block and not inserted:
                shutil.copy2(backup_file, file_path)
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
                return {"success": False, "error": "内容校验失败，已回滚", "backup_file": backup_file}
            os.replace(tmp_file, file_path)
        else:
            return {"success": False, "error": f"不支持的 insert_mode: {insert_mode}"}

        return {
            "success": True,
            "message": "已完成安全更新",
            "file_path": file_path,
            "backup_file": backup_file,
            "original_size": os.path.getsize(backup_file),
            "new_size": os.path.getsize(file_path),
            "insert_mode": mode
        }
    except Exception as e:
        return {"success": False, "error": f"安全更新失败: {str(e)}"}
