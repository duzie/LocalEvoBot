# AICreate 多 Agent 协同架构改造方案

**文档版本**: v1.0  
**创建时间**: 2026-03-02  
**当前架构**: 单 Agent + 工具集（伪多 Agent）  
**目标架构**: 真正的多进程/多端口并行 Agent 协同

---

## 一、现状诊断

### 1.1 核心问题

| 问题 | 描述 | 证据 |
|------|------|------|
| **单进程架构** | 整个系统只有一个 Python 进程 | `main.py` 启动单一 `AgentExecutor` |
| **串行执行** | 所有工具调用按顺序执行，无并行 | LangChain `AgentExecutor.invoke()` 是同步的 |
| **无独立 Agent** | PM/DEV/QA 只是提示词差异，不是独立实例 | `app/agent.py` 只创建一个 LLM + Tools |
| **公告板非消息队列** | SQLite 数据库，非分布式通信 | `board_skill` 仅 CRUD 操作 |
| **无进程隔离** | 一个工具失败影响整个 Agent | 无熔断/降级机制 |

### 1.2 代码结构分析

```
D:\dfCode\AICreate/
├── main.py                    # 72KB, 1724 行 - 单进程入口
├── app/
│   ├── agent.py               # 15KB - 创建单一 AgentExecutor
│   ├── prompts.py             # 15KB - 提示词模板
│   ├── skills/                # 技能目录（工具集）
│   │   ├── board_skill/       # 公告板（SQLite CRUD）
│   │   ├── playwright_skill/  # 浏览器自动化
│   │   ├── uia_skill/         # 桌面自动化
│   │   └── ...                # 30+ 技能
│   └── integrations/
│       ├── mcp_client.py      # MCP 客户端（已集成但未用于多 Agent）
│       └── heartbeat.py       # 心跳管理
└── gateway/                   # WhatsApp 网关（Node.js）
```

### 1.3 当前执行流程

```
用户输入 → main.py → create_agent_executor() → AgentExecutor.invoke()
                                              ↓
                              按顺序调用 Tools (playwright/uia/file...)
                                              ↓
                              返回单一结果
```

**结论**: 这是**单 Agent + 工具集**架构，不是多 Agent 协同。

---

## 二、目标架构设计

### 2.1 架构愿景

#### 3.1.2 代码示例

```python
# agents/pm_agent/main.py (独立 PM Agent 服务)
from fastapi import FastAPI
from langchain_core.messages import HumanMessage

app = FastAPI(title="PM Agent", port=8001)

@app.post("/run")
async def run(task: dict):
    # 独立的 PM Agent 逻辑
    llm = create_llm()
    tools = load_pm_tools()  # 仅加载 PM 相关技能
    agent = create_agent(llm, tools)
    result = agent.invoke({"input": task["description"]})
    return {"status": "ok", "output": result}

# orchestrator/main.py (协调器)
from langgraph.graph import StateGraph
import httpx

class AgentState(TypedDict):
    tasks: list
    results: dict
    current_step: str

async def call_pm_agent(task: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://localhost:8001/run", json=task)
        return resp.json()

async def call_dev_agent(task: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://localhost:8002/run", json=task)
        return resp.json()

# 构建状态图
workflow = StateGraph(AgentState)
workflow.add_node("pm", call_pm_agent)
workflow.add_node("dev", call_dev_agent)
workflow.add_edge("pm", "dev")
app = workflow.compile()
```

---

### 阶段二：通信协议标准化（P1 - 重要）

**目标**: 引入 MCP 协议，实现结构化通信

#### 3.2.1 任务拆解

| 任务 | 描述 | 工作量 | 优先级 |
|------|------|--------|--------|
| **2.1 MCP 服务端实现** | 将现有 `mcp_client.py` 扩展为服务端 | 2 人天 | P1 |
| **2.2 消息 Schema 定义** | 定义标准消息格式 (artifact/task/event) | 1 人天 | P1 |
| **2.3 公告板改造** | SQLite → Redis Stream (支持订阅) | 2 人天 | P1 |
| **2.4 追踪 ID 系统** | 为每个任务生成 trace_id | 1 人天 | P1 |

**阶段二小计**: **6 人天** (约 1.5 周)

#### 3.2.2 消息格式示例

```json
{
  "trace_id": "uuid-1234-5678",
  "message_type": "artifact_ready",
  "protocol": "MCP",
  "timestamp": "2026-03-02T15:00:00Z",
  "producer": "pm_agent_001",
  "consumers": ["dev_agent_001", "qa_agent_001"],
  "payload": {
    "artifact_id": "prd_v1",
    "artifact_type": "document",
    "content_hash": "sha256:abc123...",
    "storage_path": "redis://artifacts/prd_v1"
  }
}
```

