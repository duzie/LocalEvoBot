from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
import os
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.agent import create_llm
from app.skills.registry import load_skills
from app.integrations.mcp_client import load_mcp_tools
from app.prompts import get_agent_prompt

def _get_board_path():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    base = os.path.join(root, "app", "data", "board")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "board.json")

def _load_board() -> Optional[Dict[str, Any]]:
    path = _get_board_path()
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_board(board: Dict[str, Any]):
    board["updated_at"] = datetime.now().isoformat()
    path = _get_board_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(board, f, ensure_ascii=False, indent=2)

def _normalize_status(status: str) -> str:
    s = (status or "").strip()
    mapping = {
        "pending": "待处理",
        "todo": "待处理",
        "in_progress": "进行中",
        "doing": "进行中",
        "review": "待验收",
        "done": "已完成",
        "completed": "已完成",
        "rework": "需返工"
    }
    if s in mapping:
        return mapping[s]
    if s in {"待处理", "进行中", "待验收", "已完成", "需返工"}:
        return s
    return s or "待处理"

def _split_tools_from_skill_md(path: str) -> List[str]:
    tools = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception:
        return tools
    in_tools = False
    for line in lines:
        s = line.strip()
        if not in_tools:
            if s.lower() == "## tools":
                in_tools = True
            continue
        if not s:
            continue
        if s.startswith("## "):
            break
        if not s.startswith("-"):
            continue
        item = s.lstrip("-").strip()
        name = ""
        if item.startswith("**"):
            end = item.find("**", 2)
            if end != -1:
                name = item[2:end].strip()
            else:
                name = item.strip("*").strip()
        else:
            if ":" in item:
                name = item.split(":", 1)[0].strip()
            else:
                name = item.strip()
        if name:
            tools.append(name)
    return tools

def _collect_tools_for_skills(skill_names: List[str]) -> List[str]:
    if not skill_names:
        return []
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    all_tools = []
    for scope in ("skills", "auto_skills"):
        for name in skill_names:
            md_path = os.path.join(root, "app", scope, name, "skill.md")
            if os.path.exists(md_path):
                all_tools.extend(_split_tools_from_skill_md(md_path))
    return list(dict.fromkeys(all_tools))

def _filter_tools(tools, allowlist: List[str]):
    if not allowlist:
        return tools
    allowed = set([t for t in allowlist if t])
    return [t for t in tools if getattr(t, "name", "") in allowed]

def _build_role_prompt(role_name: str, role_prompt: str) -> str:
    parts = []
    if role_name:
        parts.append(f"你当前角色是: {role_name}。")
    if role_prompt:
        parts.append(role_prompt)
    return "\n".join(parts).strip()

