from langchain_core.tools import tool, BaseTool
from langchain.agents import AgentExecutor, create_tool_calling_agent
import os
import json
import re
import time
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from typing import Dict, Any, List, Optional, Type
from app.agent import create_llm
from app.skills.registry import load_skills
from app.integrations.mcp_client import load_mcp_tools
from app.integrations import heartbeat
from app.prompts import get_agent_prompt
from web.backend.shared import shared

_PATH_KEYS = {"file_path", "path", "dir", "directory", "folder", "target_dir", "output_dir", "root", "base_dir", "file", "cwd"}
_LIST_PATH_KEYS = {"file_paths", "paths", "files", "dirs", "directories"}

class WorkdirTool(BaseTool):
    name: str
    description: str
    args_schema: Optional[Type[Any]] = None
    return_direct: bool = False
    inner_tool: BaseTool
    workdir: str

    def _run(self, *args, **kwargs):
        tool = self.inner_tool
        wd = self.workdir
        if kwargs:
            data = _rewrite_paths(kwargs, wd)
            if getattr(tool, "name", "") == "run_shell_command" and isinstance(data, dict) and not data.get("cwd"):
                data["cwd"] = wd
            return tool.invoke(data)
        if args:
            data = _rewrite_paths(args[0], wd)
            if getattr(tool, "name", "") == "run_shell_command" and isinstance(data, dict) and not data.get("cwd"):
                data["cwd"] = wd
            return tool.invoke(data)
        return tool.invoke({})

    async def _arun(self, *args, **kwargs):
        tool = self.inner_tool
        wd = self.workdir
        if kwargs:
            data = _rewrite_paths(kwargs, wd)
            if getattr(tool, "name", "") == "run_shell_command" and isinstance(data, dict) and not data.get("cwd"):
                data["cwd"] = wd
            return await tool.ainvoke(data)
        if args:
            data = _rewrite_paths(args[0], wd)
            if getattr(tool, "name", "") == "run_shell_command" and isinstance(data, dict) and not data.get("cwd"):
                data["cwd"] = wd
            return await tool.ainvoke(data)
        return await tool.ainvoke({})

def _get_role_log_dir():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    base = os.path.join(root, "app", "data", "board", "role_logs")
    os.makedirs(base, exist_ok=True)
    return base

def _safe_role_name(name: str) -> str:
    s = str(name or "").strip()
    if not s:
        return "role"
    s = re.sub(r"[^\w\-\.]+", "_", s)
    return s.strip("_") or "role"

def _append_role_log(role_name: str, text: str):
    if text is None:
        return
    role = _safe_role_name(role_name)
    path = os.path.join(_get_role_log_dir(), f"{role}.log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(str(text))

def _append_role_event(role_name: str, event: str, **fields):
    payload = {"event": str(event or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    _append_role_log(role_name, json.dumps(payload, ensure_ascii=False) + "\n")

def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _read_int_env(key: str, default: int) -> int:
    try:
        value = os.getenv(key)
        if value is None or str(value).strip() == "":
            return int(default)
        parsed = int(str(value).strip())
        return parsed if parsed >= 0 else int(default)
    except Exception:
        return int(default)

def _read_bool_env(key: str, default: bool) -> bool:
    try:
        value = os.getenv(key)
        if value is None or str(value).strip() == "":
            return bool(default)
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return bool(default)

def _read_optional_bool_env(key: str):
    value = os.getenv(key)
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip().lower() in ("1", "true", "yes", "on")

def _resolve_role_limits():
    role_limits_disabled = _read_optional_bool_env("ROLE_AGENT_LIMITS_DISABLED")
    limits_disabled = role_limits_disabled if role_limits_disabled is not None else _read_bool_env("AGENT_LIMITS_DISABLED", False)
    role_max_iter = os.getenv("ROLE_AGENT_MAX_ITERATIONS")
    role_max_time = os.getenv("ROLE_AGENT_MAX_EXECUTION_TIME")
    if role_max_iter is None or str(role_max_iter).strip() == "":
        default_max_iter = _read_int_env("AGENT_MAX_ITERATIONS", 50000000)
    else:
        default_max_iter = _read_int_env("ROLE_AGENT_MAX_ITERATIONS", 50000000)
    if role_max_time is None or str(role_max_time).strip() == "":
        default_max_time = _read_int_env("AGENT_MAX_EXECUTION_TIME", 600)
    else:
        default_max_time = _read_int_env("ROLE_AGENT_MAX_EXECUTION_TIME", 600)
    return limits_disabled, default_max_iter, default_max_time

def _coerce_limit(value, fallback: int):
    if value is None:
        return fallback
    try:
        parsed = int(str(value).strip())
        return parsed if parsed > 0 else fallback
    except Exception:
        return fallback

def _next_message_id(board: Dict[str, Any]) -> int:
    next_id = int(board.get("next_message_id") or 1)
    board["next_message_id"] = next_id + 1
    return next_id

def _next_workflow_id(board: Dict[str, Any]) -> int:
    next_id = int(board.get("next_workflow_id") or 1)
    board["next_workflow_id"] = next_id + 1
    return next_id

def _is_url(value: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value or ""))

def _normalize_path_value(value: str, workdir: str) -> str:
    if not value:
        return value
    s = str(value).strip()
    if not s or _is_url(s):
        return value
    if os.path.isabs(s):
        return s
    return os.path.abspath(os.path.join(workdir, s))

def _rewrite_paths(data, workdir: str, key: str = ""):
    if not workdir:
        return data
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if k in _PATH_KEYS:
                out[k] = _rewrite_paths(v, workdir, k)
            elif k in _LIST_PATH_KEYS:
                out[k] = _rewrite_paths(v, workdir, k)
            else:
                out[k] = v
        return out
    if isinstance(data, list):
        if key in _PATH_KEYS or key in _LIST_PATH_KEYS:
            return [_rewrite_paths(v, workdir, key) for v in data]
        return data
    if isinstance(data, str) and (key in _PATH_KEYS or key in _LIST_PATH_KEYS):
        return _normalize_path_value(data, workdir)
    return data

def _wrap_tool_with_workdir(tool: BaseTool, workdir: str) -> BaseTool:
    if not workdir:
        return tool
    return WorkdirTool(
        name=getattr(tool, "name", ""),
        description=getattr(tool, "description", ""),
        args_schema=getattr(tool, "args_schema", None),
        return_direct=getattr(tool, "return_direct", False),
        inner_tool=tool,
        workdir=workdir
    )

def _get_board_path():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    base = os.path.join(root, "app", "data", "board")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "board.json")

def _get_board_output_dir():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    base = os.path.join(root, "app", "data", "board", "outputs")
    os.makedirs(base, exist_ok=True)
    return base

def _get_spec_dir():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    base = os.path.join(root, ".specify", "specs")
    os.makedirs(base, exist_ok=True)
    return base

def _save_spec_file(spec_id: str, content: str) -> str:
    spec_dir = _get_spec_dir()
    safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(spec_id or "spec"))
    path = os.path.join(spec_dir, f"{safe_id}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content or "")
    return path

def _render_simple_spec(spec_id: str, summary: str, goal: str, user_scenario: str, steps: List[str], success_outcome: str, p0_features: List[Dict[str, Any]], constraints: List[str], owner: str) -> str:
    now = datetime.now().isoformat()
    lines = [
        "# 项目规范模板 (精简版)",
        "",
        "## 规范元数据",
        f"- **规范ID**: `{spec_id}`",
        f"- **创建时间**: `{now}`",
        f"- **最后更新**: `{now}`",
        "- **状态**: draft",
        "- **版本**: 1.0",
        f"- **负责人**: {owner}",
        "",
        "## 1. 目标与成功标准",
        goal or summary,
    ]
    for item in (constraints or [])[:0]:
        lines.append(item)
    lines.append("- [ ] 成功标准：任务按 Spec 生成并执行")
    lines.append("")
    lines.append("## 2. 核心用户旅程")
    lines.append(f"**场景**: {user_scenario or summary}")
    for idx, step in enumerate(steps or [], 1):
        lines.append(f"{idx}. {step}")
    lines.append(f"**成功结果**: {success_outcome or '完成目标并通过验收'}")
    lines.append("")
    lines.append("## 3. P0 功能与验收")
    for feat in p0_features or []:
        title = str((feat or {}).get("title") or (feat or {}).get("name") or "").strip()
        acceptance = str((feat or {}).get("acceptance") or "").strip()
        if not title:
            continue
        lines.append(f"- [ ] {title}")
        if acceptance:
            lines.append(f"  - 验收：{acceptance}")
    lines.append("")
    lines.append("## 4. 关键约束")
    if constraints:
        for c in constraints:
            if str(c or "").strip():
                lines.append(f"- {str(c).strip()}")
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("## 变更记录")
    lines.append("| 版本 | 日期 | 修改内容 | 修改人 |")
    lines.append("|------|------|---------|--------|")
    lines.append(f"| 1.0 | {now.split('T')[0]} | 初始版本 | {owner} |")
    return "\n".join(lines)

def _board_exists() -> bool:
    try:
        return os.path.exists(_get_board_path())
    except Exception:
        return False

def _message_timeout_tick():
    try:
        process_board_message_timeouts.invoke({})
    except Exception:
        return

heartbeat.register_task("board_message_timeouts", _message_timeout_tick, interval=60, enabled=_board_exists)

def _board_health_tick():
    try:
        check_and_notify_board_health.invoke({})
    except Exception:
        return

heartbeat.register_task("board_health_check", _board_health_tick, interval=300, enabled=_board_exists)

def _workflow_tick():
    try:
        process_board_workflows.invoke({})
    except Exception:
        return

heartbeat.register_task("board_workflow_tick", _workflow_tick, interval=30, enabled=_board_exists)

def _get_lock_path():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    base = os.path.join(root, "app", "data", "board")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "board.lock")

