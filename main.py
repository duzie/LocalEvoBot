import os
import platform
import ctypes
import sys
import re
import threading
from web.backend.main import start as start_web_server
from web.backend.shared import shared

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HUGGINGFACE_HUB_ENDPOINT", "https://hf-mirror.com")

from app.agent import create_agent_executor, create_llm

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

            auto_input = user_input
            for step in range(max_auto_steps):
                chat_history = maybe_summarize_history(chat_history, summary_llm, max_turns=20)
                response = agent_executor.invoke({
                    "input": auto_input,
                    "chat_history": chat_history
                })

                output = response.get("output", "")
                output, reload_requested = strip_reload_signal(output)
                state, cleaned_output = parse_state(output)
                print(f"Agent: {cleaned_output}\n")
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
                    break
                if state != "CONTINUE":
                    break
                auto_input = "继续执行，基于当前屏幕状态完成任务。"
                if step == max_auto_steps - 1:
                    print("Agent: 已达到自动执行步数上限。\n")
                    break

        except KeyboardInterrupt:
            print("\nBye!")
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    main()
