# Skill

## Name
board_skill

## Version
1.0.0

## Description
多角色公告板与角色 Agent 调度。

## Entry
app.skills.board_skill.scripts

## Tools
- create_board: 创建公告板
- get_board: 获取公告板
- add_board_role: 新增角色
- add_board_task: 新增任务
- update_board_task: 更新任务
- append_board_task_output: 追加任务产物
- list_board_tasks: 任务筛选
- create_board_tasks_from_spec: Spec 生成任务
- create_spec_and_tasks: 自动生成 Spec 与任务（p0_features 为空时自动 LLM 拆解任务）
- approve_spec: 审批 Spec 并可选执行
- add_board_workflow: 创建工作流
- list_board_workflows: 查询工作流
- start_board_workflow: 启动工作流
- stop_board_workflow: 暂停工作流
- process_board_workflows: 推进工作流
- send_board_message: 发送消息
- list_board_messages: 查询消息
- mark_board_messages_read: 标记消息已读
- ack_board_message: 确认消息已处理
- process_board_message_timeouts: 处理超时消息
- cleanup_board_messages: 清理消息
- get_board_message_health: 消息健康指标
- check_and_notify_board_health: 健康检查告警
- run_role_agent: 运行角色 Agent
- run_role_agents_parallel: 并发运行角色 Agent

## Platforms
- Windows

## References
- references/usage.md