---

### 阶段三：容错与可观测性（P2 - 增强）

**目标**: 生产级可靠性

#### 3.3.1 任务拆解

| 任务 | 描述 | 工作量 | 优先级 |
|------|------|--------|--------|
| **3.1 重试机制** | Tenacity 库集成 (指数退避) | 1 人天 | P2 |
| **3.2 熔断器** | 失败阈值 + 自动恢复 | 1 人天 | P2 |
| **3.3 超时控制** | 任务级/Agent 级超时 | 1 人天 | P2 |
| **3.4 结构化日志** | JSON 日志 + trace_id 关联 | 1 人天 | P2 |
| **3.5 指标采集** | Prometheus 指标 (任务完成率/耗时) | 2 人天 | P2 |
| **3.6 工作流可视化** | LangGraph Studio 集成 | 2 人天 | P2 |

**阶段三小计**: **8 人天** (约 2 周)

---

### 阶段四：内存架构升级（P3 - 可选）

**目标**: 三层记忆架构

#### 3.4.1 任务拆解

| 任务 | 描述 | 工作量 | 优先级 |
|------|------|--------|--------|
| **4.1 热记忆 (Redis)** | 对话上下文缓存 (TTL 5 分钟) | 1 人天 | P3 |
| **4.2 温记忆 (Chroma)** | 向量检索 (已有，需优化) | 1 人天 | P3 |
| **4.3 冷记忆 (Neo4j)** | 知识图谱存储长期关系 | 3 人天 | P3 |
| **4.4 记忆同步** | 三层记忆一致性保障 | 2 人天 | P3 |

**阶段四小计**: **7 人天** (约 1.5 周)

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator (协调器)                     │
│              LangGraph 状态图 / 自定义调度器                  │
│                   Port: 8000 (HTTP/gRPC)                     │
└───────────────┬──────────────────┬──────────────────┬───────┘
                │                  │                  │
    ┌───────────▼───────┐ ┌────────▼───────┐ ┌──────▼────────┐
    │   PM Agent        │ │  DEV Agent     │ │  QA Agent     │
    │   (独立进程)       │ │  (独立进程)     │ │  (独立进程)    │
    │   Port: 8001      │ │  Port: 8002    │ │  Port: 8003   │
    │   FastAPI 服务    │ │  FastAPI 服务   │ │  FastAPI 服务  │
    └─────────┬─────────┘ └────────┬───────┘ └───────┬───────┘
              │                    │                  │
              └────────────────────┼──────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      消息总线 (Redis)        │
                    │   PubSub / Stream / Queue   │
                    └─────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      共享存储层             │
                    │  SQLite(短) + Chroma(向量)  │
                    └─────────────────────────────┘
