"""
向量索引技能
支持百万级向量存储和快速检索
"""

from .scripts import (
    create_vector_index,
    add_vectors_to_index,
    search_vectors,
    get_index_stats,
    optimize_index,
    delete_index,
    list_indexes,
    batch_index_files
)

__all__ = [
    'create_vector_index',
    'add_vectors_to_index',
    'search_vectors',
    'get_index_stats',
    'optimize_index',
    'delete_index',
    'list_indexes',
    'batch_index_files'
]