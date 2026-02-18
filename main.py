import os
import platform
import ctypes
import sys
import re
import threading
import queue
import json
import sqlite3
import urllib.request
import urllib.error
import subprocess
import atexit
import time
from datetime import datetime, timezone
from typing import List, Set
from web.backend.main import start as start_web_server
from web.backend.shared import shared

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HUGGINGFACE_HUB_ENDPOINT", "https://hf-mirror.com")

from app.agent import create_agent_executor, create_llm
from app.skills.system_skill.scripts.experience_tools import add_operation_experience, get_operation_experience
from langchain.callbacks.base import BaseCallbackHandler

RELOAD_SIGNAL = "__RELOAD_SKILLS__"
SET_MODEL_PREFIX = "__SET_MODEL__:"
WA_IN_PREFIX = "__WA_IN__:"
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[ -/]*[@-~]")

_gateway_process = None

def _env_flag(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}

def _select_skill_allowlist(user_input: str) -> List[str]:
    text = str(user_input or "").lower()
    skills: Set[str] = {"skillgen_skill", "board_skill", "system_skill"}
    def has_any(keys: List[str]) -> bool:
        return any(k in text for k in keys)
    if "http://" in text or "https://" in text or has_any(["网页", "浏览器", "网站", "web", "登录", "跳转", "url"]):
        skills.update(["playwright_skill", "browser_skill"])
    if has_any(["窗口", "控件", "uia", "桌面", "点击", "鼠标", "键盘", "输入", "激活窗口"]):
        skills.update(["uia_skill", "input_skill", "pyautogui_skill"])
    if has_any(["ocr", "识别", "截图", "验证码", "图像", "视觉"]):
        skills.update(["ocr_skill", "vision_ocr_skill", "eyes_skill"])
    if has_any(["文件", "目录", "路径", "移动", "复制", "拷贝", "删除", "重命名", "保存", "excel", "xlsx", "csv", "表格"]):
        skills.update(["file_skill", "file_directory_skill", "file_save_skill", "office_skill"])
    if has_any(["搜索", "查询", "检索", "谷歌", "bing", "google"]):
        skills.add("tavily_skill")
    if has_any(["新闻", "热点", "gnews"]):
        skills.add("gnews_skill")
    if has_any(["钉钉", "dingtalk"]):
        skills.add("dingtalk_skill")
    if has_any(["飞书", "feishu"]):
        skills.add("feishu_skill")
    if has_any(["定时", "计划任务", "scheduled task"]):
        skills.add("windows_task_skill")
    if has_any(["计算", "calculator", "算一下"]):
        skills.add("utility_skill")
    return sorted(skills)

def _wa_gateway_base_url():
    host = (os.getenv("WA_GATEWAY_HOST") or "127.0.0.1").strip()
    try:
        port = int(os.getenv("WA_GATEWAY_PORT") or 8787)
    except Exception:
        port = 8787
    return f"http://{host}:{port}"

def _wa_gateway_is_running() -> bool:
    try:
        with urllib.request.urlopen(_wa_gateway_base_url() + "/health", timeout=1.5) as resp:
            return 200 <= int(getattr(resp, "status", 0) or 0) < 300
    except Exception:
        return False

def _start_wa_gateway_subprocess():
    global _gateway_process
    if _gateway_process is not None:
        return
    if _env_flag("WA_GATEWAY_AUTOSTART", True) is False:
        return
    if _wa_gateway_is_running():
        return
    base_dir = os.path.dirname(os.path.abspath(__file__))
    gateway_dir = os.path.join(base_dir, "gateway")
    if not os.path.isdir(gateway_dir):
        return
    node_bin = (os.getenv("WA_NODE_BIN") or "node").strip()
    try:
        _gateway_process = subprocess.Popen(
            [node_bin, "index.js"],
            cwd=gateway_dir,
            env=os.environ.copy(),
        )
    except Exception as e:
        print(f">>> 系统: 启动 WA Gateway 失败: {e}")
        _gateway_process = None
        return

    def _cleanup():
        global _gateway_process
        proc = _gateway_process
        _gateway_process = None
        if proc is None:
            return
        try:
            proc.terminate()
        except Exception:
            return

    atexit.register(_cleanup)

def _extract_whatsapp_input(raw: str):
    text = str(raw or "").strip()
    if not text.startswith(WA_IN_PREFIX):
        return None, text
    payload_raw = text[len(WA_IN_PREFIX):].strip()
    try:
        data = json.loads(payload_raw)
    except Exception:
        return None, ""
    if not isinstance(data, dict):
        return None, ""
    chat_jid = str(data.get("chatJid") or "").strip()
    msg_text = str(data.get("text") or "").strip()
    sender_e164 = str(data.get("senderE164") or "").strip()
    if not chat_jid or not msg_text:
        return None, ""
    return {"chatJid": chat_jid, "senderE164": sender_e164}, msg_text

def _send_whatsapp_reply(chat_jid: str, text: str):
    token = (os.getenv("WA_GATEWAY_TOKEN") or "").strip()
    if not token:
        return False
    host = (os.getenv("WA_GATEWAY_HOST") or "127.0.0.1").strip()
    try:
        port = int(os.getenv("WA_GATEWAY_PORT") or 8787)
    except Exception:
        port = 8787
    url = f"http://{host}:{port}/send"
    body = json.dumps({"to": chat_jid, "text": text}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= int(getattr(resp, "status", 0) or 0) < 300
    except Exception:
        return False

def _get_short_term_db_path(date_key: str = None):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "app", "data")
    os.makedirs(data_dir, exist_ok=True)
    if not date_key:
        date_key = datetime.now(timezone.utc).strftime("%Y%m%d")
    return os.path.join(data_dir, f"short_term_memory_{date_key}.sqlite3")

