"""
向量索引管理器
支持百万级向量存储和快速检索
"""

import os
import json
import time
import hashlib
import threading
import sqlite3
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict, field
import pickle
import faiss
import uuid

# 确保使用HF镜像
if not (os.getenv("HF_ENDPOINT") or "").strip():
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from langchain_core.tools import tool
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import SentenceTransformer

# 全局变量
_INDEXES = {}
_INDEX_LOCK = threading.Lock()
_EMBEDDING_MODEL = None
_INDEX_STORE_PATH = None

@dataclass
class VectorIndexConfig:
    """向量索引配置"""
    index_name: str
    dimension: int
    index_type: str = "HNSW"  # HNSW, IVF_FLAT, IVF_PQ
    metric_type: str = "L2"  # L2, IP (内积)
    hnsw_m: int = 16  # HNSW参数：每个节点的连接数
    hnsw_ef_construction: int = 200  # HNSW构建参数
    hnsw_ef_search: int = 64  # HNSW搜索参数
    nlist: int = 100  # IVF聚类中心数
    nprobe: int = 10  # IVF搜索时检查的聚类中心数
    pq_m: int = 8  # PQ子空间数
    pq_nbits: int = 8  # PQ每个子空间的比特数
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    vector_count: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    vector: Optional[List[float]]
    metadata: Dict[str, Any]
    score: float
    distance: float


