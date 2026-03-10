"""
Agent Prompt System - 提示词系统

从身份文件加载：SOUL.md → AGENTS.md → WORKFLOW.md → 技能规则
"""

import os
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from typing import List


def _load_file(path: str) -> str:
    """从项目根目录加载文件"""
    # 向上查找项目根目录（包含 SOUL.md 的目录）
    current = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for _ in range(3):  # 最多向上查找 3 层
        if os.path.exists(os.path.join(current, "SOUL.md")):
            break
        current = os.path.dirname(current)
    
    full_path = os.path.join(current, path)
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return f"⚠️ {path} not found"


def _load_identity_files() -> str:
    """加载身份定义文件"""
    sections = []
    
    # 按顺序加载：SOUL → AGENTS → WORKFLOW
    soul = _load_file("SOUL.md")
    if soul and not soul.startswith("⚠️"):
        sections.append(soul)
    
    agents = _load_file("AGENTS.md")
    if agents and not agents.startswith("⚠️"):
        sections.append(agents)
    
    workflow = _load_file("WORKFLOW.md")
    if workflow and not workflow.startswith("⚠️"):
        sections.append(workflow)
    
    return "\n\n---\n\n".join(sections)


def _load_rules_for_tools(tools: List[BaseTool]) -> str:
    """根据工具列表动态加载对应 Skill 目录下的 rules.md"""
    rules = []
    seen_skills = set()
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    for tool in tools:
        skill_name = getattr(tool, "skill_name", "")
        scope = getattr(tool, "scope", "skills")  # skills or auto_skills
        
        if not skill_name or skill_name in seen_skills:
            continue
            
        # 尝试从 skill 目录下读取规则
        # 1. 优先读取 rules.md
        # 2. 如果是 OpenClaw skill，读取 SKILL.md 正文
        rule_content = ""
        
        # 路径可能是 app/skills/{skill_name} 或 app/auto_skills/{skill_name} 或 app/openclaw_skills/{skill_name}
        # 注意：openclaw_skills 可能有多层结构，这里 registry.py 并没有传递具体的子目录路径
        # 但是 OpenClawTool 的 project_root 指向了具体的 skill 目录
        
        # 为了兼容性，我们先尝试标准的 rules.md
        skill_base_dir = os.path.join(project_root, "app", scope, skill_name)
        rule_path = os.path.join(skill_base_dir, "rules.md")
        
        # 特殊处理 OpenClaw skills
        if scope == "openclaw_skills":
            # OpenClaw skills 的规则在 SKILL.md 正文中
            # 需要找到 SKILL.md 的路径。
            # 由于 scope 只是 "openclaw_skills"，但实际路径可能是 nested 的
            # 我们需要遍历 openclaw_skills 目录来找到对应的 skill
            openclaw_root = os.path.join(project_root, "app", "openclaw_skills")
            found_path = None
            for dirpath, _, filenames in os.walk(openclaw_root):
                if os.path.basename(dirpath) == skill_name and "SKILL.md" in filenames:
                    found_path = os.path.join(dirpath, "SKILL.md")
                    break
            
            if found_path and os.path.exists(found_path):
                try:
                    with open(found_path, "r", encoding="utf-8") as f:
                        lines = f.read().splitlines()
                    # 去除 frontmatter
                    if lines and lines[0].strip() == "---":
                        end_idx = -1
                        for i in range(1, len(lines)):
                            if lines[i].strip() == "---":
                                end_idx = i
                                break
                        if end_idx != -1:
                            rule_content = "\n".join(lines[end_idx+1:]).strip()
                        else:
                            rule_content = "\n".join(lines).strip()
                    else:
                        rule_content = "\n".join(lines).strip()
                    
                    # 关键修复：转义规则内容中的花括号
                    # LangChain PromptTemplate 会将 {var} 视为变量占位符
                    # SKILL.md 中包含大量 {qrcode_image_url} 等示例，会导致 Input to ChatPromptTemplate is missing variables 错误
                    # 因此必须将 { 替换为 {{，将 } 替换为 }}
                    if rule_content:
                        rule_content = rule_content.replace("{", "{{").replace("}", "}}")
                except Exception:
                    pass
        
        # 如果不是 OpenClaw skill 或者没找到，尝试读取 rules.md
        if not rule_content and os.path.exists(rule_path):
            try:
                with open(rule_path, "r", encoding="utf-8") as f:
                    rule_content = f.read().strip()
            except Exception:
                pass
        
        if rule_content:
            rules.append(rule_content)
            seen_skills.add(skill_name)
                
    return "\n\n".join(rules) if rules else ""


def get_agent_prompt(tools: List[BaseTool] = None, extra_system: str = None):
    """
    获取 Agent 的提示词模板。
    
    从身份文件加载：SOUL.md → AGENTS.md → WORKFLOW.md → 技能规则
    """
    
    # 从文件加载身份定义（替代硬编码）
    identity_prompt = _load_identity_files()
    
    # 加载技能规则
    skill_rules = _load_rules_for_tools(tools or [])
    
    # 工具调用重要说明 - 防止模型模仿工具轨迹格式导致幻觉
    tool_calling_instruction = """
## ⚠️ 工具调用重要说明

- 当你需要调用工具时，**直接使用工具调用功能**，不要输出"Invoking:"或"responded:"等文本
- 聊天历史中可能包含"[系统注释：以下工具调用轨迹是历史执行记录]"的内容，这些是**过去的执行记录**，仅供参考
- **不要模仿历史轨迹的格式**，不要输出"Invoking: `tool_name` with `{{...}}`"这样的文本
- 如果需要调用工具，请使用正确的工具调用方式（function calling）

## ⚠️ 物理操作约束

- 涉及任何物理世界操作（如发布内容、修改文件、查询数据、执行命令等），**必须调用相应的工具**。
- **严禁** 在没有调用工具的情况下直接回复"已完成"、"已发布"、"已修复"等。
- 如果用户要求"重试"、"重发"、"再说一遍"，**必须重新调用工具**，不能仅复述之前的执行结果。
- 行动胜于空谈 (Actions speak louder than words)。
"""
    
    # 组合所有部分
    system_content = identity_prompt
    if skill_rules:
        system_content += "\n\n---\n\n## Skill Rules\n\n" + skill_rules
    system_content += "\n\n---\n\n" + tool_calling_instruction
    if extra_system:
        system_content += "\n\n---\n\n" + extra_system
    
    # 返回 prompt 模板
    return ChatPromptTemplate.from_messages([
        ("system", system_content),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