def _get_file_lock_dir():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    base = os.path.join(root, "app", "data", "board", "current_tasks")
    os.makedirs(base, exist_ok=True)
    return base

def _lock_key(target: str) -> str:
    text = str(target or "").strip().lower()
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

def _safe_lock_name(name: str) -> str:
    s = str(name or "").strip()
    if not s:
        return _lock_key("empty")
    s = re.sub(r"[^\w\-\.]+", "_", s)
    s = s.strip("_")
    if len(s) > 80:
        return _lock_key(s)
    return s or _lock_key("empty")

def _lock_path_for_target(target: str) -> str:
    return os.path.join(_get_file_lock_dir(), _safe_lock_name(target) + ".lock")

def _read_lock_payload(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _is_lock_expired(payload: Dict[str, Any]) -> bool:
    try:
        expires_at = float(payload.get("expires_at") or 0)
        if expires_at <= 0:
            return False
        return time.time() > expires_at
    except Exception:
        return False

def _try_acquire_lock(target: str, owner: str, ttl: int) -> Dict[str, Any]:
    path = _lock_path_for_target(target)
    now = time.time()
    payload = {
        "mode": "git_lock",
        "owner": owner,
        "target": target,
        "created_at": now,
        "expires_at": now + max(1, int(ttl or 1))
    }
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False))
        return {"ok": True, "path": path, "payload": payload}
    except FileExistsError:
        existing = _read_lock_payload(path)
        if existing and _is_lock_expired(existing):
            try:
                os.remove(path)
            except Exception:
                return {"ok": False, "path": path, "existing": existing}
            return _try_acquire_lock(target, owner, ttl)
        return {"ok": False, "path": path, "existing": existing}
    except Exception as e:
        return {"ok": False, "path": path, "error": str(e)}

