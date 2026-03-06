# 缓存技能使用指南

## 概述

智能文件上下文缓存管理系统提供高性能的混合缓存解决方案，支持内存缓存和磁盘缓存，具有智能淘汰策略和全面的监控功能。

## 核心特性

1. **混合缓存架构**: 内存缓存（快速访问） + 磁盘缓存（持久存储）
2. **智能淘汰策略**: 支持LRU、LFU、随机淘汰算法
3. **性能监控**: 实时监控命中率、响应时间、使用率等指标
4. **缓存失效**: 支持按文件或批量清理缓存
5. **可配置性**: 支持动态调整缓存参数

## 工具说明

### 1. cache_file_content - 缓存文件内容

缓存文件内容到指定策略的缓存中。

**参数:**
- `file_path`: 文件路径（必需）
- `content`: 文件内容（必需）
- `cache_strategy`: 缓存策略，可选值：`memory`（内存）、`disk`（磁盘）、`hybrid`（混合，默认）
- `ttl_seconds`: 缓存过期时间，默认3600秒（1小时）

**示例:**
```python
# 缓存文件到内存
cache_file_content(
    file_path="/path/to/file.txt",
    content="文件内容...",
    cache_strategy="memory",
    ttl_seconds=1800
)

# 缓存文件到磁盘
cache_file_content(
    file_path="/path/to/file.txt",
    content="文件内容...",
    cache_strategy="disk",
    ttl_seconds=7200
)

# 使用混合策略缓存
cache_file_content(
    file_path="/path/to/file.txt",
    content="文件内容...",
    cache_strategy="hybrid",
    ttl_seconds=3600
)
```

### 2. get_cached_content - 获取缓存内容

从缓存中获取文件内容。

**参数:**
- `file_path`: 文件路径（必需）
- `cache_strategy`: 缓存策略，可选值：`auto`（自动，默认）、`memory`、`disk`、`hybrid`

**示例:**
```python
# 自动从缓存获取（先内存后磁盘）
result = get_cached_content(
    file_path="/path/to/file.txt",
    cache_strategy="auto"
)

if result.get("cache_hit"):
    content = result.get("content")
    response_time = result.get("response_time_ms")
    print(f"缓存命中，响应时间: {response_time}ms")
else:
    print("缓存未命中，需要重新读取文件")
```

### 3. invalidate_cache - 使缓存失效

清理指定文件或所有缓存。

**参数:**
- `file_path`: 文件路径（可选，为空则清理所有缓存）
- `cache_strategy`: 缓存策略，可选值：`all`（全部，默认）、`memory`、`disk`、`hybrid`

**示例:**
```python
# 清理单个文件的缓存
invalidate_cache(
    file_path="/path/to/file.txt",
    cache_strategy="all"
)

# 清理所有内存缓存
invalidate_cache(
    file_path="",
    cache_strategy="memory"
)

# 清理所有缓存
invalidate_cache(
    file_path="",
    cache_strategy="all"
)
```

### 4. get_cache_stats - 获取缓存统计

获取缓存系统的详细统计信息。

**参数:**
- `cache_strategy`: 缓存策略，可选值：`all`（全部，默认）、`memory`、`disk`、`hybrid`

**示例:**
```python
# 获取完整统计信息
stats = get_cache_stats(cache_strategy="all")

# 分析统计信息
analysis = stats.get("analysis", {})
summary = analysis.get("summary", {})

print(f"总体命中率: {summary.get('overall_hit_rate', 'N/A')}")
print(f"性能状态: {summary.get('performance', 'N/A')}")
print(f"系统状态: {summary.get('status', 'N/A')}")

# 查看建议和警告
recommendations = analysis.get("recommendations", [])
warnings = analysis.get("warnings", [])

if recommendations:
    print("优化建议:")
    for rec in recommendations:
        print(f"  - {rec}")

if warnings:
    print("警告:")
    for warn in warnings:
        print(f"  - {warn}")
```

### 5. configure_cache - 配置缓存参数

动态配置缓存系统参数。

**参数:**
- `max_memory_size_mb`: 最大内存缓存大小（MB），默认100
- `max_disk_size_mb`: 最大磁盘缓存大小（MB），默认1000
- `default_ttl_seconds`: 默认缓存过期时间（秒），默认3600
- `eviction_policy`: 淘汰策略，可选值：`lru`（最近最少使用，默认）、`lfu`（最不经常使用）、`random`（随机）

**示例:**
```python
# 配置为高性能模式
configure_cache(
    max_memory_size_mb=500,
    max_disk_size_mb=5000,
    default_ttl_seconds=7200,
    eviction_policy="lru"
)

# 配置为节省内存模式
configure_cache(
    max_memory_size_mb=50,
    max_disk_size_mb=2000,
    default_ttl_seconds=1800,
    eviction_policy="lfu"
)
```

