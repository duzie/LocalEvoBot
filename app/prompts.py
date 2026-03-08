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
    
    从身份文件加载：SOUL.md → AGENTS.md → WORKFLOW.md → 技能规则
    """
    
    # 从文件加载身份定义（替代硬编码）
    identity_prompt = _load_identity_files()
    
    # 加载技能规则
    skill_rules = _load_rules_for_tools(tools or [])
    
    # 组合所有部分
    system_content = identity_prompt
    if skill_rules:
        system_content += "\n\n---\n\n## Skill Rules\n\n" + skill_rules
    if extra_system:
        system_content += "\n\n---\n\n" + extra_system
    
    # 返回 prompt 模板
    return ChatPromptTemplate.from_messages([
        ("system", system_content),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
