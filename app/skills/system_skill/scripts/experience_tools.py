from langchain_core.tools import tool
import os
import json
import shutil
from datetime import datetime, timezone
import sqlite3
import glob
import re
import uuid
from difflib import SequenceMatcher

# Ensure HF mirror is used before any HF imports
if not (os.getenv("HF_ENDPOINT") or "").strip():
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# Lazy globals
_VECTOR_STORE = None
_EMBEDDINGS = None
_OVERWRITE_TEXT_SIMILARITY = float(os.getenv("MEMORY_OVERWRITE_TEXT_SIMILARITY", "0.9"))
_OVERWRITE_DISTANCE_THRESHOLD = float(os.getenv("MEMORY_OVERWRITE_DISTANCE", "0.2"))

def _get_db_path():
    # Path: app/data/experience_db
    # This file: app/skills/system_skill/scripts/experience_tools.py
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    return os.path.join(base_dir, "app", "data", "experience_db")

def _get_json_path():
    return os.path.join(os.path.dirname(__file__), "experience_store.json")

def _get_short_term_db_path(date_key: str = None):
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    data_dir = os.path.join(base_dir, "app", "data")
    os.makedirs(data_dir, exist_ok=True)
    if not date_key:
        date_key = datetime.now().astimezone().strftime("%Y%m%d")
    return os.path.join(data_dir, f"short_term_memory_{date_key}.sqlite3")

def _list_short_term_db_paths():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    data_dir = os.path.join(base_dir, "app", "data")
    os.makedirs(data_dir, exist_ok=True)
    paths = sorted(glob.glob(os.path.join(data_dir, "short_term_memory_*.sqlite3")))
    legacy_path = os.path.join(data_dir, "short_term_memory.sqlite3")
    if os.path.exists(legacy_path):
        paths.append(legacy_path)
    return paths