## 性能指标

### 验收标准
- **缓存命中率**: >70%
- **缓存响应时间**: <10ms（内存缓存）
- **磁盘缓存响应时间**: <50ms
- **混合缓存响应时间**: <30ms

### 监控指标
1. **命中率**: 缓存命中的比例
2. **响应时间**: 缓存访问的平均时间
3. **使用率**: 缓存空间的使用比例
4. **淘汰率**: 缓存项被淘汰的比例
5. **过期率**: 过期缓存项的比例

## 最佳实践

### 1. 缓存策略选择
- **热点数据**: 使用`memory`策略，快速访问
- **大文件**: 使用`disk`策略，节省内存
- **重要文件**: 使用`hybrid`策略，兼顾性能和持久性
- **临时数据**: 设置较短的TTL

### 2. 性能优化
- 根据访问模式选择合适的淘汰策略
- 监控命中率，调整缓存大小
- 定期清理过期缓存
- 使用合适的TTL设置

### 3. 内存管理
- 根据系统内存设置合理的缓存大小
- 监控内存使用率，避免内存溢出
- 对于大文件，优先使用磁盘缓存

### 4. 错误处理
- 检查缓存操作返回值
- 处理缓存未命中的情况
- 监控缓存错误率

## 集成示例

### 与文件读取集成
```python
def read_file_with_cache(file_path, use_cache=True):
    """带缓存的文件读取函数"""
    if use_cache:
        # 先尝试从缓存获取
        cached_result = get_cached_content(file_path=file_path)
        
        if cached_result.get("cache_hit"):
            print(f"缓存命中，响应时间: {cached_result.get('response_time_ms')}ms")
            return cached_result.get("content")
    
    # 缓存未命中，读取文件
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 缓存文件内容
    if use_cache:
        cache_file_content(
            file_path=file_path,
            content=content,
            cache_strategy="hybrid",
            ttl_seconds=3600
        )
    
    return content
```

### 批量文件处理
```python
def process_files_with_cache(file_paths):
    """批量处理文件，使用缓存优化"""
    results = []
    
    for file_path in file_paths:
        # 尝试从缓存获取
        cached_content = get_cached_content(file_path=file_path)
        
        if cached_content.get("cache_hit"):
            # 使用缓存内容
            content = cached_content.get("content")
            results.append({
                "file": file_path,
                "content": content,
                "from_cache": True,
                "response_time": cached_content.get("response_time_ms")
            })
        else:
            # 读取并处理文件
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 处理内容...
            processed_content = process_content(content)
            
            # 缓存处理结果
            cache_file_content(
                file_path=file_path,
                content=processed_content,
                cache_strategy="hybrid",
                ttl_seconds=7200
            )
            
            results.append({
                "file": file_path,
                "content": processed_content,
                "from_cache": False
            })
    
    return results
```

## 故障排除

### 常见问题

1. **缓存命中率低**
   - 检查缓存策略是否合适
   - 调整缓存大小
   - 检查TTL设置是否过短

2. **响应时间慢**
   - 检查磁盘缓存性能
   - 减少缓存项大小
   - 优化淘汰策略

3. **内存使用过高**
   - 减小内存缓存大小
   - 使用磁盘缓存替代
   - 清理过期缓存

4. **缓存不一致**
   - 检查文件修改时间
   - 及时使缓存失效
   - 使用版本控制

### 调试方法

1. **查看统计信息**
   ```python
   stats = get_cache_stats(cache_strategy="all")
   print(json.dumps(stats, indent=2, ensure_ascii=False))
   ```

2. **监控性能**
   ```python
   # 记录缓存操作时间
   import time
   
   start_time = time.time()
   result = get_cached_content(file_path="test.txt")
   elapsed = (time.time() - start_time) * 1000
   print(f"响应时间: {elapsed:.2f}ms")
   ```

3. **清理缓存测试**
   ```python
   # 清理后测试性能
   invalidate_cache(file_path="", cache_strategy="all")
   stats = get_cache_stats(cache_strategy="all")
   print(f"清理后缓存项数: {stats.get('memory', {}).get('item_count', 0)}")
   ```

## 版本历史

### v1.0.0 (2026-03-05)
- 初始版本发布
- 支持混合缓存架构
- 实现LRU/LFU淘汰策略
- 提供完整的监控功能
- 支持动态配置

## 技术支持

如有问题或建议，请联系：
- 项目文档: [智能文件上下文管理系统开发计划]
- 技术支持: 缓存管理模块开发工程师
- 问题反馈: 使用系统反馈功能