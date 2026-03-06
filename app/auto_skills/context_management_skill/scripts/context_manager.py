"""
分层上下文管理器
实现4层上下文架构：
1. 原始层 - 完整文件内容，存储在磁盘缓存中
2. 摘要层 - 文件关键信息摘要，存储在内存缓存中
3. 语义层 - 向量化语义表示，存储在向量数据库中
4. 元数据层 - 文件元数据和索引信息
"""

import os
import json
import hashlib
import sqlite3
import pickle
import time
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import threading
from pathlib import Path

from app.skills.common import SkillException, ok_payload, error_payload, emit_event


@dataclass
class FileMetadata:
    """文件元数据"""
    file_path: str
    file_size: int
    modified_time: float
    file_hash: str
    file_type: str
    line_count: int
    char_count: int
    created_at: float
    last_accessed: float


@dataclass
class ContextSummary:
    """上下文摘要"""
    file_path: str
    summary_hash: str
    summary_type: str  # "code", "document", "data", "mixed"
    key_classes: List[str]
    key_functions: List[str]
    key_variables: List[str]
    imports: List[str]
    main_logic: str
    dependencies: List[str]
    complexity_score: float
    summary_text: str
    compressed_size: int
    original_size: int
    compression_ratio: float
    accuracy_score: float
    created_at: float


@dataclass
class SemanticChunk:
    """语义分块"""
    chunk_id: str
    file_path: str
    chunk_index: int
    chunk_text: str
    chunk_hash: str
    embedding: Optional[List[float]]
    semantic_type: str  # "class", "function", "import", "logic", "comment"
    metadata: Dict[str, Any]
    created_at: float


