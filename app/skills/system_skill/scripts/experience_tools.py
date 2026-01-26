from langchain_core.tools import tool
import os
import json
import re
from datetime import datetime, timezone

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