def _init_short_term_db(date_key: str = None):
    path = _get_short_term_db_path(date_key)
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS short_term_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                project_id TEXT,
                user_id TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_stm_created ON short_term_messages(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_stm_project_user ON short_term_messages(project_id, user_id)")
        cur.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS short_term_messages_fts
            USING fts5(content, role, created_at, project_id, user_id)
            """
        )
        conn.commit()
    finally:
        conn.close()

def _init_components():
    global _VECTOR_STORE, _EMBEDDINGS
    if _VECTOR_STORE is False:
        return None
    if _VECTOR_STORE is not None:
        return _VECTOR_STORE

    try:
        from langchain_chroma import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError as e:
        print(f"RAG Dependency Import Error: {e}")
        return None # Should handle gracefully or let it fail at runtime if deps missing
    try:
        if _EMBEDDINGS is None:
            _EMBEDDINGS = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

        db_path = _get_db_path()
        _VECTOR_STORE = Chroma(
            persist_directory=db_path,
            embedding_function=_EMBEDDINGS,
            collection_name="agent_experiences"
        )

        try:
            data = _VECTOR_STORE.get()
            ids = data.get("ids") if isinstance(data, dict) else None
            if ids is not None and len(ids) == 0 and os.path.exists(_get_json_path()):
                _migrate_from_json()
        except Exception as e:
            print(f"DB Init/Migration warning: {e}")

        return _VECTOR_STORE
    except Exception as e:
        _VECTOR_STORE = False
        print(f"RAG init failed, fallback to JSON store: {e}")
        return None

def _load_json_store():
    path = _get_json_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            return []
        data = json.loads(content)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def _write_json_store(items: list):
    path = _get_json_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(items, ensure_ascii=False, indent=2))
    except Exception:
        return

def _append_json_store(item: dict):
    items = _load_json_store()
    items.append(item)
    _write_json_store(items)

def _split_query_terms(query: str):
    text = str(query or "").strip()
    if not text:
        return []
    parts = [p for p in re.split(r"[\s,，;；。！？!?/\\]+", text) if p]
    if text not in parts:
        parts.insert(0, text)
    deduped = []
    seen = set()
    for p in parts:
        if p in seen:
            continue
        seen.add(p)
        deduped.append(p)
    return deduped

def _normalize_text(value: str):
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)

def _text_similarity(a: str, b: str):
    a_norm = _normalize_text(a)
    b_norm = _normalize_text(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()

def _meta_matches(meta: dict, system_name: str, scope: str, project_id: str, user_id: str, memory_type: str):
    if system_name and (meta.get("system") or "") != system_name:
        return False
    if scope and (meta.get("scope") or "") != scope:
        return False
    if project_id and (meta.get("project_id") or "") != project_id:
        return False
    if user_id and (meta.get("user_id") or "") != user_id:
        return False
    if memory_type and (meta.get("memory_type") or "") != memory_type:
        return False
    return True

def _keyword_match(text: str, terms: list):
    if not terms:
        return True
    hay = str(text or "").lower()
    for term in terms:
        if str(term or "").lower() not in hay:
            return False
    return True

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
    store = _init_components()
    
    tags_list = tags if isinstance(tags, list) else []
    tags_str = ", ".join(tags_list) if tags_list else ""
    page_content = f"System: {system_name}\nContent: {content}\nTags: {tags_str}\nScope: {scope or ''}\nProject: {project_id or ''}\nUser: {user_id or ''}\nType: {memory_type or ''}"
    
    metadata = {
        "id": str(uuid.uuid4()),
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
    if not store:
        items = _load_json_store()
        best_idx = None
        best_score = 0.0
        for idx, item in enumerate(items):
            meta = (item or {}).get("metadata") or {}
            if not _meta_matches(meta, system_name, scope, project_id, user_id, memory_type):
                continue
            existing_content = meta.get("original_content") or item.get("content") or ""
            score = _text_similarity(existing_content, content)
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is not None and best_score >= _OVERWRITE_TEXT_SIMILARITY:
            meta = (items[best_idx] or {}).get("metadata") or {}
            metadata["id"] = meta.get("id") or metadata["id"]
            items[best_idx] = {"content": content, "metadata": metadata, "page_content": page_content}
            _write_json_store(items)
            return "已覆盖相似经验。"
        item = {"content": content, "metadata": metadata, "page_content": page_content}
        _append_json_store(item)
        return "已存入本地经验库。"
    from langchain_core.documents import Document
    similar_id = None
    similar_meta = None
    similar_distance = None
    where = None
    filter_dict = {}
    if system_name:
        filter_dict["system"] = system_name
    if scope:
        filter_dict["scope"] = scope
    if project_id:
        filter_dict["project_id"] = project_id
    if user_id:
        filter_dict["user_id"] = user_id
    if memory_type:
        filter_dict["memory_type"] = memory_type
    if filter_dict:
        clauses = []
        for k, v in filter_dict.items():
            if v is None or v == "":
                continue
            clauses.append({k: {"$eq": v}})
        if clauses:
            where = {"$and": clauses} if len(clauses) > 1 else clauses[0]
    try:
        result = store._collection.query(query_texts=[content], n_results=1, where=where)
        ids = (result.get("ids") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        if ids:
            similar_id = ids[0]
            similar_meta = metadatas[0] if metadatas else {}
            similar_distance = distances[0] if distances else None
            existing_content = (similar_meta or {}).get("original_content") or (documents[0] if documents else "")
            text_score = _text_similarity(existing_content, content)
            if text_score < _OVERWRITE_TEXT_SIMILARITY and not (similar_distance is not None and similar_distance <= _OVERWRITE_DISTANCE_THRESHOLD):
                similar_id = None
    except Exception:
        similar_id = None
    if similar_id:
        metadata["id"] = similar_id
        try:
            store._collection.update(ids=[similar_id], documents=[page_content], metadatas=[metadata])
        except Exception:
            store._collection.upsert(ids=[similar_id], documents=[page_content], metadatas=[metadata])
        return "已覆盖相似经验。"
    store.add_documents([Document(page_content=page_content, metadata=metadata)])
    return "已存入向量知识库。"

def list_operation_experiences(query: str = None, system_filter: str = None, scope: str = None, project_id: str = None, user_id: str = None, memory_type: str = None, tags: list = None, limit: int = 200, offset: int = 0):
    store = _init_components()
    if not store:
        terms = _split_query_terms(query) if query else []
        tag_filters = tags if isinstance(tags, list) else []
        safe_limit = max(1, min(int(limit or 200), 500))
        safe_offset = max(0, int(offset or 0))
        items = []
        for item in _load_json_store():
            meta = (item or {}).get("metadata") or {}
            if system_filter and meta.get("system") != system_filter:
                continue
            if scope and meta.get("scope") != scope:
                continue
            if project_id and meta.get("project_id") != project_id:
                continue
            if user_id and meta.get("user_id") != user_id:
                continue
            if memory_type and meta.get("memory_type") != memory_type:
                continue
            if tag_filters:
                doc_tags = meta.get("tags_list") or meta.get("tags") or ""
                if not all(tag in doc_tags for tag in tag_filters):
                    continue
            content = meta.get("original_content") or item.get("content") or ""
            if query and not _keyword_match(content + " " + (meta.get("system") or "") + " " + (meta.get("tags") or ""), terms):
                continue
            items.append({
                "id": meta.get("id") or "",
                "content": content,
                "system": meta.get("system"),
                "tags": meta.get("tags"),
                "scope": meta.get("scope"),
                "project_id": meta.get("project_id"),
                "user_id": meta.get("user_id"),
                "memory_type": meta.get("memory_type"),
                "created_at": meta.get("created_at"),
                "url": meta.get("url")
            })
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return items[safe_offset:safe_offset + safe_limit]
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
    tag_filters = tags if isinstance(tags, list) else []
    safe_limit = max(1, min(int(limit or 200), 500))
    safe_offset = max(0, int(offset or 0))
    items = []
    if query:
        try:
            result = store._collection.query(query_texts=[query], n_results=safe_limit, where=where)
            ids = (result.get("ids") or [[]])[0]
            metadatas = (result.get("metadatas") or [[]])[0]
            documents = (result.get("documents") or [[]])[0]
            for i, doc_id in enumerate(ids):
                meta = metadatas[i] if i < len(metadatas) else {}
                doc = documents[i] if i < len(documents) else ""
                if tag_filters:
                    doc_tags = meta.get("tags_list") or meta.get("tags") or ""
                    if not all(tag in doc_tags for tag in tag_filters):
                        continue
                items.append({
                    "id": doc_id,
                    "content": meta.get("original_content") or doc,
                    "system": meta.get("system"),
                    "tags": meta.get("tags"),
                    "scope": meta.get("scope"),
                    "project_id": meta.get("project_id"),
                    "user_id": meta.get("user_id"),
                    "memory_type": meta.get("memory_type"),
                    "created_at": meta.get("created_at"),
                    "url": meta.get("url")
                })
            return items
        except Exception:
            results = store.similarity_search(query, k=safe_limit, filter=where)
            for doc in results:
                meta = doc.metadata or {}
                if tag_filters:
                    doc_tags = meta.get("tags_list") or meta.get("tags") or ""
                    if not all(tag in doc_tags for tag in tag_filters):
                        continue
                items.append({
                    "id": meta.get("id") or "",
                    "content": meta.get("original_content") or doc.page_content,
                    "system": meta.get("system"),
                    "tags": meta.get("tags"),
                    "scope": meta.get("scope"),
                    "project_id": meta.get("project_id"),
                    "user_id": meta.get("user_id"),
                    "memory_type": meta.get("memory_type"),
                    "created_at": meta.get("created_at"),
                    "url": meta.get("url")
                })
            return items
    try:
        result = store.get(where=where, limit=safe_limit, offset=safe_offset)
    except Exception:
        try:
            result = store._collection.get(where=where, limit=safe_limit, offset=safe_offset)
        except Exception:
            return []
    ids = result.get("ids") or []
    metadatas = result.get("metadatas") or []
    documents = result.get("documents") or []
    for i, doc_id in enumerate(ids):
        meta = metadatas[i] if i < len(metadatas) else {}
        doc = documents[i] if i < len(documents) else ""
        if tag_filters:
            doc_tags = meta.get("tags_list") or meta.get("tags") or ""
            if not all(tag in doc_tags for tag in tag_filters):
                continue
        items.append({
            "id": doc_id,
            "content": meta.get("original_content") or doc,
            "system": meta.get("system"),
            "tags": meta.get("tags"),
            "scope": meta.get("scope"),
            "project_id": meta.get("project_id"),
            "user_id": meta.get("user_id"),
            "memory_type": meta.get("memory_type"),
            "created_at": meta.get("created_at"),
            "url": meta.get("url")
        })
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return items

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
    if not store:
        items = list_operation_experiences(
            query=query,
            system_filter=system_filter,
            scope=scope,
            project_id=project_id,
            user_id=user_id,
            memory_type=memory_type,
            tags=tags,
            limit=n_results,
            offset=0
        )
        return json.dumps(items, ensure_ascii=False, indent=2)
    
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

@tool
def search_short_term_memory(query: str, n_results: int = 8, project_id: str = None, user_id: str = None, role: str = None):
    """
    搜索本地短期记忆（对话消息），用于“搜索所有记忆”场景。
    """
    q = str(query or "").strip()
    if not q:
        return json.dumps([], ensure_ascii=False)
    db_paths = _list_short_term_db_paths()
    if not db_paths:
        _init_short_term_db()
        db_paths = [_get_short_term_db_path()]
    try:
        limit = max(1, min(int(n_results or 8), 50))
        items = []
        terms = _split_query_terms(q)
        fts_query = " OR ".join(terms) if terms else q
        fts_items = []
        seen = set()
        if fts_query:
            for path in db_paths:
                conn = sqlite3.connect(path)
                try:
                    cur = conn.cursor()
                    conditions = ["short_term_messages_fts MATCH ?"]
                    params = [fts_query]
                    if project_id:
                        conditions.append("project_id = ?")
                        params.append(str(project_id))
                    if user_id:
                        conditions.append("user_id = ?")
                        params.append(str(user_id))
                    if role:
                        conditions.append("role = ?")
                        params.append(str(role))
                    where = " AND ".join(conditions)
                    sql = f"SELECT role, content, created_at, project_id, user_id, bm25(short_term_messages_fts) as score FROM short_term_messages_fts WHERE {where} ORDER BY score LIMIT ?"
                    params.append(limit)
                    rows = cur.execute(sql, params).fetchall()
                    for r in rows:
                        key = (r[0], r[1], r[2], r[3], r[4])
                        if key in seen:
                            continue
                        seen.add(key)
                        fts_items.append({
                            "role": r[0],
                            "content": r[1],
                            "created_at": r[2],
                            "project_id": r[3],
                            "user_id": r[4],
                            "source": "short_term"
                        })
                except Exception:
                    pass
                finally:
                    conn.close()
        if fts_items:
            fts_items.sort(key=lambda x: x.get("created_at") or "")
            if len(fts_items) > limit:
                fts_items = fts_items[-limit:]
            return json.dumps(fts_items, ensure_ascii=False, indent=2)
        conditions = []
        base_params = []
        if terms:
            for term in terms:
                conditions.append("content LIKE ?")
                base_params.append(f"%{term}%")
        else:
            conditions.append("content LIKE ?")
            base_params.append(f"%{q}%")
        if project_id:
            conditions.append("project_id = ?")
            base_params.append(str(project_id))
        if user_id:
            conditions.append("user_id = ?")
            base_params.append(str(user_id))
        if role:
            conditions.append("role = ?")
            base_params.append(str(role))
        where = " AND ".join(conditions)
        sql = f"SELECT role, content, created_at, project_id, user_id FROM short_term_messages WHERE {where} ORDER BY id DESC LIMIT ?"
        for path in db_paths:
            conn = sqlite3.connect(path)
            try:
                cur = conn.cursor()
                params = list(base_params)
                params.append(limit)
                rows = cur.execute(sql, params).fetchall()
                for r in rows:
                    items.append({
                        "role": r[0],
                        "content": r[1],
                        "created_at": r[2],
                        "project_id": r[3],
                        "user_id": r[4],
                        "source": "short_term"
                    })
            finally:
                conn.close()
        items.sort(key=lambda x: x.get("created_at") or "")
        if len(items) > limit:
            items = items[-limit:]
        return json.dumps(items, ensure_ascii=False, indent=2)
    finally:
        pass
