# 小冬瓜 / 自进化本地自动化 Agent

一个基于 LangChain 的智能电脑操作 Agent，具备**自我进化能力**——能根据任务需求自动编写新技能、热加载并立即使用，无需重启。支持 Windows UI Automation、OCR、Web 自动化、多 Agent 协作、RAG 长时记忆、完整审计日志等高级功能。

**当前时间**: 2026-03-10  
**版本**: 1.1.0 (持续进化中)

---

## 🚀 核心能力

### 1. 自我进化 (Self-Evolution)
- **自动生成技能**: 遇到未知任务时，自动调用 `scaffold_skill` 生成工具脚手架
- **代码编写**: 使用 `write_tool_code` 自动编写 Python 实现代码
- **热加载**: 通过 `reload_skills` 运行时热加载新技能，即刻生效并自动继续任务
- **技能转正**: 优质技能通过 `promote_skill` 一键迁移至核心库 (`app/skills`)
- **版本控制**: 完整的变更日志、快照机制、加密存储、原子回滚

### 2. RAG 长时记忆 (Long-term Memory)
- **向量化存储**: 内置 ChromaDB 本地向量数据库，无需联网即可高效存储经验
- **语义检索**: 集成 HuggingFace 嵌入模型 (all-MiniLM-L6-v2)，支持自然语言模糊搜索
- **经验沉淀**: 自动积累任务执行中的成功/失败经验，实现"越用越聪明"
- **多库支持**: 支持按项目/用户/标签/范围/记忆类型多维度检索

### 3. 短期记忆追踪
- **SQLite 存储**: 本地存储最近对话历史，支持按角色/项目/用户检索
- **自动归档**: 每日自动归档到 Markdown 文件，便于排障和审计
- **上下文注入**: 任务执行时自动注入相关历史对话，避免"失忆"

### 4. 多角色公告板协作 (Multi-Agent Board)
- **角色定义**: 支持自定义角色和技能绑定
- **任务调度**: 自动识别依赖链，无依赖并行、有依赖串行
- **工作流引擎**: 支持创建工作流、启动/暂停/推进工作流
- **消息系统**: 完整的消息发送/接收/确认/超时处理机制
- **健康监控**: 消息队列健康检查、死信告警、自动清理

### 5. 审计日志系统
- **全量记录**: 自动记录所有工具调用的参数、结果、耗时、状态
- **Web 可视化**: 美观的日志管理界面，支持多维度筛选与全文搜索
- **WebSocket 实时流**: 日志实时更新，无需刷新页面
- **性能分析**: 统计工具调用频率与耗时，识别性能瓶颈

### 6. 任务模板系统
- **结构化总结**: 任务完成后自动生成偏好与经验总结
- **模板套用**: 新任务开始时自动检索并提示套用相似模板
- **模板 + 经验互补**: 模板给流程骨架，经验补充关键决策与注意点
- **5 秒倒计时**: 模板确认超时自动按"不使用"处理

### 7. 流式输出
- **逐字展示**: 聊天与控制台支持逐字流式展示，响应更即时
- **状态对齐**: 发送/停止按钮状态与后端执行状态精确对齐

### 8. 自动化执行
- **STATE 状态机**: 基于 `STATE: DONE` / `STATE: CONTINUE` 的多轮自动执行
- **任务拆解**: 复杂任务自动拆解为多步骤计划
- **自动续跑**: 热加载后自动读取上一轮任务状态，无缝继续执行

---

## 🛠️ 完整技能清单

### 核心技能 (app/skills) - 27 个

