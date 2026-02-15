from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
import os
import json
import re
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional
from app.agent import create_llm
from app.skills.registry import load_skills
from app.integrations.mcp_client import load_mcp_tools
from app.prompts import get_agent_prompt
from web.backend.shared import shared

def _get_board_path():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    base = os.path.join(root, "app", "data", "board")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "board.json")

def _get_lock_path():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    base = os.path.join(root, "app", "data", "board")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "board.lock")

def _acquire_lock(timeout: int = 5, interval: float = 0.05) -> bool:
    lock_path = _get_lock_path()
    deadline = time.time() + max(0, int(timeout))
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.close(fd)
            return True
        except FileExistsError:
            if time.time() >= deadline:
                return False
            time.sleep(interval)

def _release_lock():
    lock_path = _get_lock_path()
    try:
        if os.path.exists(lock_path):
            os.remove(lock_path)
    except Exception:
        pass

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

def _load_board_locked() -> Optional[Dict[str, Any]]:
    if not _acquire_lock():
        return None
    try:
        return _load_board()
    finally:
        _release_lock()

def _update_board_locked(update_fn):
    if not _acquire_lock():
        return {"ok": False, "error": "公告板正被占用，请稍后重试"}
    try:
        board = _load_board()
        if not board:
            return {"ok": False, "error": "公告板尚未创建"}
        result = update_fn(board)
        if isinstance(result, dict) and result.get("ok") is False:
            return result
        _save_board(board)
        return result
    finally:
        _release_lock()

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

def _compose_task_input(task_input: str, payload: Dict[str, Any], board_snapshot: Optional[Dict[str, Any]], task: Optional[Dict[str, Any]]) -> str:
    parts = []
    base = (task_input or "").strip()
    if base:
        parts.append(base)
    context_parts = []
    if board_snapshot:
        goal = str(board_snapshot.get("goal") or "").strip()
        phase = str(board_snapshot.get("phase") or "").strip()
        milestone = str(board_snapshot.get("milestone") or "").strip()
        if goal:
            context_parts.append(f"总体目标: {goal}")
        if phase:
            context_parts.append(f"阶段: {phase}")
        if milestone:
            context_parts.append(f"里程碑: {milestone}")
    if task:
        title = str(task.get("title") or "").strip()
        acceptance = str(task.get("acceptance") or "").strip()
        deps = task.get("deps") or []
        outputs = task.get("outputs") or []
        if title:
            context_parts.append(f"任务: {title}")
        if acceptance:
            context_parts.append(f"验收: {acceptance}")
        if deps:
            context_parts.append(f"依赖任务: {', '.join([str(d) for d in deps])}")
        if outputs:
            recent = outputs[-3:]
            texts = []
            for item in recent:
                content = item.get("content")
                if content:
                    texts.append(str(content))
            if texts:
                context_parts.append("最近产物: " + " | ".join(texts))
    extra_context = payload.get("context") or payload.get("summary") or payload.get("notes")
    if extra_context:
        context_parts.append(f"补充说明: {str(extra_context).strip()}")
    output_dir = payload.get("output_dir") or payload.get("target_dir") or payload.get("directory")
    if output_dir:
        context_parts.append(f"目标目录: {str(output_dir).strip()}")
    if context_parts:
        parts.append("上下文信息:\n" + "\n".join(context_parts))
    return "\n\n".join(parts).strip()

def _execute_role_task(role_name: str, task_input: str, role_prompt: str = "", tools_allowlist: List[str] = None, skills_allowlist: List[str] = None, max_iterations: int = 30, max_execution_time: int = 300) -> Dict[str, Any]:
    if shared.stop_requested:
        shared.clear_stop()
        shared.set_status("stopped", "已停止", task_input)
        return {"ok": False, "stopped": True, "role": role_name, "output": ""}
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
    raw_output = ""
    for chunk in executor.stream({"input": task_input or ""}):
        if shared.stop_requested:
            shared.clear_stop()
            shared.set_status("stopped", "已停止", task_input)
            return {"ok": False, "stopped": True, "role": role_name, "output": raw_output}
        if not isinstance(chunk, dict):
            continue
        text = chunk.get("output")
        if text is None:
            continue
        if text.startswith(raw_output):
            raw_output = text
        else:
            raw_output += text
    output = raw_output
    return {"ok": True, "role": role_name, "output": output}

