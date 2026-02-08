# Usage

## Scope
基于 Playwright 的现代浏览器自动化操作。

## Tools
- `playwright_open`: 打开网页（支持 headless；可加载扩展与持久化目录）
- `playwright_navigate`: 导航到新页面
- `playwright_click`: 点击元素 (自动等待)
- `playwright_fill`: 填充表单字段
- `playwright_type`: 输入文本
- `playwright_get_text`: 获取文本
- `playwright_execute_js`: 执行 JavaScript
- `extract_easyui_datagrid`: 抽取 easyui datagrid 的列与行数据
- `update_easyui_datagrid_row`: 更新 easyui datagrid 行数据（按行索引或字段匹配）
- `playwright_modal_snapshot`: 获取前景容器（模态/遮罩/弹层）内的 DOM 与可交互元素摘要（支持自动识别）
- `playwright_snapshot`: 获取页面 DOM 快照
- `playwright_accessibility_snapshot`: 获取页面 AX 树快照
- `playwright_list_frames`: 列出 iframe
- `playwright_click_in_frame`: 在 iframe 内点击元素
- `playwright_execute_js_in_frame`: 在 iframe 内执行 JS
- `playwright_snapshot_in_frame`: 获取 iframe DOM 快照
- `playwright_accessibility_snapshot_in_frame`: 获取 iframe AX 树快照
- `playwright_list_cookies`: 获取 Cookies
- `playwright_set_cookies`: 设置 Cookies
- `playwright_clear_cookies`: 清空 Cookies
- `playwright_apply_cookies`: 从本地保存的 Cookie 加载到上下文
- `playwright_get_storage`: 获取 localStorage 或 sessionStorage
- `playwright_set_storage`: 设置 localStorage 或 sessionStorage
- `playwright_start_network_capture`: 开始抓包
- `playwright_stop_network_capture`: 停止抓包
- `playwright_get_network_logs`: 获取抓包日志
- `playwright_clear_network_logs`: 清空抓包日志
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

### iframe 操作
```python
playwright_list_frames()
playwright_click_in_frame(
    selector="text=确定",
    frame_name="mainFrame"
)
playwright_execute_js_in_frame(
    script="return document.title",
    frame_url="example.com"
)
```

### AX 树快照
```python
playwright_accessibility_snapshot()
playwright_accessibility_snapshot(interesting_only=False)

playwright_accessibility_snapshot_in_frame(frame_name="mainFrame")
```

### easyui datagrid 抽取
```python
extract_easyui_datagrid(selector="#goodsDg", max_rows=50)
```

### easyui datagrid 行编辑
```python
update_easyui_datagrid_row(
    selector="#updMaterialTable",
    match_field="GoodsName",
    match_value="土豆",
    update_fields={"Quantity2": 10, "UnitPrice2": 3.5, "Memo": "测试"}
)
```

### 前景容器内快照
```python
playwright_modal_snapshot(root_selector="#updateModal")
```

### 自动识别可见前景层
```python
playwright_modal_snapshot(root_selector="")
```

### Cookies 与 Storage
```python
playwright_list_cookies()
playwright_set_storage({"token": "abc"}, storage="local", clear=True)
```

### 复用登录态（Cookie 文件）
- 浏览器扩展：加载目录 `web/extension/cookie_relay` 到 Chrome 的“加载已解压的扩展程序”
- 在已登录站点点击扩展图标，后端会保存该域名的 Cookie 到 `app/data/cookies/<domain>.json`
- 在 Agent 中加载：
```python
playwright_open("https://example.com", headless=False)
playwright_apply_cookies("example.com")
playwright_open("https://example.com", headless=False)
```

### 持久化用户数据目录
```python
playwright_open(
  url="https://example.com",
  headless=False,
  user_data_dir="D:/localevobot/langchain/app/data/playwright_user_data"
)
```
也可设置环境变量：
- `PLAYWRIGHT_USER_DATA_DIR` 指定默认用户数据目录

### 自动加载扩展（需要非 headless）
```python
playwright_open(
  url="https://example.com",
  headless=False,
  extension_dir="D:/localevobot/langchain/web/extension/cookie_relay"
)
```
默认会尝试加载项目内扩展目录：`web/extension/cookie_relay`。也可通过环境变量：
- `PLAYWRIGHT_EXTENSION_DIR` 指定扩展目录

### 抓包
```python
playwright_start_network_capture(clear_logs=True, max_entries=300)
playwright_click("text=More information")
playwright_get_network_logs(limit=50)
playwright_stop_network_capture()
```

## Setup
首次使用前需要安装浏览器驱动：
```bash
pip install playwright
playwright install
```