| 技能名称 | 功能描述 |
|----------|----------|
| **skillgen_skill** | 技能生成与管理（脚手架、代码编写、热加载、版本控制、回滚） |
| **board_skill** | 多角色公告板与 Agent 调度（任务/工作流/消息/健康监控） |
| **system_skill** | 系统级操作（进程管理、终端命令、截图、时间、经验记忆、任务计划） |
| **playwright_skill** | Web 自动化（打开网页、点击、输入、等待、截图、Cookie 管理、抓包） |
| **browser_skill** | 浏览器控制（导航、填充、点击、截图、JS 执行、快照） |
| **uia_skill** | Windows UI Automation（控件定位、点击、遍历控件树） |
| **input_skill** | 输入控制（文本输入、全选、输入法切换、键盘按键） |
| **pyautogui_skill** | 键鼠模拟（鼠标点击/移动、键盘输入、滚轮、热键） |
| **ocr_skill** | OCR 文字识别（屏幕/窗口 OCR、多语言支持） |
| **vision_ocr_skill** | 视觉 OCR（Doubao Vision 验证码识别） |
| **eyes_skill** | 视觉定位（UI 元素视觉定位、坐标点击、批量查找） |
| **file_skill** | 文件操作（复制、移动、删除、重命名、获取信息） |
| **file_directory_skill** | 目录操作（列出目录、搜索文件、递归遍历） |
| **file_save_skill** | 文件保存（智能保存文本/代码、自动创建目录、编码处理） |
| **file_lock_skill** | 文件锁（获取/检查/释放/续租文件锁） |
| **office_skill** | Office 处理（Excel 读取/求和、PPT 生成） |
| **tavily_skill** | 网页搜索（Tavily API 搜索、深度搜索、答案摘要） |
| **gnews_skill** | 新闻获取（GNews 头条、新闻搜索、保存） |
| **git_skill** | Git 版本控制（克隆、提交、推送、分支管理） |
| **windows_task_skill** | Windows 计划任务（创建定时任务、无需管理员权限） |
| **utility_skill** | 工具函数（数学计算） |
| **task_plan_guide_skill** | 任务规划指南（获取任务拆解规则） |
| **skilltest_skill** | 技能测试（测试用例执行、可加载性验证、需求评估） |
| **project_skeleton_skill** | 项目骨架（生成/缓存目录模块地图） |
| **seedream_skill** | 图像生成（Seedream 图像生成） |
| **code_review_skill** | 代码审查（代码质量检查、问题诊断、改进建议） |
| **deep_analysis_skill** | 深度分析（复杂问题拆解、多维度分析） |

### 自动生成技能 (app/auto_skills) - 32 个

Agent 根据任务需求自动生成的技能，随使用自动增长：

| 技能名称 | 功能描述 |
|----------|----------|
| **archive_skill** | 文件归档（创建 zip 压缩包） |
| **audio_transcribe_skill** | 音频转写（语音转文字） |
| **cache_skill** | 缓存管理（数据缓存、读取、清理） |
| **code_analysis_skill** | 代码分析（分析代码文件/目录、提取 API 端点） |
| **context_management_skill** | 上下文管理（对话上下文维护） |
| **coupon_agent_skill** | 优惠券 Agent（CRM.CRMChat 接口调用） |
| **documentation_skill** | 文档生成（自动生成文档） |
| **document_skill** | 文档处理（提取章节、统计信息、插入文本、分块读取、搜索） |
| **excel_read_skill** | Excel 读取（读取工作表、数据提取） |
| **file_delete_skill** | 文件删除（单文件/批量删除） |
| **http_request_skill** | HTTP 请求（发送 GET/POST/PUT/DELETE 请求） |
| **image_download_skill** | 图片下载（单张/批量下载、URL 验证） |
| **image_processing_skill** | 图片处理（缩放、裁剪、格式转换、批量调整） |
| **large_file_processing_skill** | 大文件处理（分块读取、锚点替换、安全合并、语法验证） |
| **linter_skill** | 代码检查（语法检查、格式校验） |
| **mail_126_skill** | 126 邮件发送（支持附件） |
| **moltbook** | Moltbook 社区操作（发帖、评论、点赞、关注等 20+ 工具） |
| **openscmskill** | SCM 页面打开（菜么么库存页面） |
| **open_caimomo_target_page** | 菜么么系统导航（动态菜单定位、采购入库流程） |
| **ppt_gen_skill** | PPT 生成（主题模板、图文混排） |
| **precise_code_editing_skill** | 精确代码编辑（精准代码修改） |
| **quick_edit_skill** | 快速编辑（快速文件修改） |
| **safe_file_editing_skill** | 安全文件编辑（C#/Python/JSON 专用编辑器、备份回滚） |
| **smart_file_reader_skill** | 智能文件读取（智能读取大文件） |
| **sqlserver_skill** | SQL Server 数据库操作 |
| **stock_data_collection_skill** | 股票数据采集 |
| **stock_trading_skill** | 股票交易操作 |
| **stock_unified_skill** | 股票数据（实时行情、历史数据、缓存管理、搜索） |
| **test_skill** | 测试执行（单元测试、集成测试） |
| **vector_index_skill** | 向量索引（向量数据库索引管理） |
| **web_validator_skill** | Web 验证（网页有效性检查） |
| **word_processor** | 文字处理（Word 文档操作） |

### 消息渠道集成 (channels/)

| 渠道 | 功能描述 |
|------|----------|
| **dingtalk** | 钉钉机器人集成（发送文本消息、@提醒） |
| **feishu** | 飞书机器人集成（发送文本消息、签名校验） |
| **wecom** | 企业微信集成 |