@tool
def create_board(goal: str, phase: str = "", milestone: str = "", roles: List[Dict[str, Any]] = None, tasks: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    创建新的公告板并覆盖旧状态。
    """
    if not _acquire_lock():
        return {"ok": False, "error": "公告板正被占用，请稍后重试"}
    try:
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
    finally:
        _release_lock()

@tool
def get_board() -> Dict[str, Any]:
    """
    读取当前公告板。
    """
    board = _load_board_locked()
    if not board:
        return {"ok": False, "error": "公告板尚未创建"}
    return {"ok": True, "board": board}

@tool
def add_board_role(role_name: str, description: str = "", skills: List[str] = None) -> Dict[str, Any]:
    """
    向公告板添加角色。
    """
    def _update(board):
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
        return {"ok": True, "role": roles[-1]}
    return _update_board_locked(_update)

@tool
def add_board_task(title: str, owner: str = "", status: str = "待处理", deps: List[Any] = None, acceptance: str = "") -> Dict[str, Any]:
    """
    添加任务到公告板。
    """
    def _update(board):
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
        return {"ok": True, "task": task}
    return _update_board_locked(_update)

@tool
def update_board_task(task_id: int, status: str = "", owner: str = "", title: str = "", acceptance: str = "") -> Dict[str, Any]:
    """
    更新任务字段或状态。
    """
    def _update(board):
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
                return {"ok": True, "task": task}
        return {"ok": False, "error": "未找到任务"}
    return _update_board_locked(_update)

@tool
def append_board_task_output(task_id: int, output: str, output_type: str = "text") -> Dict[str, Any]:
    """
    追加任务产物或反馈。
    """
    def _update(board):
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
                return {"ok": True, "task": task}
        return {"ok": False, "error": "未找到任务"}
    return _update_board_locked(_update)

@tool
def list_board_tasks(status: str = "", owner: str = "") -> Dict[str, Any]:
    """
    按状态或负责人筛选任务。
    """
    board = _load_board_locked()
    if not board:
        return {"ok": False, "error": "公告板尚未创建"}
    tasks = board.get("tasks") or []
    if status:
        status = _normalize_status(status)
        tasks = [t for t in tasks if t.get("status") == status]
    if owner:
        tasks = [t for t in tasks if t.get("owner") == owner]
    return {"ok": True, "tasks": tasks}

def _get_task_by_id(board: Dict[str, Any], task_id: int) -> Optional[Dict[str, Any]]:
    tasks = board.get("tasks") or []
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None

def _deps_completed(board: Dict[str, Any], deps: List[Any]) -> bool:
    dep_ids = []
    for d in deps or []:
        try:
            dep_ids.append(int(d))
        except Exception:
            continue
    if not dep_ids:
        return True
    for dep_id in dep_ids:
        dep_task = _get_task_by_id(board, dep_id)
        if not dep_task:
            return False
        if _normalize_status(dep_task.get("status") or "") != "已完成":
            return False
    return True

def _deps_satisfied(board: Dict[str, Any], deps: List[Any], policy: str) -> bool:
    p = (policy or "").strip().lower()
    if p in {"none", "ignore", "off"}:
        return True
    dep_ids = []
    for d in deps or []:
        try:
            dep_ids.append(int(d))
        except Exception:
            continue
    if not dep_ids:
        return True
    if p in {"any", "some"}:
        for dep_id in dep_ids:
            dep_task = _get_task_by_id(board, dep_id)
            if dep_task and _normalize_status(dep_task.get("status") or "") == "已完成":
                return True
        return False
    return _deps_completed(board, dep_ids)

@tool
def run_role_agent(role_name: str, task_input: str, role_prompt: str = "", tools_allowlist: List[str] = None, skills_allowlist: List[str] = None, task_id: int = 0, status_after: str = "待验收", max_iterations: int = 30, max_execution_time: int = 300, context: str = "", summary: str = "", output_dir: str = "") -> Dict[str, Any]:
    """
    创建角色 Agent 并执行单次任务，返回输出结果。
    """
    board_snapshot = _load_board_locked()
    task = _get_task_by_id(board_snapshot, int(task_id)) if board_snapshot and task_id else None
    payload = {"context": context, "summary": summary, "output_dir": output_dir}
    merged_input = _compose_task_input(task_input, payload, board_snapshot, task)
    result = _execute_role_task(
        role_name=role_name,
        task_input=merged_input,
        role_prompt=role_prompt,
        tools_allowlist=tools_allowlist,
        skills_allowlist=skills_allowlist,
        max_iterations=max_iterations,
        max_execution_time=max_execution_time
    )
    output = result.get("output")
    if task_id:
        append_board_task_output(task_id, output, "role_result")
        if status_after:
            update_board_task(task_id, status_after)
    return result

@tool
def run_role_agents_parallel(tasks: List[Dict[str, Any]], max_workers: int = 3, status_after: str = "待验收", allowed_statuses: List[str] = None, dep_policy: str = "") -> Dict[str, Any]:
    """
    并发运行多个角色 Agent。
    """
    if shared.stop_requested:
        shared.clear_stop()
        shared.set_status("stopped", "已停止", "")
        return {"ok": False, "stopped": True, "results": []}
    items = tasks or []
    if not isinstance(items, list) or not items:
        return {"ok": False, "error": "tasks 不能为空"}
    worker_count = max(1, min(int(max_workers or 3), 10))
    allow_status = allowed_statuses if allowed_statuses is not None else ["待处理", "需返工"]
    allow_status = [_normalize_status(s) for s in (allow_status or [])]
    results = []
    success_count = 0
    error_count = 0
    skipped_count = 0
    effective_policy = dep_policy or "all"
    pending = [{"index": idx, "task": (item or {})} for idx, item in enumerate(items)]
    while pending:
        if shared.stop_requested:
            shared.clear_stop()
            shared.set_status("stopped", "已停止", "")
            return {
                "ok": False,
                "stopped": True,
                "total": len(items),
                "success_count": success_count,
                "error_count": error_count,
                "skipped_count": skipped_count,
                "results": sorted(results, key=lambda x: x.get("index", 0))
            }
        board_snapshot = _load_board_locked()
        ready = []
        blocked = []
        for meta in pending:
            idx = meta["index"]
            payload = meta["task"]
            task_id = payload.get("task_id")
            if board_snapshot and task_id:
                task = _get_task_by_id(board_snapshot, int(task_id))
                if not task:
                    skipped_count += 1
                    results.append({"ok": False, "skipped": True, "reason": "task_not_found", "index": idx, "task_id": task_id})
                    continue
                if allow_status:
                    current_status = _normalize_status(task.get("status") or "")
                    if current_status not in allow_status:
                        skipped_count += 1
                        results.append({"ok": False, "skipped": True, "reason": "status_not_allowed", "index": idx, "task_id": task_id, "status": current_status})
                        continue
                deps = payload.get("deps")
                if deps is None and task:
                    deps = task.get("deps") or []
                task_policy = payload.get("dep_policy") or effective_policy
                if not _deps_satisfied(board_snapshot, deps, task_policy):
                    blocked.append({"index": idx, "task": payload, "deps": deps, "dep_policy": task_policy})
                    continue
            elif board_snapshot and payload.get("deps"):
                deps = payload.get("deps") or []
                task_policy = payload.get("dep_policy") or effective_policy
                if not _deps_satisfied(board_snapshot, deps, task_policy):
                    blocked.append({"index": idx, "task": payload, "deps": deps, "dep_policy": task_policy})
                    continue
            ready.append(meta)
        if not ready:
            for meta in blocked:
                skipped_count += 1
                payload = meta["task"]
                results.append({
                    "ok": False,
                    "skipped": True,
                    "reason": "deps_not_ready",
                    "index": meta["index"],
                    "task_id": payload.get("task_id"),
                    "deps": meta.get("deps"),
                    "dep_policy": meta.get("dep_policy")
                })
            break
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {}
            for meta in ready:
                payload = meta["task"]
                task = None
                if board_snapshot and payload.get("task_id"):
                    task = _get_task_by_id(board_snapshot, int(payload.get("task_id")))
                merged_input = _compose_task_input(payload.get("task_input") or "", payload, board_snapshot, task)
                future = executor.submit(
                    _execute_role_task,
                    role_name=payload.get("role_name") or "",
                    task_input=merged_input,
                    role_prompt=payload.get("role_prompt") or "",
                    tools_allowlist=payload.get("tools_allowlist") or [],
                    skills_allowlist=payload.get("skills_allowlist") or [],
                    max_iterations=payload.get("max_iterations") or 30,
                    max_execution_time=payload.get("max_execution_time") or 300
                )
                futures[future] = meta
            for future in as_completed(futures):
                meta = futures[future]
                payload = meta["task"]
                try:
                    result = future.result()
                    if payload.get("task_id"):
                        append_board_task_output(int(payload.get("task_id")), result.get("output") or "", "role_result")
                        update_board_task(int(payload.get("task_id")), payload.get("status_after") or status_after)
                    success_count += 1
                    results.append({"ok": True, "index": meta["index"], "result": result})
                except Exception as e:
                    error_count += 1
                    results.append({"ok": False, "index": meta["index"], "error": str(e), "task": payload})
        pending = blocked
    results = sorted(results, key=lambda x: x.get("index", 0))
    return {
        "ok": error_count == 0,
        "total": len(items),
        "success_count": success_count,
        "error_count": error_count,
        "skipped_count": skipped_count,
        "results": results
    }
