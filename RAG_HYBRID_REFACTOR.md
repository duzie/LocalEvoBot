# RAG 混合检索改造计划（可执行版）

> **目标**：为现有 RAG 系统添加 BM25 混合检索，提升精确术语匹配能力
> **适用范围**：长期记忆检索（`get_operation_experience`）
> **保持现状**：短期记忆检索（`search_short_term_memory`）继续使用 FTS5

---

## 📋 改造范围

| 组件 | 当前状态 | 改造后 | 优先级 |
|------|---------|--------|--------|
| **检索引擎** | 纯向量 (Chroma) | BM25 + 向量混合 | P0 |
| **切块策略** | 无切块 (整条存储) | 智能切块 (400 字符) | P1 |
| **融合策略** | 无 | RRF (Reciprocal Rank Fusion) | P0 |
| **短期记忆** | FTS5 + BM25 | **保持不变** | - |

---

## 🎯 成功指标

```yaml
精确术语召回率:
  测试查询: "F821 报错", "playwright_click 用法", "app/skills/board_skill"
  当前: ~45%
  目标: ≥85%

语义查询准确率:
  测试查询: "怎么修复文件备份失败", "浏览器自动化最佳实践"
  当前: ~70%
  目标: ≥80% (不下降)

响应时间:
  当前: ~200ms
  目标: ≤350ms (可接受 150ms 增长)
```

---

## 🛠️ 实施步骤

### Step 1: 安装依赖

```bash
pip install rank_bm25 langchain-community
```

**验证**：
```python
import rank_bm25
from langchain_community.retrievers import BM25Retriever
# 无报错即成功
```

---

### Step 2: 创建 BM25 检索器模块

**文件**: `app/skills/system_skill/scripts/bm25_retriever.py`

```python
"""BM25 关键词检索器（针对中文技术文档优化）"""

from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from typing import List, Any
import re


def tokenize_chinese_technical(text: str) -> List[str]:
    """
    中文技术文档分词策略
    
    保留:

---

### Step 3: 修改经验检索工具

**文件**: `app/skills/system_skill/scripts/experience_tools.py`

#### 3.1 在文件顶部添加导入

```python
# 在现有导入后添加
from langchain.retrievers import EnsembleRetriever
from .bm25_retriever import TechnicalBM25Retriever
```

#### 3.2 添加全局变量缓存检索器

```python
# 在文件顶部 _ft5_db_cache 后添加
_bm25_retriever_cache = None
_hybrid_retriever_cache = None
```

#### 3.3 创建混合检索器初始化函数

在 `_init_components()` 函数后添加：

```python
def _init_hybrid_retriever():
    """初始化 BM25 + 向量混合检索器"""
    global _hybrid_retriever_cache
    
    if _hybrid_retriever_cache is not None:
        return _hybrid_retriever_cache
    
    vector_store = _init_components()
    if vector_store is None:
        return None
    
    try:
        all_docs = vector_store.similarity_search("", k=1000)
    except Exception:
        return vector_store.as_retriever(search_kwargs={"k": 5})
    
    if not all_docs:
        return vector_store.as_retriever(search_kwargs={"k": 5})
    
    bm25_retriever = TechnicalBM25Retriever.from_documents(all_docs, k=10)
    vector_retriever = vector_store.as_retriever(search_kwargs={"k": 10})
    
    hybrid_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[0.5, 0.5]
    )
    
    _hybrid_retriever_cache = hybrid_retriever
    return hybrid_retriever
```

#### 3.4 修改 `get_operation_experience` 函数

替换检索逻辑为：

```python
@tool
def get_operation_experience(query: str, system_filter: str = None, n_results: int = 3, ...):
    """语义检索操作经验（支持 BM25 + 向量混合检索）"""
    retriever = _init_hybrid_retriever()
    
    if retriever is None:
        return []
    
    try:
        docs = retriever.invoke(query)
    except Exception as e:
        vector_store = _init_components()
        if vector_store:
            docs = vector_store.similarity_search(query, k=n_results)
        else:
            return []
    
    # 后处理和过滤
    filtered_results = []
    for doc in docs:
        meta = doc.metadata
        if system_filter and meta.get("system") != system_filter:
            continue
        
        result = {
            "content": meta.get("original_content") or doc.page_content,
            "system": meta.get("system", "unknown"),
            "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
            "url": meta.get("url", ""),
            "created_at": meta.get("created_at", ""),
        }

