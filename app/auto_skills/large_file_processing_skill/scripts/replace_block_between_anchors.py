from langchain_core.tools import tool
import os
import re
import shutil
from typing import Dict, Any


@tool
def replace_block_between_anchors(file_path: str, start_pattern: str, end_pattern: str, new_block: str, backup_suffix: str = ".bak", require_unique: bool = True) -> Dict[str, Any]:
    """
    按锚点区间替换内容，避免重复与错位插入。
    """
    try:
        if not file_path:
            return {"success": False, "error": "file_path 不能为空"}
        if not start_pattern or not end_pattern:
            return {"success": False, "error": "start_pattern 与 end_pattern 不能为空"}
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        if not os.path.isfile(file_path):
            return {"success": False, "error": f"路径不是文件: {file_path}"}

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            original = f.read()

        starts = [m for m in re.finditer(start_pattern, original)]
        ends = [m for m in re.finditer(end_pattern, original)]
        if not starts or not ends:
            return {
                "success": False,
                "error": "锚点未匹配",
                "start_matches": len(starts),
                "end_matches": len(ends)
            }
        if require_unique and (len(starts) != 1 or len(ends) != 1):
            return {
                "success": False,
                "error": "锚点不唯一",
                "start_matches": len(starts),
                "end_matches": len(ends)
            }

        start = starts[0]
        end = None
        for m in ends:
            if m.start() >= start.end():
                end = m
                break
        if end is None:
            return {"success": False, "error": "未找到位于起始锚点之后的结束锚点"}

        before = original[:start.end()]
        after = original[end.start():]
        replacement = before + "\n" + (new_block or "") + "\n" + after

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
                "new_size": len(replacement)
            }

        if new_block and new_block not in replacement:
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
            "new_size": len(replacement)
        }
    except Exception as e:
        return {"success": False, "error": f"替换失败: {str(e)}"}
