# Usage

## Scope
公告板与多角色任务流转。

## Tools
- create_board
- get_board
- add_board_role
- add_board_task
- update_board_task
- append_board_task_output
- list_board_tasks
- create_board_tasks_from_spec
- create_spec_and_tasks
- approve_spec
- add_board_workflow
- list_board_workflows
- start_board_workflow
- stop_board_workflow
- process_board_workflows
- send_board_message
- list_board_messages
- mark_board_messages_read
- ack_board_message
- process_board_message_timeouts
- cleanup_board_messages
- get_board_message_health
- check_and_notify_board_health
- run_role_agent
- run_role_agents_parallel

## Examples
- 创建公告板并录入角色与任务
- 从精简 Spec 生成任务条目
- 由 Agent 自动生成 Spec 并派生任务
- **自动拆解复杂任务**：`create_spec_and_tasks(summary="开发登录功能")` 自动拆解成多个子任务
- 审批 Spec 后再触发执行
- 运行角色 Agent 回写任务结果
- 并发运行多个角色加速任务产出
- 并发执行时按依赖与状态筛选任务
- 发送消息给指定角色或任务
- 拉取未读消息并标记已读
- 处理超时消息并重试或转入死信
- 定期清理过期消息与死信
- 查询消息队列健康状态
- 死信过多时自动告警
- 创建与启动工作流并自动推进
- 任务默认按 task_id 生成锁文件（current_tasks/）
- 使用 lock_paths 自定义锁目标（文件/目录/任务）
- 依赖门禁支持 all/any/none 策略
- dep_policy 为空时默认 all



## 自动任务拆解示例

### 简单用法（自动拆解）
```python
# 无需提供 p0_features，自动 LLM 拆解
create_spec_and_tasks.invoke({
    "summary": "开发一个用户登录功能，包含前端页面、后端 API 和数据库设计"
})
```

### 自动拆解 + 自动执行
```python
# 拆解后立即并行执行
create_spec_and_tasks.invoke({
    "summary": "开发一个用户登录功能",
    "auto_start": True,  # 拆解后立即执行
    "max_workers": 3     # 最多 3 个任务并行
})
```

### 向后兼容（手动提供 p0_features）
```python
# 如果手动提供 p0_features，直接使用（不自动拆解）
create_spec_and_tasks.invoke({
    "summary": "开发一个用户登录功能",
    "p0_features": [
        {
            "title": "需求分析",
            "owner": "产品分析师",
            "acceptance": "完成 PRD 文档",
            "deps": []
        },
        {
            "title": "代码实现",
            "owner": "开发工程师",
            "acceptance": "完成核心功能开发",
            "deps": [1]
        }
    ]
})
```

### 拆解后的典型输出
输入：`"开发一个用户登录功能"`

LLM 自动拆解成 5 个子任务：
```json
[
    {"title": "需求分析与 PRD 文档", "owner": "产品分析师", "deps": []},
    {"title": "数据库设计", "owner": "开发工程师", "deps": [1]},
    {"title": "后端登录 API 开发", "owner": "开发工程师", "deps": [2]},
    {"title": "前端登录页面开发", "owner": "开发工程师", "deps": [2]},
    {"title": "测试用例编写与执行", "owner": "测试工程师", "deps": [3, 4]}
]
```

### 支持的 8 种角色
LLM 会根据任务内容自动分配最合适的角色：
1. **产品分析师** - 需求分析、PRD 文档
2. **开发工程师** - 代码实现、架构设计
3. **测试工程师** - 测试用例、质量验证
4. **数据分析师** - 数据分析、报表可视化
5. **运维工程师** - 部署、CI/CD、监控
6. **技术文档工程师** - 文档编写
7. **UI/UX 设计师** - 界面设计、交互设计
8. **执行工程师** - 通用任务（兜底）
