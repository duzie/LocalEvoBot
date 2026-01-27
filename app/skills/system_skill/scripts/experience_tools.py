from langchain_core.tools import tool
import os
import json
import shutil
from datetime import datetime, timezone

# Lazy globals
_VECTOR_STORE = None
_EMBEDDINGS = None

def _get_db_path():
    # Path: app/data/experience_db
    # This file: app/skills/system_skill/scripts/experience_tools.py
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    return os.path.join(base_dir, "app", "data", "experience_db")

def _get_json_path():
    return os.path.join(os.path.dirname(__file__), "experience_store.json")

def _init_components():
    global _VECTOR_STORE, _EMBEDDINGS
    if _VECTOR_STORE is not None:
        return _VECTOR_STORE

    try:
        from langchain_chroma import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        return None # Should handle gracefully or let it fail at runtime if deps missing

    if _EMBEDDINGS is None:
        # Use lightweight local model
        _EMBEDDINGS = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    db_path = _get_db_path()
    _VECTOR_STORE = Chroma(
        persist_directory=db_path,
        embedding_function=_EMBEDDINGS,
        collection_name="agent_experiences"
    )
    
    # Auto-migration check
    try:
        if len(_VECTOR_STORE.get()['ids']) == 0 and os.path.exists(_get_json_path()):
            _migrate_from_json()
    except Exception as e:
        print(f"DB Init/Migration warning: {e}")

    return _VECTOR_STORE

def _migrate_from_json():
    from langchain_core.documents import Document
    json_path = _get_json_path()
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            content = f.read()
            if not content.strip(): return
            data = json.loads(content)
        
        if not data: return
        
        docs = []
        for item in data:
            sys = item.get("system", "")
            txt = item.get("content", "")
            tags = item.get("tags", [])
            tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
            
            # Rich context for embedding
            page_content = f"System: {sys}\nContent: {txt}\nTags: {tags_str}"
            
            metadata = {
                "system": sys,
                "tags": tags_str,
                "url": item.get("url") or "",
                "created_at": item.get("created_at") or datetime.now(timezone.utc).isoformat(),
                "original_content": txt
            }
            docs.append(Document(page_content=page_content, metadata=metadata))
            
        if docs:
            _VECTOR_STORE.add_documents(docs)
            print(f"Migrated {len(docs)} experiences to Vector DB.")
            shutil.move(json_path, json_path + ".migrated")
            
    except Exception as e:
        print(f"Migration failed: {e}")

@tool
def add_operation_experience(system_name: str, content: str, tags: list = None, url: str = None):
    """
    记录系统操作经验到向量知识库 (RAG)。
    
    Args:
        system_name: 系统名称
        content: 经验内容
        tags: 标签列表
        url: 相关链接
    """
    from langchain_core.documents import Document
    store = _init_components()
    if not store: return "Error: RAG dependencies missing."
    
    tags_str = ", ".join(tags) if tags else ""
    page_content = f"System: {system_name}\nContent: {content}\nTags: {tags_str}"
    
    metadata = {
        "system": system_name,
        "tags": tags_str,
        "url": url or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "original_content": content
    }
    
    store.add_documents([Document(page_content=page_content, metadata=metadata)])
    return "已存入向量知识库。"

@tool
def get_operation_experience(query: str, system_filter: str = None, n_results: int = 5):
    """
    语义检索操作经验。
    
    Args:
        query: 问题描述或关键词 (如 "Selenium 报错")
        system_filter: (可选) 限定系统名称
        n_results: 返回数量
    """
    store = _init_components()
    if not store: return "Error: RAG dependencies missing."
    
    filter_dict = {"system": system_filter} if system_filter else None
    results = store.similarity_search(query, k=n_results, filter=filter_dict)
    
    if not results: return "知识库中未找到相关经验。"
    
    formatted = []
    for doc in results:
        formatted.append({
            "content": doc.metadata.get("original_content"),
            "system": doc.metadata.get("system"),
            "tags": doc.metadata.get("tags")
        })
    return json.dumps(formatted, ensure_ascii=False, indent=2)

@tool
def compress_operation_experience():
    """[Deprecated] RAG模式下无需手动压缩。"""
    return "Feature deprecated: Using Vector DB now."
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
