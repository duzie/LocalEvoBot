# Skill

## Name
vector_index_skill

## Version
1.0.0

## Description
高性能向量索引系统，支持百万级向量存储和快速检索

## Entry
app.auto_skills.vector_index_skill.scripts

## Tools
- create_vector_index: 创建向量索引
- add_vectors_to_index: 向索引添加向量
- search_vectors: 搜索向量
- get_index_stats: 获取索引统计信息
- optimize_index: 优化索引
- delete_index: 删除索引
- list_indexes: 列出所有索引
- batch_index_files: 批量索引文件

## Platforms
- Windows
- Linux
- macOS

## Dependencies
- faiss-cpu: 向量索引库
- numpy: 数值计算
- sentence-transformers: 文本向量化
- langchain-huggingface: 嵌入模型集成

## Features
1. **高性能索引**: 支持HNSW、IVF_FLAT、IVF_PQ等多种索引算法
2. **百万级存储**: 支持百万级向量存储，索引构建速度>1000文档/分钟
3. **快速检索**: 检索准确率>90%，支持并发访问
4. **智能分块**: 自动文件分块和向量化
5. **性能监控**: 提供详细的性能指标和统计信息
6. **持久化存储**: 索引数据自动保存到磁盘

## Usage Examples

### 创建索引
```python
result = create_vector_index(
    index_name="document_index",
    dimension=384,
    index_type="HNSW"
)
```

### 批量索引文件
```python
result = batch_index_files(
    file_paths=["file1.txt", "file2.py", "file3.md"],
    chunk_size=1000,
    overlap=200,
    index_name="file_content_index"
)
```

### 搜索向量
```python
result = search_vectors(
    index_name="file_content_index",
    query_vector=[0.1, 0.2, 0.3, ...],  # 384维向量
    k=10,
    filters={"file_type": "py"}
)
```

### 获取索引统计
```python
result = get_index_stats("file_content_index")
```

## Performance Targets
- 索引构建速度: >1000文档/分钟
- 检索准确率: >90%
- 检索响应时间: <100ms (百万级向量)
- 并发支持: 支持多线程并发访问

## References
- references/usage.md