def _get_short_term_md_dir():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "app", "data", "short_term_markdown")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def _sanitize_filename(value: str):
    text = str(value or "").strip().replace(" ", "_")
    cleaned = "".join(ch for ch in text if ch.isalnum() or ch in ("_", "-", "."))
    return cleaned or "default"

def _append_short_term_markdown(role: str, content: str, created_at: str, project_id: str, user_id: str, date_key: str):
    if not content:
        return
    folder = _get_short_term_md_dir()
    name = f"short_term_{_sanitize_filename(project_id)}_{_sanitize_filename(user_id)}_{date_key}.md"
    path = os.path.join(folder, name)
    header = f"# Short Term Memory\n\n- Project: {project_id}\n- User: {user_id}\n\n"
    body = str(content).replace("\r\n", "\n").replace("\r", "\n")
    body = body.replace("\n", "\n  ")
    line = f"- **{created_at}** `{role}`\n  {body}\n"
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(header)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)

def _init_short_term_db(date_key: str = None):
    path = _get_short_term_db_path(date_key)
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS short_term_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                project_id TEXT,
                user_id TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_stm_created ON short_term_messages(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_stm_project_user ON short_term_messages(project_id, user_id)")
        cur.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS short_term_messages_fts
            USING fts5(content, role, created_at, project_id, user_id)
            """
        )
        conn.commit()
    finally:
        conn.close()

def _add_short_term_message(role: str, content: str, project_id: str, user_id: str):
    text = str(content or "").strip()
    if not text:
        return
    created_at = datetime.now(timezone.utc).isoformat()
    date_key = created_at[:10].replace("-", "")
    _init_short_term_db(date_key)
    path = _get_short_term_db_path(date_key)
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO short_term_messages(role, content, created_at, project_id, user_id) VALUES (?, ?, ?, ?, ?)",
            (str(role or "").strip(), text, created_at, project_id or "", user_id or ""),
        )
        cur.execute(
            "INSERT INTO short_term_messages_fts(content, role, created_at, project_id, user_id) VALUES (?, ?, ?, ?, ?)",
            (text, str(role or "").strip(), created_at, project_id or "", user_id or ""),
        )
        conn.commit()
    finally:
        conn.close()
    _append_short_term_markdown(role, text, created_at, project_id or "", user_id or "", date_key)


class ShortTermToolTraceHandler(BaseCallbackHandler):
    def __init__(self, project_id: str, user_id: str, max_len: int = 2000):
        self.project_id = project_id or ""
        self.user_id = user_id or ""
        self.max_len = max_len
        self._starts = {}

    def _try_parse_json(self, value):
        if not isinstance(value, str):
            return None
        return _parse_json_object_from_text(value)

    def _extract_file_summary(self, tool_name: str, data):
        payload = data
        if isinstance(payload, str):
            parsed = self._try_parse_json(payload)
            if parsed is not None:
                payload = parsed
        if not isinstance(payload, dict):
            return None
        file_path = payload.get("file_path") or payload.get("path") or payload.get("file")
        stats = payload.get("stats")
        if not file_path and isinstance(stats, dict):
            file_path = stats.get("file_path") or stats.get("path")
        if not file_path:
            return None
        start_line = payload.get("start_line")
        end_line = payload.get("end_line")
        line_number = payload.get("line_number")
        message = payload.get("message") if isinstance(payload.get("message"), str) else ""
        if (start_line is None or end_line is None) and message:
            m = re.search(r"行\\s*(\\d+)\\s*-\\s*(\\d+)", message)
            if m:
                start_line = start_line if start_line is not None else int(m.group(1))
                end_line = end_line if end_line is not None else int(m.group(2))
        content = payload.get("content")
        line_count = None
        if content is not None:
            line_count = len(str(content).splitlines())
        if line_number is not None:
            start_line = int(line_number)
            end_line = int(line_number)
        if start_line is None and end_line is None and line_count:
            start_line = 1
            end_line = line_count
        summary = {"file": file_path}
        try:
            summary["name"] = os.path.basename(str(file_path))
        except Exception:
            pass
        if start_line is not None:
            if end_line is not None:
                summary["lines"] = f"{int(start_line)}-{int(end_line)}"
            else:
                summary["lines"] = str(int(start_line))
        return summary

    def _compact_payload(self, payload: dict):
        event = payload.get("event")
        tool_name = payload.get("tool") or ""
        if event == "tool_start":
            info = self._extract_file_summary(tool_name, payload.get("input"))
            if info:
                payload["input"] = info
        elif event == "tool_end":
            info = self._extract_file_summary(tool_name, payload.get("output"))
            if info:
                payload["output"] = info
        elif event == "agent_action":
            info = self._extract_file_summary(tool_name, payload.get("tool_input"))
            if info:
                payload["tool_input"] = info
        return payload

    def _emit(self, payload: dict):
        payload = self._compact_payload(payload)
        try:
            text = json.dumps(payload, ensure_ascii=False)
        except Exception:
            text = str(payload)
        if self.max_len and len(text) > self.max_len:
            text = text[: self.max_len] + "…"
        _add_short_term_message("tool", text, self.project_id, self.user_id)

    def on_tool_start(self, serialized, input_str=None, **kwargs):
        tool_name = None
        if isinstance(serialized, dict):
            tool_name = serialized.get("name") or serialized.get("id")
        run_id = kwargs.get("run_id")
        inputs = kwargs.get("inputs")
        payload = {
            "event": "tool_start",
            "tool": tool_name,
            "input": input_str if input_str is not None else inputs,
            "time": datetime.now(timezone.utc).isoformat()
        }
        if run_id:
            self._starts[run_id] = {"t": time.monotonic(), "tool": tool_name}
        self._emit(payload)

    def on_tool_end(self, output, **kwargs):
        run_id = kwargs.get("run_id")
        info = self._starts.pop(run_id, None) if run_id else None
        duration_ms = None
        tool_name = None
        if info:
            tool_name = info.get("tool")
            duration_ms = int((time.monotonic() - info.get("t", time.monotonic())) * 1000)
        payload = {
            "event": "tool_end",
            "tool": tool_name,
            "output": output,
            "time": datetime.now(timezone.utc).isoformat()
        }
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        self._emit(payload)

    def on_tool_error(self, error, **kwargs):
        run_id = kwargs.get("run_id")
        info = self._starts.pop(run_id, None) if run_id else None
        payload = {
            "event": "tool_error",
            "tool": info.get("tool") if info else None,
            "error": str(error),
            "time": datetime.now(timezone.utc).isoformat()
        }
        self._emit(payload)

    def on_agent_action(self, action, **kwargs):
        payload = {
            "event": "agent_action",
            "tool": getattr(action, "tool", None),
            "tool_input": getattr(action, "tool_input", None),
            "log": getattr(action, "log", None),
            "time": datetime.now(timezone.utc).isoformat()
        }
        self._emit(payload)

    def on_agent_finish(self, finish, **kwargs):
        payload = {
            "event": "agent_finish",
            "output": getattr(finish, "return_values", None),
            "log": getattr(finish, "log", None),
            "time": datetime.now(timezone.utc).isoformat()
        }
        self._emit(payload)

def _requests_all_memory_search(text: str):
    t = str(text or "").strip()
    if not t:
        return False
    keywords = ["搜索所有记忆", "搜所有记忆", "搜索全部记忆", "搜全部记忆", "全量搜索记忆", "搜索全量记忆"]
    return any(k in t for k in keywords)

def parse_state(output: str):
    def normalize_state(value: str):
        if value is None:
            return None
        v = str(value).strip().upper()
        v = re.sub(r"[^\w]+$", "", v)
        if v.startswith("DONE"):
            return "DONE"
        if v.startswith("CONTINUE"):
            return "CONTINUE"
        return v or None

    lines = [line.rstrip("\n") for line in output.splitlines() if line.strip()]
    if not lines:
        return None, output

    state = None
    state_idx = None
    for i in range(len(lines) - 1, -1, -1):
        m = re.match(r"^\s*STATE\s*[:：]\s*(.+?)\s*$", lines[i], flags=re.IGNORECASE)
        if not m:
            continue
        state = normalize_state(m.group(1))
        state_idx = i
        break

    if state is None or state_idx is None:
        return None, output

    kept = []
    for idx, line in enumerate(lines):
        if idx == state_idx:
            continue
        kept.append(line.strip())
    cleaned = "\n".join([line_text for line_text in kept if line_text]).strip()
    return state, cleaned

def strip_reload_signal(output: str):
    if not output:
        return output, False
    lines = output.splitlines()
    kept = [line for line in lines if RELOAD_SIGNAL not in line]
    changed = len(kept) != len(lines)
    return "\n".join(kept).strip(), changed

def _format_history_for_summary(messages):
    lines = []
    for role, content in messages:
        if role == "assistant":
            content, _ = strip_reload_signal(content)
        lines.append(f"{role}: {content}")
    return "\n\n".join(lines).strip()

def _extract_project_id():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.basename(base_dir)

def _get_task_plan_path():
    return os.path.join(os.path.dirname(__file__), "app", "skills", "system_skill", "scripts", "current_task_plan.json")

def _load_task_plan():
    path = _get_task_plan_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _get_next_pending_step(plan):
    if not plan:
        return None
    steps = plan.get("steps") or []
    for step in steps:
        if step.get("status") == "pending":
            return step
    return None

def _normalize_tags(tags):
    if not tags:
        return []
    cleaned = []
    for tag in tags:
        if not tag:
            continue
        item = str(tag).strip()
        if item:
            cleaned.append(item)
    return list(dict.fromkeys(cleaned))

def _build_cognition_summary(chat_history, llm, project_id, user_id):
    transcript = _format_history_for_summary(chat_history[-40:])
    system_text = "你是个人认知总结器。基于对话内容抽取稳定偏好与可复用经验，输出严格 JSON。字段: summary_type, project, user_id, items{behavior_preferences, code_style_preferences, task_experiences}, task_templates, sources, proposed_tags。若对话包含明确完成的可复用流程，必须在 task_experiences 提供 1-3 条，描述流程与关键决策，不包含一次性数据。若 task_experiences 非空且流程可抽象，task_templates 必须输出至少 1 个对象，字段: name, trigger_keywords, steps, inputs, outputs, constraints, tags。没有内容的数组输出空数组。只输出 JSON，不要额外文本。"
    user_text = f"项目: {project_id}\n用户: {user_id}\n对话:\n{transcript}\n\n请输出 JSON："
    from langchain_core.messages import SystemMessage, HumanMessage
    resp = llm.invoke([SystemMessage(content=system_text), HumanMessage(content=user_text)])
    content = getattr(resp, "content", "") or str(resp)
    return content.strip()

def _build_task_reflection(chat_history, llm, project_id, user_id):
    transcript = _format_history_for_summary(chat_history[-50:])
    system_text = "你是任务复盘器。基于对话与执行过程进行复盘，输出严格 JSON。字段: project, user_id, blockers, mistakes, improvements{template, prompt, skill}, evidence, proposed_tags。blockers/mistakes/evidence 为字符串数组；improvements 各字段为字符串数组。无法判断则输出空数组或空对象。只输出 JSON，不要额外文本。"
    user_text = f"项目: {project_id}\n用户: {user_id}\n对话:\n{transcript}\n\n请输出 JSON："
    from langchain_core.messages import SystemMessage, HumanMessage
    resp = llm.invoke([SystemMessage(content=system_text), HumanMessage(content=user_text)])
    content = getattr(resp, "content", "") or str(resp)
    return content.strip()

def _ensure_task_templates(summary_data, chat_history, llm, project_id, user_id):
    if not isinstance(summary_data, dict):
        return summary_data
    items = summary_data.get("items") or {}
    tasks = items.get("task_experiences") or []
    templates = summary_data.get("task_templates") or []
    if templates:
        return summary_data
    if not tasks:
        plan = _load_task_plan()
        tasks = _build_task_experiences_from_plan(plan)
        if tasks:
            if "items" not in summary_data or not isinstance(summary_data.get("items"), dict):
                summary_data["items"] = {}
            summary_data["items"]["task_experiences"] = tasks
        else:
            return summary_data
    transcript = _format_history_for_summary(chat_history[-40:])
    system_text = "你是任务模板抽象器。根据对话与任务经验抽象 1-2 个可复用模板，输出严格 JSON 数组。每个对象字段: name, trigger_keywords, steps, inputs, outputs, constraints, tags。若无法抽象则输出空数组。只输出 JSON，不要额外文本。"
    user_text = f"项目: {project_id}\n用户: {user_id}\n任务经验:\n{json.dumps(tasks, ensure_ascii=False)}\n\n对话:\n{transcript}\n\n请输出 JSON 数组："
    from langchain_core.messages import SystemMessage, HumanMessage
    resp = llm.invoke([SystemMessage(content=system_text), HumanMessage(content=user_text)])
    content = getattr(resp, "content", "") or str(resp)
    data = _parse_json_list_from_text(content)
    if isinstance(data, dict):
        data = data.get("task_templates")
    if not isinstance(data, list):
        return summary_data
    cleaned = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        steps = item.get("steps") or []
        if not name or not isinstance(steps, list) or not steps:
            continue
        cleaned.append(item)
    if cleaned:
        summary_data["task_templates"] = cleaned
    return summary_data

def _parse_json_list_from_text(text):
    if not text:
        return None
    cleaned = str(text).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            pass
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None
    return None

def _parse_json_object_from_text(text):
    if not text:
        return None
    cleaned = str(text).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            return None
    return None

def _build_task_experiences_from_plan(plan):
    if not isinstance(plan, dict):
        return []
    steps = plan.get("steps") or []
    if not steps:
        return []
    parts = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        desc = str(step.get("desc") or "").strip()
        if not desc:
            continue
        result = str(step.get("result") or "").strip()
        if result:
            parts.append(f"{desc} -> {result}")
        else:
            parts.append(desc)
    if not parts:
        return []
    summary = "任务计划步骤: " + "; ".join(parts)
    return [summary]

def _save_cognition_summary(summary, project_id, user_id):
    items = summary.get("items") or {}
    task_templates = summary.get("task_templates") or []
    proposed_tags = _normalize_tags(summary.get("proposed_tags") or [])
    base_tags = proposed_tags + [f"project:{project_id}"]
    saved = []

    def save_items(values, scope, memory_type, topic_tag):
        if not values:
            return
        for value in values:
            content = str(value).strip()
            if not content:
                continue
            tags = _normalize_tags(base_tags + [f"scope:{scope}", topic_tag])
            result = add_operation_experience.invoke({
                "system_name": "personal_cognition",
                "content": content,
                "tags": tags,
                "scope": scope,
                "project_id": project_id,
                "user_id": user_id,
                "memory_type": memory_type
            })
            saved.append(result)

    save_items(items.get("behavior_preferences"), "user", "behavior", "topic:behavior")
    save_items(items.get("code_style_preferences"), "user", "code_style", "topic:code_style")
    save_items(items.get("task_experiences"), "project", "task", "topic:task")
    _save_task_templates(task_templates, project_id, user_id, base_tags, saved)

    return saved

def _save_task_reflection(reflection, project_id, user_id):
    data = reflection if isinstance(reflection, dict) else None
    proposed_tags = _normalize_tags(data.get("proposed_tags") or []) if data else []
    tags = _normalize_tags(proposed_tags + ["scope:project", f"project:{project_id}", "topic:reflection"])
    content = json.dumps(data, ensure_ascii=False, indent=2) if data else str(reflection)
    return add_operation_experience.invoke({
        "system_name": "task_reflection",
        "content": content,
        "tags": tags,
        "scope": "project",
        "project_id": project_id,
        "user_id": user_id,
        "memory_type": "reflection"
    })

def _save_task_templates(task_templates, project_id, user_id, base_tags, saved):
    if not task_templates:
        return
    for template in task_templates:
        if not isinstance(template, dict):
            continue
        name = str(template.get("name") or "").strip()
        if not name:
            continue
        tags = _normalize_tags(base_tags + ["scope:project", "topic:task_template"])
        if isinstance(template.get("tags"), list):
            tags = _normalize_tags(tags + template.get("tags"))
        content = json.dumps(template, ensure_ascii=False)
        result = add_operation_experience.invoke({
            "system_name": "task_template",
            "content": content,
            "tags": tags,
            "scope": "project",
            "project_id": project_id,
            "user_id": user_id,
            "memory_type": "task_template"
        })
        saved.append(result)

def _should_prompt_save(summary_text):
    data = _parse_json_object_from_text(summary_text)
    if not data or not isinstance(data, dict):
        return False, None
    items = data.get("items") or {}
    behavior = items.get("behavior_preferences") or []
    code_style = items.get("code_style_preferences") or []
    templates = data.get("task_templates") or []
    task_experiences = items.get("task_experiences") or []
    has_items = any([behavior, code_style, task_experiences, templates])
    return has_items, data

def _should_auto_save_summary():
    value = os.getenv("SUMMARY_AUTO_SAVE", "1")
    return str(value).strip().lower() not in ["0", "false", "no"]

def _should_auto_save_reflection():
    value = os.getenv("REFLECTION_AUTO_SAVE", "1")
    return str(value).strip().lower() not in ["0", "false", "no"]

def _run_reflection_async(chat_history, project_id, user_id):
    try:
        llm = create_llm()
        reflection_text = _build_task_reflection(chat_history, llm, project_id, user_id)
        reflection_json = _parse_json_object_from_text(reflection_text)
        if reflection_json is not None:
            reflection_text = json.dumps(reflection_json, ensure_ascii=False, indent=2)
        shared.broadcast_threadsafe(">>> 系统: 复盘已生成")
        if _should_auto_save_reflection():
            result = _save_task_reflection(reflection_json or reflection_text, project_id, user_id)
            shared.broadcast_threadsafe(f">>> 系统: 复盘已保存 {result}")
        else:
            shared.broadcast_threadsafe(">>> 系统: 复盘已生成，未保存")
    except Exception as e:
        shared.set_error(f"生成复盘失败: {e}")
        shared.broadcast_threadsafe(f">>> 系统: 生成复盘失败: {e}")

def _run_summary_async(chat_history, project_id, user_id):
    try:
        llm = create_llm()
        summary_text = _build_cognition_summary(chat_history, llm, project_id, user_id)
        should_prompt, summary_json = _should_prompt_save(summary_text)
        if summary_json is not None:
            summary_json = _ensure_task_templates(summary_json, chat_history, llm, project_id, user_id)
            summary_text = json.dumps(summary_json, ensure_ascii=False, indent=2)
            should_prompt, summary_json = _should_prompt_save(summary_text)
        shared.set_summary(summary_text)
        shared.broadcast_threadsafe(">>> 系统: 总结已生成")
        if should_prompt and _should_auto_save_summary():
            try:
                if summary_json is None:
                    summary_json = json.loads(summary_text)
                saved = _save_cognition_summary(summary_json, project_id, user_id)
                if saved:
                    shared.broadcast_threadsafe(">>> 系统: 总结已保存")
                else:
                    shared.broadcast_threadsafe(">>> 系统: 总结未提取到可保存条目")
            except Exception:
                result = add_operation_experience.invoke({
                    "system_name": "personal_cognition",
                    "content": summary_text,
                    "tags": ["scope:project", f"project:{project_id}", "topic:summary"],
                    "scope": "project",
                    "project_id": project_id,
                    "user_id": user_id,
                    "memory_type": "task"
                })
                shared.broadcast_threadsafe(f">>> 系统: 已保存摘要。{result}")
        elif should_prompt:
            shared.broadcast_threadsafe(">>> 系统: 总结已生成，未保存")
    except Exception as e:
        shared.set_error(f"生成总结失败: {e}")
        shared.broadcast_threadsafe(f">>> 系统: 生成总结失败: {e}")

def _parse_template_results(raw_text):
    try:
        data = json.loads(raw_text)
    except Exception:
        return []
    if isinstance(data, list):
        return data
    return []

def _select_template(results):
    for item in results:
        content = item.get("content")
        if not content:
            continue
        try:
            template = json.loads(content)
            if isinstance(template, dict) and template.get("name"):
                return template
        except Exception:
            continue
    return None

def _format_template_for_prompt(template):
    name = template.get("name") or "未命名模板"
    steps = template.get("steps") or []
    inputs = template.get("inputs") or []
    outputs = template.get("outputs") or []
    constraints = template.get("constraints") or []
    parts = [f"模板名称: {name}"]
    if steps:
        parts.append("步骤:")
        parts.extend([f"- {s}" for s in steps])
    if inputs:
        parts.append("输入:")
        parts.extend([f"- {i}" for i in inputs])
    if outputs:
        parts.append("输出:")
        parts.extend([f"- {o}" for o in outputs])
    if constraints:
        parts.append("约束:")
        parts.extend([f"- {c}" for c in constraints])
    return "\n".join(parts)

def _get_task_experiences(user_input, project_id, user_id):
    raw = get_operation_experience.invoke({
        "query": user_input,
        "n_results": 3,
        "scope": "project",
        "project_id": project_id,
        "user_id": user_id,
        "memory_type": "task"
    })
    results = _parse_template_results(raw) if isinstance(raw, str) else []
    experiences = []
    for item in results:
        content = item.get("content")
        if content:
            experiences.append(str(content).strip())
    return [e for e in experiences if e]

def _format_experiences_for_prompt(experiences):
    if not experiences:
        return ""
    parts = ["相关经验:"]
    parts.extend([f"- {e}" for e in experiences])
    return "\n".join(parts)

def _read_yes_no_or_defer():
    raw = shared.get_input()
    text = str(raw or "").strip()
    low = text.lower()
    if low in ["y", "yes"] or text in ["是", "保存", "使用", "好", "ok"]:
        return True, None
    if low in ["n", "no"] or text in ["否", "不保存", "不使用", "不要", "算了", "取消"]:
        return False, None
    return None, text

def _read_yes_no_or_timeout(timeout_seconds: int = 5):
    try:
        raw = shared.get_input(timeout=timeout_seconds)
    except queue.Empty:
        return None, None, True
    text = str(raw or "").strip()
    low = text.lower()
    if low in ["y", "yes"] or text in ["是", "保存", "使用", "好", "ok"]:
        return True, None, False
    if low in ["n", "no"] or text in ["否", "不保存", "不使用", "不要", "算了", "取消"]:
        return False, None, False
    return None, text, False

def _contains_task_intent(text):
    if not text:
        return False
    keywords = {
        "发送", "邮件", "邮箱", "通知", "提醒", "生成", "制作", "整理", "搜索", "查询", "下载",
        "导出", "保存", "统计", "分析", "报告", "自动化", "爬取", "抓取", "写入", "提交",
        "执行", "创建", "配置", "部署", "重构", "修复", "优化", "转换", "翻译"
    }
    return any(k in text for k in keywords)

def _looks_like_small_talk(text):
    if not text:
        return True
    casual = {
        "今天吃什么", "今天吃啥", "吃什么", "吃啥", "吃点啥", "吃点什么",
        "喝什么", "喝点什么", "晚饭吃什么", "午饭吃什么", "早餐吃什么",
        "好无聊", "想睡觉", "累了", "冷不冷", "热不热", "天气怎么样"
    }
    if text in casual:
        return True
    if len(text) <= 12 and any(p in text for p in ["吃什么", "吃啥", "喝什么", "干嘛"]):
        return True
    return False

def _template_matches_input(template, user_input):
    text = str(user_input or "").strip()
    if not text:
        return False
    if not _contains_task_intent(text):
        return False
    steps = template.get("steps") or []
    outputs = template.get("outputs") or []
    constraints = template.get("constraints") or []
    template_text = json.dumps({"steps": steps, "outputs": outputs, "constraints": constraints}, ensure_ascii=False)
    if "邮件" in template_text or "邮箱" in template_text:
        if "邮件" not in text and "邮箱" not in text and "发送" not in text:
            return False
    return True

def _maybe_apply_template(user_input, project_id, user_id):
    if _should_skip_template(user_input):
        return user_input
    raw = get_operation_experience.invoke({
        "query": user_input,
        "n_results": 3,
        "scope": "project",
        "project_id": project_id,
        "user_id": user_id,
        "memory_type": "task_template"
    })
    results = _parse_template_results(raw) if isinstance(raw, str) else []
    template = _select_template(results)
    if not template:
        return user_input
    if not _template_matches_input(template, user_input):
        return user_input
    preview = _format_template_for_prompt(template)
    print("Agent: 检索到可用模板\n")
    print(preview + "\n")
    print("User: 是否使用该模板执行？(yes/no) ", end="", flush=True)
    ok, deferred = _read_yes_no_or_defer()
    if ok is None and deferred:
        shared.put_back(deferred)
    if ok is True:
        experiences = _get_task_experiences(user_input, project_id, user_id)
        exp_text = _format_experiences_for_prompt(experiences)
        exp_block = f"\n\n{exp_text}" if exp_text else ""
        return f"请按以下模板执行任务，并结合用户需求与相关经验补充细节：\n{preview}{exp_block}\n\n用户需求：{user_input}"
    return user_input

def _is_lightweight_user_input(text):
    if not text:
        return True
    if len(text) < 6:
        return True
    lower = text.lower()
    short_greetings = {"hi", "hello", "hey", "yo", "ok", "thanks", "thx"}
    if lower in short_greetings:
        return True
    zh_greetings = {"你好", "您好", "在吗", "谢谢", "多谢", "早上好", "晚上好"}
    if text in zh_greetings:
        return True
    lightweight_phrases = {"你是谁", "你叫什么", "自我介绍", "介绍一下你", "你是谁啊", "你是谁呀"}
    if any(p in text for p in lightweight_phrases) and len(text) <= 20:
        return True
    emotion_keywords = {"难过", "开心", "郁闷", "生气", "烦", "焦虑", "压力", "emo", "安慰", "倾诉", "发泄"}
    if any(k in text for k in emotion_keywords) and len(text) <= 20:
        return True
    return False

def _should_skip_template(user_input):
    text = str(user_input or "").strip()
    if _is_lightweight_user_input(text):
        return True
    if _looks_like_small_talk(text):
        return True
    if len(text) < 12 and not _contains_task_intent(text):
        return True
    return False

_SUMMARY_PREFIXES = {
    "long": "对话摘要（长期）：",
    "stage": "对话摘要（阶段）：",
    "legacy": "对话摘要（用于延续上下文）："
}

def _parse_summary_message(msg):
    if not msg:
        return None
    role, content = msg
    if role != "system":
        return None
    if not isinstance(content, str):
        return None
    for key, prefix in _SUMMARY_PREFIXES.items():
        if content.startswith(prefix):
            return key, content.split("：", 1)[1].strip()
    return None

def _is_summary_message(msg):
    return _parse_summary_message(msg) is not None

def _extract_summaries(chat_history):
    summaries = {"long": None, "stage": None}
    rest = chat_history[:]
    while rest:
        parsed = _parse_summary_message(rest[0])
        if not parsed:
            break
        level, text = parsed
        if level == "legacy":
            level = "long"
        summaries[level] = text
        rest = rest[1:]
    return summaries, rest

def _summarize_text(llm, transcript_text, existing_summary=None, summary_kind="阶段"):
    from langchain_core.messages import SystemMessage, HumanMessage
    system_text = (
        "你是对话摘要器。输出用于继续执行任务的摘要，"
        "要求分级结构，保留关键信息、约束、已完成事项、未完成事项、关键决定、关键路径/变量名、风险与下一步。"
        "只输出摘要正文。"
    )
    user_text = ""
    if existing_summary:
        user_text += f"已有{summary_kind}摘要：\n{existing_summary}\n\n"
    user_text += (
        f"需要压缩的新增内容：\n{transcript_text}\n\n"
        f"请输出更新后的{summary_kind}摘要（分级条目）："
    )
    resp = llm.invoke([SystemMessage(content=system_text), HumanMessage(content=user_text)])
    new_summary = getattr(resp, "content", "") or str(resp)
    return new_summary.strip()

def maybe_summarize_history(chat_history, llm, max_recent_turns=8, max_stage_chars=1200):
    summaries, non_summary = _extract_summaries(chat_history)
    long_summary = summaries.get("long")
    stage_summary = summaries.get("stage")

    chunk_size = max_recent_turns * 2
    if len(non_summary) <= chunk_size:
        history = []
        if long_summary:
            history.append(("system", f"对话摘要（长期）：\n{long_summary}"))
        if stage_summary:
            history.append(("system", f"对话摘要（阶段）：\n{stage_summary}"))
        return history + non_summary

    older = non_summary[:-chunk_size]
    recent = non_summary[-chunk_size:]

    transcript = _format_history_for_summary(older)
    stage_summary = _summarize_text(llm, transcript, stage_summary, "阶段")

    if long_summary:
        if len(stage_summary) > max_stage_chars:
            long_summary = _summarize_text(llm, stage_summary, long_summary, "长期")
            stage_summary = None
    else:
        if len(stage_summary) > max_stage_chars:
            long_summary = _summarize_text(llm, stage_summary, None, "长期")
            stage_summary = None

    history = []
    if long_summary:
        history.append(("system", f"对话摘要（长期）：\n{long_summary}"))
    if stage_summary:
        history.append(("system", f"对话摘要（阶段）：\n{stage_summary}"))
    return history + recent

def enable_dpi_awareness():
    if platform.system() != "Windows":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

class DualOutput:
    def __init__(self, original_stdout):
        self.original_stdout = original_stdout
        self.blocked_tokens = [
        ]
        
    def _sanitize_for_web(self, message):
        cleaned = ANSI_ESCAPE_RE.sub("", message)
        stripped = cleaned.strip()
        if stripped == "User:":
            return ""
        lowered = cleaned.lower()
        if any(token in lowered for token in self.blocked_tokens):
            return ""
        return cleaned

    def write(self, message):
        self.original_stdout.write(message)
        # Broadcast to web, non-blocking
        # Only broadcast non-empty messages to avoid noise
        if message: 
             sanitized = self._sanitize_for_web(message)
             if sanitized.strip():
                 shared.broadcast_threadsafe(sanitized)
            
    def flush(self):
        self.original_stdout.flush()

    def isatty(self):
        return getattr(self.original_stdout, 'isatty', lambda: False)()
    
    def __getattr__(self, name):
        return getattr(self.original_stdout, name)

def console_reader():
    """Reads from stdin and puts into shared input queue"""
    while True:
        try:
            # Note: input() blocks. 
            text = input()
            shared.put_input(text)
        except EOFError:
            break
        except Exception as e:
            print(f"Console input error: {e}")
            break

def main():
    enable_dpi_awareness()

    _start_wa_gateway_subprocess()
    
    # Start Web Server in a daemon thread
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    
    # Redirect stdout to capture agent output
    sys.stdout = DualOutput(sys.stdout)
    
    # Start Console Reader
    input_thread = threading.Thread(target=console_reader, daemon=True)
    input_thread.start()

    print("正在初始化 Agent...")
    try:
        project_id = _extract_project_id()
        user_id = os.getenv("LOCAL_USER_ID", "local_user")
        tool_trace_callbacks = [ShortTermToolTraceHandler(project_id, user_id)]
        agent_executor = create_agent_executor(callbacks=tool_trace_callbacks)
        summary_llm = create_llm()
    except Exception as e:
        print(f"初始化失败: {e}")
        return

    print("\n✅ Agent 已就绪！")
    print("输入 'exit' 或 'quit' 退出。")
    print("也可以通过 Web 控制台发送指令。\n")

    chat_history = []
    max_auto_steps = 60
    tool_router_enabled = _env_flag("TOOL_ROUTER_ENABLED", True)
    current_skill_allowlist = None
    current_skill_allowlist_key = None
    '''
    最大自动执行步数，防止无限循环。
    '''

    while True:
        try:
            # Print prompt (optional, visual cue)
            print("User: ", end="", flush=True)
            
            # Wait for input from either Console or Web
            user_input = shared.get_input()
            user_input = user_input.strip()
            wa_ctx, user_input = _extract_whatsapp_input(user_input)
            
            if user_input.startswith(SET_MODEL_PREFIX):
                provider = user_input[len(SET_MODEL_PREFIX):].strip().lower()
                previous_provider = os.getenv("LLM_PROVIDER", "deepseek")
                os.environ["LLM_PROVIDER"] = provider
                try:
                    if tool_router_enabled and current_skill_allowlist:
                        agent_executor = create_agent_executor(skill_allowlist=current_skill_allowlist, callbacks=tool_trace_callbacks)
                    else:
                        agent_executor = create_agent_executor(callbacks=tool_trace_callbacks)
                    chat_history = []
                    print(f">>> 系统: 已切换模型为 {provider}\n")
                except Exception as e:
                    os.environ["LLM_PROVIDER"] = previous_provider
                    try:
                        if tool_router_enabled and current_skill_allowlist:
                            agent_executor = create_agent_executor(skill_allowlist=current_skill_allowlist, callbacks=tool_trace_callbacks)
                        else:
                            agent_executor = create_agent_executor(callbacks=tool_trace_callbacks)
                    except Exception:
                        pass
                    print(f">>> 系统: 切换模型失败: {e}\n")
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("Bye!")
                break

            if not user_input:
                continue

            if user_input.strip().lower() in ["y", "yes", "n", "no"]:
                continue

            _add_short_term_message("user", user_input, project_id, user_id)
            resume_keywords = {"继续", "继续执行", "继续做", "continue"}
            if user_input.strip().lower() in resume_keywords:
                plan = _load_task_plan()
                step = _get_next_pending_step(plan)
                if step:
                    auto_input = f"继续执行任务计划第{step.get('id')}步：{step.get('desc')}。完成后调用 mark_task_completed 标记，并继续 read_task_plan 获取下一步。"
                else:
                    auto_input = "继续执行，基于当前屏幕状态完成任务。"
            else:
                if wa_ctx:
                    auto_input = (
                        "你正在通过 WhatsApp 私聊与用户对话。"
                        "请直接回复对方的消息内容，输出为纯文本，不要包含 'User:'/'Agent:'/'STATE:' 等标记。\n\n"
                        f"用户消息：{user_input}"
                    )
                elif _requests_all_memory_search(user_input):
                    auto_input = f"用户要求搜索所有记忆。请同时检索长期记忆(get_operation_experience)与短期记忆(search_short_term_memory)，并合并后给出结论与依据。\n\n用户原始输入：{user_input}"
                else:
                    auto_input = _maybe_apply_template(user_input, project_id, user_id)
            if tool_router_enabled:
                selected_skill_allowlist = _select_skill_allowlist(auto_input)
                selected_key = tuple(selected_skill_allowlist)
                if selected_key != current_skill_allowlist_key:
                    current_skill_allowlist = selected_skill_allowlist
                    current_skill_allowlist_key = selected_key
                    agent_executor = create_agent_executor(skill_allowlist=current_skill_allowlist, callbacks=tool_trace_callbacks)
            for step in range(max_auto_steps):
                chat_history = maybe_summarize_history(chat_history, summary_llm, max_recent_turns=8)
                raw_output = ""
                print("Agent: ", end="", flush=True)
                buffer = ""
                shared.set_status("running", "执行中", auto_input)
                print(">>> 系统: 状态=执行中")
                for chunk in agent_executor.stream({
                    "input": auto_input,
                    "chat_history": chat_history
                }):
                    if shared.stop_requested:
                        shared.clear_stop()
                        shared.set_status("stopped", "已停止", auto_input)
                        print(">>> 系统: 状态=已停止")
                        break
                    if not isinstance(chunk, dict):
                        continue
                    text = chunk.get("output")
                    if text is None:
                        continue
                    if text.startswith(raw_output):
                        delta = text[len(raw_output):]
                        raw_output = text
                    else:
                        delta = text
                        raw_output += delta
                    if not delta:
                        continue
                    buffer += delta
                    if RELOAD_SIGNAL in buffer:
                        buffer = buffer.replace(RELOAD_SIGNAL, "")
                    while True:
                        idx = buffer.find("\n")
                        if idx == -1:
                            break
                        line = buffer[:idx + 1]
                        buffer = buffer[idx + 1:]
                        if line.strip().upper().startswith("STATE:"):
                            continue
                        print(line, end="", flush=True)
                if buffer and not buffer.strip().upper().startswith("STATE:"):
                    print(buffer, end="", flush=True)
                print("\n")
                if shared.stop_requested:
                    shared.clear_stop()
                    shared.set_status("idle", "空闲")
                    print(">>> 系统: 状态=空闲")

                output = raw_output
                output, reload_requested = strip_reload_signal(output)
                state, cleaned_output = parse_state(output)
                _add_short_term_message("assistant", cleaned_output or output, project_id, user_id)
                if wa_ctx and state != "CONTINUE":
                    reply_text = (cleaned_output or output or "").strip()
                    if reply_text:
                        _send_whatsapp_reply(wa_ctx.get("chatJid"), reply_text)
                chat_history.extend([
                    ("user", auto_input),
                    ("assistant", output)
                ])
                if reload_requested:
                    try:
                        if tool_router_enabled and current_skill_allowlist:
                            agent_executor = create_agent_executor(skill_allowlist=current_skill_allowlist)
                        else:
                            agent_executor = create_agent_executor()
                        summary_llm = create_llm()
                        print("Agent: 已重载技能\n")
                        chat_history.append(("system", "系统消息：技能热加载已完成，请继续上一轮任务，避免重复生成技能。"))
                        auto_input = (
                            "系统消息：技能热加载已完成。请继续执行上一轮未完成的任务，不要重复创建已存在的技能/目录/文件。"
                            "如果你不确定新技能是否已创建成功，优先通过 inspect_environment 或检查目录确认；"
                            "确认存在后，直接调用新工具完成任务。\n\n"
                            f"上一轮任务输入：{auto_input}"
                        )
                        continue # 跳过后续的状态检查，直接进入下一轮循环（使用新的 auto_input）
                    except Exception as e:
                        print(f"Agent: 技能重载失败: {e}\n")
                        try:
                            from app.skills.skillgen_skill.scripts.skill_tools import rollback_change
                            msg = rollback_change(change_id=None)
                            print(f"Agent: 已自动回滚到最近稳定版本: {msg}\n")
                            agent_executor = create_agent_executor()
                            summary_llm = create_llm()
                            chat_history.append(("system", f"系统消息：热加载失败已自动回滚。{msg}"))
                            auto_input = (
                                "系统消息：热加载失败，已自动回滚到最近稳定版本。"
                                "请继续上一轮未完成的任务，不要重复创建技能/目录/文件。\n\n"
                                f"上一轮任务输入：{auto_input}"
                            )
                            continue
                        except Exception as e2:
                            print(f"Agent: 自动回滚失败: {e2}\n")

                if state == "DONE":
                    project_id = _extract_project_id()
                    try:
                        print("Agent: 状态=生成总结\n")
                        chat_snapshot = chat_history[:]
                        summary_thread = threading.Thread(
                            target=_run_summary_async,
                            args=(chat_snapshot, project_id, user_id),
                            daemon=True
                        )
                        summary_thread.start()
                        reflection_thread = threading.Thread(
                            target=_run_reflection_async,
                            args=(chat_snapshot, project_id, user_id),
                            daemon=True
                        )
                        reflection_thread.start()
                    except Exception as e:
                        print(f"Agent: 生成总结失败: {e}\n")
                        shared.set_error(f"生成总结失败: {e}")
                    try:
                        plan_path = _get_task_plan_path()
                        if os.path.exists(plan_path):
                            os.remove(plan_path)
                    except Exception as e:
                        print(f"Agent: 清理任务计划失败: {e}\n")
                        shared.set_error(f"清理任务计划失败: {e}")
                    shared.set_status("idle", "空闲")
                    print(">>> 系统: 状态=空闲")
                    break
                if state != "CONTINUE":
                    shared.set_status("idle", "空闲")
                    print(">>> 系统: 状态=空闲")
                    break
                auto_input = "继续执行，基于当前屏幕状态完成任务。"
                if step == max_auto_steps - 1:
                    print("Agent: 已达到自动执行步数上限。输入“继续”将从任务计划的当前步骤继续。\n")
                    shared.set_status("idle", "空闲")
                    print(">>> 系统: 状态=空闲")
                    break

        except KeyboardInterrupt:
            print("\nBye!")
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    main()
