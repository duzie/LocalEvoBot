import os
import time
import random
import asyncio
from typing import List, Dict, Set
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from dotenv import load_dotenv

from app.skills.registry import load_skills
from app.integrations.mcp_client import load_mcp_tools
from app.prompts import get_agent_prompt

# 加载环境变量
load_dotenv()

_skill_tool_cache: Dict[str, List[str]] = {}

def _read_skill_tool_names(skill_dir: str) -> List[str]:
    path = os.path.join(skill_dir, "skill.md")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception:
        return []
    tools = []
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
                rest = item[end + 2 :].strip()
                if not name and rest.startswith(":"):
                    name = rest.lstrip(":").strip().split(" ", 1)[0].strip()
        else:
            if ":" in item:
                name = item.split(":", 1)[0].strip()
            else:
                name = item.split(" ", 1)[0].strip()
        if name:
            tools.append(name)
    return tools

def _collect_tools_for_skills(skill_names: List[str]) -> Set[str]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    skills_root = os.path.join(base_dir, "skills")
    auto_root = os.path.join(base_dir, "auto_skills")
    collected: Set[str] = set()
    for raw in skill_names or []:
        name = str(raw or "").strip()
        if not name:
            continue
        cached = _skill_tool_cache.get(name)
        if cached is not None:
            collected.update(cached)
            continue
        tool_names: List[str] = []
        for root in (skills_root, auto_root):
            skill_dir = os.path.join(root, name)
            if not os.path.isdir(skill_dir):
                continue
            tool_names.extend(_read_skill_tool_names(skill_dir))
        _skill_tool_cache[name] = tool_names
        collected.update(tool_names)
    return collected

