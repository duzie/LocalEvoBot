from langchain_core.tools import tool
from pathlib import Path
from typing import Any, Dict, List, Optional


@tool
def delete_file(file_path: Optional[str] = None, file_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    删除指定文件或文件列表。

    Args:
        file_path: 单个文件路径
        file_paths: 文件路径列表
    """
    targets: List[str] = []
    if file_path:
        targets.append(file_path)
    if file_paths:
        targets.extend([p for p in file_paths if p])

    if not targets:
        return {
            "success": False,
            "message": "未提供要删除的文件路径",
            "deleted": [],
            "failed": [],
            "skipped": [],
            "total_processed": 0,
        }

    deleted: List[str] = []
    failed: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []

    for raw in targets:
        try:
            path = Path(raw).expanduser()
            try:
                abs_path = path.resolve(strict=False)
            except Exception:
                abs_path = path.absolute()

            if not abs_path.exists():
                skipped.append({"path": str(abs_path), "reason": "not_found"})
                continue

            if not abs_path.is_file():
                skipped.append({"path": str(abs_path), "reason": "not_a_file"})
                continue

            abs_path.unlink()
            deleted.append(str(abs_path))
        except Exception as e:
            failed.append({"path": raw, "error": str(e)})

    success = len(failed) == 0
    return {
        "success": success,
        "message": f"处理完成: 成功删除 {len(deleted)} 个，失败 {len(failed)} 个，跳过 {len(skipped)} 个",
        "deleted": deleted,
        "failed": failed,
        "skipped": skipped,
        "total_processed": len(targets),
    }