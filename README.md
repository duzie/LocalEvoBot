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
- **自动多步执行**：基于 `STATE` 状态机的多轮自动执行与任务拆解
- **UI Automation**：基于 Windows UIA 精准定位与操作原生控件
- **Web 自动化**：内置 Playwright 支持，接管浏览器进行复杂网页交互
- **视觉与 OCR**：屏幕/窗口文字识别，辅助定位与决策
- **系统控制**：文件操作、进程管理、键盘鼠标模拟
- **Web 控制台**：移动端友好的网页界面（聊天、日志、配置、局域网地址与二维码）

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
WEB_PORT=5010

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

运行后会同时启动 Web 控制台（默认端口 `5010`），浏览器打开：
- `http://127.0.0.1:5010/`

在 Web 控制台中：
- 可切换模型（下拉框）
- 可编辑 `.env` 配置
- 可显示局域网地址并生成二维码，方便手机访问

## 个人认知与模板使用

**任务结束总结**
- 当任务输出 `STATE: DONE` 时，会生成结构化总结
- 若总结包含可复用内容，会提示是否保存到经验库

**模板套用**
- 新任务开始时会检索项目级模板
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

## Skills 概览

### 核心技能 (app/skills)
**1. 自进化 (SkillGen)**
- `scaffold_skill`: 生成新技能目录结构
- `write_tool_code`: 编写或修改工具代码
- `promote_skill`: **技能转正**。将 `auto_skills` 中验证通过的技能一键迁移至 `app/skills`，成为永久核心能力
- `reload_skills`: **热加载与自动回复**。运行时重载所有技能，并自动读取上一轮任务状态，无缝继续执行 (Auto-Resume)

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

<img width="2085" height="1359" alt="QQ截图20260129145008" src="https://github.com/user-attachments/assets/c2432457-359b-430b-9b35-2faad619d138" />
