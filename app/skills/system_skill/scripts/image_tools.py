from langchain_core.tools import tool
import os
import json

@tool
def delete_image(image_path: str = None, image_paths: list = None):
    """
    删除指定图片文件。

    Args:
        image_path: 图片路径
        image_paths: 图片路径列表
    """
    if not image_path and not image_paths:
        return "image_path 或 image_paths 不能为空"
    paths = []
    if image_path:
        paths.append(image_path)
    if image_paths:
        paths.extend(image_paths)
    deleted = []
    skipped = []
    valid_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
    for p in paths:
        try:
            ap = os.path.abspath(p)
            if not os.path.exists(ap):
                skipped.append(f"{ap} 不存在")
                continue
            if os.path.isdir(ap):
                skipped.append(f"{ap} 是目录")
                continue
            ext = os.path.splitext(ap)[1].lower()
            if ext not in valid_exts:
                skipped.append(f"{ap} 非图片文件")
                continue
            os.remove(ap)
            deleted.append(ap)
        except Exception as e:
            skipped.append(f"{p} 删除失败: {e}")
    return json.dumps({"deleted": deleted, "skipped": skipped}, ensure_ascii=False, indent=2)
