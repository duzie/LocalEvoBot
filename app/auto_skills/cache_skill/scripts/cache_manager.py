"""
缓存管理器 - 实现混合缓存系统的核心功能
支持内存缓存（LRU/LFU）和磁盘缓存（SQLite）
"""

import os
import json
import sqlite3
import hashlib
import time
import threading
from typing import Dict, Any, Optional, List, Tuple
from collections import OrderedDict
from datetime import datetime, timedelta
import pickle


class CacheItem:
    """缓存项数据结构"""
    
    def __init__(self, key: str, value: Any, ttl_seconds: int = 3600):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        self.access_count = 0
        self.last_accessed = self.created_at
        self.size = self._calculate_size(value)
    
    def _calculate_size(self, value: Any) -> int:
        """计算缓存项大小（字节）"""
        try:
            if isinstance(value, str):
                return len(value.encode('utf-8'))
            elif isinstance(value, bytes):
                return len(value)
            else:
                # 序列化后计算大小
                return len(pickle.dumps(value))
        except:
            return 1024  # 默认1KB
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() > self.expires_at
    
    def access(self) -> None:
        """访问缓存项"""
        self.access_count += 1
        self.last_accessed = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'key': self.key,
            'value': self.value,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'access_count': self.access_count,
            'last_accessed': self.last_accessed,
            'size': self.size
        }


