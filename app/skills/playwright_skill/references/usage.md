# Usage

## Scope
基于 Playwright 的现代浏览器自动化操作。

## Tools
- `playwright_open`: 打开网页 (支持 headless 模式)
- `playwright_click`: 点击元素 (自动等待)
- `playwright_type`: 输入文本
- `playwright_get_text`: 获取文本
- `playwright_screenshot`: 截图
- `playwright_run_steps`: 批量执行步骤
- `playwright_close`: 关闭浏览器

## Examples

### 基础操作
```python
playwright_open(url="https://www.google.com", headless=False)
playwright_type(selector="[title='Search']", text="LangChain")
playwright_click(selector="input[value='Google Search']")
```

### 批量执行
```python
steps = [
    {"action": "open", "url": "https://example.com"},
    {"action": "click", "selector": "text=More information"},
    {"action": "screenshot", "path": "reports/example.png"}
]
playwright_run_steps(steps=steps)
```

## Setup
首次使用前需要安装浏览器驱动：
```bash
pip install playwright
playwright install
```
