=== 数据库操作安全规范 ===

1) 会话管理（推荐）：
   - 使用 start_session 建立数据库会话，连接会保持开启状态
   - 使用 execute_in_session 在会话中执行多个查询，无需重复连接
   - 使用 list_sessions 查看当前活跃的会话状态
   - 使用 end_session 关闭指定会话，或使用 close_all_sessions 关闭所有会话
   - 会话管理会自动跟踪查询次数和会话时长，便于监控

2) 连接管理（传统方式）：
   - 使用 configure_sqlserver 或 enhanced_configure_sqlserver 配置连接池参数，避免连接泄露
   - 操作完成后确保连接正确释放
   - 对于连续操作，可使用 execute_sql_query_enhanced 设置 reuse_connection=True 来提高性能

3) SQL安全：
   - 使用参数化查询防止SQL注入
   - 敏感操作(DDL/DML)前先进行语法检查(test_sql_syntax)

4) 事务处理：
   - 批量操作时使用 execute_batch_sql 或 execute_transaction_sql 确保原子性
   - 重要数据变更前先备份

5) 性能监控：
   - 复杂查询前使用 analyze_sql_performance 检查执行计划
   - 避免N+1查询问题

6) 敏感信息：
   - 数据库凭证使用环境变量或加密存储，避免硬编码在代码中

7) 事务支持：
   - 对于需要原子性的多语句操作，使用 execute_transaction_sql 工具

8) 大数据查询：
   - 对于可能返回大量数据的查询，使用 paginated_sql_query 或 paginated_sql_query_fixed 工具进行分页查询，避免内存溢出

9) 分页查询：
   - 使用 paginated_sql_query、paginated_sql_query_fixed 或 paginated_sql_query_with_order_fixed 进行分页数据检索，控制每页数据量
   - 原版分页查询可能存在连接管理问题，推荐使用修复版

10) 工具选择指南：
    - **推荐使用会话管理**：start_session → execute_in_session → end_session（适合多次查询）
    - 普通查询：execute_sql_query（适合单次查询）
    - 需要连接复用的连续查询：execute_sql_query_enhanced（reuse_connection=True）
    - 大数据量查询：使用修复后的分页查询工具

11) 会话生命周期管理：
    - Agent应在开始数据库操作时调用 start_session
    - 在会话中执行所有需要的查询
    - 完成所有操作后调用 end_session 关闭会话
    - 如果不确定会话状态，可以调用 list_sessions 查看活跃会话
    - 如果需要清理，可以调用 close_all_sessions 关闭所有会话