def _release_lock_path(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        return

def _normalize_lock_targets(paths: List[str]) -> List[str]:
    seen = set()
    results = []
    for p in paths or []:
        text = str(p or "").strip()
        if not text:
            continue
        if text.startswith("task:") or text.startswith("dir:") or text.startswith("file:"):
            norm = text
        else:
            norm = os.path.abspath(text)
        if norm in seen:
            continue
        seen.add(norm)
        results.append(norm)
    return results

def _acquire_locks(lock_paths: List[str], owner: str, ttl: int) -> Dict[str, Any]:
    targets = _normalize_lock_targets(lock_paths)
    acquired = []
    for target in targets:
        result = _try_acquire_lock(target, owner, ttl)
        if not result.get("ok"):
            for item in acquired:
                _release_lock_path(item.get("path"))
            return {
                "ok": False,
                "failed_target": target,
                "failed_lock_path": result.get("path"),
                "existing": result.get("existing"),
                "error": result.get("error"),
                "acquired": acquired
            }
        acquired.append({"target": target, "path": result.get("path")})
    return {"ok": True, "acquired": acquired}

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
        return _error_payload("board_locked", "公告板正被占用，请稍后重试")
    try:
        board = _load_board()
        if not board:
            return _error_payload("board_missing", "公告板尚未创建")
        result = update_fn(board)
        if isinstance(result, dict) and result.get("ok") is False:
            if result.get("error_info"):
                return result
            msg = str(result.get("error") or "")
            extra = {k: v for k, v in result.items() if k not in {"ok", "error"}}
            return _error_payload("error", msg, **extra)
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

def _allow_all_tools_for_subagents() -> bool:
    v = os.getenv("BOARD_SUBAGENT_ALL_TOOLS")
    s = str(v).strip().lower() if v is not None else ""
    return s not in {"", "0", "false", "no", "off"}

def _always_allowed_tools() -> set:
    return {
        "search_short_term_memory",
        "inspect_environment",
        "get_current_time",
        "save_document",
        "read_document_part",
        "search_document",
    }

def _infer_skills_allowlist(task_input: str) -> List[str]:
    text = str(task_input or "").lower()
    skills = {"system_skill", "board_skill"}
    if any(k in text for k in ["ppt", "演示", "幻灯", "powerpoint"]):
        skills.add("ppt_gen_skill")
    if any(k in text for k in ["音频", "录音", "转写", "听写", "语音", ".mp3", ".wav", ".m4a", ".flac"]):
        skills.add("audio_transcribe_skill")
    if any(k in text for k in ["读取", "read", "打开文件", "查找", "search", ".py", ".md", ".txt"]):
        skills.add("document_skill")
    return sorted(skills)

def _filter_tools(tools, allowlist: List[str]):
    always_allowed = _always_allowed_tools()
    
    if _allow_all_tools_for_subagents():
        return tools
    
    if not allowlist:
        return tools
        
    allowed = set([t for t in allowlist if t]) | always_allowed
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
        roles = board_snapshot.get("roles") or []
        if roles:
            role_lines = []
            for r in roles:
                name = str(r.get("name") or "").strip()
                desc = str(r.get("description") or "").strip()
                if not name:
                    continue
                if desc:
                    role_lines.append(f"- {name}: {desc}")
                else:
                    role_lines.append(f"- {name}")
            if role_lines:
                context_parts.append("角色清单:\n" + "\n".join(role_lines))
        tasks = board_snapshot.get("tasks") or []
        if tasks:
            task_lines = []
            for t in tasks:
                title = str(t.get("title") or "").strip()
                owner = str(t.get("owner") or "").strip()
                status = str(t.get("status") or "").strip()
                if not title:
                    continue
                if owner:
                    task_lines.append(f"- {title}（{status} | {owner}）")
                else:
                    task_lines.append(f"- {title}（{status}）")
            if task_lines:
                context_parts.append("任务分布:\n" + "\n".join(task_lines))
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
    role_name = str(payload.get("role_name") or "").strip()
    if role_name:
        context_parts.append(f"当前角色: {role_name}")
    if board_snapshot and role_name:
        board_messages = board_snapshot.get("messages") or []
        unread = [m for m in board_messages if m.get("target") == role_name and role_name not in (m.get("read_by") or [])]
        if unread:
            recent = unread[-5:]
            lines = []
            for msg in recent:
                sender = str(msg.get("sender") or "").strip()
                message = str(msg.get("message") or "").strip()
                if sender and message:
                    lines.append(f"- {sender}: {message}")
                elif message:
                    lines.append(f"- {message}")
            if lines:
                context_parts.append("未读消息:\n" + "\n".join(lines))
    if extra_context:
        context_parts.append(f"补充说明: {str(extra_context).strip()}")
    output_dir = payload.get("output_dir") or payload.get("target_dir") or payload.get("directory")
    if output_dir:
        context_parts.append(f"目标目录: {str(output_dir).strip()}")
    workdir = payload.get("workdir")
    if workdir:
        context_parts.append(f"工作目录: {str(workdir).strip()}")
    if context_parts:
        parts.append("上下文信息:\n" + "\n".join(context_parts))
    return "\n\n".join(parts).strip()

def _execute_role_task(role_name: str, task_input: str, role_prompt: str = "", tools_allowlist: List[str] = None, skills_allowlist: List[str] = None, max_iterations: int = None, max_execution_time: int = None, workdir: str = "") -> Dict[str, Any]:
    if shared.stop_requested:
        shared.set_status("stopped", "已停止", task_input)
        _append_role_event(role_name, "stopped", role=role_name)
        return _error_payload("stopped", "已停止", stopped=True, role=role_name, output="")
    llm = create_llm()
    tools = load_skills(package_name="app.skills")
    mcp_tools = load_mcp_tools()
    if mcp_tools:
        tools.extend(mcp_tools)
    wd = (workdir or "").strip()
    if wd and not os.path.isabs(wd):
        wd = os.path.abspath(wd)
    if wd:
        tools = [_wrap_tool_with_workdir(t, wd) for t in tools]
    allow = tools_allowlist or []
    allow.extend(_collect_tools_for_skills(skills_allowlist or []))
    if not _allow_all_tools_for_subagents():
        always_allowed = _always_allowed_tools()
        allow_clean = [t for t in (allow or []) if t]
        looks_like_only_base = bool(allow) and (not allow_clean or all(t in always_allowed for t in allow_clean))
        if looks_like_only_base:
            inferred = _infer_skills_allowlist(task_input)
            allow.extend(_collect_tools_for_skills(inferred))
    tools = _filter_tools(tools, allow)
    prompt_extra = _build_role_prompt(role_name, role_prompt)
    prompt = get_agent_prompt(tools, prompt_extra if prompt_extra else None)
    agent = create_tool_calling_agent(llm, tools, prompt)
    limits_disabled, default_max_iter, default_max_time = _resolve_role_limits()
    effective_max_iterations = None
    effective_max_time = None
    if not limits_disabled:
        effective_max_iterations = _coerce_limit(max_iterations, default_max_iter)
        effective_max_time = _coerce_limit(max_execution_time, default_max_time)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=effective_max_iterations,
        max_execution_time=effective_max_time
    )
    _append_role_event(role_name, "start", role=role_name, workdir=wd)
    # 强制写入一条初始日志，确保日志文件创建，从而使前端能识别到该角色
    _append_role_log(role_name, f"=== Agent {role_name} Started ===\nTask: {task_input}\nWorkdir: {wd}\n\n")
    
    started_at = time.monotonic()
    raw_output = ""
    try:
        for chunk in executor.stream({"input": task_input or ""}):
            if effective_max_time and (time.monotonic() - started_at) > float(effective_max_time):
                shared.set_status("idle", "空闲", task_input, error="执行超时")
                _append_role_event(role_name, "timeout", role=role_name, max_execution_time=effective_max_time)
                return _error_payload("timeout", "执行超时", timed_out=True, role=role_name, output=raw_output)
            if shared.stop_requested:
                shared.set_status("stopped", "已停止", task_input)
                _append_role_event(role_name, "stopped", role=role_name)
                return _error_payload("stopped", "已停止", stopped=True, role=role_name, output=raw_output)
            
            if not isinstance(chunk, dict):
                continue
                
            # 捕获中间步骤（AgentAction）
            if "actions" in chunk:
                for action in chunk["actions"]:
                    log_text = f"\n> Action: {action.tool}\n> Input: {action.tool_input}\n"
                    _append_role_log(role_name, log_text)
                    
            # 捕获工具输出（Observation）
            if "steps" in chunk:
                for step in chunk["steps"]:
                    # step 是 (AgentAction, observation) 元组
                    if isinstance(step, (list, tuple)) and len(step) >= 2:
                        observation = step[1]
                        log_text = f"\n< Observation: {str(observation)}\n"
                        _append_role_log(role_name, log_text)

            text = chunk.get("output")
            if text is None:
                continue
            
            # 确保 text 是字符串
            if not isinstance(text, str):
                text = str(text)
                
            # 处理最终输出的增量更新
            # 注意：LangChain 的 stream output 有时是全量，有时是增量，取决于 LLM
            # 这里沿用原有逻辑，假设是全量覆盖或增量追加
            if text.startswith(raw_output):
                delta = text[len(raw_output):]
                raw_output = text
            else:
                delta = text
                raw_output += delta
            if delta:
                _append_role_log(role_name, delta)
    except Exception as e:
        shared.set_status("idle", "空闲", task_input, error=f"{e}")
        _append_role_event(role_name, "error", role=role_name, error=str(e), error_type=type(e).__name__)
        return _error_payload("exception", str(e), role=role_name, output=raw_output, error_type=type(e).__name__)
    output = raw_output
    _append_role_event(role_name, "end", role=role_name)
    return {"ok": True, "role": role_name, "output": output}

def _execute_role_task_with_locks(role_name: str, task_input: str, role_prompt: str, tools_allowlist: List[str], skills_allowlist: List[str], max_iterations: int, max_execution_time: int, workdir: str, lock_paths: List[str], lock_ttl: int, lock_owner: str, task_id: int = 0) -> Dict[str, Any]:
    effective_lock_paths = lock_paths or ([f"task:{task_id}"] if task_id else [])
    lock_result = _acquire_locks(effective_lock_paths, lock_owner, lock_ttl)
    if not lock_result.get("ok"):
        return _error_payload(
            "lock_conflict",
            "文件锁冲突",
            role=role_name,
            lock=lock_result
        )
    try:
        return _execute_role_task(
            role_name=role_name,
            task_input=task_input,
            role_prompt=role_prompt,
            tools_allowlist=tools_allowlist,
            skills_allowlist=skills_allowlist,
            max_iterations=max_iterations,
            max_execution_time=max_execution_time,
            workdir=workdir
        )
    finally:
        for item in (lock_result.get("acquired") or []):
            _release_lock_path(item.get("path"))

