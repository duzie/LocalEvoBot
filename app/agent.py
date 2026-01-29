import os
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from dotenv import load_dotenv

from app.skills.registry import load_skills
from app.prompts import get_agent_prompt

# 加载环境变量
load_dotenv()

def create_agent_executor():
    """
    创建并配置 Agent Executor
    """
    provider = (os.getenv("LLM_PROVIDER") or "deepseek").strip().lower()

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
        )
    elif provider == "qwen":
        api_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        base_url = os.getenv("QWEN_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        model_name = os.getenv("QWEN_MODEL_NAME") or "qwen-plus"
        if not api_key:
            raise ValueError("请确保 .env 文件中配置了 QWEN_API_KEY (或 DASHSCOPE_API_KEY)")
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7,
        )
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        model_name = os.getenv("OPENAI_MODEL_NAME") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        if not api_key:
            raise ValueError("请确保 .env 文件中配置了 OPENAI_API_KEY")
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7,
        )
    elif provider in {"nim_minimax_m2", "nim_glm47"}:
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
        )
    else:
        raise ValueError(f"不支持的 LLM_PROVIDER: {provider}")

    # 2. 动态加载工具列表 (Skills)
    # 自动扫描 app.skills 包下的多 Skill 子包
    tools = load_skills(package_name="app.skills")
    print(f"已加载 {len(tools)} 个 Skills")

    # 3. 获取提示词模板 (动态注入 Tools 信息)
    prompt = get_agent_prompt(tools)

    # 4. 创建 Agent
    # create_tool_calling_agent 适用于支持 Function Calling 的模型 (如 GPT-3.5/4, 豆包等)
    agent = create_tool_calling_agent(llm, tools, prompt)

    # 5. 创建 Executor
    # AgentExecutor 负责运行 Agent，处理循环、错误捕获等
    executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=1000,
        max_execution_time=600
    )

    return executor