---

## 🌐 Web 控制台

### 功能页面

| 页面 | 路径 | 功能 |
|------|------|------|
| 对话 | `/` | 聊天界面、流式输出、模板确认 |
| 审计日志 | `/audit-logs.html` | 工具调用记录、筛选搜索、WebSocket 实时流 |
| 配置 | `/config.html` | 模型切换、.env 编辑、心跳任务管理、局域网地址 |
| 模板 | `/templates.html` | 任务模板管理 |
| 记忆 | `/memories.html` | 长时记忆检索与查看 |
| Cookie | `/cookies.html` | Playwright Cookie 管理 |

### API 接口

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/config` | GET/POST | 配置管理 |
| `/api/config/access-url` | GET | 获取访问地址 |
| `/api/config/hosts` | GET | 局域网地址发现 |
| `/api/config/heartbeat/tasks` | GET | 心跳任务列表 |
| `/api/config/heartbeat/update` | POST | 更新心跳任务 |
| `/api/logs/ws` | WebSocket | 日志实时流 |
| `/api/chat/ws` | WebSocket | 对话实时流 |
| `/api/skills/generate` | POST | 技能生成（自动测试 + 热重载） |

### 特色功能

- **模型切换**: 下拉框快速切换 LLM 提供方
- **心跳任务**: 可视化配置后台监听任务间隔/暂停
- **技能生成 UI**: 自然语言或 JSON 规格生成新技能
- **局域网访问**: 显示局域网地址并生成二维码，方便手机访问
- **实时流**: 日志与对话 WebSocket 实时更新

---

## 🔌 集成与扩展

### 模型支持

通过 `.env` 的 `LLM_PROVIDER` 选择模型提供方：

| 提供方 | 环境变量 | 示例模型 |
|--------|----------|----------|
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat |
| Qwen (阿里) | `QWEN_API_KEY` | qwen-plus |
| OpenAI | `OPENAI_API_KEY` | gpt-4o-mini |
| NVIDIA NIM | `NIM_API_KEY` | minimaxai/minimax-m2, z-ai/glm4.7 |
| 本地模型 | `LOCAL_MODEL_PATH` | llama-cpp-python 加载 |

### MCP 客户端

- 支持 Model Context Protocol (MCP) 工具扩展
- 自动加载 MCP 服务器工具
- 与本地技能无缝集成

### WA Gateway (WhatsApp)

- 支持 WhatsApp 消息网关
- 提供 `baileys` / `cloud` / `official` / `business` 多种 Provider
- 自动安装依赖、健康检查、子进程管理

### Playwright 登录复用

- Cookie 文件保存于 `app/data/cookies/<domain>.json`
- 支持扩展自动保存 Cookie (`web/extension/cookie_relay`)
- 再次打开时自动载入 Cookie，无需重复登录

---

## 📁 项目结构

```
langchain/
├── main.py                     # 程序入口、热加载循环、状态管理
├── requirements.txt            # Python 依赖
├── model.json                  # 模型配置
├── HEARTBEAT.md                # 心跳机制文档
├── contact.txt                 # 联系方式
│
├── app/
│   ├── agent.py                # Agent 核心逻辑、LLM 配置、重试包装
│   ├── prompts.py              # System Prompt 与自动化策略
│   ├── registry.py             # 技能注册与动态加载器
│   │
│   ├── skills/                 # [核心技能] 31 个手动维护技能
│   │   ├── skillgen_skill/     # 技能生成与管理
│   │   ├── board_skill/        # 多角色公告板
│   │   ├── system_skill/       # 系统操作
│   │   ├── playwright_skill/   # Web 自动化
│   │   ├── uia_skill/          # UI Automation
│   │   ├── git_skill/          # Git 版本控制
│   │   ├── code_review_skill/  # 代码审查
│   │   ├── deep_analysis_skill/# 深度分析
│   │   └── ... (31 个)
│   │
│   ├── auto_skills/            # [扩展技能] Agent 自动生成 (32 个)
│   │   ├── archive_skill/
│   │   ├── code_analysis_skill/
│   │   ├── stock_unified_skill/
│   │   └── ... (随使用增长)
│   │
│   ├── context/                # 上下文管理
│   │   └── transcript_manager.py  # 对话记录管理
│   │
│   ├── integrations/           # 第三方集成
│   │   ├── audit_logger.py     # 审计日志
│   │   ├── heartbeat.py        # 心跳机制
│   │   └── mcp_client.py       # MCP 客户端
│   │
│   └── data/                   # 数据目录
│       ├── experience_db*      # ChromaDB 向量数据库 (RAG)
│       ├── short_term_memory*.sqlite3  # 短期记忆 (每日归档)
│       ├── audit_logs.db       # 审计日志数据库
│       ├── devops/             # DevOps 数据
│       │   ├── change_history.sqlite3  # 变更历史
│       │   ├── devops.key      # 加密密钥
│       │   └── snapshots/      # 文件快照 (回滚用)
│       ├── stock_cache/        # 股票数据缓存
│       ├── project_skeleton/   # 项目骨架缓存
│       ├── cookies/            # Playwright Cookie
│       └── playwright_user_data/  # 浏览器用户数据
│
├── channels/                   # 消息渠道集成
│   ├── dingtalk/               # 钉钉
│   ├── feishu/                 # 飞书
│   └── wecom/                  # 企业微信
│
├── web/
│   ├── backend/                # Web 控制台后端 (FastAPI)
│   │   ├── main.py             # 后端入口
│   │   ├── shared.py           # 共享状态
│   │   └── ...
│   ├── frontend/               # Web 控制台前端 (纯 HTML/CSS/JS)
│   │   ├── index.html          # 对话页面
│   │   ├── audit-logs.html     # 审计日志
│   │   ├── config.html         # 配置页面
│   │   └── ...
│   └── extension/              # 浏览器扩展 (Cookie 保存)
│
├── src/
│   └── frontend/               # 前端源码
│
├── gateway/                    # WA Gateway (Node.js)
│   ├── index.js
│   └── node_modules/
│
├── images/                     # 图片输出目录
├── screenshots/                # 截图保存目录
└── memory/                     # 记忆文件
    ├── MEMORY.md               # 长期记忆
    └── YYYY-MM-DD.md           # 每日记忆
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# 模型提供方选择 (deepseek | qwen | openai | local | nim_minimax_m2 | nim_glm47)
LLM_PROVIDER=deepseek

