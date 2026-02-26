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
