import os
import platform
import ctypes
import sys
import re
import threading
import json
from web.backend.main import start as start_web_server
from web.backend.shared import shared

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HUGGINGFACE_HUB_ENDPOINT", "https://hf-mirror.com")

from app.agent import create_agent_executor, create_llm
from app.skills.system_skill.scripts.experience_tools import add_operation_experience, get_operation_experience

RELOAD_SIGNAL = "__RELOAD_SKILLS__"
SET_MODEL_PREFIX = "__SET_MODEL__:"
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[ -/]*[@-~]")

def parse_state(output: str):
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return None, output
    last_line = lines[-1]
    if last_line.upper().startswith("STATE:"):
        state = last_line.split(":", 1)[1].strip().upper()
        cleaned = "\n".join(lines[:-1]).strip()
        return state, cleaned
    return None, output

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
    confirm_input = shared.get_input().strip().lower()
    if confirm_input in ["y", "yes", "是", "使用", "好", "ok"]:
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

def _is_summary_message(msg):
    if not msg:
        return False
    role, content = msg
    if role != "system":
        return False
    return isinstance(content, str) and content.startswith("对话摘要（用于延续上下文）：")

def maybe_summarize_history(chat_history, llm, max_turns=20):
    non_summary = chat_history[:]
    rolling_summary = None
    if non_summary and _is_summary_message(non_summary[0]):
        rolling_summary = non_summary[0][1].split("：", 1)[1].strip()
        non_summary = non_summary[1:]

    chunk_size = max_turns * 2
    if len(non_summary) <= chunk_size:
        return chat_history

    chunk = non_summary[:chunk_size]
    rest = non_summary[chunk_size:]

    from langchain_core.messages import SystemMessage, HumanMessage

    system_text = "你是对话摘要器。把对话压缩为可用于继续对话的摘要，保留关键信息、约束、已完成事项、未完成事项、关键决定、关键参数/路径/变量名,并给出最后一轮对话执行到哪一步了。只输出摘要正文。"
    transcript = _format_history_for_summary(chunk)
    user_text = ""
    if rolling_summary:
        user_text += f"已有摘要：\n{rolling_summary}\n\n"
    user_text += f"需要压缩的新增对话（按顺序）：\n{transcript}\n\n请输出更新后的摘要："

    resp = llm.invoke([SystemMessage(content=system_text), HumanMessage(content=user_text)])
    new_summary = getattr(resp, "content", "") or str(resp)
    new_summary = new_summary.strip()

    summary_msg = ("system", f"对话摘要（用于延续上下文）：\n{new_summary}")
    if rest:
        return [summary_msg] + rest
    return [summary_msg]

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
        agent_executor = create_agent_executor()
        summary_llm = create_llm()
    except Exception as e:
        print(f"初始化失败: {e}")
        return

    print("\n✅ Agent 已就绪！")
    print("输入 'exit' 或 'quit' 退出。")
    print("也可以通过 Web 控制台发送指令。\n")

    chat_history = []
    max_auto_steps = 30
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
            
            if user_input.startswith(SET_MODEL_PREFIX):
                provider = user_input[len(SET_MODEL_PREFIX):].strip().lower()
                previous_provider = os.getenv("LLM_PROVIDER", "deepseek")
                os.environ["LLM_PROVIDER"] = provider
                try:
                    agent_executor = create_agent_executor()
                    chat_history = []
                    print(f">>> 系统: 已切换模型为 {provider}\n")
                except Exception as e:
                    os.environ["LLM_PROVIDER"] = previous_provider
                    try:
                        agent_executor = create_agent_executor()
                    except Exception:
                        pass
                    print(f">>> 系统: 切换模型失败: {e}\n")
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("Bye!")
                break
            
            if not user_input:
                continue

            project_id = _extract_project_id()
            user_id = os.getenv("LOCAL_USER_ID", "local_user")
            resume_keywords = {"继续", "继续执行", "继续做", "continue"}
            if user_input.strip().lower() in resume_keywords:
                plan = _load_task_plan()
                step = _get_next_pending_step(plan)
                if step:
                    auto_input = f"继续执行任务计划第{step.get('id')}步：{step.get('desc')}。完成后调用 mark_task_completed 标记，并继续 read_task_plan 获取下一步。"
                else:
                    auto_input = "继续执行，基于当前屏幕状态完成任务。"
            else:
                auto_input = _maybe_apply_template(user_input, project_id, user_id)
            for step in range(max_auto_steps):
                chat_history = maybe_summarize_history(chat_history, summary_llm, max_turns=20)
                raw_output = ""
                print("Agent: ", end="", flush=True)
                buffer = ""
                for chunk in agent_executor.stream({
                    "input": auto_input,
                    "chat_history": chat_history
                }):
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

                output = raw_output
                output, reload_requested = strip_reload_signal(output)
                state, cleaned_output = parse_state(output)
                chat_history.extend([
                    ("user", auto_input),
                    ("assistant", output)
                ])
                if reload_requested:
                    try:
                        agent_executor = create_agent_executor()
                        summary_llm = create_llm()
                        print("Agent: 已重载技能\n")
                        # 主动发起一轮对话，告知 Agent 技能已重载，让其决定下一步
                        auto_input = "系统消息：技能热加载已完成。请确认新技能是否可用继续执行上一步未完成的任务。"
                        continue # 跳过后续的状态检查，直接进入下一轮循环（使用新的 auto_input）
                    except Exception as e:
                        print(f"Agent: 技能重载失败: {e}\n")

                if state == "DONE":
                    project_id = _extract_project_id()
                    user_id = os.getenv("LOCAL_USER_ID", "local_user")
                    try:
                        summary_text = _build_cognition_summary(chat_history, summary_llm, project_id, user_id)
                        should_prompt, summary_json = _should_prompt_save(summary_text)
                        if summary_json:
                            summary_json = _ensure_task_templates(summary_json, chat_history, summary_llm, project_id, user_id)
                            summary_text = json.dumps(summary_json, ensure_ascii=False, indent=2)
                            should_prompt, summary_json = _should_prompt_save(summary_text)
                        if should_prompt:
                            print("Agent: 已生成个人认知总结（待确认）\n")
                            print(summary_text + "\n")
                            print("User: 是否保存以上总结？(yes/no) ", end="", flush=True)
                            confirm_input = shared.get_input().strip().lower()
                            if confirm_input in ["y", "yes", "是", "保存", "好", "ok"]:
                                try:
                                    if summary_json is None:
                                        summary_json = json.loads(summary_text)
                                    saved = _save_cognition_summary(summary_json, project_id, user_id)
                                    if saved:
                                        print("Agent: 已保存到经验库。\n")
                                    else:
                                        print("Agent: 未提取到可保存的条目。\n")
                                except Exception:
                                    result = add_operation_experience(
                                        system_name="personal_cognition",
                                        content=summary_text,
                                        tags=[f"scope:project", f"project:{project_id}", "topic:summary"],
                                        scope="project",
                                        project_id=project_id,
                                        user_id=user_id,
                                        memory_type="task"
                                    )
                                    print(f"Agent: 已保存摘要。{result}\n")
                            else:
                                print("Agent: 已放弃保存。\n")
                    except Exception as e:
                        print(f"Agent: 生成总结失败: {e}\n")
                    try:
                        plan_path = _get_task_plan_path()
                        if os.path.exists(plan_path):
                            os.remove(plan_path)
                    except Exception as e:
                        print(f"Agent: 清理任务计划失败: {e}\n")
                    break
                if state != "CONTINUE":
                    break
                auto_input = "继续执行，基于当前屏幕状态完成任务。"
                if step == max_auto_steps - 1:
                    print("Agent: 已达到自动执行步数上限。输入“继续”将从任务计划的当前步骤继续。\n")
                    break

        except KeyboardInterrupt:
            print("\nBye!")
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    main()