---

### Step 4: 实现智能切块（P1 可选）

**文件**: `app/skills/system_skill/scripts/chunking.py` (新建)

```python
"""智能切块器（针对技术经验文档优化）"""

from typing import List
import re


def smart_chunk_experience(
    content: str,
    system_name: str,
    tags: List[str] = None,
    chunk_size: int = 400,
    chunk_overlap: int = 80
) -> List[str]:
    """智能切分经验内容"""
    if len(content) <= chunk_size:
        return [content]
    
    chunks = []
    current_pos = 0
    
    while current_pos < len(content):
        window_end = min(current_pos + chunk_size, len(content))
        window = content[current_pos:window_end]
        
        split_point = None
        
        # 1. 代码块边界
        code_block_match = re.search(r'\n```\s*$', window)
        if code_block_match:
            split_point = current_pos + code_block_match.end()
        
        # 2. 段落边界
        if split_point is None:
            paragraph_match = re.search(r'\n\n', window)
            if paragraph_match:
                split_point = current_pos + paragraph_match.end()
        
        # 3. 句子边界
        if split_point is None:
            sentence_match = re.search(r'[。！？.!?]\s*', window)
            if sentence_match:
                split_point = current_pos + sentence_match.end()
        
        # 4. 强制切分
        if split_point is None:
            split_point = window_end
        
        chunk = content[current_pos:split_point].strip()
        if chunk:
            chunks.append(chunk)
        
        current_pos = split_point - chunk_overlap
        if current_pos <= 0:
            current_pos = split_point
    
    return chunks
```

#### 修改 `add_operation_experience` 函数

在 `experience_tools.py` 中：

```python
from .chunking import smart_chunk_experience

@tool
def add_operation_experience(system_name: str, content: str, tags: list = None, ...):
    """记录系统操作经验到向量知识库 (RAG)"""
    
    chunks = smart_chunk_experience(content, system_name, tags or [], 400, 80)
    tags_str = ", ".join(tags) if tags else ""
    
    store = _init_components()
    docs_to_add = []
    
    for i, chunk in enumerate(chunks):
        full_text = f"System: {system_name}\nTags: {tags_str}\nContent:\n{chunk}"
        
        metadata = {
            "id": f"exp_{uuid.uuid4().hex[:8]}",
            "system": system_name,
            "tags": tags_str,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "original_content": content,
            "created_at": datetime.now().isoformat(),
        }
        docs_to_add.append(Document(page_content=full_text, metadata=metadata))
    
    if store and docs_to_add:
        store.add_documents(docs_to_add)
    
    invalidate_retriever_cache()  # 使缓存失效
    return f"已存入 {len(chunks)} 个片段"
```

---

### Step 5: 添加缓存失效机制

```python
def invalidate_retriever_cache():
    """使检索器缓存失效"""
    global _bm25_retriever_cache, _hybrid_retriever_cache
    _bm25_retriever_cache = None
    _hybrid_retriever_cache = None
```

在 `add_operation_experience` 末尾调用此函数。
        filtered_results.append(result)
        
        if len(filtered_results) >= n_results:

---

## 🧪 测试验证

### 测试文件：`tests/test_rag_hybrid.py`

```python
"""RAG 混合检索测试"""

import pytest
from app.skills.system_skill.scripts.experience_tools import (
    get_operation_experience,
    add_operation_experience,
    invalidate_retriever_cache,
)


