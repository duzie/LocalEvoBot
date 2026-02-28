# 我是小冬瓜 / 自进化本地自动化 Agent

一个基于 LangChain 的智能电脑操作 Agent，不仅支持 Windows UI Automation、OCR、Web 自动化，更具备**自我进化能力**——能根据任务需求自动编写新技能、热加载并立即使用，无需重启。

**核心能力**
- **自我进化 (Self-Evolution)**：
  - 遇到未知任务时，自动生成工具脚手架 (`scaffold_skill`)
  - 自动编写 Python 实现代码 (`write_tool_code`)
  - 运行时热加载新技能 (`reload_skills`)，即刻生效并自动继续任务
  - 优质技能一键转正 (`promote_skill`)，沉淀为核心能力
- **RAG 长时记忆 (Long-term Memory)**：
  - **向量化存储**：内置 ChromaDB 本地向量数据库，无需联网即可高效存储经验
  - **语义检索**：集成 HuggingFace 嵌入模型 (all-MiniLM-L6-v2)，支持自然语言模糊搜索
  - **经验沉淀**：自动积累任务执行中的成功/失败经验，实现“越用越聪明”
- **个人认知与任务模板**：
  - **结构化总结**：任务完成后自动生成偏好与经验总结，用户确认后入库
  - **任务模板**：将已完成流程抽象为模板，下次命中时可一键套用
  - **模板+经验互补**：模板给流程骨架，经验补充关键决策与注意点
- **流式输出**：聊天与控制台支持逐字流式展示，响应更即时
- **自动多步执行**：基于 `STATE` 状态机的多轮自动执行与任务拆解
- **审计日志系统**：
  - **全量记录**：自动记录所有工具调用的参数、结果、耗时、状态
  - **Web 可视化**：美观的日志管理界面，支持多维度筛选与全文搜索
  - **问题排查**：快速定位失败原因，追溯操作历史
  - **性能分析**：统计工具调用频率与耗时，识别性能瓶颈
- **多角色公告板协作**：角色拆解、任务流转与产物回写，支持并发执行
  - **依赖调度**：自动识别依赖链，无依赖并行、有依赖串行（`deps` + `dep_policy=all/any/none`）
- **短期记忆追踪**：记录工具调用的输入/输出/耗时，写入本地短期记忆与 Markdown 便于排障
- **UI Automation**：基于 Windows UIA 精准定位与操作原生控件
- **Web 自动化**：内置 Playwright 支持，接管浏览器进行复杂网页交互
- **视觉与 OCR**：屏幕/窗口文字识别，辅助定位与决策
- **系统控制**：文件操作、进程管理、键盘鼠标模拟
- **Web 控制台**：移动端友好的网页界面（聊天、日志、配置、局域网地址与二维码）

## 变更记录

### 2026-02-22
- Web 对话区“工具/思考详情”展开状态可保持，新增消息不再自动折叠
- Web 对话滚动：仅在用户位于底部附近时自动跟随滚动，避免查看历史时被拉回底部
- Web 发送/停止按钮状态与后端执行状态对齐，避免执行中误显示“发送”
- 热加载与续跑上下文：注入本轮工具轨迹（文件路径/行范围/分块信息），减少重复读取与“失忆”式重做
- 对话历史与短期记忆写入增加长度上限，避免大段文件原文导致上下文溢出
- 大文件读取工具 `read_large_file_chunks` 改为分页限量返回，避免一次性把全文件分块塞进上下文
- 对话摘要逻辑增加硬裁剪（单条/总量），进一步降低模型最大上下文超限（131072 tokens）风险

### 2026-02-21
- 统一 Playwright 与浏览器工具的错误结构和结构化事件输出
- 补齐 system_skill 多个工具的结构化错误返回与事件广播
- 为进程查询与命令执行补充超时控制与统一返回格式
- 修复 run_shell_command 的解码逻辑，支持多编码自动识别
- 文档读取类工具加入多编码回退，避免中文乱码
- 旧版 skill 入口读取兜底，空 Entry 自动推断 scripts 包
- 关闭默认工具路由过滤，避免自动禁用已加载工具
- 模板确认增加 5 秒倒计时，超时默认不使用（控制台与网页端）

## 更新说明

