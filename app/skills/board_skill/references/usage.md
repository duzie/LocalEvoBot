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
- run_role_agent
- run_role_agents_parallel

## Examples
- 创建公告板并录入角色与任务
- 运行角色 Agent 回写任务结果
- 并发运行多个角色加速任务产出
- 并发执行时按依赖与状态筛选任务
- 依赖门禁支持 all/any/none 策略
- dep_policy 为空时默认 all