class _LLMRetryWrapper:
    def __init__(self, llm, max_attempts: int, base_delay: float, max_delay: float):
        self._llm = llm
        self._max_attempts = max(1, int(max_attempts))
        self._base_delay = max(0.0, float(base_delay))
        self._max_delay = max(0.0, float(max_delay))

    def _should_retry(self, exc: Exception) -> bool:
        text = str(exc).lower()
        if "no suitable clusters" in text:
            return True
        if "internalerror.algo" in text:
            return True
        if "model serving" in text:
            return True
        if "timeout" in text:
            return True
        if "rate limit" in text or "429" in text:
            return True
        return False

    def _sleep(self, attempt: int):
        if self._base_delay <= 0:
            return
        delay = min(self._max_delay, self._base_delay * (2 ** (attempt - 1)))
        jitter = delay * (0.2 * random.random())
        time.sleep(delay + jitter)

    async def _sleep_async(self, attempt: int):
        if self._base_delay <= 0:
            return
        delay = min(self._max_delay, self._base_delay * (2 ** (attempt - 1)))
        jitter = delay * (0.2 * random.random())
        await asyncio.sleep(delay + jitter)

    def invoke(self, *args, **kwargs):
        last_exc = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return self._llm.invoke(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt >= self._max_attempts or not self._should_retry(exc):
                    raise
                self._sleep(attempt)
        if last_exc:
            raise last_exc

    async def ainvoke(self, *args, **kwargs):
        last_exc = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await self._llm.ainvoke(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt >= self._max_attempts or not self._should_retry(exc):
                    raise
                await self._sleep_async(attempt)
        if last_exc:
            raise last_exc

    def stream(self, *args, **kwargs):
        last_exc = None
        for attempt in range(1, self._max_attempts + 1):
            yielded = False
            try:
                for chunk in self._llm.stream(*args, **kwargs):
                    yielded = True
                    yield chunk
                return
            except Exception as exc:
                last_exc = exc
                if yielded or attempt >= self._max_attempts or not self._should_retry(exc):
                    raise
                self._sleep(attempt)
        if last_exc:
            raise last_exc

    async def astream(self, *args, **kwargs):
        last_exc = None
        for attempt in range(1, self._max_attempts + 1):
            yielded = False
            try:
                async for chunk in self._llm.astream(*args, **kwargs):
                    yielded = True
                    yield chunk
                return
            except Exception as exc:
                last_exc = exc
                if yielded or attempt >= self._max_attempts or not self._should_retry(exc):
                    raise
                await self._sleep_async(attempt)
        if last_exc:
            raise last_exc

    def __getattr__(self, name):
        return getattr(self._llm, name)

def _apply_llm_retry(llm):
    try:
        max_attempts = int(os.getenv("LLM_RETRY_MAX") or 3)
    except Exception:
        max_attempts = 3
    try:
        base_delay = float(os.getenv("LLM_RETRY_BASE_DELAY") or 1.0)
    except Exception:
        base_delay = 1.0
    try:
        max_delay = float(os.getenv("LLM_RETRY_MAX_DELAY") or 6.0)
    except Exception:
        max_delay = 6.0
    if max_attempts <= 1:
        return llm
    return _LLMRetryWrapper(llm, max_attempts=max_attempts, base_delay=base_delay, max_delay=max_delay)

def create_llm():
    provider_raw = (os.getenv("LLM_PROVIDER") or "").strip().strip("'\"").lower()
    if provider_raw:
        provider = provider_raw
    else:
        if (os.getenv("DOUBAO_MODEL_NAME") or os.getenv("ARK_MODEL_NAME") or os.getenv("ARK_ENDPOINT_ID") or "").strip():
            provider = "doubao"
        elif (os.getenv("DEEPSEEK_API_KEY") or "").strip():
            provider = "deepseek"
        elif (os.getenv("QWEN_CODING_PLAN_API_KEY") or os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or "").strip():
            provider = "qwen"
        elif (os.getenv("OPENAI_API_KEY") or "").strip():
            provider = "openai"
        elif (os.getenv("LOCAL_MODEL_PATH") or "").strip():
            provider = "local"
        elif (os.getenv("NIM_API_KEY") or os.getenv("NVIDIA_NIM_API_KEY") or os.getenv("NVIDIA_API_KEY") or "").strip():
            if (os.getenv("NIM_MINIMAX_M2_MODEL_NAME") or "").strip():
                provider = "nim_minimax_m2"
            elif (os.getenv("NIM_GLM47_MODEL_NAME") or "").strip():
                provider = "nim_glm47"
            else:
                provider = "nim_glm47"
        else:
            raise ValueError("未检测到可用的模型配置。请复制 .env.example 为 .env 并填写 LLM_PROVIDER 与相应 API_KEY。")

    if provider == "doubao":
        api_key = os.getenv("DOUBAO_API_KEY") or os.getenv("ARK_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("DOUBAO_BASE_URL") or os.getenv("ARK_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"
        model_name = os.getenv("DOUBAO_MODEL_NAME") or os.getenv("ARK_MODEL_NAME") or os.getenv("ARK_ENDPOINT_ID")
        if not api_key:
            raise ValueError("请确保 .env 文件中配置了 DOUBAO_API_KEY（或复用 OPENAI_API_KEY）")
        if not model_name:
            raise ValueError("请确保 .env 文件中配置了 DOUBAO_MODEL_NAME（填接入点 Endpoint ID）")
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7,
            streaming=True,
        )
        return _apply_llm_retry(llm)

    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
        model_name = os.getenv("DEEPSEEK_MODEL_NAME") or "deepseek-chat"
        if not api_key:
            raise ValueError("请确保 .env 文件中配置了 DEEPSEEK_API_KEY")
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7,
            streaming=True,
        )
        return _apply_llm_retry(llm)

    if provider == "qwen":
        coding_plan_key = os.getenv("QWEN_CODING_PLAN_API_KEY")
        api_key = coding_plan_key or os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        if (os.getenv("QWEN_BASE_URL") or "").strip():
            base_url = os.getenv("QWEN_BASE_URL")
        elif (coding_plan_key or "").strip():
            base_url = "https://coding.dashscope.aliyuncs.com/v1"
        else:
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        model_name = os.getenv("QWEN_MODEL_NAME") or "qwen-plus"
        if not api_key:
            raise ValueError("请确保 .env 文件中配置了 QWEN_CODING_PLAN_API_KEY 或 QWEN_API_KEY (或 DASHSCOPE_API_KEY)")
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7,
            streaming=True,
        )
        return _apply_llm_retry(llm)

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        model_name = os.getenv("OPENAI_MODEL_NAME") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        if not api_key:
            raise ValueError("请确保 .env 文件中配置了 OPENAI_API_KEY")
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7,
            streaming=True,
        )

    if provider == "local":
        model_path = os.getenv("LOCAL_MODEL_PATH")
        if not model_path:
            raise ValueError("请确保 .env 文件中配置了 LOCAL_MODEL_PATH")
        try:
            from langchain_community.chat_models import ChatLlamaCpp
        except Exception as e:
            raise ValueError("请安装 llama-cpp-python 以启用本地模型") from e
        n_ctx = int(os.getenv("LOCAL_CTX_SIZE") or 4096)
        n_gpu_layers = int(os.getenv("LOCAL_GPU_LAYERS") or 0)
        n_threads = int(os.getenv("LOCAL_THREADS") or 8)
        n_batch = int(os.getenv("LOCAL_BATCH_SIZE") or 512)
        temperature = float(os.getenv("LOCAL_TEMPERATURE") or 0.7)
        llm = ChatLlamaCpp(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_threads=n_threads,
            n_batch=n_batch,
            temperature=temperature,
        )
        return _apply_llm_retry(llm)

    if provider in {"nim_minimax_m2", "nim_glm47"}:
        api_key = os.getenv("NIM_API_KEY") or os.getenv("NVIDIA_NIM_API_KEY") or os.getenv("NVIDIA_API_KEY")
        base_url = os.getenv("NIM_BASE_URL") or "https://integrate.api.nvidia.com/v1"
        if provider == "nim_minimax_m2":
            model_name = os.getenv("NIM_MINIMAX_M2_MODEL_NAME") or "minimaxai/minimax-m2"
        else:
            model_name = os.getenv("NIM_GLM47_MODEL_NAME") or "z-ai/glm4.7"
        if not api_key:
            raise ValueError("请确保 .env 文件中配置了 NIM_API_KEY（NVIDIA API Catalog Key；自建 NIM 可填 no-key-required）")
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7,
            streaming=True,
        )
        return _apply_llm_retry(llm)

    raise ValueError(f"不支持的 LLM_PROVIDER: {provider}")