- 模板确认：5 秒内不选择则自动按“不使用”处理
- 工具启用：默认不再按路由过滤，加载即启用
- 编码兼容：命令输出与文档读取自动尝试常见中文编码
- 旧 Skill 兼容：空 Entry 自动识别 scripts 入口
- 技能自进化：技能页新增“新增技能”模态框，支持自然语言（或 JSON 规格）生成技能
- 自动测试闭环：后端新增 `/api/skills/generate`，生成后自动做可加载性检测与用例调用测试，并触发热重载

## 快速开始

**安装依赖**
```bash
pip install -r requirements.txt
```

**准备 .env**
```
# 选择模型提供方（可选，默认 deepseek）
LLM_PROVIDER=deepseek

# Web 控制台（可选）
WEB_HOST=0.0.0.0
WEB_PORT=5011

LOCAL_MODEL_PATH=...
LOCAL_CTX_SIZE=4096
LOCAL_GPU_LAYERS=0
LOCAL_THREADS=8
LOCAL_BATCH_SIZE=512
LOCAL_TEMPERATURE=0.7

# DeepSeek（示例）
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_NAME=deepseek-chat

# Qwen（示例）
QWEN_API_KEY=...
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL_NAME=qwen-plus

# OpenAI（示例）
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4o-mini

# NVIDIA NIM / API Catalog（示例）
NIM_API_KEY=...
NIM_BASE_URL=https://integrate.api.nvidia.com/v1
# NIM_MINIMAX_M2_MODEL_NAME=minimaxai/minimax-m2
# NIM_GLM47_MODEL_NAME=z-ai/glm4.7

DOUBAO_VISION_MODEL_NAME=...
```

**运行**
```bash
python main.py
```

运行后会同时启动 Web 控制台（默认端口 `5011`），浏览器打开：
- `http://127.0.0.1:5011/audit-logs.html`（审计日志）
- `http://127.0.0.1:5011/`

在 Web 控制台中：
- 可切换模型（下拉框）
- 可编辑 `.env` 配置
- 可显示局域网地址并生成二维码，方便手机访问
- **审计日志**：查看所有工具调用记录，支持筛选和搜索
- 提供日志与对话的 WebSocket 实时流

**Web 控制台接口**
- 配置管理：`/api/config`
- 访问地址与局域网发现：`/api/config/access-url`、`/api/config/hosts`
- 心跳任务：`/api/config/heartbeat/tasks`、`/api/config/heartbeat/update`
- 日志 WebSocket：`/api/logs/ws`
- 对话 WebSocket：`/api/chat/ws`

**Web 控制台页面**
- 对话：`/index.html`
- 日志：`/logs.html`
- 配置：`/config.html`
- 模板：`/templates.html`
- 记忆：`/memories.html`
- 审计日志：`/audit-logs.html`
- Cookie：`/cookies.html`

## 个人认知与模板使用

**任务结束总结**
- 当任务输出 `STATE: DONE` 时，会生成结构化总结
- 若总结包含可复用内容，会提示是否保存到经验库

**模板套用**
- 新任务开始时会检索项目级模板
- 仅在检测到明确任务意图时才会提示套用模板（避免闲聊触发）
- 命中模板会询问是否套用，并同时拉取相关经验补充细节

**经验与模板关系**
- 经验：记录关键决策、注意事项与偏好
- 模板：记录稳定可复用的流程步骤
- 二者互补使用，不互相替代

## 使用示例

```
显示桌面
帮我把桌面上所有 png 移动到 D:/screenshots
读取 Excel 里 A 列总和并保存结果
```

## 模型与提供方

通过 `.env` 的 `LLM_PROVIDER` 选择模型提供方（也可在 Web 控制台里切换）：
- `deepseek`
- `qwen`
- `openai`
- `local`
- `nim_minimax_m2`（NVIDIA NIM / API Catalog：`minimaxai/minimax-m2`）
- `nim_glm47`（NVIDIA NIM / API Catalog：`z-ai/glm4.7`）

