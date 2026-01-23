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
    # 1. 配置 LLM
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

    # 2. 动态加载工具列表 (Skills)
    # 自动扫描 app.skills 包下的多 Skill 子包
    tools = load_skills(package_name="app.skills")
    print(f"已加载 {len(tools)} 个 Skills: {[t.name for t in tools]}")

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
        max_iterations=100,
        max_execution_time=600
    )

    return executor