```

### 2.2 核心特性

| 特性 | 实现方式 | 收益 |
|------|----------|------|
| **进程隔离** | 每个 Agent 独立 FastAPI 服务 | 单 Agent 崩溃不影响全局 |
| **并行执行** | 协调器并发调用多个 Agent | 任务完成时间缩短 60-80% |
| **标准通信** | Redis PubSub + MCP 协议 | 支持跨语言/跨系统协作 |
| **状态图编排** | LangGraph 有向图 | 可视化的工作流管理 |
| **动态扩展** | 运行时注册/注销 Agent | 无需重启即可增减角色 |

---

## 三、改造方案（分四阶段）

### 阶段一：基础架构改造（P0 - 必须）

**目标**: 实现真正的多进程 Agent，支持并行执行

#### 3.1.1 任务拆解

| 任务 | 描述 | 工作量 | 优先级 |
|------|------|--------|--------|
| **1.1 创建 Agent 服务框架** | 基于 FastAPI 创建独立 Agent 服务模板 | 2 人天 | P0 |
| **1.2 实现协调器 (Orchestrator)** | LangGraph 状态图 + HTTP 调用 | 3 人天 | P0 |
| **1.3 消息总线集成** | Redis PubSub 通信层 | 2 人天 | P0 |
| **1.4 迁移现有技能** | 将 30+ 技能适配到新架构 | 3 人天 | P0 |
| **1.5 部署脚本** | Docker Compose / systemd 配置 | 1 人天 | P0 |

**阶段一小计**: **11 人天** (约 2.5 周)

---

## 四、工作量总览

### 4.1 分阶段汇总

| 阶段 | 任务数 | 工作量 (人天) | 周期 (周) | 优先级 |
|------|--------|---------------|-----------|--------|
| **阶段一** | 5 | 11 | 2.5 | P0 (必须) |
| **阶段二** | 4 | 6 | 1.5 | P1 (重要) |
| **阶段三** | 6 | 8 | 2.0 | P2 (增强) |
| **阶段四** | 4 | 7 | 1.5 | P3 (可选) |
| **总计** | **19** | **32** | **7.5** | - |

### 4.2 最小可行改造 (MVP)

如果资源有限，建议只实施 **阶段一 + 阶段二核心任务**：

| 任务 | 工作量 | 说明 |
|------|--------|------|
| 创建 Agent 服务框架 | 2 人天 | FastAPI 模板 |
| 实现协调器 | 3 人天 | LangGraph 状态图 |
| 迁移核心技能 (10 个) | 2 人天 | 优先迁移高频技能 |
| 部署脚本 | 1 人天 | Docker Compose |
| **MVP 总计** | **8 人天** | **约 2 周** |

**MVP 收益**:
- ✅ 真正的多进程 Agent
- ✅ 并行执行能力
- ✅ 进程级隔离
- ❌ 无 MCP 协议（用 HTTP 代替）
- ❌ 无高级容错

---

## 五、风险评估

### 5.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| LangGraph 学习曲线 | 中 | 中 | 先做 PoC 验证 |
| Redis 运维复杂度 | 低 | 中 | 使用 Docker 部署 |
| 技能迁移兼容性 | 高 | 高 | 保持向后兼容 |
| 性能瓶颈 (HTTP 调用) | 中 | 中 | 使用连接池 + gRPC |

### 5.2 迁移风险

| 风险 | 缓解措施 |
|------|----------|
| 现有功能回归 | 保留旧架构，灰度发布 |
| 数据丢失 | 双写 SQLite + Redis，逐步切换 |
| 用户习惯改变 | 保持 API 接口不变 |

---

## 六、实施建议

### 6.1 团队配置

| 角色 | 人数 | 职责 |
|------|------|------|
| 架构师 | 1 | 整体设计 + 代码审查 |
| 后端开发 | 2 | Agent 服务 + 协调器开发 |
| DevOps | 1 | 部署 + 监控 |
| 测试 | 1 | 自动化测试 + 性能测试 |

**建议**: 3-4 人团队，7.5 周完成全部改造

### 6.2 里程碑

```
Week 1-2:  阶段一 (基础架构)
Week 3:    阶段二 (通信协议)
Week 4-5:  阶段三 (容错可观测)
Week 6-7:  阶段四 (记忆升级)
Week 8:    灰度发布 + 性能调优
```

### 6.3 技术选型建议

| 组件 | 推荐方案 | 备选方案 |
|------|----------|----------|
| 协调器 | LangGraph | AutoGen / CrewAI |
| 消息总线 | Redis PubSub | RabbitMQ / Kafka |
| 服务框架 | FastAPI | Flask / gRPC |
| 部署 | Docker Compose | Kubernetes |
| 监控 | Prometheus + Grafana | LangSmith |
| 向量库 | Chroma (已有) | Qdrant / Milvus |
| 知识图谱 | Neo4j | NebulaGraph |

---

## 七、结论

### 7.1 工作量评估

- **完整改造**: **32 人天** (约 7.5 周，3-4 人团队)
- **MVP 改造**: **8 人天** (约 2 周，2 人团队)

### 7.2 是否值得改造？

| 场景 | 建议 |
|------|------|
| 个人项目/小团队 (<3 人) | ❌ 不建议，维持现状 |
| 中型团队 (3-10 人) | ✅ 建议 MVP 改造 |
| 企业级/生产环境 | ✅✅ 强烈建议完整改造 |
| 需要高并发/高可用 | ✅✅ 必须改造 |

### 7.3 核心收益

1. **性能提升**: 并行执行可缩短 60-80% 任务时间
2. **可靠性**: 进程隔离，单点故障不影响全局
3. **可扩展**: 运行时动态增减 Agent
4. **可观测**: 完整追踪链路 + 指标监控
5. **标准化**: MCP 协议支持跨系统协作

---

## 附录 A: 快速启动 MVP 示例

```bash
# 1. 创建项目结构
mkdir -p agents/{pm,dev,qa}/app
mkdir -p orchestrator

# 2. 安装依赖
pip install fastapi uvicorn langgraph redis httpx

# 3. 启动 Redis
docker run -d --name redis -p 6379:6379 redis:7

# 4. 启动 PM Agent
cd agents/pm && uvicorn app.main:app --port 8001

# 5. 启动 DEV Agent
cd agents/dev && uvicorn app.main:app --port 8002

# 6. 启动协调器
cd orchestrator && python main.py

# 7. 测试
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"task": "开发登录功能"}'
```

---

**文档结束**