@tool
def create_board(goal: str, phase: str = "", milestone: str = "", roles: List[Dict[str, Any]] = None, tasks: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    创建新的公告板并覆盖旧状态。
    """
    now = datetime.now().isoformat()
    board = {
        "board_id": f"board-{now.replace(':','').replace('.','')}",
        "goal": goal or "",
        "phase": phase or "",
        "milestone": milestone or "",
        "roles": roles or [],
        "tasks": [],
        "created_at": now,
        "updated_at": now,
        "next_task_id": 1
    }
    for task in tasks or []:
        title = str(task.get("title") or "").strip()
        if not title:
            continue
        board["tasks"].append({
            "id": board["next_task_id"],
            "title": title,
            "owner": str(task.get("owner") or "").strip(),
            "status": _normalize_status(task.get("status") or "待处理"),
            "deps": task.get("deps") or [],
            "acceptance": str(task.get("acceptance") or "").strip(),
            "outputs": [],
            "created_at": now,
            "updated_at": now
        })
        board["next_task_id"] += 1
    _save_board(board)
    return board

@tool
def get_board() -> Dict[str, Any]:
    """
    读取当前公告板。
    """
    board = _load_board()
    if not board:
        return {"ok": False, "error": "公告板尚未创建"}
    return {"ok": True, "board": board}

@tool
def add_board_role(role_name: str, description: str = "", skills: List[str] = None) -> Dict[str, Any]:
    """
    向公告板添加角色。
    """
    board = _load_board()
    if not board:
        return {"ok": False, "error": "公告板尚未创建"}
    roles = board.get("roles") or []
    if any(r.get("name") == role_name for r in roles):
        return {"ok": False, "error": "角色已存在"}
    roles.append({
        "name": role_name,
        "description": description or "",
        "skills": skills or [],
        "created_at": datetime.now().isoformat()
    })
    board["roles"] = roles
    _save_board(board)
    return {"ok": True, "role": roles[-1]}

@tool
def add_board_task(title: str, owner: str = "", status: str = "待处理", deps: List[Any] = None, acceptance: str = "") -> Dict[str, Any]:
    """
    添加任务到公告板。
    """
    board = _load_board()
    if not board:
        return {"ok": False, "error": "公告板尚未创建"}
    task = {
        "id": board.get("next_task_id", 1),
        "title": title,
        "owner": owner or "",
        "status": _normalize_status(status),
        "deps": deps or [],
        "acceptance": acceptance or "",
        "outputs": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    board["tasks"] = board.get("tasks") or []
    board["tasks"].append(task)
    board["next_task_id"] = task["id"] + 1
    _save_board(board)
    return {"ok": True, "task": task}

@tool
def update_board_task(task_id: int, status: str = "", owner: str = "", title: str = "", acceptance: str = "") -> Dict[str, Any]:
    """
    更新任务字段或状态。
    """
    board = _load_board()
    if not board:
        return {"ok": False, "error": "公告板尚未创建"}
    tasks = board.get("tasks") or []
    for task in tasks:
        if task.get("id") == task_id:
            if status:
                task["status"] = _normalize_status(status)
            if owner:
                task["owner"] = owner
            if title:
                task["title"] = title
            if acceptance:
                task["acceptance"] = acceptance
            task["updated_at"] = datetime.now().isoformat()
            _save_board(board)
            return {"ok": True, "task": task}
    return {"ok": False, "error": "未找到任务"}

@tool
def append_board_task_output(task_id: int, output: str, output_type: str = "text") -> Dict[str, Any]:
    """
    追加任务产物或反馈。
    """
    board = _load_board()
    if not board:
        return {"ok": False, "error": "公告板尚未创建"}
    tasks = board.get("tasks") or []
    for task in tasks:
        if task.get("id") == task_id:
            outputs = task.get("outputs") or []
            outputs.append({
                "type": output_type,
                "content": output,
                "created_at": datetime.now().isoformat()
            })
            task["outputs"] = outputs
            task["updated_at"] = datetime.now().isoformat()
            _save_board(board)
            return {"ok": True, "task": task}
    return {"ok": False, "error": "未找到任务"}

@tool
def list_board_tasks(status: str = "", owner: str = "") -> Dict[str, Any]:
    """
    按状态或负责人筛选任务。
    """
    board = _load_board()
    if not board:
        return {"ok": False, "error": "公告板尚未创建"}
    tasks = board.get("tasks") or []
    if status:
        status = _normalize_status(status)
        tasks = [t for t in tasks if t.get("status") == status]
    if owner:
        tasks = [t for t in tasks if t.get("owner") == owner]
    return {"ok": True, "tasks": tasks}

@tool
def run_role_agent(role_name: str, task_input: str, role_prompt: str = "", tools_allowlist: List[str] = None, skills_allowlist: List[str] = None, task_id: int = 0, status_after: str = "待验收", max_iterations: int = 30, max_execution_time: int = 300) -> Dict[str, Any]:
    """
    创建角色 Agent 并执行单次任务，返回输出结果。
    """
    llm = create_llm()
    tools = load_skills(package_name="app.skills")
    mcp_tools = load_mcp_tools()
    if mcp_tools:
        tools.extend(mcp_tools)
    allow = tools_allowlist or []
    allow.extend(_collect_tools_for_skills(skills_allowlist or []))
    tools = _filter_tools(tools, allow)
    prompt_extra = _build_role_prompt(role_name, role_prompt)
    prompt = get_agent_prompt(tools, prompt_extra if prompt_extra else None)
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=max(1, int(max_iterations or 30)),
        max_execution_time=max(1, int(max_execution_time or 300))
    )
    result = executor.invoke({"input": task_input or ""})
    output = result.get("output") if isinstance(result, dict) else str(result)
    if task_id:
        append_board_task_output(task_id, output, "role_result")
        if status_after:
            update_board_task(task_id, status_after)
    return {"ok": True, "role": role_name, "output": output}