# DeepSeek 配置
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_NAME=deepseek-chat

# Qwen 配置 (可选)
# QWEN_API_KEY=your_dashscope_key
# QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# QWEN_MODEL_NAME=qwen-plus

# OpenAI 配置 (可选)
# OPENAI_API_KEY=your_openai_key
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_MODEL_NAME=gpt-4o-mini

# NVIDIA NIM 配置 (可选)
# NIM_API_KEY=your_nim_key
# NIM_BASE_URL=https://integrate.api.nvidia.com/v1

# 本地模型配置 (可选)
# LOCAL_MODEL_PATH=/path/to/model.gguf
# LOCAL_CTX_SIZE=4096
# LOCAL_GPU_LAYERS=0
# LOCAL_THREADS=8
# LOCAL_BATCH_SIZE=512
# LOCAL_TEMPERATURE=0.7

# Web 控制台配置
WEB_HOST=0.0.0.0
WEB_PORT=5011
PUBLIC_URL=http://127.0.0.1:5011

# Playwright 配置
PLAYWRIGHT_USER_DATA_DIR=app/data/playwright_user_data
PLAYWRIGHT_AUTO_LOAD_COOKIES=true

# WhatsApp Gateway (可选)
# WA_PROVIDER=baileys
# WA_GATEWAY_AUTOSTART=true
# WA_GATEWAY_HOST=127.0.0.1
# WA_GATEWAY_PORT=8787

# 镜像加速 (中国区)
HF_ENDPOINT=https://hf-mirror.com
HUGGINGFACE_HUB_ENDPOINT=https://hf-mirror.com
```

### 3. 运行

```bash
python main.py
```

运行后：
- 启动 Agent 主循环
- 启动 Web 控制台 (默认端口 `5011`)
- 自动加载技能和 Cookie
- 初始化心跳任务

### 4. 访问 Web 控制台

浏览器打开：
- **对话**: `http://127.0.0.1:5011/`
- **审计日志**: `http://127.0.0.1:5011/audit-logs.html`
- **配置**: `http://127.0.0.1:5011/config.html`

控制台会显示局域网地址和二维码，手机扫码即可访问。

---

## 💡 使用示例

### 基础操作

```
显示桌面
帮我把桌面上所有 png 移动到 D:/screenshots
读取 Excel 里 A 列总和并保存结果
打开记事本，输入"Hello World"
截图保存
```

### Web 自动化

```
打开 https://github.com 登录
搜索 "langchain" 项目
截取搜索结果页面
```

### UI Automation

```
打开微信
找到"文件传输助手"
发送消息"测试"
```

### 文件与代码