class MemoryCache:
    """内存缓存实现（支持LRU和LFU）"""
    
    def __init__(self, max_size_mb: int = 100, eviction_policy: str = 'lru'):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.eviction_policy = eviction_policy.lower()
        self.cache: Dict[str, CacheItem] = {}
        self.lru_order = OrderedDict()  # 用于LRU
        self.current_size = 0
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self.lock:
            if key in self.cache:
                item = self.cache[key]
                if item.is_expired():
                    self._remove(key)
                    self.misses += 1
                    return None
                
                item.access()
                self.hits += 1
                
                # 更新LRU顺序
                if self.eviction_policy == 'lru':
                    if key in self.lru_order:
                        self.lru_order.move_to_end(key)
                
                return item.value
            else:
                self.misses += 1
                return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """设置缓存值"""
        with self.lock:
            # 创建缓存项
            item = CacheItem(key, value, ttl_seconds)
            
            # 检查是否需要淘汰
            while self.current_size + item.size > self.max_size_bytes and self.cache:
                self._evict()
            
            # 添加或更新缓存
            if key in self.cache:
                old_item = self.cache[key]
                self.current_size -= old_item.size
            
            self.cache[key] = item
            self.current_size += item.size
            
            # 更新LRU顺序
            if self.eviction_policy == 'lru':
                self.lru_order[key] = True
            
            return True
    
    def delete(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            return self._remove(key)
    
    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.lru_order.clear()
            self.current_size = 0
    
    def _remove(self, key: str) -> bool:
        """内部删除方法"""
        if key in self.cache:
            item = self.cache[key]
            self.current_size -= item.size
            del self.cache[key]
            
            if key in self.lru_order:
                del self.lru_order[key]
            
            return True
        return False
    
    def _evict(self) -> None:
        """淘汰缓存项"""
        if not self.cache:
            return
        
        if self.eviction_policy == 'lru':
            # LRU淘汰：移除最久未使用的
            key = next(iter(self.lru_order))
            self._remove(key)
        elif self.eviction_policy == 'lfu':
            # LFU淘汰：移除访问次数最少的
            key = min(self.cache.keys(), key=lambda k: self.cache[k].access_count)
            self._remove(key)
        else:
            # 随机淘汰
            key = next(iter(self.cache))
            self._remove(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            total_hits = self.hits + self.misses
            hit_rate = self.hits / total_hits if total_hits > 0 else 0
            
            return {
                'size_mb': self.current_size / (1024 * 1024),
                'max_size_mb': self.max_size_bytes / (1024 * 1024),
                'item_count': len(self.cache),
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': round(hit_rate * 100, 2),
                'eviction_policy': self.eviction_policy
            }
    
    def cleanup_expired(self) -> int:
        """清理过期缓存项"""
        with self.lock:
            expired_keys = [key for key, item in self.cache.items() if item.is_expired()]
            for key in expired_keys:
                self._remove(key)
            return len(expired_keys)


class DiskCache:
    """磁盘缓存实现（基于SQLite）"""
    
    def __init__(self, db_path: str = None, max_size_mb: int = 1000):
        if db_path is None:
            # 默认路径
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            db_path = os.path.join(cache_dir, 'file_cache.db')
        
        self.db_path = db_path
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.conn = None
        self.lock = threading.RLock()
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        with self.lock:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = self.conn.cursor()
            
            # 创建缓存表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS file_cache (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    created_at REAL,
                    expires_at REAL,
                    access_count INTEGER DEFAULT 0,
                    last_accessed REAL,
                    size INTEGER,
                    metadata TEXT
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_expires_at ON file_cache(expires_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_accessed ON file_cache(last_accessed)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_count ON file_cache(access_count)')
            
            self.conn.commit()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                'SELECT value, expires_at FROM file_cache WHERE key = ?',
                (key,)
            )
            row = cursor.fetchone()
            
            if row:
                value_blob, expires_at = row
                
                # 检查是否过期
                if time.time() > expires_at:
                    self.delete(key)
                    return None
                
                # 更新访问统计
                cursor.execute('''
                    UPDATE file_cache 
                    SET access_count = access_count + 1, 
                        last_accessed = ?
                    WHERE key = ?
                ''', (time.time(), key))
                self.conn.commit()
                
                # 反序列化值
                try:
                    value = pickle.loads(value_blob)
                    return value
                except:
                    return None
            return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """设置缓存值"""
        with self.lock:
            try:
                # 序列化值
                value_blob = pickle.dumps(value)
                size = len(value_blob)
                
                # 检查大小限制
                if size > self.max_size_bytes:
                    return False
                
                # 清理空间
                self._cleanup_if_needed(size)
                
                # 插入或更新
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO file_cache 
                    (key, value, created_at, expires_at, size, last_accessed, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    key,
                    value_blob,
                    time.time(),
                    time.time() + ttl_seconds,
                    size,
                    time.time(),
                    json.dumps({'type': type(value).__name__})
                ))
                
                self.conn.commit()
                return True
            except Exception as e:
                print(f"Disk cache set error: {e}")
                return False
    
    def delete(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute('DELETE FROM file_cache WHERE key = ?', (key,))
                self.conn.commit()
                return cursor.rowcount > 0
            except:
                return False
    
    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM file_cache')
            self.conn.commit()
    
    def _cleanup_if_needed(self, new_size: int) -> None:
        """如果需要，清理空间"""
        cursor = self.conn.cursor()
        
        # 获取当前总大小
        cursor.execute('SELECT SUM(size) FROM file_cache')
        total_size = cursor.fetchone()[0] or 0
        
        # 如果加上新项会超过限制，清理
        if total_size + new_size > self.max_size_bytes:
            # 先清理过期的
            cursor.execute('DELETE FROM file_cache WHERE expires_at < ?', (time.time(),))
            
            # 如果还不够，按LRU清理
            cursor.execute('SELECT SUM(size) FROM file_cache')
            total_size = cursor.fetchone()[0] or 0
            
            if total_size + new_size > self.max_size_bytes:
                # 按最后访问时间排序，删除最旧的
                cursor.execute('''
                    DELETE FROM file_cache 
                    WHERE key IN (
                        SELECT key FROM file_cache 
                        ORDER BY last_accessed ASC 
                        LIMIT ?
                    )
                ''', (10,))  # 每次清理10个
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            cursor = self.conn.cursor()
            
            # 获取基本信息
            cursor.execute('SELECT COUNT(*), SUM(size) FROM file_cache')
            count, total_size = cursor.fetchone()
            count = count or 0
            total_size = total_size or 0
            
            # 获取过期项数量
            cursor.execute('SELECT COUNT(*) FROM file_cache WHERE expires_at < ?', (time.time(),))
            expired_count = cursor.fetchone()[0] or 0
            
            # 获取命中率（需要额外的统计表）
            cursor.execute('''
                SELECT SUM(access_count), COUNT(*) FROM file_cache
            ''')
            total_access, total_items = cursor.fetchone()
            total_access = total_access or 0
            total_items = total_items or 0
            
            avg_access = total_access / total_items if total_items > 0 else 0
            
            return {
                'size_mb': total_size / (1024 * 1024),
                'max_size_mb': self.max_size_bytes / (1024 * 1024),
                'item_count': count,
                'expired_count': expired_count,
                'total_access': total_access,
                'avg_access_per_item': round(avg_access, 2),
                'db_path': self.db_path
            }
    
    def cleanup_expired(self) -> int:
        """清理过期缓存项"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM file_cache WHERE expires_at < ?', (time.time(),))
            expired_count = cursor.fetchone()[0] or 0
            
            cursor.execute('DELETE FROM file_cache WHERE expires_at < ?', (time.time(),))
            self.conn.commit()
            
            return expired_count


class HybridCacheManager:
    """混合缓存管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.memory_cache = MemoryCache(max_size_mb=100, eviction_policy='lru')
        self.disk_cache = DiskCache(max_size_mb=1000)
        self._initialized = True
        
        # 启动后台清理线程
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """启动后台清理线程"""
        def cleanup_worker():
            while True:
                time.sleep(300)  # 每5分钟清理一次
                try:
                    self.cleanup_expired()
                except:
                    pass
        
        thread = threading.Thread(target=cleanup_worker, daemon=True)
        thread.start()
    
    def _generate_cache_key(self, file_path: str) -> str:
        """生成缓存键"""
        # 使用文件路径和修改时间的哈希作为键
        try:
            stat = os.stat(file_path)
            key_data = f"{file_path}:{stat.st_mtime}:{stat.st_size}"
        except:
            key_data = file_path
        
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()
    
    def cache_file_content(self, file_path: str, content: Any, 
                          cache_strategy: str = 'hybrid', ttl_seconds: int = 3600) -> bool:
        """缓存文件内容"""
        # 生成缓存键
        cache_key = self._generate_cache_key(file_path)
        
        if cache_strategy == 'memory':
            return self.memory_cache.set(cache_key, content, ttl_seconds)
        elif cache_strategy == 'disk':
            return self.disk_cache.set(cache_key, content, ttl_seconds)
        else:  # hybrid
            # 先存内存，再存磁盘
            memory_success = self.memory_cache.set(cache_key, content, ttl_seconds)
            disk_success = self.disk_cache.set(cache_key, content, ttl_seconds)
            return memory_success and disk_success
    
    def get_cached_content(self, file_path: str, cache_strategy: str = 'auto') -> Optional[Any]:
        """获取缓存的文件内容"""
        cache_key = self._generate_cache_key(file_path)
        
        if cache_strategy == 'memory':
            return self.memory_cache.get(cache_key)
        elif cache_strategy == 'disk':
            return self.disk_cache.get(cache_key)
        else:  # auto 或 hybrid
            # 先查内存，再查磁盘
            content = self.memory_cache.get(cache_key)
            if content is not None:
                return content
            
            content = self.disk_cache.get(cache_key)
            if content is not None:
                # 如果从磁盘找到，也放入内存缓存
                self.memory_cache.set(cache_key, content, ttl_seconds=3600)
                return content
            
            return None
    
    def invalidate_cache(self, file_path: str = None, cache_strategy: str = 'all') -> Dict[str, int]:
        """使缓存失效"""
        result = {'memory_deleted': 0, 'disk_deleted': 0}
        
        if file_path:
            cache_key = self._generate_cache_key(file_path)
            
            if cache_strategy in ['all', 'memory']:
                if self.memory_cache.delete(cache_key):
                    result['memory_deleted'] = 1
            
            if cache_strategy in ['all', 'disk']:
                if self.disk_cache.delete(cache_key):
                    result['disk_deleted'] = 1
        else:
            # 清除所有缓存
            if cache_strategy in ['all', 'memory']:
                self.memory_cache.clear()
                result['memory_deleted'] = len(self.memory_cache.cache)
            
            if cache_strategy in ['all', 'disk']:
                count_before = self.disk_cache.get_stats()['item_count']
                self.disk_cache.clear()
                result['disk_deleted'] = count_before
        
        return result
    
    def get_cache_stats(self, cache_strategy: str = 'all') -> Dict[str, Any]:
        """获取缓存统计信息"""
        stats = {}
        
        if cache_strategy in ['all', 'memory']:
            stats['memory'] = self.memory_cache.get_stats()
        
        if cache_strategy in ['all', 'disk']:
            stats['disk'] = self.disk_cache.get_stats()
        
        if cache_strategy == 'all':
            # 计算总体命中率
            memory_stats = stats.get('memory', {})
            disk_stats = stats.get('disk', {})
            
            total_hits = memory_stats.get('hits', 0)
            total_misses = memory_stats.get('misses', 0)
            
            if total_hits + total_misses > 0:
                overall_hit_rate = total_hits / (total_hits + total_misses)
                stats['overall'] = {
                    'hit_rate': round(overall_hit_rate * 100, 2),
                    'total_hits': total_hits,
                    'total_misses': total_misses,
                    'total_requests': total_hits + total_misses
                }
        
        return stats
    
    def configure_cache(self, max_memory_size_mb: int = 100, max_disk_size_mb: int = 1000,
                       default_ttl_seconds: int = 3600, eviction_policy: str = 'lru') -> Dict[str, Any]:
        """配置缓存参数"""
        # 更新内存缓存配置
        self.memory_cache.max_size_bytes = max_memory_size_mb * 1024 * 1024
        self.memory_cache.eviction_policy = eviction_policy.lower()
        
        # 更新磁盘缓存配置
        self.disk_cache.max_size_bytes = max_disk_size_mb * 1024 * 1024
        
        return {
            'max_memory_size_mb': max_memory_size_mb,
            'max_disk_size_mb': max_disk_size_mb,
            'default_ttl_seconds': default_ttl_seconds,
            'eviction_policy': eviction_policy,
            'message': '缓存配置已更新'
        }
    
    def cleanup_expired(self) -> Dict[str, int]:
        """清理过期缓存项"""
        memory_expired = self.memory_cache.cleanup_expired()
        disk_expired = self.disk_cache.cleanup_expired()
        
        return {
            'memory_expired': memory_expired,
            'disk_expired': disk_expired,
            'total_expired': memory_expired + disk_expired
        }


# 全局缓存管理器实例
cache_manager = HybridCacheManager()