def _read_str_env(key: str, default: str = "") -> str:
    try:
        value = os.getenv(key)
        if value is None:
            return str(default)
        return str(value).strip()
    except Exception:
        return str(default)

def create_agent_executor(tool_allowlist: List[str] = None, skill_allowlist: List[str] = None, callbacks: List = None):
    """
    创建并配置 Agent Executor
    """
    llm = create_llm()

    # 2. 动态加载工具列表 (Skills)
    # 自动扫描 app.skills 包下的多 Skill 子包
    tools = load_skills(package_name="app.skills")
    mcp_tools = load_mcp_tools()
    if mcp_tools:
        tools.extend(mcp_tools)
    total_tools = len(tools)
    allowed_names = None
    
    # 从环境变量读取全局 skill_allowlist 配置
    env_skill_allowlist = _read_str_env("AGENT_SKILL_ALLOWLIST", "")
    global_allowed_skills = set()
    if env_skill_allowlist:
        for s in env_skill_allowlist.split(","):
            s = s.strip()
            if s:
                global_allowed_skills.add(s)
                
    # 合并传入的 skill_allowlist (优先级更高)
    final_skill_allowlist = set(skill_allowlist) if skill_allowlist else set()
    if not final_skill_allowlist and global_allowed_skills:
        final_skill_allowlist = global_allowed_skills
    elif final_skill_allowlist and global_allowed_skills:
        # 如果两者都存在，取交集？还是并集？通常是传入的参数作为 override
        # 但这里语义是 "allowlist"，所以应该是交集更安全（或者取参数覆盖）
        # 假设参数是用来进一步收窄范围的
        # 但如果是子 agent，可能需要继承全局配置
        # 这里简化处理：如果参数传了，以参数为准；否则用全局
        pass

    if tool_allowlist:
        allowed_names = set([t for t in tool_allowlist if t])
    elif final_skill_allowlist:
        allowed_names = _collect_tools_for_skills(list(final_skill_allowlist))
    
    if allowed_names:
        tools = [t for t in tools if getattr(t, "name", "") in allowed_names]
        print(f"已加载 {total_tools} 个 Tools，启用 {len(tools)} 个 Tools")
    else:
        print(f"已加载 {total_tools} 个 Tools")

    # 3. 获取提示词模板 (动态注入 Tools 信息)
    prompt = get_agent_prompt(tools)

    # 4. 创建 Agent
    # create_tool_calling_agent 适用于支持 Function Calling 的模型 (如 GPT-3.5/4, 豆包等)
    agent = create_tool_calling_agent(llm, tools, prompt)

    # 5. 创建 Executor
    # AgentExecutor 负责运行 Agent，处理循环、错误捕获等
    limits_disabled = _read_bool_env("AGENT_LIMITS_DISABLED", False)
    max_iterations = None if limits_disabled else _read_int_env("AGENT_MAX_ITERATIONS", 50000000)
    max_execution_time = None if limits_disabled else _read_int_env("AGENT_MAX_EXECUTION_TIME", 600)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=max_iterations,
        max_execution_time=max_execution_time,
        callbacks=callbacks
    )

    return executor


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
