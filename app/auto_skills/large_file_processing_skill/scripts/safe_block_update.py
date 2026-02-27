from langchain_core.tools import tool
import os
import re
import shutil
from typing import Dict, Any


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
    skip_if_present: bool = True
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

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            original = f.read()

        content = original
        if truncate_incomplete_tail and content and not content.endswith("\n"):
            last_newline = content.rfind("\n")
            if last_newline > -1:
                content = content[:last_newline + 1]

        backup_file = file_path + backup_suffix
        shutil.copy2(file_path, backup_file)

        updated = None
        mode = (insert_mode or "").strip().lower()
        if mode == "replace_between":
            if not start_pattern or not end_pattern:
                return {"success": False, "error": "replace_between 需要 start_pattern 与 end_pattern"}
            starts = [m for m in re.finditer(start_pattern, content)]
            ends = [m for m in re.finditer(end_pattern, content)]
            if not starts or not ends:
                return {"success": False, "error": "锚点未匹配", "start_matches": len(starts), "end_matches": len(ends)}
            if require_unique and (len(starts) != 1 or len(ends) != 1):
                return {"success": False, "error": "锚点不唯一", "start_matches": len(starts), "end_matches": len(ends)}
            start = starts[0]
            end = None
            for m in ends:
                if m.start() >= start.end():
                    end = m
                    break
            if end is None:
                return {"success": False, "error": "未找到位于起始锚点之后的结束锚点"}
            if skip_if_present and new_block and new_block in content[start.end():end.start()]:
                return {
                    "success": True,
                    "message": "区间已包含内容，已跳过",
                    "file_path": file_path,
                    "backup_file": backup_file,
                    "original_size": len(original),
                    "new_size": len(original),
                    "insert_mode": mode,
                    "skipped": True
                }
            if expected_old and expected_old not in content[start.end():end.start()]:
                return {"success": False, "error": "锚点命中但内容校验失败"}
            before = content[:start.end()]
            after = content[end.start():]
            updated = before + "\n" + (new_block or "") + "\n" + after
        elif mode == "after_pattern":
            if not anchor_pattern:
                return {"success": False, "error": "after_pattern 需要 anchor_pattern"}
            lines = content.split("\n")
            matches = [i for i, line in enumerate(lines) if re.search(anchor_pattern, line)]
            if not matches:
                return {"success": False, "error": "未找到锚点匹配行", "anchor_pattern": anchor_pattern}
            if require_unique and len(matches) != 1:
                return {"success": False, "error": "锚点匹配行不唯一", "anchor_pattern": anchor_pattern, "match_count": len(matches)}
            idx = matches[0]
            before = "\n".join(lines[:idx + 1])
            after = "\n".join(lines[idx + 1:])
            if skip_if_present and new_block and new_block in after:
                return {
                    "success": True,
                    "message": "锚点后已包含内容，已跳过",
                    "file_path": file_path,
                    "backup_file": backup_file,
                    "original_size": len(original),
                    "new_size": len(original),
                    "insert_mode": mode,
                    "skipped": True
                }
            updated = before + "\n" + (new_block or "") + "\n" + after
        elif mode == "append":
            if skip_if_present and new_block and new_block in content:
                return {
                    "success": True,
                    "message": "内容已存在，已跳过",
                    "file_path": file_path,
                    "backup_file": backup_file,
                    "original_size": len(original),
                    "new_size": len(original),
                    "insert_mode": mode,
                    "skipped": True
                }
            updated = content + ("\n" if content and not content.endswith("\n") else "") + (new_block or "") + "\n"
        else:
            return {"success": False, "error": f"不支持的 insert_mode: {insert_mode}"}

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated)

        if ensure_present and new_block and new_block not in updated:
            shutil.copy2(backup_file, file_path)
            return {"success": False, "error": "内容校验失败，已回滚", "backup_file": backup_file}

        return {
            "success": True,
            "message": "已完成安全更新",
            "file_path": file_path,
            "backup_file": backup_file,
            "original_size": len(original),
            "new_size": len(updated),
            "insert_mode": mode
        }
    except Exception as e:
        return {"success": False, "error": f"安全更新失败: {str(e)}"}
