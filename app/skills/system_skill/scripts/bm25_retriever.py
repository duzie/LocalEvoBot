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
    
    # 3. 提取中文连续字符 (2 字以上优先，避免单字噪声)
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
    
    async def _aget_relevant_documents(self, query: str, **kwargs) -> List[Document]:
        """异步版本（同步实现）"""
        return self._get_relevant_documents(query, **kwargs)
