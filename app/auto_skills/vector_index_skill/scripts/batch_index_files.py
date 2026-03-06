"""
批量索引文件工具
"""

from langchain_core.tools import tool
from typing import List, Dict, Optional
import os
import time
from .vector_index_manager import _get_manager

# 尝试导入嵌入模型
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    _EMBEDDINGS_AVAILABLE = True
except ImportError:
    _EMBEDDINGS_AVAILABLE = False

@tool
def batch_index_files(file_paths: List[str], chunk_size: int = 1000, 
                      overlap: int = 200, index_name: str = "file_content_index"):
    """批量索引文件
    
    Args:
        file_paths: 文件路径列表
        chunk_size: 分块大小（字符数），默认1000
        overlap: 重叠大小（字符数），默认200
        index_name: 索引名称，默认"file_content_index"
    
    Returns:
        包含批量索引结果的字典
    """
    try:
        manager = _get_manager()
        
        # 验证参数
        if not file_paths or not isinstance(file_paths, list):
            return {
                "success": False,
                "error": "file_paths必须是非空列表"
            }
        
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            return {
                "success": False,
                "error": "chunk_size必须是正整数"
            }
        
        if not isinstance(overlap, int) or overlap < 0:
            return {
                "success": False,
                "error": "overlap必须是非负整数"
            }
        
        if overlap >= chunk_size:
            return {
                "success": False,
                "error": "overlap必须小于chunk_size"
            }
        
        if not index_name or not isinstance(index_name, str):
            return {
                "success": False,
                "error": "index_name必须是有效的字符串"
            }
        
        # 检查嵌入模型是否可用
        if not _EMBEDDINGS_AVAILABLE:
            return {
                "success": False,
                "error": "嵌入模型不可用，请安装 langchain-huggingface"
            }
        
        # 验证文件路径
        valid_files = []
        invalid_files = []
        
        for file_path in file_paths:
            if not isinstance(file_path, str):
                invalid_files.append((file_path, "不是字符串"))
                continue
            
            if not os.path.exists(file_path):
                invalid_files.append((file_path, "文件不存在"))
                continue
            
            if not os.path.isfile(file_path):
                invalid_files.append((file_path, "不是文件"))
                continue
            
            # 检查文件大小（限制为100MB）
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:  # 100MB
                invalid_files.append((file_path, f"文件过大 ({file_size/1024/1024:.1f}MB)"))
                continue
            
            valid_files.append(file_path)
        
        if not valid_files:
            return {
                "success": False,
                "error": "没有有效的文件可处理",
                "invalid_files": invalid_files
            }
        
        # 创建索引（如果不存在）
        # 使用 all-MiniLM-L6-v2 模型的维度是384
        index_dimension = 384
        
        # 检查索引是否存在
        existing_stats = manager.get_stats(index_name)
        if existing_stats is None:
            # 创建新索引
            success = manager.create_index(index_name, index_dimension, "HNSW")
            if not success:
                return {
                    "success": False,
                    "error": f"创建索引 '{index_name}' 失败"
                }
        
        # 初始化嵌入模型
        try:
            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"初始化嵌入模型失败: {str(e)}"
            }
        
        # 批量处理文件
        start_time = time.time()
        total_chunks = 0
        total_vectors = 0
        processed_files = []
        failed_files = []
        
        for file_path in valid_files:
            try:
                file_start_time = time.time()
                
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 分块处理
                chunks = []
                current_pos = 0
                content_length = len(content)
                
                while current_pos < content_length:
                    chunk_end = min(current_pos + chunk_size, content_length)
                    chunk = content[current_pos:chunk_end]
                    
                    # 尝试在句子边界处截断
                    if chunk_end < content_length:
                        # 查找最近的句子结束符
                        sentence_endings = ['. ', '。', '! ', '！', '? ', '？', '\n\n']
                        for ending in sentence_endings:
                            pos = chunk.rfind(ending)
                            if pos > chunk_size * 0.5:  # 至少保留一半内容
                                chunk = chunk[:pos + len(ending)]
                                chunk_end = current_pos + len(chunk)
                                break
                    
                    chunks.append(chunk)
                    current_pos = chunk_end - overlap
                    
                    # 防止无限循环
                    if current_pos <= chunk_end - chunk_size:
                        current_pos = chunk_end
                
                # 生成向量
                if chunks:
                    vectors = embeddings.embed_documents(chunks)
                    
                    # 准备元数据
                    file_metadata = {
                        "file_path": file_path,
                        "file_name": os.path.basename(file_path),
                        "file_size": os.path.getsize(file_path),
                        "file_extension": os.path.splitext(file_path)[1],
                        "chunk_count": len(chunks),
                        "processed_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    metadata_list = []
                    for i, chunk in enumerate(chunks):
                        chunk_metadata = file_metadata.copy()
                        chunk_metadata.update({
                            "chunk_index": i,
                            "chunk_size": len(chunk),
                            "chunk_preview": chunk[:100] + "..." if len(chunk) > 100 else chunk
                        })
                        metadata_list.append(chunk_metadata)
                    
                    # 添加到索引
                    success = manager.add_vectors(index_name, vectors, metadata=metadata_list)
                    
                    if success:
                        file_processing_time = time.time() - file_start_time
                        processed_files.append({
                            "file_path": file_path,
                            "chunks_processed": len(chunks),
                            "vectors_added": len(vectors),
                            "processing_time_ms": round(file_processing_time * 1000, 2),
                            "chunks_per_second": round(len(chunks) / file_processing_time, 2) if file_processing_time > 0 else 0
                        })
                        total_chunks += len(chunks)
                        total_vectors += len(vectors)
                    else:
                        failed_files.append((file_path, "添加向量到索引失败"))
                
                else:
                    failed_files.append((file_path, "文件内容为空或分块失败"))
            
            except Exception as e:
                failed_files.append((file_path, f"处理失败: {str(e)}"))
        
        # 计算总体统计
        total_time = time.time() - start_time
        overall_stats = manager.get_stats(index_name)
        
        return {
            "success": True,
            "message": f"批量索引完成，处理了 {len(processed_files)} 个文件",
            "index_name": index_name,
            "total_files": len(file_paths),
            "valid_files": len(valid_files),
            "processed_files": len(processed_files),
            "failed_files": len(failed_files),
            "total_chunks": total_chunks,
            "total_vectors": total_vectors,
            "total_time_ms": round(total_time * 1000, 2),
            "chunks_per_second": round(total_chunks / total_time, 2) if total_time > 0 else 0,
            "vectors_per_second": round(total_vectors / total_time, 2) if total_time > 0 else 0,
            "processed_files_details": processed_files,
            "failed_files_details": failed_files,
            "index_stats_after": overall_stats,
            "performance_metrics": {
                "chunk_size": chunk_size,
                "overlap": overlap,
                "avg_chunks_per_file": round(total_chunks / len(processed_files), 2) if processed_files else 0,
                "avg_processing_time_per_file_ms": round((total_time * 1000) / len(processed_files), 2) if processed_files else 0
            }
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"批量索引文件时发生错误: {str(e)}"
        }