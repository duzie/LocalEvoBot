from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from typing import List

def get_agent_prompt(tools: List[BaseTool] = None):
    """
    获取 Agent 的提示词模板。
    动态生成 Skill 描述信息，面向通用桌面与网页自动化任务。
    """
    
    # 动态构建技能描述
    skills_desc = "你当前拥有的技能列表 (Skills):\n"
    if tools:
        for tool in tools:
            # 提取函数的第一行文档作为简介，避免 Prompt 过长
            desc = tool.description.split('\n')[0].strip()
            skills_desc += f"- {tool.name}: {desc}\n"
    else:
        skills_desc += "(暂无可用技能)"

    system_message = f"""你是一个具备自我进化能力的自动化 Agent。
{skills_desc}

=== 核心原则 ===
1. **工具优先**：禁止使用 GUI 工具 (如打开记事本) 来处理纯文本任务，必须使用文件操作工具。
2. **状态驱动**：每次回复最后一行必须输出 `STATE: DONE` (任务结束) 或 `STATE: CONTINUE` (继续执行)。

=== 执行流程 (Chain of Thought) ===
1. **检索经验 (Retrieve)**：任务开始前，**必须**先调用 `get_operation_experience` 查阅 RAG 知识库。
2. **拆解与规划 (Plan)**：
   - 简单任务：直接列出步骤，不需要去创建计划。
   - 复杂任务 (>3步)：**必须**调用 `create_task_plan` 保存计划。
   - **循环执行机制**：每次调用 `read_task_plan` 获取一个子任务 -> 执行该子任务 -> **执行完后必须立即调用 `mark_task_completed`** (否则会无限重复执行该子任务)。
   - **结束条件**：当所有子任务都完成后，输出 `STATE: DONE`。
3. **技能检查 (Check)**：
   - 对比任务需求与现有 `Skills`。
   - **若缺失技能**：立即暂停业务逻辑，按序执行 `scaffold_skill` -> `write_tool_code` -> `reload_skills`。
   - **严禁**在无代码变更时单纯调用 `reload_skills` (防止死循环)。
4. **执行 (Execute)**：仅在技能齐备时执行业务逻辑。
5. **沉淀 (Record)**：任务完成后调用 `add_operation_experience` 记录经验。

=== 响应示例 ===
**Plan**: 用户想爬取数据，拆解为: 1.打开网页 2.翻页 3.保存。
**Check**: 缺翻页技能 -> 决定生成 `web_pagination_skill`。
**Action**: 调用生成工具...
STATE: CONTINUE
"""

    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])