class VectorIndexManager:
    """向量索引管理器"""
    
    def __init__(self, store_path: Optional[str] = None):
        """初始化向量索引管理器
        
        Args:
            store_path: 索引存储路径，默认为 app/data/vector_indexes
        """
        global _INDEX_STORE_PATH
        
        if store_path:
            _INDEX_STORE_PATH = store_path
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            _INDEX_STORE_PATH = os.path.join(base_dir, "app", "data", "vector_indexes")
        
        os.makedirs(_INDEX_STORE_PATH, exist_ok=True)
        self._load_indexes()
    
    def _get_index_path(self, index_name: str) -> str:
        """获取索引文件路径"""
        safe_name = hashlib.md5(index_name.encode()).hexdigest()
        return os.path.join(_INDEX_STORE_PATH, f"{safe_name}.index")
    
    def _get_config_path(self, index_name: str) -> str:
        """获取配置文件路径"""
        safe_name = hashlib.md5(index_name.encode()).hexdigest()
        return os.path.join(_INDEX_STORE_PATH, f"{safe_name}.config.json")
    
    def _get_data_path(self, index_name: str) -> str:
        """获取数据文件路径"""
        safe_name = hashlib.md5(index_name.encode()).hexdigest()
        return os.path.join(_INDEX_STORE_PATH, f"{safe_name}.data.pkl")
    
    def _load_indexes(self):
        """加载所有索引"""
        with _INDEX_LOCK:
            if not os.path.exists(_INDEX_STORE_PATH):
                return
            
            for filename in os.listdir(_INDEX_STORE_PATH):
                if filename.endswith(".config.json"):
                    index_name_hash = filename.replace(".config.json", "")
                    config_path = os.path.join(_INDEX_STORE_PATH, filename)
                    
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                        
                        # 重建索引对象
                        index_path = os.path.join(_INDEX_STORE_PATH, f"{index_name_hash}.index")
                        if os.path.exists(index_path):
                            index = faiss.read_index(index_path)
                            _INDEXES[config_data['index_name']] = {
                                'index': index,
                                'config': VectorIndexConfig(**config_data),
                                'data': self._load_index_data(config_data['index_name'])
                            }
                    except Exception as e:
                        print(f"加载索引 {filename} 失败: {e}")
    
    def _load_index_data(self, index_name: str) -> Dict:
        """加载索引数据"""
        data_path = self._get_data_path(index_name)
        if os.path.exists(data_path):
            try:
                with open(data_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"加载索引数据失败: {e}")
        return {
            'vectors': [],
            'ids': [],
            'metadata': []
        }
    
    def _save_index_data(self, index_name: str, data: Dict):
        """保存索引数据"""
        data_path = self._get_data_path(index_name)
        try:
            with open(data_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            print(f"保存索引数据失败: {e}")
    
    def create_index(self, index_name: str, dimension: int, index_type: str = "HNSW", **kwargs) -> bool:
        """创建向量索引
        
        Args:
            index_name: 索引名称
            dimension: 向量维度
            index_type: 索引类型，可选 HNSW/IVF_FLAT/IVF_PQ
            **kwargs: 其他索引参数
        
        Returns:
            是否创建成功
        """
        with _INDEX_LOCK:
            if index_name in _INDEXES:
                return False
            
            # 创建索引配置
            config = VectorIndexConfig(
                index_name=index_name,
                dimension=dimension,
                index_type=index_type,
                **kwargs
            )
            
            # 创建FAISS索引
            if index_type == "HNSW":
                index = faiss.IndexHNSWFlat(dimension, config.hnsw_m)
                index.hnsw.efConstruction = config.hnsw_ef_construction
                index.hnsw.efSearch = config.hnsw_ef_search
            elif index_type == "IVF_FLAT":
                quantizer = faiss.IndexFlatL2(dimension)
                index = faiss.IndexIVFFlat(quantizer, dimension, config.nlist, faiss.METRIC_L2)
                index.nprobe = config.nprobe
            elif index_type == "IVF_PQ":
                quantizer = faiss.IndexFlatL2(dimension)
                index = faiss.IndexIVFPQ(quantizer, dimension, config.nlist, config.pq_m, config.pq_nbits)
                index.nprobe = config.nprobe
            else:
                # 默认使用Flat索引
                index = faiss.IndexFlatL2(dimension)
            
            # 保存索引
            _INDEXES[index_name] = {
                'index': index,
                'config': config,
                'data': {
                    'vectors': [],
                    'ids': [],
                    'metadata': []
                }
            }
            
            # 保存到文件
            self._save_index(index_name)
            return True


    
    def _save_index(self, index_name: str):
        """保存索引到文件"""
        if index_name not in _INDEXES:
            return
        
        index_info = _INDEXES[index_name]
        
        # 保存索引文件
        index_path = self._get_index_path(index_name)
        faiss.write_index(index_info['index'], index_path)
        
        # 保存配置文件
        config_path = self._get_config_path(index_name)
        config_dict = asdict(index_info['config'])
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=2)
        
        # 保存数据文件
        self._save_index_data(index_name, index_info['data'])
    
    def add_vectors(self, index_name: str, vectors: List[List[float]], 
                   ids: Optional[List[str]] = None, 
                   metadata: Optional[List[Dict]] = None) -> bool:
        """向索引添加向量
        
        Args:
            index_name: 索引名称
            vectors: 向量列表
            ids: 向量ID列表，如未提供则自动生成
            metadata: 元数据列表
        
        Returns:
            是否添加成功
        """
        with _INDEX_LOCK:
            if index_name not in _INDEXES:
                return False
            
            index_info = _INDEXES[index_name]
            index = index_info['index']
            config = index_info['config']
            data = index_info['data']
            
            # 转换为numpy数组
            vectors_np = np.array(vectors, dtype=np.float32)
            
            # 检查维度
            if vectors_np.shape[1] != config.dimension:
                return False
            
            # 生成ID
            if ids is None:
                ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
            
            # 处理元数据
            if metadata is None:
                metadata = [{} for _ in range(len(vectors))]
            
            # 添加到索引
            if not index.is_trained:
                index.train(vectors_np)
            index.add(vectors_np)
            
            # 更新数据
            data['vectors'].extend(vectors)
            data['ids'].extend(ids)
            data['metadata'].extend(metadata)
            
            # 更新配置
            config.vector_count += len(vectors)
            config.last_updated = datetime.now().isoformat()
            
            # 保存到文件
            self._save_index(index_name)
            return True
    
    def search(self, index_name: str, query_vector: List[float], k: int = 10, 
               filters: Optional[Dict] = None) -> List[SearchResult]:
        """搜索向量
        
        Args:
            index_name: 索引名称
            query_vector: 查询向量
            k: 返回结果数量
            filters: 过滤条件
        
        Returns:
            搜索结果列表
        """
        if index_name not in _INDEXES:
            return []
        
        index_info = _INDEXES[index_name]
        index = index_info['index']
        data = index_info['data']
        
        # 转换为numpy数组
        query_np = np.array([query_vector], dtype=np.float32)
        
        # 执行搜索
        distances, indices = index.search(query_np, min(k * 2, len(data['ids'])))
        
        # 处理结果
        results = []
        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < 0 or idx >= len(data['ids']):
                continue
            
            # 应用过滤条件
            if filters:
                metadata = data['metadata'][idx]
                skip = False
                for key, value in filters.items():
                    if key not in metadata or metadata[key] != value:
                        skip = True
                        break
                if skip:
                    continue
            
            # 计算相似度分数（距离转换为相似度）
            score = 1.0 / (1.0 + distance) if distance > 0 else 1.0
            
            result = SearchResult(
                id=data['ids'][idx],
                vector=data['vectors'][idx] if idx < len(data['vectors']) else None,
                metadata=data['metadata'][idx],
                score=score,
                distance=float(distance)
            )
            results.append(result)
            
            if len(results) >= k:
                break
        
        return results


    
    def get_stats(self, index_name: str) -> Optional[Dict]:
        """获取索引统计信息
        
        Args:
            index_name: 索引名称
        
        Returns:
            索引统计信息
        """
        if index_name not in _INDEXES:
            return None
        
        index_info = _INDEXES[index_name]
        config = index_info['config']
        data = index_info['data']
        
        return {
            'index_name': config.index_name,
            'dimension': config.dimension,
            'index_type': config.index_type,
            'vector_count': config.vector_count,
            'created_at': config.created_at,
            'last_updated': config.last_updated,
            'total_vectors': len(data['ids']),
            'index_size': os.path.getsize(self._get_index_path(index_name)) if os.path.exists(self._get_index_path(index_name)) else 0
        }
    
    def optimize(self, index_name: str) -> bool:
        """优化索引
        
        Args:
            index_name: 索引名称
        
        Returns:
            是否优化成功
        """
        if index_name not in _INDEXES:
            return False
        
        # 对于FAISS索引，优化主要是重新训练（如果需要）
        index_info = _INDEXES[index_name]
        index = index_info['index']
        
        # 如果索引未训练且向量数量足够，则训练
        if not index.is_trained and len(index_info['data']['vectors']) > 0:
            vectors_np = np.array(index_info['data']['vectors'], dtype=np.float32)
            index.train(vectors_np)
            self._save_index(index_name)
        
        return True
    
    def delete_index(self, index_name: str) -> bool:
        """删除索引
        
        Args:
            index_name: 索引名称
        
        Returns:
            是否删除成功
        """
        with _INDEX_LOCK:
            if index_name not in _INDEXES:
                return False
            
            # 删除文件
            index_path = self._get_index_path(index_name)
            config_path = self._get_config_path(index_name)
            data_path = self._get_data_path(index_name)
            
            for path in [index_path, config_path, data_path]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as e:
                        print(f"删除文件 {path} 失败: {e}")
            
            # 从内存中删除
            del _INDEXES[index_name]
            return True
    
    def list_indexes(self) -> List[Dict]:
        """列出所有索引
        
        Returns:
            索引列表
        """
        result = []
        for index_name, index_info in _INDEXES.items():
            config = index_info['config']
            result.append({
                'index_name': index_name,
                'dimension': config.dimension,
                'index_type': config.index_type,
                'vector_count': config.vector_count,
                'created_at': config.created_at
            })
        return result

# 全局管理器实例
_manager = None
_MANAGER_LOCK = threading.Lock()

def _get_manager() -> VectorIndexManager:
    """获取向量索引管理器实例"""
    global _manager
    with _MANAGER_LOCK:
        if _manager is None:
            _manager = VectorIndexManager()
    return _manager