@tool
def create_board(goal: str, phase: str = "", milestone: str = "", roles: List[Dict[str, Any]] = None, tasks: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    创建新的公告板并覆盖旧状态。
    """
    if not _acquire_lock():
        return _error_payload("board_locked", "公告板正被占用，请稍后重试")
    try:
        now = datetime.now().isoformat()
        board = {
            "board_id": f"board-{now.replace(':','').replace('.','')}",
            "goal": goal or "",
            "phase": phase or "",
            "milestone": milestone or "",
            "roles": roles or [],
            "tasks": [],
            "messages": [],
            "created_at": now,
            "updated_at": now,
            "next_task_id": 1,
            "next_message_id": 1,
            "dead_messages": [],
            "workflows": [],
            "next_workflow_id": 1,
            "specs": []
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
                "spec_id": str(task.get("spec_id") or "").strip(),
                "spec_summary": str(task.get("spec_summary") or "").strip(),
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
        return _error_payload("board_missing", "公告板尚未创建")
    return {"ok": True, "board": board}

@tool
def add_board_role(role_name: str, description: str = "", skills: List[str] = None) -> Dict[str, Any]:
    """
    向公告板添加角色。
    """
    def _update(board):
        roles = board.get("roles") or []
        if any(r.get("name") == role_name for r in roles):
            return _error_payload("role_exists", "角色已存在")
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
def add_board_task(title: str, owner: str = "", status: str = "待处理", deps: List[Any] = None, acceptance: str = "", spec_id: str = "", spec_summary: str = "") -> Dict[str, Any]:
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
            "spec_id": str(spec_id or "").strip(),
            "spec_summary": str(spec_summary or "").strip(),
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
def update_board_task(task_id: int, status: str = "", owner: str = "", title: str = "", acceptance: str = "", spec_id: str = "", spec_summary: str = "") -> Dict[str, Any]:
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
                if spec_id:
                    task["spec_id"] = str(spec_id)
                if spec_summary:
                    task["spec_summary"] = str(spec_summary)
                task["updated_at"] = datetime.now().isoformat()
                return {"ok": True, "task": task}
        return _error_payload("task_not_found", "未找到任务")
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
        return _error_payload("task_not_found", "未找到任务")
    return _update_board_locked(_update)

@tool
def list_board_tasks(status: str = "", owner: str = "") -> Dict[str, Any]:
    """
    按状态或负责人筛选任务。
    """
    board = _load_board_locked()
    if not board:
        return _error_payload("board_missing", "公告板尚未创建")
    tasks = board.get("tasks") or []
    if status:
        status = _normalize_status(status)
        tasks = [t for t in tasks if t.get("status") == status]
    if owner:
        tasks = [t for t in tasks if t.get("owner") == owner]
    return {"ok": True, "tasks": tasks}

@tool
def create_board_tasks_from_spec(spec_id: str, spec_summary: str, p0_features: List[Dict[str, Any]], owner: str = "") -> Dict[str, Any]:
    """
    从精简 Spec 生成任务。
    """
    def _update(board):
        if not str(spec_id or "").strip():
            return _error_payload("spec_id_empty", "spec_id 不能为空")
        if not isinstance(p0_features, list) or not p0_features:
            return _error_payload("p0_features_empty", "p0_features 不能为空")
        created = []
        for item in p0_features:
            data = item or {}
            title = str(data.get("title") or data.get("name") or "").strip()
            if not title:
                continue
            acceptance = str(data.get("acceptance") or "").strip()
            task = {
                "id": board.get("next_task_id", 1),
                "title": title,
                "owner": str(data.get("owner") or owner or "").strip(),
                "status": _normalize_status("待处理"),
                "deps": data.get("deps") or [],
                "acceptance": acceptance,
                "spec_id": str(spec_id),
                "spec_summary": str(spec_summary or "").strip(),
                "outputs": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            board["tasks"] = board.get("tasks") or []
            board["tasks"].append(task)
            board["next_task_id"] = task["id"] + 1
            created.append(task)
        if not created:
            return _error_payload("p0_features_invalid", "未生成任何任务")
        return {"ok": True, "tasks": created}
    return _update_board_locked(_update)

@tool
def create_spec_and_tasks(summary: str, p0_features: List[Dict[str, Any]] = None, owner: str = "spec_agent", goal: str = "", user_scenario: str = "", steps: List[str] = None, success_outcome: str = "", constraints: List[str] = None, auto_start: bool = False, max_workers: int = 3) -> Dict[str, Any]:
    """
    自动生成精简 Spec 并创建任务，可选自动执行。
    
    Args:
        summary: 任务描述
        p0_features: P0 功能列表（可选，为空时自动拆解任务）
        owner: 负责人
        goal: 目标
        user_scenario: 用户场景
        steps: 步骤列表
        success_outcome: 成功结果
        constraints: 约束条件
        auto_start: 是否自动开始执行
        max_workers: 最大并发数
    """
    if not str(summary or "").strip():
        return _error_payload("summary_empty", "summary 不能为空")
    
    # 如果 p0_features 为空，自动调用 LLM 拆解任务
    if not p0_features:
        decompose_result = _auto_decompose_task(summary)
        if not decompose_result.get("ok"):
            return decompose_result
        p0_features = decompose_result.get("p0_features", [])
    
    spec_id = f"SPEC-{int(time.time())}"
    content = _render_simple_spec(
        spec_id=spec_id,
        summary=str(summary),
        goal=str(goal or summary),
        user_scenario=str(user_scenario or summary),
        steps=steps or [],
        success_outcome=str(success_outcome or ""),
        p0_features=p0_features or [],
        constraints=constraints or [],
        owner=str(owner or "spec_agent")
    )
    spec_path = _save_spec_file(spec_id, content)
    board_snapshot = _load_board_locked()
    if board_snapshot:
        def _update_board_spec(b):
            b["specs"] = b.get("specs") or []
            b["specs"].append({
                "id": spec_id,
                "summary": summary,
                "path": spec_path,
                "status": "draft",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "approved_at": ""
            })
            b["updated_at"] = datetime.now().isoformat()
            return {"ok": True}
        _update_board_locked(_update_board_spec)
    result = create_board_tasks_from_spec.invoke({
        "spec_id": spec_id,
        "spec_summary": str(summary),
        "p0_features": p0_features,
        "owner": owner
    })
    if not result.get("ok"):
        return result
    if auto_start:
        tasks = result.get("tasks") or []
        run_payloads = []
        for t in tasks:
            run_payloads.append({
                "task_id": t.get("id"),
                "role_name": t.get("owner") or owner or "",
                "task_input": t.get("title") or "",
                "status_after": "待验收"
            })
        if run_payloads:
            run_role_agents_parallel.invoke({
                "tasks": run_payloads,
                "max_workers": max_workers,
                "allowed_statuses": ["待处理", "需返工"]
            })
    return {
        "ok": True,
        "spec_id": spec_id,
        "spec_path": spec_path,
        "spec_content": content,
        "tasks": result.get("tasks") or [],
        "auto_start": bool(auto_start),
        "awaiting_approval": not bool(auto_start),
        "auto_decomposed": not bool(p0_features)
    }

@tool
def approve_spec(spec_id: str, auto_start: bool = False, max_workers: int = 3) -> Dict[str, Any]:
    """
    审批 Spec 并可选开始执行已生成的任务。
    """
    def _update(board):
        specs = board.get("specs") or []
        found = None
        for s in specs:
            if str(s.get("id")) == str(spec_id):
                found = s
                break
        if not found:
            return _error_payload("spec_not_found", "未找到 Spec")
        found["status"] = "approved"
        found["approved_at"] = datetime.now().isoformat()
        found["updated_at"] = datetime.now().isoformat()
        board["specs"] = specs
        board["updated_at"] = datetime.now().isoformat()
        return {"ok": True, "spec": found}
    approve_result = _update_board_locked(_update)
    if not approve_result.get("ok"):
        return approve_result
    if auto_start:
        board = _load_board_locked()
        if not board:
            return approve_result
        tasks = [t for t in (board.get("tasks") or []) if str(t.get("spec_id") or "") == str(spec_id)]
        run_payloads = []
        for t in tasks:
            run_payloads.append({
                "task_id": t.get("id"),
                "role_name": t.get("owner") or "",
                "task_input": t.get("title") or "",
                "status_after": "待验收"
            })
        if run_payloads:
            run_role_agents_parallel.invoke({
                "tasks": run_payloads,
                "max_workers": max_workers,
                "allowed_statuses": ["待处理", "需返工"]
            })
    return approve_result

@tool
def add_board_workflow(name: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    创建工作流定义。
    """
    def _update(board):
        if not str(name or "").strip():
            return _error_payload("workflow_name_empty", "name 不能为空")
        if not isinstance(steps, list) or not steps:
            return _error_payload("workflow_steps_empty", "steps 不能为空")
        normalized = []
        for idx, step in enumerate(steps):
            data = step or {}
            # 兼容 params 嵌套的情况
            if "params" in data and isinstance(data["params"], dict):
                params = data["params"]
                for k, v in params.items():
                    if k not in data:
                        data[k] = v
            
            title = str(data.get("title") or data.get("task_input") or f"步骤 {idx + 1}").strip()
            role_name = str(data.get("role_name") or data.get("owner") or "").strip()
            task_input = str(data.get("task_input") or data.get("input") or "").strip()
            deps = data.get("deps") or []
            normalized.append({
                "id": idx + 1,
                "title": title,
                "role_name": role_name,
                "role_prompt": data.get("role_prompt") or "",
                "task_input": task_input,
                "deps": deps,
                "dep_policy": data.get("dep_policy") or "",
                "status_after": data.get("status_after") or "待验收",
                "tools_allowlist": data.get("tools_allowlist") or [],
                "skills_allowlist": data.get("skills_allowlist") or [],
                "max_iterations": data.get("max_iterations") or 30,
                "max_execution_time": data.get("max_execution_time") or 300,
                "lock_paths": data.get("lock_paths") or [],
                "lock_ttl": data.get("lock_ttl") or 900,
                "workdir": data.get("workdir") or "",
                "output_dir": data.get("output_dir") or "",
                "task_id": 0,
                "status": "待处理"
            })
        wf = {
            "id": _next_workflow_id(board),
            "name": str(name),
            "status": "draft",
            "steps": normalized,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "started_at": "",
            "completed_at": ""
        }
        board["workflows"] = board.get("workflows") or []
        board["workflows"].append(wf)
        return {"ok": True, "workflow": wf}
    return _update_board_locked(_update)

@tool
def list_board_workflows(status: str = "") -> Dict[str, Any]:
    """
    列出公告板工作流。
    """
    board = _load_board_locked()
    if not board:
        return _error_payload("board_missing", "公告板尚未创建")
    workflows = board.get("workflows") or []
    if status:
        workflows = [w for w in workflows if str(w.get("status") or "") == str(status)]
    return {"ok": True, "workflows": workflows}

@tool
def start_board_workflow(workflow_id: int) -> Dict[str, Any]:
    """
    启动工作流并创建关联任务。
    """
    def _update(board):
        workflows = board.get("workflows") or []
        for wf in workflows:
            if int(wf.get("id") or 0) == int(workflow_id):
                steps = wf.get("steps") or []
                for step in steps:
                    if int(step.get("task_id") or 0) > 0:
                        continue
                    task = {
                        "id": board.get("next_task_id", 1),
                        "title": step.get("title") or "",
                        "owner": step.get("role_name") or "",
                        "status": _normalize_status(step.get("status") or "待处理"),
                        "deps": step.get("deps") or [],
                        "acceptance": "",
                        "outputs": [],
                        "workflow_id": wf.get("id"),
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                    board["tasks"] = board.get("tasks") or []
                    board["tasks"].append(task)
                    board["next_task_id"] = task["id"] + 1
                    step["task_id"] = task["id"]
                wf["steps"] = steps
                wf["status"] = "running"
                if not wf.get("started_at"):
                    wf["started_at"] = datetime.now().isoformat()
                wf["updated_at"] = datetime.now().isoformat()
                board["workflows"] = workflows
                return {"ok": True, "workflow": wf}
        return _error_payload("workflow_not_found", "未找到工作流")
    return _update_board_locked(_update)

@tool
def stop_board_workflow(workflow_id: int, status: str = "paused") -> Dict[str, Any]:
    """
    暂停或停止工作流。
    """
    def _update(board):
        workflows = board.get("workflows") or []
        for wf in workflows:
            if int(wf.get("id") or 0) == int(workflow_id):
                wf["status"] = str(status or "paused")
                wf["updated_at"] = datetime.now().isoformat()
                board["workflows"] = workflows
                return {"ok": True, "workflow": wf}
        return _error_payload("workflow_not_found", "未找到工作流")
    return _update_board_locked(_update)

@tool
def process_board_workflows(max_workers: int = 3) -> Dict[str, Any]:
    """
    推进运行中的工作流。
    """
    board = _load_board_locked()
    if not board:
        return _error_payload("board_missing", "公告板尚未创建")
    workflows = board.get("workflows") or []
    running = [w for w in workflows if str(w.get("status") or "") == "running"]
    if not running:
        return {"ok": True, "message": "无运行中的工作流", "workflows": []}
    tasks = []
    for wf in running:
        for step in wf.get("steps") or []:
            task_id = int(step.get("task_id") or 0)
            if not task_id:
                continue
            tasks.append({
                "task_id": task_id,
                "role_name": step.get("role_name") or "",
                "role_prompt": step.get("role_prompt") or "",
                "task_input": step.get("task_input") or "",
                "deps": step.get("deps") or [],
                "dep_policy": step.get("dep_policy") or "",
                "status_after": step.get("status_after") or "待验收",
                "tools_allowlist": step.get("tools_allowlist") or [],
                "skills_allowlist": step.get("skills_allowlist") or [],
                "max_iterations": step.get("max_iterations") or 30,
                "max_execution_time": step.get("max_execution_time") or 300,
                "lock_paths": step.get("lock_paths") or [],
                "lock_ttl": step.get("lock_ttl") or 900,
                "workdir": step.get("workdir") or "",
                "output_dir": step.get("output_dir") or ""
            })
    if tasks:
        run_role_agents_parallel.invoke({
            "tasks": tasks,
            "max_workers": max_workers,
            "allowed_statuses": ["待处理", "需返工"]
        })
    board_latest = _load_board_locked()
    if board_latest:
        def _update(b):
            updated = []
            for wf in b.get("workflows") or []:
                if str(wf.get("status") or "") != "running":
                    updated.append(wf)
                    continue
                all_done = True
                for step in wf.get("steps") or []:
                    task_id = int(step.get("task_id") or 0)
                    if not task_id:
                        all_done = False
                        break
                    task = _get_task_by_id(b, task_id)
                    if not task:
                        all_done = False
                        break
                    status = _normalize_status(task.get("status") or "")
                    if status not in {"已完成", "待验收"}:
                        all_done = False
                        break
                if all_done:
                    wf["status"] = "completed"
                    wf["completed_at"] = datetime.now().isoformat()
                wf["updated_at"] = datetime.now().isoformat()
                updated.append(wf)
            b["workflows"] = updated
            return {"ok": True, "workflows": updated}
        return _update_board_locked(_update)
    return {"ok": True, "workflows": running}

@tool
def send_board_message(sender: str, message: str, target: str = "", task_id: int = 0, message_type: str = "info", require_ack: bool = False, ack_timeout: int = 300, max_retries: int = 2) -> Dict[str, Any]:
    """
    发送公告板消息。
    """
    def _update(board):
        if not str(message or "").strip():
            return _error_payload("message_empty", "message 不能为空")
        messages = board.get("messages") or []
        msg = {
            "id": _next_message_id(board),
            "sender": str(sender or "").strip(),
            "target": str(target or "").strip(),
            "task_id": int(task_id or 0),
            "type": str(message_type or "info"),
            "message": str(message),
            "created_at": datetime.now().isoformat(),
            "read_by": [],
            "require_ack": bool(require_ack),
            "ack_timeout": int(ack_timeout or 0),
            "max_retries": int(max_retries or 0),
            "retry_count": 0,
            "last_retry_at": "",
            "status": "sent",
            "acked_at": ""
        }
        messages.append(msg)
        board["messages"] = messages
        board["updated_at"] = datetime.now().isoformat()
        return {"ok": True, "message": msg}
    return _update_board_locked(_update)

@tool
def list_board_messages(target: str = "", sender: str = "", task_id: int = 0, unread_for: str = "", status: str = "", limit: int = 50) -> Dict[str, Any]:
    """
    获取公告板消息列表。
    """
    board = _load_board_locked()
    if not board:
        return _error_payload("board_missing", "公告板尚未创建")
    messages = board.get("messages") or []
    if target:
        messages = [m for m in messages if str(m.get("target") or "") == str(target)]
    if sender:
        messages = [m for m in messages if str(m.get("sender") or "") == str(sender)]
    if task_id:
        messages = [m for m in messages if int(m.get("task_id") or 0) == int(task_id)]
    if unread_for:
        messages = [m for m in messages if str(unread_for) not in (m.get("read_by") or [])]
    if status:
        messages = [m for m in messages if str(m.get("status") or "") == str(status)]
    messages = messages[-max(1, int(limit or 1)):]
    return {"ok": True, "messages": messages}

@tool
def mark_board_messages_read(reader: str, message_ids: List[int]) -> Dict[str, Any]:
    """
    标记公告板消息已读。
    """
    def _update(board):
        if not reader:
            return _error_payload("reader_missing", "reader 不能为空")
        ids = set()
        for i in message_ids or []:
            try:
                ids.add(int(i))
            except Exception:
                continue
        if not ids:
            return _error_payload("message_ids_empty", "message_ids 不能为空")
        messages = board.get("messages") or []
        updated = 0
        for m in messages:
            if int(m.get("id") or 0) in ids:
                readers = m.get("read_by") or []
                if reader not in readers:
                    readers.append(reader)
                    m["read_by"] = readers
                    updated += 1
        board["messages"] = messages
        board["updated_at"] = datetime.now().isoformat()
        return {"ok": True, "updated": updated}
    return _update_board_locked(_update)

@tool
def ack_board_message(reader: str, message_id: int) -> Dict[str, Any]:
    """
    确认消息已处理。
    """
    def _update(board):
        if not reader:
            return _error_payload("reader_missing", "reader 不能为空")
        target_id = int(message_id or 0)
        if target_id <= 0:
            return _error_payload("message_id_invalid", "message_id 非法")
        messages = board.get("messages") or []
        updated = False
        for m in messages:
            if int(m.get("id") or 0) == target_id:
                readers = m.get("read_by") or []
                if reader not in readers:
                    readers.append(reader)
                    m["read_by"] = readers
                if m.get("require_ack"):
                    m["status"] = "acked"
                    m["acked_at"] = datetime.now().isoformat()
                updated = True
                break
        if not updated:
            return _error_payload("message_not_found", "未找到消息")
        board["messages"] = messages
        board["updated_at"] = datetime.now().isoformat()
        return {"ok": True, "updated": True}
    return _update_board_locked(_update)

@tool
def process_board_message_timeouts(now: str = "") -> Dict[str, Any]:
    """
    处理需要确认的超时消息，执行重试或进入死信。
    """
    def _update(board):
        messages = board.get("messages") or []
        dead = board.get("dead_messages") or []
        current = datetime.now() if not now else datetime.fromisoformat(str(now))
        retried = 0
        dead_count = 0
        retry_delays = [60, 300, 900, 1800]
        for m in messages:
            if not m.get("require_ack"):
                continue
            if str(m.get("status") or "") == "acked":
                continue
            timeout = int(m.get("ack_timeout") or 0)
            if timeout <= 0:
                continue
            base_time = m.get("last_retry_at") or m.get("created_at") or ""
            if not base_time:
                continue
            try:
                base_dt = datetime.fromisoformat(str(base_time))
            except Exception:
                continue
            delta = (current - base_dt).total_seconds()
            retry_count = int(m.get("retry_count") or 0)
            delay_idx = min(retry_count, len(retry_delays) - 1)
            next_delay = max(timeout, retry_delays[delay_idx])
            if delta <= next_delay:
                continue
            max_retries = int(m.get("max_retries") or 0)
            if retry_count < max_retries:
                m["retry_count"] = retry_count + 1
                m["last_retry_at"] = current.isoformat()
                m["status"] = "retry"
                retried += 1
            else:
                m["status"] = "dead"
                dead.append({
                    "id": m.get("id"),
                    "sender": m.get("sender"),
                    "target": m.get("target"),
                    "task_id": m.get("task_id"),
                    "message": m.get("message"),
                    "dead_at": current.isoformat()
                })
                dead_count += 1
        board["messages"] = messages
        board["dead_messages"] = dead
        board["updated_at"] = datetime.now().isoformat()
        return {"ok": True, "retried": retried, "dead": dead_count}
    return _update_board_locked(_update)

@tool
def cleanup_board_messages(max_age_days: int = 7, max_dead_messages: int = 200) -> Dict[str, Any]:
    """
    清理过期消息与过多死信。
    """
    def _update(board):
        messages = board.get("messages") or []
        dead = board.get("dead_messages") or []
        now = datetime.now()
        cutoff = now.timestamp() - max(0, int(max_age_days or 0)) * 86400
        kept = []
        removed = 0
        for m in messages:
            created = m.get("created_at") or ""
            if not created:
                kept.append(m)
                continue
            try:
                created_ts = datetime.fromisoformat(str(created)).timestamp()
            except Exception:
                kept.append(m)
                continue
            if created_ts < cutoff:
                removed += 1
                continue
            kept.append(m)
        if max_dead_messages and len(dead) > int(max_dead_messages):
            dead = dead[-int(max_dead_messages):]
        board["messages"] = kept
        board["dead_messages"] = dead
        board["updated_at"] = datetime.now().isoformat()
        return {"ok": True, "removed": removed, "remaining": len(kept), "dead_remaining": len(dead)}
    return _update_board_locked(_update)

@tool
def get_board_message_health() -> Dict[str, Any]:
    """
    获取消息队列健康指标。
    """
    board = _load_board_locked()
    if not board:
        return _error_payload("board_missing", "公告板尚未创建")
    messages = board.get("messages") or []
    dead = board.get("dead_messages") or []
    unacked = [m for m in messages if m.get("require_ack") and str(m.get("status") or "") != "acked"]
    oldest_age = 0
    now = datetime.now()
    for m in messages:
        created = m.get("created_at") or ""
        if not created:
            continue
        try:
            age = (now - datetime.fromisoformat(str(created))).total_seconds()
        except Exception:
            continue
        if age > oldest_age:
            oldest_age = age
    return {
        "ok": True,
        "total_messages": len(messages),
        "unacked_messages": len(unacked),
        "dead_messages": len(dead),
        "oldest_message_age_sec": int(oldest_age)
    }

@tool
def check_and_notify_board_health(dead_threshold: int = 10, target: str = "admin", message_type: str = "warning") -> Dict[str, Any]:
    """
    检查消息健康并在死信过多时发出告警。
    """
    board = _load_board_locked()
    if not board:
        return _error_payload("board_missing", "公告板尚未创建")
    health = get_board_message_health.invoke({})
    if not health.get("ok"):
        return health
    dead_count = int(health.get("dead_messages") or 0)
    if dead_count < int(dead_threshold or 0):
        return {"ok": True, "notified": False, "dead_messages": dead_count}
    alert_message = f"死信数量过多: {dead_count}"
    def _update(b):
        msg = {
            "id": _next_message_id(b),
            "sender": "system",
            "target": str(target or "admin"),
            "task_id": 0,
            "type": str(message_type or "warning"),
            "message": alert_message,
            "created_at": datetime.now().isoformat(),
            "read_by": [],
            "require_ack": False,
            "ack_timeout": 0,
            "max_retries": 0,
            "retry_count": 0,
            "last_retry_at": "",
            "status": "sent",
            "acked_at": ""
        }
        b["messages"] = (b.get("messages") or []) + [msg]
        b["updated_at"] = datetime.now().isoformat()
        return {"ok": True, "notified": True, "message": msg, "dead_messages": dead_count}
    return _update_board_locked(_update)

def _get_task_by_id(board: Dict[str, Any], task_id: int) -> Optional[Dict[str, Any]]:
    tasks = board.get("tasks") or []
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None

def _get_workflow_by_id(board: Dict[str, Any], workflow_id: int) -> Optional[Dict[str, Any]]:
    workflows = board.get("workflows") or []
    for wf in workflows:
        if int(wf.get("id") or 0) == int(workflow_id):
            return wf
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
def run_role_agent(role_name: str, task_input: str, role_prompt: str = "", tools_allowlist: List[str] = None, skills_allowlist: List[str] = None, task_id: int = 0, status_after: str = "待验收", max_iterations: int = None, max_execution_time: int = None, context: str = "", summary: str = "", output_dir: str = "", workdir: str = "", lock_paths: List[str] = None, lock_ttl: int = 900) -> Dict[str, Any]:
    """
    创建角色 Agent 并执行单次任务，返回输出结果。
    """
    board_snapshot = _load_board_locked()
    task = _get_task_by_id(board_snapshot, int(task_id)) if board_snapshot and task_id else None
    env_workdir = (os.getenv("AGENT_WORKDIR") or "").strip()
    if env_workdir and not os.path.isabs(env_workdir):
        env_workdir = os.path.abspath(env_workdir)
    if env_workdir:
        os.makedirs(env_workdir, exist_ok=True)
    effective_workdir = (workdir or output_dir or "").strip() or env_workdir or _get_board_output_dir()
    payload = {"context": context, "summary": summary, "output_dir": output_dir, "workdir": workdir, "role_name": role_name}
    if not output_dir and not workdir:
        payload["output_dir"] = effective_workdir
    merged_input = _compose_task_input(task_input, payload, board_snapshot, task)
    selected_workdir = effective_workdir
    lock_owner = role_name or f"task_{task_id or 'role'}"
    effective_lock_paths = lock_paths or ([f"task:{task_id}"] if task_id else [])
    lock_result = _acquire_locks(effective_lock_paths, lock_owner, lock_ttl)
    if not lock_result.get("ok"):
        return _error_payload(
            "lock_conflict",
            "文件锁冲突",
            role=role_name,
            task_id=task_id,
            lock=lock_result
        )
    try:
        result = _execute_role_task(
            role_name=role_name,
            task_input=merged_input,
            role_prompt=role_prompt,
            tools_allowlist=tools_allowlist,
            skills_allowlist=skills_allowlist,
            max_iterations=max_iterations,
            max_execution_time=max_execution_time,
            workdir=selected_workdir
        )
    finally:
        for item in (lock_result.get("acquired") or []):
            _release_lock_path(item.get("path"))
    output = result.get("output")
    if task_id:
        append_board_task_output.invoke({
            "task_id": task_id,
            "output": output,
            "output_type": "role_result"
        })
        current_status = _normalize_status((task or {}).get("status") or "")
        should_update = current_status != "已完成"
        if result.get("stopped"):
            # shared.clear_stop() # 不要清除
            if should_update:
                update_board_task.invoke({"task_id": task_id, "status": "待处理"})
        elif result.get("ok"):
            if status_after and should_update:
                update_board_task.invoke({"task_id": task_id, "status": status_after})
        else:
            if should_update:
                update_board_task.invoke({"task_id": task_id, "status": "需返工"})
    return result

@tool
def run_role_agents_parallel(tasks: List[Dict[str, Any]], max_workers: int = 3, status_after: str = "待验收", allowed_statuses: List[str] = None, dep_policy: str = "") -> Dict[str, Any]:
    """
    并发运行多个角色 Agent。
    """
    if shared.stop_requested:
        shared.clear_stop()
        shared.set_status("stopped", "已停止", "")
        return _error_payload("stopped", "已停止", stopped=True, results=[])
    items = tasks or []
    if not isinstance(items, list) or not items:
        return _error_payload("invalid_args", "tasks 不能为空")
    worker_count = max(1, min(int(max_workers or 3), 10))
    allow_status = allowed_statuses if allowed_statuses is not None else ["待处理", "需返工"]
    allow_status = [_normalize_status(s) for s in (allow_status or [])]
    results = []
    success_count = 0
    error_count = 0
    skipped_count = 0
    effective_policy = dep_policy or "all"
    pending = [{"index": idx, "task": (item or {})} for idx, item in enumerate(items)]
    stopped_found = False
    while pending:
        if shared.stop_requested:
            shared.clear_stop()
            shared.set_status("stopped", "已停止", "")
            return _error_payload(
                "stopped",
                "已停止",
                stopped=True,
                total=len(items),
                success_count=success_count,
                error_count=error_count,
                skipped_count=skipped_count,
                results=sorted(results, key=lambda x: x.get("index", 0)),
            )
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
                working_payload = payload
                if "role_name" not in working_payload:
                    working_payload = dict(working_payload)
                    working_payload["role_name"] = payload.get("role_name") or ""
                selected_workdir = payload.get("workdir") or payload.get("output_dir") or payload.get("target_dir") or payload.get("directory") or ""
                if not selected_workdir:
                    env_workdir = (os.getenv("AGENT_WORKDIR") or "").strip()
                    if env_workdir and not os.path.isabs(env_workdir):
                        env_workdir = os.path.abspath(env_workdir)
                    if env_workdir:
                        os.makedirs(env_workdir, exist_ok=True)
                    selected_workdir = env_workdir or _get_board_output_dir()
                    working_payload = dict(payload)
                    if not working_payload.get("workdir") and not working_payload.get("output_dir"):
                        working_payload["output_dir"] = selected_workdir
                merged_input = _compose_task_input(working_payload.get("task_input") or "", working_payload, board_snapshot, task)
                lock_owner = payload.get("role_name") or f"task_{payload.get('task_id') or meta['index']}"
                future = executor.submit(
                    _execute_role_task_with_locks,
                    role_name=payload.get("role_name") or "",
                    task_input=merged_input,
                    role_prompt=payload.get("role_prompt") or "",
                    tools_allowlist=payload.get("tools_allowlist") or [],
                    skills_allowlist=payload.get("skills_allowlist") or [],
                    max_iterations=payload.get("max_iterations"),
                    max_execution_time=payload.get("max_execution_time"),
                    workdir=selected_workdir,
                    lock_paths=payload.get("lock_paths") or [],
                    lock_ttl=payload.get("lock_ttl") or 900,
                    lock_owner=lock_owner,
                    task_id=int(payload.get("task_id") or 0)
                )
                futures[future] = meta
            
            # 使用 wait 和超时机制，以便及时响应停止请求
            while futures:
                if shared.stop_requested:
                    stopped_found = True
                    # 取消所有剩余任务
                    for f in futures:
                        f.cancel()
                    break

                done, _ = wait(list(futures.keys()), return_when=FIRST_COMPLETED, timeout=0.5)
                if not done:
                    continue

                for future in done:
                    meta = futures[future]
                    del futures[future]
                    payload = meta["task"]
                    try:
                        result = future.result()
                        task_id = payload.get("task_id")
                        if task_id:
                            append_board_task_output.invoke({
                                "task_id": int(task_id),
                                "output": result.get("output") or "",
                                "output_type": "role_result"
                            })
                            task = _get_task_by_id(board_snapshot, int(task_id)) if board_snapshot else None
                            current_status = _normalize_status((task or {}).get("status") or "")
                            should_update = current_status != "已完成"
                            desired_status = None
                            if result.get("stopped"):
                                desired_status = "待处理"
                                stopped_found = True
                            elif result.get("ok"):
                                desired_status = payload.get("status_after") or status_after
                            else:
                                desired_status = "需返工"
                            if desired_status and should_update:
                                update_board_task.invoke({
                                    "task_id": int(task_id),
                                    "status": desired_status
                                })
                        if result.get("ok"):
                            success_count += 1
                            results.append({"ok": True, "index": meta["index"], "result": result})
                        elif result.get("stopped"):
                            results.append({"ok": False, "stopped": True, "index": meta["index"], "result": result})
                        else:
                            error_count += 1
                            results.append({"ok": False, "index": meta["index"], "result": result})
                    except Exception as e:
                        error_count += 1
                        shared.set_error(str(e))
                        results.append({"ok": False, "index": meta["index"], "error": str(e), "task": payload})
        if stopped_found or shared.stop_requested:
            # shared.clear_stop() # 不要清除，让上层感知
            shared.set_status("stopped", "已停止", "")
            break
        pending = blocked
    results = sorted(results, key=lambda x: x.get("index", 0))
    return {
        "ok": (error_count == 0) and (not stopped_found),
        "total": len(items),
        "success_count": success_count,
        "error_count": error_count,
        "skipped_count": skipped_count,
        "stopped": stopped_found,
        "results": results
    }




def _auto_decompose_task(summary: str) -> Dict[str, Any]:
    """
    使用 LLM 自动拆解任务，生成 p0_features 列表。
    
    Args:
        summary: 任务描述
        
    Returns:
        包含 p0_features 的字典，格式：{"ok": True, "p0_features": [...]}
        或错误信息：{"ok": False, "error": "..."}
    """
    if not str(summary or "").strip():
        return _error_payload("summary_empty", "任务描述不能为空")
    
    # 预定义角色列表
    available_roles = [
        "产品分析师",
        "开发工程师",
        "测试工程师",
        "数据分析师",
        "运维工程师",
        "技术文档工程师",
        "UI/UX 设计师",
        "执行工程师"
    ]
    
    roles_str = "、".join(available_roles)
    
    prompt = f"""你是一个专业的任务拆解专家。请分析以下任务，将其拆解成多个可并行的子任务。

任务描述：
{summary}

请为每个子任务指定：
1. title: 任务标题（简洁描述，20 字以内）
2. owner: 负责人角色（从以下角色中选择最合适的：{roles_str}）
3. acceptance: 验收标准（具体可验证的成果）
4. deps: 依赖的任务 ID 列表（如果没有依赖，填空数组 []）

返回 JSON 数组格式，例如：
[
    {{
        "title": "需求分析与 PRD 文档",
        "owner": "产品分析师",
        "acceptance": "完成 PRD 文档，包含用户故事、功能列表和验收标准",
        "deps": []
    }},
    {{
        "title": "数据库设计",
        "owner": "开发工程师",
        "acceptance": "完成数据库表结构设计，包含 ER 图和建表 SQL",
        "deps": [1]
    }},
    {{
        "title": "后端 API 开发",
        "owner": "开发工程师",
        "acceptance": "完成 RESTful API 开发，通过单元测试",
        "deps": [2]
    }}
]

要求：
1. 子任务数量根据任务复杂度决定（简单任务 2-3 个，复杂任务 5-8 个）
2. 合理分配角色，不要所有任务都分配给同一个角色
3. 正确识别任务依赖关系（如：开发依赖设计，测试依赖开发）
4. 验收标准要具体可验证

只返回 JSON 数组，不要包含其他文字说明。"""

    try:
        # 调用 LLM（使用 run_role_agent 的简化方式）
        from app.skills.board_skill.scripts.board_tools import _invoke_llm_simple
        
        response_text = _invoke_llm_simple(prompt, max_tokens=2000)
        
        if not response_text:
            return _error_payload("llm_empty_response", "LLM 返回为空")
        
        # 尝试解析 JSON
        import json
        import re
        
        # 提取 JSON 数组（处理可能的 Markdown 格式）
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
        else:
            json_str = response_text
        
        p0_features = json.loads(json_str)
        
        if not isinstance(p0_features, list):
            return _error_payload("invalid_format", "LLM 返回的不是数组格式")
        
        # 验证每个任务的格式
        validated_features = []
        for i, feature in enumerate(p0_features):
            if not isinstance(feature, dict):
                continue
            
            title = feature.get("title", f"任务{i+1}")
            owner = feature.get("owner", "执行工程师")
            acceptance = feature.get("acceptance", "完成任务")
            deps = feature.get("deps", [])
            
            # 验证角色是否合法
            if owner not in available_roles:
                owner = "执行工程师"
            
            # 验证 deps 是否为数字列表
            if not isinstance(deps, list):
                deps = []
            else:
                deps = [int(d) for d in deps if isinstance(d, (int, float))]
            
            validated_features.append({
                "title": str(title),
                "owner": str(owner),
                "acceptance": str(acceptance),
                "deps": deps
            })
        
        if not validated_features:
            return _error_payload("no_valid_features", "未生成有效的子任务")
        
        return {"ok": True, "p0_features": validated_features}
        
    except json.JSONDecodeError as e:
        return _error_payload("json_parse_error", f"JSON 解析失败：{str(e)}")
    except Exception as e:
        return _error_payload("decompose_error", f"任务拆解失败：{str(e)}")


def _invoke_llm_simple(prompt: str, max_tokens: int = 2000) -> str:
    """
    简化版 LLM 调用函数。
    
    Args:
        prompt: 提示词
        max_tokens: 最大 token 数
        
    Returns:
        LLM 返回的文本
    """
    try:
        # 尝试使用 run_role_agent 调用 LLM
        result = run_role_agent.invoke({
            "role_name": "执行工程师",
            "task_input": prompt,
            "role_prompt": "你是一个专业的 AI 助手，直接回答用户的问题。",
            "max_iterations": 1,
            "max_execution_time": 60
        })
        
        if result.get("ok"):
            return result.get("output", "")
        return ""
    except Exception:
        return ""