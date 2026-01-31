from langchain_core.tools import tool
import os
import json
import shutil
from datetime import datetime, timezone

# Ensure HF mirror is used before any HF imports
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

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
    except ImportError as e:
        print(f"RAG Dependency Import Error: {e}")
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
def add_operation_experience(system_name: str, content: str, tags: list = None, url: str = None, scope: str = None, project_id: str = None, user_id: str = None, memory_type: str = None):
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
    
    tags_list = tags if isinstance(tags, list) else []
    tags_str = ", ".join(tags_list) if tags_list else ""
    page_content = f"System: {system_name}\nContent: {content}\nTags: {tags_str}\nScope: {scope or ''}\nProject: {project_id or ''}\nUser: {user_id or ''}\nType: {memory_type or ''}"
    
    metadata = {
        "system": system_name,
        "tags": tags_str,
        "tags_list": ", ".join(tags_list),
        "url": url or "",
        "scope": scope or "",
        "project_id": project_id or "",
        "user_id": user_id or "",
        "memory_type": memory_type or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "original_content": content
    }
    
    store.add_documents([Document(page_content=page_content, metadata=metadata)])
    return "已存入向量知识库。"

@tool
def get_operation_experience(query: str, system_filter: str = None, n_results: int = 3, scope: str = None, project_id: str = None, user_id: str = None, memory_type: str = None, tags: list = None):
    """
    语义检索操作经验。
    
    Args:
        query: 问题描述或关键词 (如 "Playwright 报错")
        system_filter: (可选) 限定系统名称
        n_results: 返回数量
    """
    store = _init_components()
    if not store: return "Error: RAG dependencies missing."
    
    filter_dict = {}
    if system_filter:
        filter_dict["system"] = system_filter
    if scope:
        filter_dict["scope"] = scope
    if project_id:
        filter_dict["project_id"] = project_id
    if user_id:
        filter_dict["user_id"] = user_id
    if memory_type:
        filter_dict["memory_type"] = memory_type
    where = None
    if filter_dict:
        clauses = []
        for k, v in filter_dict.items():
            if v is None or v == "":
                continue
            clauses.append({k: {"$eq": v}})
        if clauses:
            where = {"$and": clauses} if len(clauses) > 1 else clauses[0]
    results = store.similarity_search(query, k=n_results, filter=where)
    
    if not results: return "知识库中未找到相关经验。"
    
    tag_filters = tags if isinstance(tags, list) else []
    formatted = []
    for doc in results:
        if tag_filters:
            doc_tags = doc.metadata.get("tags_list") or []
            doc_tags_str = doc.metadata.get("tags") or ""
            if not all(tag in doc_tags or tag in doc_tags_str for tag in tag_filters):
                continue
        formatted.append({
            "content": doc.metadata.get("original_content"),
            "system": doc.metadata.get("system"),
            "tags": doc.metadata.get("tags"),
            "scope": doc.metadata.get("scope"),
            "project_id": doc.metadata.get("project_id"),
            "user_id": doc.metadata.get("user_id"),
            "memory_type": doc.metadata.get("memory_type")
        })
    return json.dumps(formatted, ensure_ascii=False, indent=2)

@tool
def compress_operation_experience():
    """[Deprecated] RAG模式下无需手动压缩。"""
    return "Feature deprecated: Using Vector DB now."
