from langchain_core.tools import tool


@tool
def get_task_planning_rules() -> str:
    """
    返回任务拆解与任务计划执行规则，用于约束复杂任务的计划与推进方式。
    """
    text = """
## 任务评估 (Evaluate)
- 简单任务：直接执行，不需要自主判断用户意图，做完输出 STATE: DONE。
- 复杂任务（>3步）：调用 create_task_plan 创建计划。
- 需求容易跑偏或验收标准不清晰：先使用精简 Spec（.specify/spec-template.md）明确目标与验收，再进入 Plan。
- 多角色任务：调用 create_board 初始化公告板；需要并发时使用 run_role_agents_parallel；依赖策略用 dep_policy。
- 问候/无意义语句/追问：回复或反问后直接 STATE: DONE。
- 开始执行前先调用 inspect_environment 检查工具与环境。

## 拆解与规划 (Plan - 仅复杂任务)
- 循环执行：每次调用 read_task_plan 取一个待办步骤 → 执行 → 立即调用 mark_task_completed（否则会重复同一步）。
- 用户输入“继续/continue”：先调用 read_task_plan，从未完成步骤继续，并在完成后标记。
- 结束条件：当所有步骤都完成后输出 STATE: DONE。
""".strip()
    return text