```
分析 D:\dfCode\AICreate 项目结构
提取所有 Python 文件的类和方法
生成项目骨架缓存
```

### 多 Agent 协作

```
创建一个公告板
添加角色：产品经理、开发工程师、测试工程师
分配任务：设计一个用户登录功能
并发执行任务
```

### 技能自进化

```
帮我写一个技能，功能是批量重命名文件
技能要支持正则表达式匹配
测试一下这个技能
```

---

## 🔧 高级功能

### 心跳机制

用于调度后台监听与保活任务：

```python
from app.integrations import heartbeat

def _my_tick():
    # 定期执行的任务
    return {"status": "ok"}

def start_my_feature():
    heartbeat.register_task(
        "my_feature_heartbeat",
        _my_tick,
        interval=5.0  # 5 秒执行一次
    )
```

在配置页可查看和调整心跳任务。

### 技能开发流程

```python
# 1. 生成技能脚手架
scaffold_skill("my_skill", [
    {"name": "my_tool", "description": "我的工具", "args": [...]}
])

# 2. 编写工具代码
write_tool_code("my_skill/scripts/my_tool.py", code)

# 3. 安装依赖 (如需要)
install_packages(["requests", "beautifulsoup4"])

# 4. 热加载技能
reload_skills()

# 5. 测试技能
run_skill_test_cases("my_skill", [...])

# 6. 技能转正 (验证通过后)
promote_skill("my_skill")
```

### 版本控制与回滚

```python
# 查看变更历史
list_change_versions(10)

# 搜索特定操作
search_change_logs("write_tool_code")

# 回滚到最近稳定版本
rollback_change()

# 回滚到指定版本
rollback_change("change_id_123")

# 导出审计日志
export_change_logs("audit.json", fmt="json")
```

### RAG 经验检索

```python
# 记录经验
add_operation_experience(
    system_name="Playwright",
    content="登录时需要等待 2 秒避免验证码",
    tags=["登录", "验证码", "等待"]
)

# 检索经验
get_operation_experience(
    query="Playwright 登录失败怎么办",
    n_results=3
)
```

---

## 📊 变更日志

### 2026-03-10
- 成功发布小红书文章《小冬瓜 vs 小龙虾：不只是名字的差异，更是能力的进化 🥒🦞》
- 文章重点介绍了小冬瓜与小龙虾（OpenClaw）的区别，突出了小冬瓜在导出能力方面的优势，特别是"术业有专攻"的特色
- 生成了配套宣传图片，展示了两个角色的对比

### 2026-03-09
- 更新 README 以反映实际项目结构
- 核心技能增至 27 个（新增 git_skill, code_review_skill, deep_analysis_skill）
- 自动生成技能增至 32 个
- 消息渠道集成独立至 channels/ 目录（dingtalk, feishu, wecom）

### 2026-02-22
- Web 对话区"工具/思考详情"展开状态可保持
- Web 对话滚动优化：仅在用户位于底部附近时自动跟随
- 发送/停止按钮状态与后端执行状态对齐
- 热加载注入本轮工具轨迹，减少重复读取
- 对话历史与短期记忆增加长度上限
- 大文件读取工具分页限量返回

### 2026-02-21
- 统一 Playwright 与浏览器工具的错误结构
- 补齐 system_skill 多个工具的结构化错误返回
- 修复 run_shell_command 的解码逻辑
- 文档读取类工具加入多编码回退
- 模板确认增加 5 秒倒计时

### 2026-02-18
- 技能生成 UI 上线
- 自动测试闭环：生成后自动检测可加载性与用例测试
- 心跳任务可视化配置

---

## 🛡️ 安全特性

- **加密存储**: 变更记录使用 Fernet 加密
- **文件快照**: 操作前自动创建快照，支持精确回滚
- **原子操作**: 每个工具调用都是原子操作
- **权限控制**: 基于操作者身份记录操作历史
- **密钥管理**: 支持环境变量和文件两种密钥管理方式

---

## 📝 注意事项

1. **首次运行**: 会自动下载 HuggingFace 嵌入模型 (约 90MB)
2. **Playwright**: 首次使用需运行 `playwright install` 安装浏览器
3. **WA Gateway**: 如使用 WhatsApp 功能，需安装 Node.js
4. **本地模型**: 需自行下载 GGUF 格式模型文件
5. **技能转正**: 自动生成的技能需验证通过后才可转正

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

联系方式：见 `contact.txt`

---

## 📄 许可证

见 `LICENSE` 文件

---

**小冬瓜** - 你的智能电脑操作助手，越用越聪明！🥒