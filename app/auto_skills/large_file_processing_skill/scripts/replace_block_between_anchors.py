from langchain_core.tools import tool
import os
import re
import shutil
from typing import Dict, Any


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

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            original = f.read()

        replacement = ""
        if skip_if_present and new_block and new_block in original:
            return {
                "success": True,
                "message": "内容已存在，已跳过",
                "file_path": file_path,
                "used_fallback": False,
                "skipped": True
            }
        used_fallback = False
        if start_pattern and end_pattern:
            starts = [m for m in re.finditer(start_pattern, original)]
            ends = [m for m in re.finditer(end_pattern, original)]
            if starts and ends and (not require_unique or (len(starts) == 1 and len(ends) == 1)):
                start = starts[0]
                end = None
                for m in ends:
                    if m.start() >= start.end():
                        end = m
                        break
                if end:
                    if skip_if_present and new_block and new_block in original[start.end():end.start()]:
                        return {
                            "success": True,
                            "message": "区间已包含内容，已跳过",
                            "file_path": file_path,
                            "used_fallback": False,
                            "skipped": True
                        }
                    if expected_old and expected_old not in original[start.end():end.start()]:
                        return {"success": False, "error": "锚点命中但内容校验失败", "used_fallback": False}
                    before = original[:start.end()]
                    after = original[end.start():]
                    replacement = before + "\n" + (new_block or "") + "\n" + after
            if not replacement and not allow_fallback:
                return {
                    "success": False,
                    "error": "锚点未匹配" if not starts or not ends else "锚点不唯一",
                    "start_matches": len(starts),
                    "end_matches": len(ends)
                }
        if not replacement:
            if not (allow_fallback and start_line and end_line):
                return {"success": False, "error": "锚点未匹配且未启用行号兜底"}
            if allow_fallback and not expected_old:
                return {"success": False, "error": "行号兜底必须提供 expected_old"}
            lines = original.splitlines(keepends=True)
            total = len(lines)
            s = max(1, int(start_line))
            e = max(1, int(end_line))
            if s > e:
                s, e = e, s
            if s > total or e > total:
                return {"success": False, "error": "行号范围超出文件长度", "total_lines": total}
            if expected_old and expected_old not in "".join(lines[s - 1:e]):
                return {"success": False, "error": "行号兜底内容校验失败", "total_lines": total}
            if skip_if_present and new_block and new_block in "".join(lines[s - 1:e]):
                return {
                    "success": True,
                    "message": "区间已包含内容，已跳过",
                    "file_path": file_path,
                    "used_fallback": True,
                    "skipped": True
                }
            before = "".join(lines[:s - 1])
            after = "".join(lines[e:])
            mid = (new_block or "")
            if mid and not mid.endswith("\n"):
                mid = mid + "\n"
            replacement = before + mid + after
            used_fallback = True

        backup_file = file_path + backup_suffix
        shutil.copy2(file_path, backup_file)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(replacement)

        if len(replacement) < len(original) and not new_block:
            return {
                "success": True,
                "message": "已清空锚点区间内容",
                "file_path": file_path,
                "backup_file": backup_file,
                "original_size": len(original),
                "new_size": len(replacement),
                "used_fallback": used_fallback
            }

        if ensure_present and new_block and new_block not in replacement:
            shutil.copy2(backup_file, file_path)
            return {
                "success": False,
                "error": "替换内容校验失败，已回滚",
                "backup_file": backup_file
            }

        return {
            "success": True,
            "message": "已按锚点区间替换内容",
            "file_path": file_path,
            "backup_file": backup_file,
            "original_size": len(original),
            "new_size": len(replacement),
            "used_fallback": used_fallback
        }
    except Exception as e:
        return {"success": False, "error": f"替换失败: {str(e)}"}