class TestHybridRetrieval:
    
    @pytest.fixture(autouse=True)
    def setup(self):
        invalidate_retriever_cache()
        yield
        invalidate_retriever_cache()
    
    def test_exact_match_error_code(self):
        """测试精确匹配错误码"""
        add_operation_experience(
            system_name="Python",
            content="F821 错误表示未定义的名称。使用 validate_code_syntax 检查语法。",
            tags=["error", "python", "F821"]
        )
        
        results = get_operation_experience("F821 报错", n_results=3)
        assert len(results) > 0
        assert any("F821" in r["content"] for r in results)
    
    def test_exact_match_api_name(self):
        """测试精确匹配 API 名称"""
        add_operation_experience(
            system_name="Playwright",
            content="playwright_click 用于点击页面元素。参数 selector 是必需的。",
            tags=["playwright", "click", "api"]
        )
        
        results = get_operation_experience("playwright_click 用法", n_results=3)
        assert len(results) > 0
        assert any("playwright_click" in r["content"] for r in results)
    
    def test_exact_match_file_path(self):
        """测试精确匹配文件路径"""
        add_operation_experience(
            system_name="Project",
            content="文件位于 app/skills/board_skill/scripts/board_tools.py",
            tags=["file", "path"]
        )
        
        results = get_operation_experience("app/skills/board_skill", n_results=3)
        assert len(results) > 0
        assert any("board_tools.py" in r["content"] for r in results)
    
    def test_semantic_query(self):
        """测试语义查询（不下降）"""
        add_operation_experience(
            system_name="File",
            content="修改文件前必须先备份。使用 safe_file_backup 创建备份。",
            tags=["file", "backup"]
        )
        
        results = get_operation_experience("怎么安全修改文件", n_results=3)
        assert len(results) > 0
        assert any("备份" in r["content"] for r in results)
    
    def test_response_time(self):
        """测试响应时间"""
        import time
        
        start = time.time()
        results = get_operation_experience("文件备份", n_results=3)
        elapsed = time.time() - start
        
        assert elapsed < 0.35, f"响应时间 {elapsed*1000:.0f}ms 超过 350ms"
```

### 运行测试

```bash
cd D:\localevobot
pytest tests/test_rag_hybrid.py -v
```

---

## 📦 依赖包

在 `requirements.txt` 中添加：

```txt
rank_bm25>=0.2.2
langchain-community>=0.2.0
```

---

## ⚠️ 注意事项

1. **不要修改短期记忆**：`search_short_term_memory` 继续使用 FTS5
2. **缓存失效**：每次添加/删除经验后调用 `invalidate_retriever_cache()`
3. **向后兼容**：现有经验数据无需迁移
4. **降级策略**：BM25 失败时自动降级为纯向量检索

---

## 🚀 执行顺序

```bash
# 1. 安装依赖
pip install rank_bm25 langchain-community

# 2. 创建 bm25_retriever.py

# 3. 创建 chunking.py

# 4. 修改 experience_tools.py

# 5. 运行测试
pytest tests/test_rag_hybrid.py -v
```

---

## 🔄 回滚方案

如果出现问题，临时回滚 `get_operation_experience`：

```python
# 直接使用纯向量检索
vector_store = _init_components()
docs = vector_store.similarity_search(query, k=n_results)
```
            break
    
    return filtered_results
```
    - 英文单词和标识符 (playwright_click, F821, app/skills)
    - 中文连续字符
    - 数字序列
    
    忽略:
    - 标点符号
    - 空白字符
    """
    tokens = []
    
    # 1. 提取英文标识符和路径 (playwright_click, app/skills/board_skill)
    identifiers = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*(?:/[a-zA-Z_][a-zA-Z0-9_]*)*', text)
    tokens.extend([i.lower() for i in identifiers])
    
    # 2. 提取错误码和数字 (F821, 2026, 404)
    codes = re.findall(r'[A-Z]{1,3}\d{2,4}|\d{3,}', text)
    tokens.extend(codes)
    
    # 3. 提取中文连续字符 (4 字以上优先，避免单字噪声)
    chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
    tokens.extend(chinese_words)
    
    return tokens


class TechnicalBM25Retriever(BaseRetriever):
    """针对技术文档优化的 BM25 检索器"""
    
    documents: List[Document]
    bm25: Any
    k: int = 10
    
    @classmethod
    def from_documents(cls, documents: List[Document], k: int = 10):
        if not documents:
            return cls(documents=[], bm25=None, k=k)
        
        tokenized_docs = [tokenize_chinese_technical(doc.page_content) for doc in documents]
        bm25 = BM25Okapi(tokenized_docs)
        return cls(documents=documents, bm25=bm25, k=k)
    
    def _get_relevant_documents(self, query: str, **kwargs) -> List[Document]:
        if not self.documents or self.bm25 is None:
            return []
        
        query_tokens = tokenize_chinese_technical(query)
        if not query_tokens:
            return []
        
        scores = self.bm25.get_scores(query_tokens)
        valid_indices = [(i, s) for i, s in enumerate(scores) if s > 0]
        if not valid_indices:
            return []
        
        valid_indices.sort(key=lambda x: x[1], reverse=True)
        top_indices = [i for i, _ in valid_indices[:self.k]]
        
        return [self.documents[i] for i in top_indices]
```