对应的关键环境变量：
- DeepSeek：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL_NAME`
- Qwen：`QWEN_API_KEY`（或 `DASHSCOPE_API_KEY`）、`QWEN_BASE_URL`、`QWEN_MODEL_NAME`
- OpenAI：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL_NAME`
- Local：`LOCAL_MODEL_PATH`、`LOCAL_CTX_SIZE`、`LOCAL_GPU_LAYERS`、`LOCAL_THREADS`、`LOCAL_BATCH_SIZE`、`LOCAL_TEMPERATURE`
- NVIDIA NIM：`NIM_API_KEY`、`NIM_BASE_URL`、`NIM_MINIMAX_M2_MODEL_NAME`、`NIM_GLM47_MODEL_NAME`
- Web 控制台：`WEB_HOST`、`WEB_PORT`、`PUBLIC_URL`
- Playwright：`PLAYWRIGHT_USER_DATA_DIR`、`PLAYWRIGHT_EXTENSION_DIR`、`PLAYWRIGHT_AUTO_LOAD_COOKIES`

## Playwright 登录复用

- Cookie 文件默认保存于 `app/data/cookies/<domain>.json`
- 默认会尝试加载 `web/extension/cookie_relay` 作为扩展（需 `headless=False`）
- 推荐流程：
  1. 打开浏览器并登录站点（加载扩展）
  2. 扩展保存 Cookie
  3. 再次打开时自动载入 Cookie

## 心跳机制

心跳机制用于调度各类后台监听与保活任务，可在运行时统一管理。

**注册心跳任务**
```python
from app.integrations import heartbeat

def _my_tick():
    pass

def start_my_feature():
    heartbeat.register_task(
        "my_feature_heartbeat",
        _my_tick,
        interval=5.0
    )
```

**最简可用步骤**
- 1) 在任意模块里写一个 `start_xxx()`，内部调用 `heartbeat.register_task(...)`
- 2) 在 `main.py` 启动时调用 `start_xxx()`，或在模块加载时主动调用
- 3) 打开配置页 → “心跳任务”，确认任务已出现并可调整间隔/暂停

**示例（在 integrations 中新增任务）**
```python
from app.integrations import heartbeat

def _sample_tick():
    return

def start():
    heartbeat.register_task(
        "sample_task",
        _sample_tick,
        interval=3.0
    )
```

**示例（在 main.py 启动时调用）**
```python
from app.integrations import sample_task

def main():
    sample_task.start()
```

**配置页管理**
- 配置页新增“心跳任务”区域，可查看任务并修改间隔/暂停
- 间隔留空表示使用默认间隔
- 暂停仅对当前进程有效，重启后恢复默认

## Skills 概览

### 核心技能 (app/skills)
**1. 自进化 (SkillGen)**
- `inspect_environment`: 查看环境、依赖与可用技能列表
- `scaffold_skill`: 生成新技能目录结构
- `write_tool_code`: 编写或修改工具代码
- `list_change_versions`: 列出最近变更版本
- `rollback_change`: 回滚到最近稳定版本或指定版本
- `search_change_logs`: 关键词检索变更溯源日志
- `export_change_logs`: 导出变更日志（JSON/CSV）
- `promote_skill`: **技能转正**。将 `auto_skills` 中验证通过的技能一键迁移至 `app/skills`，成为永久核心能力
- `reload_skills`: **热加载与自动回复**。运行时重载所有技能，并自动读取上一轮任务状态，无缝继续执行 (Auto-Resume)

**2. 公告板与多角色协作 (Board)**
- `create_board`: 创建公告板
- `add_board_role`: 新增角色
- `add_board_task`: 新增任务
- `run_role_agent`: 单角色任务执行
- `run_role_agents_parallel`: 并发执行多个角色任务

**2. UI Automation (Windows)**
- `uia_find_control`: 定位窗口控件
- `uia_click_control`: 点击控件
- `uia_list_controls`: 遍历控件树

**3. Web 自动化 (Playwright)**
- `playwright_open`: 打开网页
- `playwright_click` / `playwright_type`: 网页交互
- `playwright_run_steps`: 批量执行网页操作

**4. 视觉与 OCR**
- `ocr_screen` / `ocr_window`: 文字识别
- `take_screenshot`: 屏幕截图

