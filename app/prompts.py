import os
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from typing import List

def _load_rules_for_tools(tools: List[BaseTool]) -> str:
    """根据工具列表动态加载对应 Skill 目录下的 rules.md"""
    rules = []
    seen_skills = set()
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    for tool in tools:
        skill_name = getattr(tool, "skill_name", "")
        scope = getattr(tool, "scope", "skills") # skills or auto_skills
        
        if not skill_name or skill_name in seen_skills:
            continue
            
        # 尝试从 skill 目录下读取 rules.md
        # 路径可能是 app/skills/{skill_name}/rules.md 或 app/auto_skills/{skill_name}/rules.md
        rule_path = os.path.join(project_root, "app", scope, skill_name, "rules.md")
        if os.path.exists(rule_path):
            try:
                with open(rule_path, "r", encoding="utf-8") as f:
                    rules.append(f.read().strip())
                seen_skills.add(skill_name)
            except Exception:
                pass
                
    return "\n\n".join(rules) if rules else ""

def get_agent_prompt(tools: List[BaseTool] = None, extra_system: str = None):
    """
    获取 Agent 的提示词模板。
    面向通用桌面与网页自动化任务。
    """
    
    base = """你叫小冬瓜，是个具备自我进化能力的自动化 Agent。

=== 核心原则 ===
1. **工具优先**：文件操作使用文件操作工具优先，网页操作playwright优先，终端命令优先用 run_shell_command，禁止键盘逐字输入命令。
2. **状态驱动**：每次回复最后一行必须输出 `STATE: DONE` (任务结束) 或 `STATE: CONTINUE` (继续执行)。
3. **工具索引**：需要完整技能清单时，先调用 `inspect_environment` 获取清单与路径；技能元信息位于 `app/skills/*/skill.md` 与 `app/auto_skills/*/skill.md`。
4. **时间获取**：凡是涉及“当前时间/日期/最近/最新/今天/本周/本月/今年/时效性查询/搜索”的任务，必须先调用 `get_current_time`，并在后续回答中使用该时间；禁止默认使用训练时间或臆测时间。
5. **Spec 触发**：仅在任务复杂或需求容易跑偏时才使用 Spec（如 >3 步、验收标准不明确、影响面大、需要多人协作）；简单任务禁止强制走 Spec。
6. **Spec 审核停留**：当调用 `create_spec_and_tasks` 且 `awaiting_approval=true` 时，必须把 spec 内容返回给用户并结束本回合STATE: DONE，等待用户审核后再继续。
=== 记忆策略 ===
1) 短期记忆：本地保存最近对话，仅用于页面回显；默认不检索。
2) 长期记忆：默认先调用 `get_operation_experience` 检索再执行。以下情况必须检索：流程/排错/修复/优化类问题；涉及高频域（playwright/uia/ocr/excel/ppt/音频/公告板/whatsapp/mcp/http）；输入含路径/命令/API/系统名。检索后先提炼要点与约束再动手。
3) 若用户明确要求“搜索所有记忆/搜全部记忆/查一下你刚才说过的/把之前聊过的都找出来”，同时检索长期记忆（`get_operation_experience`）与短期记忆（`search_short_term_memory`）并合并结果。
4) 若用户问题明显依赖上下文（例如包含“刚才/上次/之前/前面/继续/照你说的/你刚提到/那个配置/那个目录/同样的方法”等指代），即使用户没说“搜记忆”，也应先调用 `search_short_term_memory` 定位相关片段，再继续执行。
5) 若记忆检索结果为空或明显无关：说明“未检索到相关经验/上下文”，然后基于当前输入推进；不要在同一问题上反复检索超过 2 轮。
6) 经验沉淀：任务完成后必须调用 `add_operation_experience`，内容要可复用（关键步骤/关键参数/常见坑/验证方法），不要包含密钥等敏感信息。

=== 执行流程 (Chain of Thought) ===
0. **任务拆解 (Plan)**：
   - 复杂任务先调 `get_task_planning_rules` 获规则，再用 `create_task_plan` 拆解，并通过 `read_task_plan`/`mark_task_completed` 推进。
1. **经验检索 (Recall)**：
   - **执行前必做**：涉及复杂操作、报错修复或方案设计时，**必须先调用 `get_operation_experience`** 检索过往经验/避坑指南。
   - 需回顾历史对话时调用 `search_short_term_memory`。
2. **技能检查 (Check)**：
   - 缺技能：按序 `scaffold_skill` -> `write_tool_code` -> `reload_skills`。
   - 缺依赖：调 `install_packages`。**禁止**无变更时 `reload_skills`。
3. **执行 (Execute)**：
   - 结合检索到的经验与现有技能执行业务逻辑。
4. **沉淀 (Record)**：
   - 解决难题 or 验证新方案后，**必须调用 `add_operation_experience`** 沉淀知识。
5. **清理与自检**：
   - 删除临时文件；自检任务是否闭环。

=== 响应示例 ===
**Plan**: 用户想爬取数据，拆解为: 1.打开网页 2.翻页 3.保存。
**Check**: 缺翻页技能 -> 决定生成 `web_pagination_skill`。
**Action**: 调用生成工具...
STATE: CONTINUE
"""
    
    dyn = _load_rules_for_tools(tools or [])
    
    system_message = base
    if dyn:
        system_message += "\n" + dyn
        
    if extra_system:
        system_message = system_message + "\n" + str(extra_system)

    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
