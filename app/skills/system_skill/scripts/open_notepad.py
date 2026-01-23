from langchain_core.tools import tool
import subprocess
import platform
import os
import time
import json
import re
from datetime import datetime, timezone

@tool
def open_notepad():
    """
    打开 Windows 记事本程序。无需参数。
    如果是 macOS，则尝试打开 TextEdit。
    """
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen("notepad.exe")
            return "已启动记事本 (notepad.exe)"
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", "TextEdit"])
            return "已启动 TextEdit"
        else:
            return f"不支持的操作系统: {system}"
    except Exception as e:
        return f"启动失败: {e}"

@tool
def read_notepad_text(window_title: str = None, file_path: str = None, try_open: bool = True):
    """
    读取记事本中的文本内容或直接读取文件内容。

    Args:
        window_title: 记事本窗口标题正则，未提供时自动匹配包含“记事本/Notepad”的窗口
        file_path: 文件路径，若提供且存在则直接读取文件内容
        try_open: 当未找到窗口但提供了 file_path 时，尝试用记事本打开并读取
    """
    system = platform.system()
    if system != "Windows":
        return "当前仅支持 Windows"
    if file_path and os.path.exists(file_path):
        try:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                with open(file_path, "r", encoding="gbk", errors="ignore") as f:
                    return f.read()
        except Exception as e:
            return f"读取文件失败: {e}"
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        pattern = window_title or r".*(记事本|Notepad).*"
        win = desktop.window(title_re=pattern)
        if not win.exists(timeout=2):
            if file_path and try_open:
                try:
                    subprocess.Popen(["notepad.exe", file_path])
                    time.sleep(1.5)
                    base = os.path.basename(file_path)
                    alt = rf".*{base}.*"
                    win = desktop.window(title_re=alt)
                    if not win.exists(timeout=3):
                        win = desktop.window(title_re=r".*(记事本|Notepad).*")
                except Exception:
                    pass
            else:
                return f"未找到记事本窗口: {pattern}"
        try:
            win.set_focus()
        except Exception:
            pass
        try:
            edit = win.child_window(control_type="Edit")
            if edit.exists(timeout=1):
                return edit.window_text()
        except Exception:
            pass
        try:
            edit_list = win.descendants(control_type="Edit")
            if edit_list:
                return edit_list[0].window_text()
        except Exception:
            pass
        return "未找到可读取的文本控件"
    except Exception as e:
        return f"读取失败: {e}"

def _experience_store_path():
    return os.path.join(os.path.dirname(__file__), "experience_store.json")

def _load_experiences():
    path = _experience_store_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.loads(f.read() or "[]")
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []

def _save_experiences(items):
    path = _experience_store_path()
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(items, ensure_ascii=False, indent=2))
    return path

@tool
def add_operation_experience(system_name: str, content: str, tags: list = None, url: str = None):
    """
    记录某个系统的操作经验。

    Args:
        system_name: 系统名称
        content: 操作经验内容
        tags: 标签列表
        url: 相关页面地址
    """
    if not system_name or not content:
        return "system_name 与 content 不能为空"
    items = _load_experiences()
    item = {
        "system": system_name.strip(),
        "content": content.strip(),
        "tags": tags or [],
        "url": url,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    items.append(item)
    path = _save_experiences(items)
    return f"已记录经验，当前共 {len(items)} 条，保存于 {path}"

@tool
def get_operation_experience(system_name: str, keyword: str = None, max_items: int = 5):
    """
    查询某个系统的操作经验。

    Args:
        system_name: 系统名称
        keyword: 关键词过滤
        max_items: 最大返回数量
    """
    if not system_name:
        return "system_name 不能为空"
    items = _load_experiences()
    sys_key = system_name.lower().strip()
    filtered = [x for x in items if sys_key in str(x.get("system", "")).lower()]
    if keyword:
        kw = keyword.lower().strip()
        filtered = [x for x in filtered if kw in str(x.get("content", "")).lower() or kw in str(x.get("tags", "")).lower()]
    if max_items and max_items > 0:
        filtered = filtered[-max_items:]
    return json.dumps(filtered, ensure_ascii=False, indent=2)

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

@tool
def compress_operation_experience(max_chars_per_system: int = 800, max_items_per_system: int = 5, dry_run: bool = False):
    """
    压缩操作经验，按系统合并并去重，降低上下文长度。

    Args:
        max_chars_per_system: 每个系统的最大字符数
        max_items_per_system: 每个系统最多合并的条数
        dry_run: 仅返回压缩结果，不写回文件
    """
    items = _load_experiences()
    if not items:
        return "无可压缩经验"
    grouped = {}
    for item in items:
        system = str(item.get("system", "")).strip() or "未命名系统"
        grouped.setdefault(system, []).append(item)

    def _clean_line(value: str):
        s = str(value or "").strip()
        if not s:
            return ""
        s = re.sub(r"^\s*[\-\*\u2022]\s*", "", s)
        s = re.sub(r"^\s*\d+[\.\)、\)]\s*", "", s)
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    compressed = []
    for system, entries in grouped.items():
        if max_items_per_system and max_items_per_system > 0:
            entries = entries[-max_items_per_system:]
        lines = []
        tags = []
        url = None
        for item in entries:
            content = str(item.get("content", "") or "")
            for raw in content.splitlines():
                cleaned = _clean_line(raw)
                if cleaned:
                    lines.append(cleaned)
            item_tags = item.get("tags") or []
            for t in item_tags:
                cleaned = _clean_line(t)
                if cleaned:
                    tags.append(cleaned)
            if item.get("url"):
                url = item.get("url")
        seen = set()
        uniq_lines = []
        for line in lines:
            if line in seen:
                continue
            seen.add(line)
            uniq_lines.append(line)
        content = "；".join(uniq_lines)
        if max_chars_per_system and max_chars_per_system > 0 and len(content) > max_chars_per_system:
            content = content[:max_chars_per_system].rstrip("；，,。; ") + "…"
        tag_seen = set()
        uniq_tags = []
        for t in tags:
            if t in tag_seen:
                continue
            tag_seen.add(t)
            uniq_tags.append(t)
        compressed.append({
            "system": system,
            "content": content,
            "tags": uniq_tags,
            "url": url,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_count": len(entries)
        })
    if dry_run:
        return json.dumps(compressed, ensure_ascii=False, indent=2)
    path = _save_experiences(compressed)
    return f"已压缩经验，当前共 {len(compressed)} 条，保存于 {path}"