**5. 系统与文件**
- `add_operation_experience`: 记录经验到向量库 (RAG)
- `get_operation_experience`: 语义检索历史经验
- `file_directory_skill`: **文件目录操作**。列出目录内容、搜索文件、获取详细信息 (支持递归与正则)
- `file_save_skill`: **文件保存**。智能保存文本/代码到指定路径，自动处理目录创建与编码
- `file_organize`: 文件整理
- `check_process_status`: 进程检查
- `mouse_click` / `type_text`: 键鼠模拟

### 自动生成技能 (app/auto_skills)
Agent 根据任务需求自动生成的技能存放于此，例如：
- `file_directory_skill`: 复杂文件搜索与列表
- `excel_read_skill`: 特定 Excel 处理逻辑
- ... (随使用自动增长)

## 技能加载规则

- 每个技能目录必须包含 `skill.md`，并在 `## Entry` 指向 `...scripts` 包路径
- `app/skills` 为核心技能，`app/auto_skills` 为自动生成技能
- 新技能生成后执行 `reload_skills` 触发热加载

## 目录结构

```
app/
  agent.py         Agent 核心逻辑与 LLM 配置
  prompts.py       System Prompt 与自动化策略
  skills/          [核心技能] 手动维护的基础能力
    registry.py    技能注册与动态加载器
  auto_skills/     [扩展技能] Agent 自动编写的技能库
web/
  backend/         Web 控制台后端（FastAPI）
  frontend/        Web 控制台前端（纯 HTML/CSS/JS）
main.py            程序入口、热加载循环与状态管理
requirements.txt   项目依赖
```

## 模块文档

- app 目录说明：见 app/README.md
- gateway 目录说明：见 gateway/README.md
- web 目录说明：见 web/README.md

## 运行环境说明

- UI Automation 仅支持 Windows
- OCR 依赖 Tesseract，本机需安装并确保 `tesseract` 可在 PATH 中访问。
  - **安装指南**:
    1. 下载安装包: [Tesseract at UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
    2. 安装时勾选 "Additional language data (download)" -> "Chinese (Simplified)"
    3. 建议安装到默认路径 `C:\Program Files\Tesseract-OCR`，本程序会自动检测
    4. 如果安装到其他路径，请手动将安装目录添加到系统环境变量 `PATH` 中
- 视觉理解依赖具备视觉能力的模型，使用 `.env` 中的 `DOUBAO_VISION_MODEL_NAME`

## 自动执行机制

程序会根据 Agent 输出中的 `STATE: CONTINUE` 或 `STATE: DONE` 自动进行多轮调用，直到任务完成或达到上限。

## 大文件与上下文控制

当任务涉及超长代码/文档时，优先使用“分块读取 + 轨迹推进”的方式，避免将整段文件原文塞入对话历史导致模型报错。

- `read_document_part`：按行读取，默认带 `max_chars` 截断（适合定点查看/逐段读取）
- `read_large_file_chunks`：分页返回少量分块（通过 `start_chunk` / `max_chunks` 继续读取）
- 热加载与自动续跑：会带上本轮工具轨迹（文件路径/行范围/分块索引/是否截断），用于继续下一段而不是从头重复

## 运行限制与停止

### 运行上限（步数/时间）

`AgentExecutor` 默认启用运行上限，防止无限循环：
- `AGENT_MAX_ITERATIONS`：最大步数，默认 `50000000`
- `AGENT_MAX_EXECUTION_TIME`：最大执行时间（秒），默认 `600`

当 `AGENT_LIMITS_DISABLED=1/true` 时，将忽略以上两个上限（传入 `None`），任务仅受显式停止/链路结束影响。

可在 Web 配置页 `/config.html` 的 “Agent 运行参数” 中设置：
- “是否解除限制”：是（解除限制）/ 否（保持限制）
- “最大步数”、“最大执行时间(秒)”：保存后对新会话生效

### 停止当前任务

- Web 控制台点击 “停止” 会调用后端接口：`POST /api/chat/stop`
- 正常情况下，停止后状态会从 “执行中” 变为 “已停止/空闲”，按钮回到 “发送”
- 如果发生异常或进程被中断，建议刷新页面；若后端进程仍卡在旧代码/旧状态，重启 `python main.py`（`reload_skills` 只热加载技能，不会重载 `main.py`）

<img width="2085" height="1359" alt="" src="https://github.com/user-attachments/assets/c2432457-359b-430b-9b35-2faad619d138" />

