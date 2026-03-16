# SQL Server 技能使用指南

## 会话管理功能（推荐使用）

会话管理是推荐的使用方式，可以避免重复连接数据库，提高性能。

### 会话管理工具

#### `start_session`
- **用途**: 开始一个新的数据库会话，建立连接并保持开启状态
- **参数**:
  - `server`: 服务器地址（可选，默认使用配置）
  - `database`: 数据库名称（可选，默认使用配置）
  - `username`: 用户名（可选，默认使用配置）
  - `password`: 密码（可选，默认使用配置）
- **返回值**: 包含会话ID和连接信息的字典

**示例**:
```python
# 开始会话
result = start_session()
session_id = result['session_id']
print(f"会话已建立: {session_id}")
```

#### `execute_in_session`
- **用途**: 在指定会话中执行SQL查询
- **参数**:
  - `session_id`: 会话ID（由start_session返回）
  - `sql`: SQL查询语句
  - `params`: 查询参数（可选）
- **返回值**: 包含查询结果和统计信息的字典

**示例**:
```python
# 在会话中执行查询
result = execute_in_session(
    session_id=session_id,
    sql="SELECT * FROM Sysstoreinfo WHERE uid = ?",
    params={"uid": 114200}
)

# 执行多个查询
result1 = execute_in_session(session_id=session_id, sql="SELECT COUNT(*) FROM Sysstoreinfo")
result2 = execute_in_session(session_id=session_id, sql="SELECT * FROM Sysstoreinfo WHERE uid = ?", params={"uid": 114200})
```

#### `end_session`
- **用途**: 结束指定的数据库会话，关闭连接
- **参数**:
  - `session_id`: 会话ID（由start_session返回）
- **返回值**: 包含会话结束信息的字典

**示例**:
```python
# 结束会话
result = end_session(session_id=session_id)
print(f"会话已关闭，执行了 {result['session_stats']['query_count']} 次查询")
```

#### `list_sessions`
- **用途**: 列出所有活跃的数据库会话
- **返回值**: 包含所有活跃会话信息的字典

**示例**:
```python
# 查看所有活跃会话
result = list_sessions()
for session in result['active_sessions']:
    print(f"会话 {session['session_id']}: 执行了 {session['query_count']} 次查询")
```

#### `close_all_sessions`
- **用途**: 关闭所有活跃的数据库会话
- **返回值**: 包含关闭操作结果的字典

**示例**:
```python
# 关闭所有会话
result = close_all_sessions()
print(f"已关闭 {result['closed_count']} 个会话")
```

### 会话管理使用流程

```python
# 1. 开始会话
session_result = start_session()
session_id = session_result['session_id']

# 2. 在会话中执行多个查询
try:
    # 查询1
    result1 = execute_in_session(
        session_id=session_id,
        sql="SELECT * FROM Sysstoreinfo WHERE uid = ?",
        params={"uid": 114200}
    )
    
    # 查询2
    result2 = execute_in_session(
        session_id=session_id,
        sql="SELECT * FROM SysGroupUser WHERE storeid = ?",
        params={"storeid": 114200}
    )
    
    # 查询3
    result3 = execute_in_session(
        session_id=session_id,
        sql="SELECT COUNT(*) as total FROM Sysstoreinfo"
    )
    
finally:
    # 3. 结束会话
    end_session(session_id=session_id)
```

### 会话管理优势

1. **性能提升**: 避免重复连接数据库的开销
2. **简单易用**: Agent只需要管理会话的开始和结束
3. **自动跟踪**: 自动记录查询次数和会话时长
4. **状态监控**: 可以随时查看活跃会话状态

## 分页查询功能

为了防止大量数据查询导致的内存问题，我们新增了分页查询功能。

### 分页查询工具

#### `paginated_sql_query`
- **用途**: 执行分页SQL查询，防止大量数据导致的内存问题
- **参数**:
  - `sql`: SQL查询语句（不包含ORDER BY和OFFSET/FETCH子句）
  - `page`: 页码，从1开始
  - `page_size`: 每页大小，默认50条记录
  - `params`: 查询参数（可选）
- **返回值**: 包含分页查询结果和统计信息的字典

**示例**:
```python
# 查询前100条门店信息，每页20条，获取第一页
result = paginated_sql_query(
    sql="SELECT * FROM Sysstoreinfo",
    page=1,
    page_size=20
)

# 获取第二页
result = paginated_sql_query(
    sql="SELECT * FROM Sysstoreinfo",
    page=2,
    page_size=20
)
```

#### `paginated_sql_query_with_order`
- **用途**: 执行分页SQL查询，支持自定义排序
- **参数**:
  - `sql`: SQL查询语句（不包含ORDER BY和OFFSET/FETCH子句）
  - `order_by`: 排序列，如 'id ASC' 或 'name DESC'
  - `page`: 页码，从1开始
  - `page_size`: 每页大小，默认50条记录
  - `params`: 查询参数（可选）
- **返回值**: 包含分页查询结果和统计信息的字典

**示例**:
```python
# 按门店名称降序排列，每页10条，获取第一页
result = paginated_sql_query_with_order(
    sql="SELECT * FROM Sysstoreinfo",
    order_by="StoreName DESC",
    page=1,
    page_size=10
)
```

### 分页查询返回值说明

- `success`: 布尔值，表示查询是否成功
- `message`: 操作结果消息
- `results`: 当前页的查询结果列表
- `pagination_info`: 分页信息对象
  - `current_page`: 当前页码
  - `page_size`: 每页大小
  - `total_count`: 总记录数
  - `total_pages`: 总页数
  - `has_next`: 是否有下一页
  - `has_prev`: 是否有上一页

### 注意事项

1. 分页查询只适用于SELECT语句
2. 不要在提供的SQL语句中包含ORDER BY、OFFSET、FETCH子句，这些将由分页功能自动处理
3. 对于大量数据的查询，请始终使用分页查询功能
4. 合理设置page_size以平衡性能和内存使用

## 原有功能

原有的SQL执行功能依然可用：
- `execute_sql_query`: 基础SQL查询功能
- `execute_batch_sql`: 批量执行SQL
- `execute_transaction_sql`: 事务执行功能
- `execute_sql_query_enhanced`: 增强版查询功能（支持连接复用）

## 工具选择指南

- **推荐使用会话管理**: start_session → execute_in_session → end_session（适合多次查询）
- 普通查询: execute_sql_query（适合单次查询）
- 需要连接复用的连续查询: execute_sql_query_enhanced（reuse_connection=True）
- 大数据量查询: 使用分页查询工具