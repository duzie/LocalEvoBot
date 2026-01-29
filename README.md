# 我是小冬瓜 / 自进化本地自动化 Agent

一个基于 LangChain 的智能电脑操作 Agent，不仅支持 Windows UI Automation、OCR、Web 自动化，更具备**自我进化能力**——能根据任务需求自动编写新技能、热加载并立即使用，无需重启。

**核心能力**
- **自我进化 (Self-Evolution)**：
  - 遇到未知任务时，自动生成工具脚手架 (`scaffold_skill`)
  - 自动编写 Python 实现代码 (`write_tool_code`)
  - 运行时热加载新技能 (`reload_skills`)，即刻生效并自动继续任务
  - 优质技能一键转正 (`promote_skill`)，沉淀为核心能力
- **RAG 长时记忆 (Long-term Memory)**：
  - 内置本地向量数据库 (ChromaDB)，支持语义检索
  - 自动积累成功/失败经验，实现“不二过”的能力提升
- **自动多步执行**：基于 `STATE` 状态机的多轮自动执行与任务拆解
- **UI Automation**：基于 Windows UIA 精准定位与操作原生控件
- **Web 自动化**：内置 Selenium 支持，接管浏览器进行复杂网页交互
- **视觉与 OCR**：屏幕/窗口文字识别，辅助定位与决策
- **系统控制**：文件操作、进程管理、键盘鼠标模拟

## 快速开始

**安装依赖**
```bash
pip install -r requirements.txt
```

**准备 .env**
```
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_NAME=deepseek-chat
DOUBAO_VISION_MODEL_NAME=...
```

**运行**
```bash
python main.py
```

## 使用示例

```
显示桌面
帮我把桌面上所有 png 移动到 D:/screenshots
读取 Excel 里 A 列总和并保存结果
```

## Skills 概览

### 核心技能 (app/skills)
**1. 自进化 (SkillGen)**
- `scaffold_skill`: 生成新技能目录结构
- `write_tool_code`: 编写或修改工具代码
- `promote_skill`: 将验证通过的自动技能“转正”迁移至核心技能库
- `reload_skills`: 热加载所有技能并自动衔接当前任务 (Auto-Resume)

**2. UI Automation (Windows)**
- `uia_find_control`: 定位窗口控件
- `uia_click_control`: 点击控件
- `uia_list_controls`: 遍历控件树

**3. Web 自动化 (Selenium)**
- `selenium_open_url`: 打开网页
- `selenium_click` / `selenium_type`: 网页交互
- `selenium_run_steps`: 批量执行网页操作

**4. 视觉与 OCR**
- `ocr_screen` / `ocr_window`: 文字识别
- `take_screenshot`: 屏幕截图

**5. 系统与文件**
- `add_operation_experience`: 记录经验到向量库 (RAG)
- `get_operation_experience`: 语义检索历史经验
- `file_directory_skill`: 目录遍历、文件搜索与信息获取
- `file_save_skill`: 文件内容写入与保存
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
