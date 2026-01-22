# 电脑操作 Agent 项目

一个基于 LangChain 的电脑操作 Agent，支持多轮自动执行、Windows UI Automation、OCR 文本识别与视觉理解辅助，用于桌面任务自动化。

**核心能力**
- 自动多步执行：一次输入可连续执行多个工具调用
- UI Automation 优先：基于 Windows UIA 精准定位控件
- OCR 识别：读取界面文字，辅助下一步决策
- 视觉理解：分析界面状态与可见信息
- 常见桌面操作：点击、输入、显示桌面、进程检查等
- 技能按一文件一技能拆分，便于扩展与维护

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
打开微信并给肚子饱发消息，说晚上来吃饭
帮我把桌面上所有 png 移动到 D:/screenshots
读取 Excel 里 A 列总和并保存结果
```

## Skills 概览

**UI Automation (Windows)**
- `uia_find_control`：按窗口与控件属性定位控件并返回坐标
- `uia_click_control`：直接点击控件
- `uia_list_controls`：枚举窗口控件树，便于探索控件名称

**OCR 文本识别**
- `ocr_screen`：全屏 OCR
- `ocr_window`：指定窗口 OCR

**视觉理解**
- `analyze_screen`：输出界面摘要、可见文字、UI 元素与建议动作

**桌面操作**
- `mouse_click` / `type_text` / `wait_seconds`
- `show_desktop`

**进程与系统**
- `check_process_status`
- `list_processes`
- `get_current_time`
- `calculator`

**文件与办公**
- `file_organize`
- `excel_sum`
- `take_screenshot`

## 目录结构

```
app/
  agent.py         Agent 创建与执行器配置
  prompts.py       系统提示词与执行策略
  skills/          工具集合
main.py            启动入口与自动多轮执行
requirements.txt   依赖列表
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