class ContextLayerManager:
    """分层上下文管理器"""
    
    def __init__(self, data_dir: Optional[str] = None):
        """初始化上下文管理器
        
        Args:
            data_dir: 数据目录，默认为app/data/context_cache
        """
        if data_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            self.data_dir = os.path.join(project_root, "app", "data", "context_cache")
        else:
            self.data_dir = data_dir
            
        # 创建目录
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "raw"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "summary"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "semantic"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "metadata"), exist_ok=True)
        
        # 配置参数
        self.config = {
            "raw_layer_size_mb": 1000,
            "summary_layer_size_mb": 100,
            "semantic_layer_size_mb": 500,
            "compression_ratio": 0.5,
            "min_accuracy": 0.9,
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "max_summary_length": 500,
            "cache_ttl": 3600 * 24 * 7,  # 7天
        }
        
        # 内存缓存
        self.memory_cache = {}
        self.cache_lock = threading.RLock()
        
        # 初始化数据库
        self._init_databases()
        
    def _init_databases(self):
        """初始化数据库"""
        # 元数据数据库
        metadata_db_path = os.path.join(self.data_dir, "metadata", "metadata.db")
        self.metadata_conn = sqlite3.connect(metadata_db_path, check_same_thread=False)
        self.metadata_conn.row_factory = sqlite3.Row
        
        # 创建表
        with self.metadata_conn:
            self.metadata_conn.execute("""
                CREATE TABLE IF NOT EXISTS file_metadata (
                    file_path TEXT PRIMARY KEY,
                    file_size INTEGER,
                    modified_time REAL,
                    file_hash TEXT,
                    file_type TEXT,
                    line_count INTEGER,
                    char_count INTEGER,
                    created_at REAL,
                    last_accessed REAL,
                    INDEX idx_file_hash (file_hash),
                    INDEX idx_file_type (file_type),
                    INDEX idx_last_accessed (last_accessed)
                )
            """)
            
            self.metadata_conn.execute("""
                CREATE TABLE IF NOT EXISTS context_summary (
                    file_path TEXT PRIMARY KEY,
                    summary_hash TEXT,
                    summary_type TEXT,
                    key_classes TEXT,
                    key_functions TEXT,
                    key_variables TEXT,
                    imports TEXT,
                    main_logic TEXT,
                    dependencies TEXT,
                    complexity_score REAL,
                    summary_text TEXT,
                    compressed_size INTEGER,
                    original_size INTEGER,
                    compression_ratio REAL,
                    accuracy_score REAL,
                    created_at REAL,
                    FOREIGN KEY (file_path) REFERENCES file_metadata(file_path),
                    INDEX idx_summary_hash (summary_hash),
                    INDEX idx_summary_type (summary_type),
                    INDEX idx_created_at (created_at)
                )
            """)
            
            self.metadata_conn.execute("""
                CREATE TABLE IF NOT EXISTS access_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT,
                    layer TEXT,
                    access_time REAL,
                    operation TEXT,
                    success INTEGER,
                    FOREIGN KEY (file_path) REFERENCES file_metadata(file_path),
                    INDEX idx_file_path (file_path),
                    INDEX idx_access_time (access_time)
                )
            """)
        
        # 语义数据库
        semantic_db_path = os.path.join(self.data_dir, "semantic", "semantic.db")
        self.semantic_conn = sqlite3.connect(semantic_db_path, check_same_thread=False)
        self.semantic_conn.row_factory = sqlite3.Row
        
        with self.semantic_conn:
            self.semantic_conn.execute("""
                CREATE TABLE IF NOT EXISTS semantic_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    file_path TEXT,
                    chunk_index INTEGER,
                    chunk_text TEXT,
                    chunk_hash TEXT,
                    embedding BLOB,
                    semantic_type TEXT,
                    metadata TEXT,
                    created_at REAL,
                    FOREIGN KEY (file_path) REFERENCES file_metadata(file_path),
                    INDEX idx_file_path (file_path),
                    INDEX idx_semantic_type (semantic_type),
                    INDEX idx_created_at (created_at)
                )
            """)


            
    def _get_file_hash(self, file_path: str) -> str:
        """计算文件哈希值"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
            
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _analyze_file_type(self, file_path: str) -> str:
        """分析文件类型"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.py']:
            return 'python'
        elif ext in ['.cs']:
            return 'csharp'
        elif ext in ['.js', '.jsx', '.ts', '.tsx']:
            return 'javascript'
        elif ext in ['.java']:
            return 'java'
        elif ext in ['.cpp', '.c', '.h', '.hpp']:
            return 'cpp'
        elif ext in ['.html', '.htm']:
            return 'html'
        elif ext in ['.css', '.scss', '.less']:
            return 'css'
        elif ext in ['.md', '.markdown']:
            return 'markdown'
        elif ext in ['.json']:
            return 'json'
        elif ext in ['.xml']:
            return 'xml'
        elif ext in ['.yaml', '.yml']:
            return 'yaml'
        elif ext in ['.sql']:
            return 'sql'
        else:
            return 'text'
    
    def _extract_code_summary(self, file_path: str, content: str, file_type: str) -> ContextSummary:
        """提取代码摘要"""
        # 基础统计
        lines = content.split('\n')
        line_count = len(lines)
        char_count = len(content)
        
        # 提取关键信息
        key_classes = []
        key_functions = []
        key_variables = []
        imports = []
        dependencies = []
        
        if file_type == 'python':
            # 提取Python代码信息
            class_pattern = r'^class\s+(\w+)'
            function_pattern = r'^def\s+(\w+)'
            import_pattern = r'^(?:from\s+(\w+)|import\s+(\w+))'
            
            for line in lines:
                line = line.strip()
                if class_match := re.match(class_pattern, line):
                    key_classes.append(class_match.group(1))
                elif func_match := re.match(function_pattern, line):
                    key_functions.append(func_match.group(1))
                elif import_match := re.match(import_pattern, line):
                    imports.append(import_match.group(1) or import_match.group(2))
                    
        elif file_type == 'csharp':
            # 提取C#代码信息
            class_pattern = r'^\s*(?:public|private|protected|internal)?\s*class\s+(\w+)'
            method_pattern = r'^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?\w+\s+(\w+)\s*\('
            using_pattern = r'^using\s+([\w\.]+)'
            
            for line in lines:
                line = line.strip()
                if class_match := re.match(class_pattern, line):
                    key_classes.append(class_match.group(1))
                elif method_match := re.match(method_pattern, line):
                    key_functions.append(method_match.group(1))
                elif using_match := re.match(using_pattern, line):
                    imports.append(using_match.group(1))
        
        # 计算复杂度分数
        complexity_score = min(1.0, (len(key_classes) * 0.1 + len(key_functions) * 0.05 + line_count / 1000))
        
        # 生成摘要文本
        summary_parts = []
        if key_classes:
            summary_parts.append(f"包含 {len(key_classes)} 个类: {', '.join(key_classes[:5])}")
        if key_functions:
            summary_parts.append(f"包含 {len(key_functions)} 个函数: {', '.join(key_functions[:5])}")
        if imports:
            summary_parts.append(f"导入 {len(imports)} 个模块: {', '.join(imports[:5])}")
        
        summary_text = f"{file_type.upper()} 文件，{line_count} 行，{char_count} 字符。"
        if summary_parts:
            summary_text += " " + "；".join(summary_parts)
        
        # 计算压缩信息
        compressed_size = len(summary_text.encode('utf-8'))
        original_size = char_count
        compression_ratio = compressed_size / original_size if original_size > 0 else 0
        
        # 准确率估算（基于摘要覆盖率）
        coverage_score = min(1.0, (len(key_classes) + len(key_functions)) / max(1, line_count / 10))
        accuracy_score = 0.7 + 0.3 * coverage_score  # 基础准确率 + 覆盖率加成
        
        return ContextSummary(
            file_path=file_path,
            summary_hash=hashlib.sha256(summary_text.encode()).hexdigest(),
            summary_type="code",
            key_classes=key_classes,
            key_functions=key_functions,
            key_variables=key_variables,
            imports=imports,
            main_logic="",
            dependencies=dependencies,
            complexity_score=complexity_score,
            summary_text=summary_text,
            compressed_size=compressed_size,
            original_size=original_size,
            compression_ratio=compression_ratio,
            accuracy_score=accuracy_score,
            created_at=time.time()
        )
    
    def _extract_document_summary(self, file_path: str, content: str, file_type: str) -> ContextSummary:
        """提取文档摘要"""
        lines = content.split('\n')
        line_count = len(lines)
        char_count = len(content)
        
        # 提取标题和关键段落
        headings = []
        if file_type == 'markdown':
            heading_pattern = r'^(#{1,6})\s+(.+)$'
            for line in lines:
                if match := re.match(heading_pattern, line):
                    level = len(match.group(1))
                    text = match.group(2).strip()
                    headings.append(f"{'#' * level} {text}")
        
        # 生成摘要
        summary_text = f"{file_type.upper()} 文档，{line_count} 行，{char_count} 字符。"
        if headings:
            summary_text += f" 包含 {len(headings)} 个标题: {'; '.join(headings[:3])}"
        
        # 计算压缩信息
        compressed_size = len(summary_text.encode('utf-8'))
        original_size = char_count
        compression_ratio = compressed_size / original_size if original_size > 0 else 0
        
        # 准确率估算
        accuracy_score = 0.8  # 文档摘要基础准确率
        
        return ContextSummary(
            file_path=file_path,
            summary_hash=hashlib.sha256(summary_text.encode()).hexdigest(),
            summary_type="document",
            key_classes=[],
            key_functions=[],
            key_variables=[],
            imports=[],
            main_logic="",
            dependencies=[],
            complexity_score=0.1,
            summary_text=summary_text,
            compressed_size=compressed_size,
            original_size=original_size,
            compression_ratio=compression_ratio,
            accuracy_score=accuracy_score,
            created_at=time.time()
        )


    
    def _chunk_content(self, content: str, file_path: str, file_type: str) -> List[SemanticChunk]:
        """将内容分块"""
        chunks = []
        lines = content.split('\n')
        chunk_size = self.config['chunk_size']
        overlap = self.config['chunk_overlap']
        
        current_chunk = []
        current_length = 0
        chunk_index = 0
        
        for i, line in enumerate(lines):
            line_length = len(line) + 1  # +1 for newline
            
            if current_length + line_length > chunk_size and current_chunk:
                # 完成当前块
                chunk_text = '\n'.join(current_chunk)
                chunk_hash = hashlib.sha256(chunk_text.encode()).hexdigest()
                chunk_id = f"{hashlib.sha256(file_path.encode()).hexdigest()[:16]}_{chunk_index}"
                
                # 确定语义类型
                semantic_type = "text"
                if file_type == 'python':
                    if any(keyword in chunk_text for keyword in ['class ', 'def ']):
                        semantic_type = "code_structure"
                    elif 'import ' in chunk_text or 'from ' in chunk_text:
                        semantic_type = "import"
                
                chunks.append(SemanticChunk(
                    chunk_id=chunk_id,
                    file_path=file_path,
                    chunk_index=chunk_index,
                    chunk_text=chunk_text,
                    chunk_hash=chunk_hash,
                    embedding=None,
                    semantic_type=semantic_type,
                    metadata={
                        "line_start": i - len(current_chunk),
                        "line_end": i - 1,
                        "char_count": len(chunk_text),
                        "file_type": file_type
                    },
                    created_at=time.time()
                ))
                
                # 保留重叠部分
                overlap_lines = current_chunk[-overlap//20:] if overlap > 0 else []
                current_chunk = overlap_lines + [line]
                current_length = sum(len(l) + 1 for l in current_chunk)
                chunk_index += 1
            else:
                current_chunk.append(line)
                current_length += line_length
        
        # 处理最后一块
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunk_hash = hashlib.sha256(chunk_text.encode()).hexdigest()
            chunk_id = f"{hashlib.sha256(file_path.encode()).hexdigest()[:16]}_{chunk_index}"
            
            chunks.append(SemanticChunk(
                chunk_id=chunk_id,
                file_path=file_path,
                chunk_index=chunk_index,
                chunk_text=chunk_text,
                chunk_hash=chunk_hash,
                embedding=None,
                semantic_type="text",
                metadata={
                    "line_start": len(lines) - len(current_chunk),
                    "line_end": len(lines) - 1,
                    "char_count": len(chunk_text),
                    "file_type": file_type
                },
                created_at=time.time()
            ))
        
        return chunks
    
    def analyze_file(self, file_path: str, max_raw_size_kb: int = 100, generate_summary: bool = True) -> Dict[str, Any]:
        """分析文件并生成分层上下文
        
        Args:
            file_path: 文件路径
            max_raw_size_kb: 最大原始内容大小（KB）
            generate_summary: 是否生成摘要
            
        Returns:
            包含分析结果的字典
        """
        try:
            emit_event("context_manager", "analyze_file_start", file_path=file_path)
            
            if not os.path.exists(file_path):
                return error_payload("file_not_found", f"文件不存在: {file_path}")
            
            # 获取文件信息
            stat = os.stat(file_path)
            file_hash = self._get_file_hash(file_path)
            file_type = self._analyze_file_type(file_path)
            
            # 读取文件内容
            max_size = max_raw_size_kb * 1024
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(max_size)
            
            # 基础统计
            lines = content.split('\n')
            line_count = len(lines)
            char_count = len(content)
            
            # 创建文件元数据
            metadata = FileMetadata(
                file_path=file_path,
                file_size=stat.st_size,
                modified_time=stat.st_mtime,
                file_hash=file_hash,
                file_type=file_type,
                line_count=line_count,
                char_count=char_count,
                created_at=time.time(),
                last_accessed=time.time()
            )
            
            # 保存到元数据层
            self._save_metadata(metadata)
            
            # 保存到原始层
            raw_cache_path = self._get_raw_cache_path(file_hash)
            with open(raw_cache_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 生成摘要层
            summary = None
            if generate_summary:
                if file_type in ['python', 'csharp', 'javascript', 'java', 'cpp']:
                    summary = self._extract_code_summary(file_path, content, file_type)
                elif file_type in ['markdown', 'html', 'text']:
                    summary = self._extract_document_summary(file_path, content, file_type)
                else:
                    # 通用摘要
                    summary = ContextSummary(
                        file_path=file_path,
                        summary_hash=hashlib.sha256(content[:500].encode()).hexdigest(),
                        summary_type="data",
                        key_classes=[],
                        key_functions=[],
                        key_variables=[],
                        imports=[],
                        main_logic="",
                        dependencies=[],
                        complexity_score=0.2,
                        summary_text=f"{file_type.upper()} 数据文件，{line_count} 行，{char_count} 字符。",
                        compressed_size=len(content[:500]),
                        original_size=char_count,
                        compression_ratio=min(0.5, 500 / char_count),
                        accuracy_score=0.7,
                        created_at=time.time()
                    )
                
                # 保存摘要层
                self._save_summary(summary)
                
                # 缓存到内存
                with self.cache_lock:
                    cache_key = f"summary:{file_path}"
                    self.memory_cache[cache_key] = {
                        "data": summary,
                        "timestamp": time.time()
                    }
            
            # 生成语义层
            chunks = self._chunk_content(content, file_path, file_type)
            for chunk in chunks:
                self._save_semantic_chunk(chunk)
            
            # 记录访问日志
            self._log_access(file_path, "analyze", True)
            
            # 返回结果
            result = {
                "file_path": file_path,
                "file_hash": file_hash,
                "file_type": file_type,
                "file_size": stat.st_size,
                "line_count": line_count,
                "char_count": char_count,
                "metadata": asdict(metadata),
                "summary": asdict(summary) if summary else None,
                "chunk_count": len(chunks),
                "compression_ratio": summary.compression_ratio if summary else 0,
                "accuracy_score": summary.accuracy_score if summary else 0,
                "layers_generated": ["raw", "metadata"] + (["summary", "semantic"] if summary else ["semantic"])
            }
            
            emit_event("context_manager", "analyze_file_complete", 
                      file_path=file_path, file_type=file_type, chunk_count=len(chunks))
            
            return ok_payload("文件分析完成", **result)
            
        except Exception as e:
            emit_event("context_manager", "analyze_file_error", 
                      file_path=file_path, error=str(e))
            return error_payload("analyze_error", f"分析文件时出错: {str(e)}")
    
    def _get_raw_cache_path(self, file_hash: str) -> str:
        """获取原始层缓存路径"""
        # 使用哈希前2位作为目录名
        dir_name = file_hash[:2]
        dir_path = os.path.join(self.data_dir, "raw", dir_name)
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, f"{file_hash}.cache")
    
    def _save_metadata(self, metadata: FileMetadata):
        """保存元数据"""
        with self.metadata_conn:
            self.metadata_conn.execute("""
                INSERT OR REPLACE INTO file_metadata 
                (file_path, file_size, modified_time, file_hash, file_type, 
                 line_count, char_count, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.file_path, metadata.file_size, metadata.modified_time,
                metadata.file_hash, metadata.file_type, metadata.line_count,
                metadata.char_count, metadata.created_at, metadata.last_accessed
            ))
    
    def _save_summary(self, summary: ContextSummary):
        """保存摘要"""
        with self.metadata_conn:
            self.metadata_conn.execute("""
                INSERT OR REPLACE INTO context_summary 
                (file_path, summary_hash, summary_type, key_classes, key_functions,
                 key_variables, imports, main_logic, dependencies, complexity_score,
                 summary_text, compressed_size, original_size, compression_ratio,
                 accuracy_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                summary.file_path, summary.summary_hash, summary.summary_type,
                json.dumps(summary.key_classes), json.dumps(summary.key_functions),
                json.dumps(summary.key_variables), json.dumps(summary.imports),
                summary.main_logic, json.dumps(summary.dependencies),
                summary.complexity_score, summary.summary_text,
                summary.compressed_size, summary.original_size,
                summary.compression_ratio, summary.accuracy_score,
                summary.created_at
            ))
    
    def _save_semantic_chunk(self, chunk: SemanticChunk):
        """保存语义分块"""
        with self.semantic_conn:
            self.semantic_conn.execute("""
                INSERT OR REPLACE INTO semantic_chunks 
                (chunk_id, file_path, chunk_index, chunk_text, chunk_hash,
                 embedding, semantic_type, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk.chunk_id, chunk.file_path, chunk.chunk_index,
                chunk.chunk_text, chunk.chunk_hash,
                pickle.dumps(chunk.embedding) if chunk.embedding else None,
                chunk.semantic_type, json.dumps(chunk.metadata),
                chunk.created_at
            ))
    
    def _log_access(self, file_path: str, operation: str, success: bool):
        """记录访问日志"""
        with self.metadata_conn:
            self.metadata_conn.execute("""
                INSERT INTO access_log (file_path, layer, access_time, operation, success)
                VALUES (?, ?, ?, ?, ?)
            """, (file_path, "all", time.time(), operation, 1 if success else 0))


    
    def get_context_layer(self, file_path: str, layer: str = "summary", 
                         query: str = "", max_results: int = 5) -> Dict[str, Any]:
        """获取指定层的上下文内容
        
        Args:
            file_path: 文件路径
            layer: 上下文层：raw/summary/semantic/metadata
            query: 语义查询（仅对semantic层有效）
            max_results: 最大返回结果数
            
        Returns:
            包含上下文内容的字典
        """
        try:
            emit_event("context_manager", "get_context_start", 
                      file_path=file_path, layer=layer, query=query)
            
            if not os.path.exists(file_path):
                return error_payload("file_not_found", f"文件不存在: {file_path}")
            
            file_hash = self._get_file_hash(file_path)
            
            if layer == "raw":
                # 获取原始层内容
                raw_cache_path = self._get_raw_cache_path(file_hash)
                if os.path.exists(raw_cache_path):
                    with open(raw_cache_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    result = {
                        "layer": "raw",
                        "file_path": file_path,
                        "content": content,
                        "size": len(content)
                    }
                else:
                    # 从原始文件读取
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    result = {
                        "layer": "raw",
                        "file_path": file_path,
                        "content": content,
                        "size": len(content),
                        "source": "original_file"
                    }
                    
            elif layer == "summary":
                # 获取摘要层内容
                cache_key = f"summary:{file_path}"
                with self.cache_lock:
                    if cache_key in self.memory_cache:
                        cache_data = self.memory_cache[cache_key]
                        if time.time() - cache_data["timestamp"] < self.config["cache_ttl"]:
                            summary = cache_data["data"]
                        else:
                            # 缓存过期，从数据库读取
                            summary = self._load_summary_from_db(file_path)
                            if summary:
                                self.memory_cache[cache_key] = {
                                    "data": summary,
                                    "timestamp": time.time()
                                }
                    else:
                        summary = self._load_summary_from_db(file_path)
                        if summary:
                            self.memory_cache[cache_key] = {
                                "data": summary,
                                "timestamp": time.time()
                            }
                
                if summary:
                    result = {
                        "layer": "summary",
                        "file_path": file_path,
                        "summary": asdict(summary),
                        "compression_ratio": summary.compression_ratio,
                        "accuracy_score": summary.accuracy_score,
                        "size_reduction": f"{(1 - summary.compression_ratio) * 100:.1f}%"
                    }
                else:
                    # 如果没有摘要，生成一个
                    analysis_result = self.analyze_file(file_path, generate_summary=True)
                    if analysis_result.get("ok"):
                        summary_data = analysis_result.get("summary")
                        result = {
                            "layer": "summary",
                            "file_path": file_path,
                            "summary": summary_data,
                            "compression_ratio": summary_data.get("compression_ratio", 0),
                            "accuracy_score": summary_data.get("accuracy_score", 0),
                            "size_reduction": f"{(1 - summary_data.get('compression_ratio', 0)) * 100:.1f}%",
                            "generated": True
                        }
                    else:
                        return error_payload("summary_not_found", "无法生成文件摘要")
                        
            elif layer == "semantic":
                # 获取语义层内容
                chunks = self._load_semantic_chunks(file_path, query, max_results)
                result = {
                    "layer": "semantic",
                    "file_path": file_path,
                    "chunks": [asdict(chunk) for chunk in chunks],
                    "chunk_count": len(chunks),
                    "query": query if query else "all"
                }
                
            elif layer == "metadata":
                # 获取元数据层内容
                metadata = self._load_metadata(file_path)
                if metadata:
                    result = {
                        "layer": "metadata",
                        "file_path": file_path,
                        "metadata": asdict(metadata)
                    }
                else:
                    return error_payload("metadata_not_found", "文件元数据不存在")
                    
            else:
                return error_payload("invalid_layer", f"无效的上下文层: {layer}")
            
            # 更新最后访问时间
            self._update_last_accessed(file_path)
            
            # 记录访问日志
            self._log_access(file_path, f"get_{layer}", True)
            
            emit_event("context_manager", "get_context_complete", 
                      file_path=file_path, layer=layer, success=True)
            
            return ok_payload(f"获取{layer}层上下文成功", **result)
            
        except Exception as e:
            emit_event("context_manager", "get_context_error", 
                      file_path=file_path, layer=layer, error=str(e))
            return error_payload("get_context_error", f"获取上下文时出错: {str(e)}")
    
    def _load_summary_from_db(self, file_path: str) -> Optional[ContextSummary]:
        """从数据库加载摘要"""
        cursor = self.metadata_conn.execute(
            "SELECT * FROM context_summary WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        
        if row:
            return ContextSummary(
                file_path=row['file_path'],
                summary_hash=row['summary_hash'],
                summary_type=row['summary_type'],
                key_classes=json.loads(row['key_classes']),
                key_functions=json.loads(row['key_functions']),
                key_variables=json.loads(row['key_variables']),
                imports=json.loads(row['imports']),
                main_logic=row['main_logic'],
                dependencies=json.loads(row['dependencies']),
                complexity_score=row['complexity_score'],
                summary_text=row['summary_text'],
                compressed_size=row['compressed_size'],
                original_size=row['original_size'],
                compression_ratio=row['compression_ratio'],
                accuracy_score=row['accuracy_score'],
                created_at=row['created_at']
            )
        return None
    
    def _load_semantic_chunks(self, file_path: str, query: str = "", max_results: int = 5) -> List[SemanticChunk]:
        """加载语义分块"""
        chunks = []
        
        if query:
            # 简单文本搜索（未来可以集成向量搜索）
            cursor = self.semantic_conn.execute("""
                SELECT * FROM semantic_chunks 
                WHERE file_path = ? AND chunk_text LIKE ?
                LIMIT ?
            """, (file_path, f"%{query}%", max_results))
        else:
            cursor = self.semantic_conn.execute("""
                SELECT * FROM semantic_chunks 
                WHERE file_path = ? 
                ORDER BY chunk_index
                LIMIT ?
            """, (file_path, max_results))
        
        for row in cursor:
            embedding = pickle.loads(row['embedding']) if row['embedding'] else None
            chunks.append(SemanticChunk(
                chunk_id=row['chunk_id'],
                file_path=row['file_path'],
                chunk_index=row['chunk_index'],
                chunk_text=row['chunk_text'],
                chunk_hash=row['chunk_hash'],
                embedding=embedding,
                semantic_type=row['semantic_type'],
                metadata=json.loads(row['metadata']),
                created_at=row['created_at']
            ))
        
        return chunks
    
    def _load_metadata(self, file_path: str) -> Optional[FileMetadata]:
        """加载元数据"""
        cursor = self.metadata_conn.execute(
            "SELECT * FROM file_metadata WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        
        if row:
            return FileMetadata(
                file_path=row['file_path'],
                file_size=row['file_size'],
                modified_time=row['modified_time'],
                file_hash=row['file_hash'],
                file_type=row['file_type'],
                line_count=row['line_count'],
                char_count=row['char_count'],
                created_at=row['created_at'],
                last_accessed=row['last_accessed']
            )
        return None
    
    def _update_last_accessed(self, file_path: str):
        """更新最后访问时间"""
        with self.metadata_conn:
            self.metadata_conn.execute("""
                UPDATE file_metadata SET last_accessed = ? WHERE file_path = ?
            """, (time.time(), file_path))


    
    def get_context_stats(self, file_path: str = "", layer: str = "all") -> Dict[str, Any]:
        """获取上下文统计信息
        
        Args:
            file_path: 文件路径（空表示所有文件）
            layer: 上下文层：all/raw/summary/semantic/metadata
            
        Returns:
            包含统计信息的字典
        """
        try:
            emit_event("context_manager", "get_stats_start", 
                      file_path=file_path, layer=layer)
            
            stats = {
                "timestamp": time.time(),
                "layer": layer,
                "file_specific": file_path != ""
            }
            
            if file_path:
                # 单个文件统计
                if not os.path.exists(file_path):
                    return error_payload("file_not_found", f"文件不存在: {file_path}")
                
                file_hash = self._get_file_hash(file_path)
                metadata = self._load_metadata(file_path)
                summary = self._load_summary_from_db(file_path)
                
                if metadata:
                    stats["file_info"] = {
                        "path": metadata.file_path,
                        "size": metadata.file_size,
                        "type": metadata.file_type,
                        "lines": metadata.line_count,
                        "chars": metadata.char_count,
                        "last_accessed": datetime.fromtimestamp(metadata.last_accessed).isoformat()
                    }
                
                if summary:
                    stats["summary_info"] = {
                        "compression_ratio": summary.compression_ratio,
                        "accuracy_score": summary.accuracy_score,
                        "size_reduction": f"{(1 - summary.compression_ratio) * 100:.1f}%",
                        "key_classes_count": len(summary.key_classes),
                        "key_functions_count": len(summary.key_functions)
                    }
                
                # 获取语义分块统计
                cursor = self.semantic_conn.execute("""
                    SELECT COUNT(*) as count, 
                           AVG(LENGTH(chunk_text)) as avg_size,
                           MIN(LENGTH(chunk_text)) as min_size,
                           MAX(LENGTH(chunk_text)) as max_size
                    FROM semantic_chunks WHERE file_path = ?
                """, (file_path,))
                chunk_stats = cursor.fetchone()
                
                if chunk_stats and chunk_stats['count'] > 0:
                    stats["semantic_info"] = {
                        "chunk_count": chunk_stats['count'],
                        "avg_chunk_size": chunk_stats['avg_size'],
                        "min_chunk_size": chunk_stats['min_size'],
                        "max_chunk_size": chunk_stats['max_size']
                    }
                
                # 获取访问日志统计
                cursor = self.metadata_conn.execute("""
                    SELECT COUNT(*) as total_access,
                           MIN(access_time) as first_access,
                           MAX(access_time) as last_access
                    FROM access_log WHERE file_path = ?
                """, (file_path,))
                access_stats = cursor.fetchone()
                
                if access_stats:
                    stats["access_info"] = {
                        "total_access": access_stats['total_access'],
                        "first_access": datetime.fromtimestamp(access_stats['first_access']).isoformat() if access_stats['first_access'] else None,
                        "last_access": datetime.fromtimestamp(access_stats['last_access']).isoformat() if access_stats['last_access'] else None
                    }
                    
            else:
                # 全局统计
                # 文件统计
                cursor = self.metadata_conn.execute("""
                    SELECT COUNT(*) as file_count,
                           SUM(file_size) as total_size,
                           AVG(file_size) as avg_size,
                           COUNT(DISTINCT file_type) as type_count
                    FROM file_metadata
                """)
                file_stats = cursor.fetchone()
                
                if file_stats:
                    stats["global_file_stats"] = {
                        "file_count": file_stats['file_count'],
                        "total_size": file_stats['total_size'],
                        "avg_size": file_stats['avg_size'],
                        "type_count": file_stats['type_count']
                    }
                
                # 摘要统计
                cursor = self.metadata_conn.execute("""
                    SELECT COUNT(*) as summary_count,
                           AVG(compression_ratio) as avg_compression,
                           AVG(accuracy_score) as avg_accuracy,
                           MIN(compression_ratio) as min_compression,
                           MAX(compression_ratio) as max_compression
                    FROM context_summary
                """)
                summary_stats = cursor.fetchone()
                
                if summary_stats and summary_stats['summary_count'] > 0:
                    stats["global_summary_stats"] = {
                        "summary_count": summary_stats['summary_count'],
                        "avg_compression": summary_stats['avg_compression'],
                        "avg_accuracy": summary_stats['avg_accuracy'],
                        "min_compression": summary_stats['min_compression'],
                        "max_compression": summary_stats['max_compression'],
                        "avg_size_reduction": f"{(1 - summary_stats['avg_compression']) * 100:.1f}%"
                    }
                
                # 语义分块统计
                cursor = self.semantic_conn.execute("""
                    SELECT COUNT(*) as chunk_count,
                           COUNT(DISTINCT file_path) as file_count,
                           AVG(LENGTH(chunk_text)) as avg_chunk_size
                    FROM semantic_chunks
                """)
                semantic_stats = cursor.fetchone()
                
                if semantic_stats:
                    stats["global_semantic_stats"] = {
                        "chunk_count": semantic_stats['chunk_count'],
                        "file_count": semantic_stats['file_count'],
                        "avg_chunk_size": semantic_stats['avg_chunk_size']
                    }
                
                # 内存缓存统计
                with self.cache_lock:
                    cache_count = len(self.memory_cache)
                    cache_size = sum(len(str(v).encode()) for v in self.memory_cache.values())
                    
                    stats["memory_cache_stats"] = {
                        "cache_count": cache_count,
                        "cache_size_bytes": cache_size,
                        "cache_size_mb": cache_size / (1024 * 1024)
                    }
            
            emit_event("context_manager", "get_stats_complete", 
                      file_path=file_path, stats_count=len(stats))
            
            return ok_payload("获取统计信息成功", **stats)
            
        except Exception as e:
            emit_event("context_manager", "get_stats_error", 
                      file_path=file_path, error=str(e))
            return error_payload("stats_error", f"获取统计信息时出错: {str(e)}")
    
    def compress_context(self, file_path: str, target_ratio: float = 0.5,
                        preserve_structure: bool = True, preserve_keywords: bool = True) -> Dict[str, Any]:
        """压缩上下文，减少大小
        
        Args:
            file_path: 文件路径
            target_ratio: 目标压缩比率（0-1）
            preserve_structure: 是否保留代码结构
            preserve_keywords: 是否保留关键词
            
        Returns:
            包含压缩结果的字典
        """
        try:
            emit_event("context_manager", "compress_start", 
                      file_path=file_path, target_ratio=target_ratio)
            
            if not os.path.exists(file_path):
                return error_payload("file_not_found", f"文件不存在: {file_path}")
            
            # 获取当前摘要
            summary = self._load_summary_from_db(file_path)
            if not summary:
                # 如果没有摘要，先生成
                analysis_result = self.analyze_file(file_path, generate_summary=True)
                if not analysis_result.get("ok"):
                    return error_payload("analyze_failed", "无法分析文件")
                summary = self._load_summary_from_db(file_path)
            
            current_ratio = summary.compression_ratio
            current_accuracy = summary.accuracy_score
            
            if current_ratio <= target_ratio:
                # 已经达到或超过目标压缩率
                return ok_payload("已达到目标压缩率", 
                                 current_ratio=current_ratio,
                                 target_ratio=target_ratio,
                                 accuracy_score=current_accuracy,
                                 size_reduction=f"{(1 - current_ratio) * 100:.1f}%")
            
            # 应用压缩策略
            compressed_summary = self._apply_compression_strategy(
                summary, target_ratio, preserve_structure, preserve_keywords)
            
            # 保存压缩后的摘要
            self._save_summary(compressed_summary)
            
            # 更新内存缓存
            cache_key = f"summary:{file_path}"
            with self.cache_lock:
                self.memory_cache[cache_key] = {
                    "data": compressed_summary,
                    "timestamp": time.time()
                }
            
            result = {
                "file_path": file_path,
                "original_ratio": current_ratio,
                "compressed_ratio": compressed_summary.compression_ratio,
                "accuracy_score": compressed_summary.accuracy_score,
                "size_reduction": f"{(1 - compressed_summary.compression_ratio) * 100:.1f}%",
                "improvement": f"{(current_ratio - compressed_summary.compression_ratio) * 100:.1f}%",
                "summary_preview": compressed_summary.summary_text[:200] + "..." 
                if len(compressed_summary.summary_text) > 200 else compressed_summary.summary_text
            }
            
            emit_event("context_manager", "compress_complete", 
                      file_path=file_path, 
                      compression_ratio=compressed_summary.compression_ratio,
                      accuracy_score=compressed_summary.accuracy_score)
            
            return ok_payload("上下文压缩成功", **result)
            
        except Exception as e:
            emit_event("context_manager", "compress_error", 
                      file_path=file_path, error=str(e))
            return error_payload("compress_error", f"压缩上下文时出错: {str(e)}")
    
    def _apply_compression_strategy(self, summary: ContextSummary, target_ratio: float,
                                   preserve_structure: bool, preserve_keywords: bool) -> ContextSummary:
        """应用压缩策略"""
        # 简化摘要文本
        summary_text = summary.summary_text
        
        if preserve_structure:
            # 保留结构，但简化描述
            lines = summary_text.split('。')
            if len(lines) > 3:
                summary_text = '。'.join(lines[:3]) + '。'
        
        if preserve_keywords:
            # 确保关键词被保留
            keywords = summary.key_classes + summary.key_functions + summary.imports
            for keyword in keywords[:10]:  # 只保留前10个关键词
                if keyword not in summary_text:
                    summary_text += f" 关键词: {keyword}"
        
        # 计算新的压缩信息
        compressed_size = len(summary_text.encode('utf-8'))
        compression_ratio = compressed_size / summary.original_size if summary.original_size > 0 else 0
        
        # 调整准确率（压缩越多，准确率可能下降）
        accuracy_adjustment = max(0, 1 - (compression_ratio / target_ratio) * 0.2)
        accuracy_score = summary.accuracy_score * accuracy_adjustment
        
        # 确保达到目标压缩率
        if compression_ratio > target_ratio:
            # 进一步压缩
            max_length = int(len(summary_text) * target_ratio / compression_ratio)
            summary_text = summary_text[:max_length] + "..."
            compressed_size = len(summary_text.encode('utf-8'))
            compression_ratio = compressed_size / summary.original_size
        
        return ContextSummary(
            file_path=summary.file_path,
            summary_hash=hashlib.sha256(summary_text.encode()).hexdigest(),
            summary_type=summary.summary_type,
            key_classes=summary.key_classes,
            key_functions=summary.key_functions,
            key_variables=summary.key_variables,
            imports=summary.imports,
            main_logic=summary.main_logic,
            dependencies=summary.dependencies,
            complexity_score=summary.complexity_score,
            summary_text=summary_text,
            compressed_size=compressed_size,
            original_size=summary.original_size,
            compression_ratio=compression_ratio,
            accuracy_score=accuracy_score,
            created_at=time.time()
        )
    
    def invalidate_context_cache(self, file_path: str = "", layer: str = "all") -> Dict[str, Any]:
        """使上下文缓存失效
        
        Args:
            file_path: 文件路径（空表示所有文件）
            layer: 上下文层：all/raw/summary/semantic/metadata
            
        Returns:
            包含失效结果的字典
        """
        try:
            emit_event("context_manager", "invalidate_start", 
                      file_path=file_path, layer=layer)
            
            invalidated_count = 0
            
            if layer in ["all", "summary"]:
                # 清理内存缓存
                with self.cache_lock:
                    if file_path:
                        cache_key = f"summary:{file_path}"
                        if cache_key in self.memory_cache:
                            del self.memory_cache[cache_key]
                            invalidated_count += 1
                    else:
                        # 清理所有缓存
                        invalidated_count = len(self.memory_cache)
                        self.memory_cache.clear()
            
            if layer in ["all", "raw"] and file_path:
                # 清理原始层缓存
                file_hash = self._get_file_hash(file_path)
                raw_cache_path = self._get_raw_cache_path(file_hash)
                if os.path.exists(raw_cache_path):
                    os.remove(raw_cache_path)
                    invalidated_count += 1
            
            if layer in ["all", "semantic"] and file_path:
                # 清理语义层数据
                with self.semantic_conn:
                    self.semantic_conn.execute(
                        "DELETE FROM semantic_chunks WHERE file_path = ?", (file_path,))
                    invalidated_count += 1
            
            if layer in ["all", "metadata"] and file_path:
                # 清理元数据
                with self.metadata_conn:
                    self.metadata_conn.execute(
                        "DELETE FROM file_metadata WHERE file_path = ?", (file_path,))
                    self.metadata_conn.execute(
                        "DELETE FROM context_summary WHERE file_path = ?", (file_path,))
                    invalidated_count += 2
            
            result = {
                "file_path": file_path if file_path else "all",
                "layer": layer,
                "invalidated_count": invalidated_count,
                "timestamp": time.time()
            }
            
            emit_event("context_manager", "invalidate_complete", 
                      file_path=file_path, invalidated_count=invalidated_count)
            
            return ok_payload("缓存失效成功", **result)
            
        except Exception as e:
            emit_event("context_manager", "invalidate_error", 
                      file_path=file_path, error=str(e))
            return error_payload("invalidate_error", f"缓存失效时出错: {str(e)}")
    
    def optimize_context_layers(self, target_reduction: float = 0.5, 
                               min_accuracy: float = 0.9) -> Dict[str, Any]:
        """优化上下文层配置
        
        Args:
            target_reduction: 目标大小减少比率（0-1）
            min_accuracy: 最小准确率（0-1）
            
        Returns:
            包含优化结果的字典
        """
        try:
            emit_event("context_manager", "optimize_start", 
                      target_reduction=target_reduction, min_accuracy=min_accuracy)
            
            # 获取所有文件摘要
            cursor = self.metadata_conn.execute("""
                SELECT cs.*, fm.file_size 
                FROM context_summary cs
                JOIN file_metadata fm ON cs.file_path = fm.file_path
                WHERE cs.compression_ratio > ? OR cs.accuracy_score < ?
            """, (target_reduction, min_accuracy))
            
            optimized_files = []
            total_original_size = 0
            total_compressed_size = 0
            
            for row in cursor:
                summary = ContextSummary(
                    file_path=row['file_path'],
                    summary_hash=row['summary_hash'],
                    summary_type=row['summary_type'],
                    key_classes=json.loads(row['key_classes']),
                    key_functions=json.loads(row['key_functions']),
                    key_variables=json.loads(row['key_variables']),
                    imports=json.loads(row['imports']),
                    main_logic=row['main_logic'],
                    dependencies=json.loads(row['dependencies']),
                    complexity_score=row['complexity_score'],
                    summary_text=row['summary_text'],
                    compressed_size=row['compressed_size'],
                    original_size=row['original_size'],
                    compression_ratio=row['compression_ratio'],
                    accuracy_score=row['accuracy_score'],
                    created_at=row['created_at']
                )
                
                # 检查是否需要优化
                needs_optimization = (
                    summary.compression_ratio > target_reduction or 
                    summary.accuracy_score < min_accuracy
                )
                
                if needs_optimization:
                    # 应用优化
                    target_ratio = min(target_reduction, summary.compression_ratio * 0.8)
                    optimized_summary = self._apply_compression_strategy(
                        summary, target_ratio, True, True)
                    
                    # 保存优化后的摘要
                    self._save_summary(optimized_summary)
                    
                    optimized_files.append({
                        "file_path": summary.file_path,
                        "original_ratio": summary.compression_ratio,
                        "optimized_ratio": optimized_summary.compression_ratio,
                        "original_accuracy": summary.accuracy_score,
                        "optimized_accuracy": optimized_summary.accuracy_score,
                        "size_reduction": f"{(1 - optimized_summary.compression_ratio) * 100:.1f}%"
                    })
                    
                    total_original_size += summary.original_size
                    total_compressed_size += optimized_summary.compressed_size
            
            # 清理内存缓存
            with self.cache_lock:
                self.memory_cache.clear()
            
            result = {
                "optimized_files": optimized_files,
                "total_files_optimized": len(optimized_files),
                "total_original_size": total_original_size,
                "total_compressed_size": total_compressed_size,
                "overall_compression_ratio": total_compressed_size / total_original_size if total_original_size > 0 else 0,
                "overall_size_reduction":

 f"{(1 - (total_compressed_size / total_original_size)) * 100:.1f}%" if total_original_size > 0 else "0%",
                "target_reduction": target_reduction,
                "min_accuracy": min_accuracy,
                "timestamp": time.time()
            }
            
            emit_event("context_manager", "optimize_complete", 
                      optimized_count=len(optimized_files),
                      overall_compression=result["overall_compression_ratio"])
            
            return ok_payload("上下文层优化完成", **result)
            
        except Exception as e:
            emit_event("context_manager", "optimize_error", error=str(e))
            return error_payload("optimize_error", f"优化上下文层时出错: {str(e)}")
    
    def update_config(self, **kwargs):
        """更新配置参数"""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
                emit_event("context_manager", "config_updated", key=key, value=value)


# 全局上下文管理器实例
_context_manager = None

def get_context_manager() -> ContextLayerManager:
    """获取全局上下文管理器实例"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextLayerManager()
    return _context_manager