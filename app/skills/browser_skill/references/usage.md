# Usage

## Scope
基于OpenClaw的浏览器自动化操作，提供类似OpenClaw内置browser工具的功能。

## Tools
- `browser_open`: 启动浏览器并打开网页
- `browser_snapshot`: 获取页面DOM快照和可交互元素
- `browser_click`: 点击指定元素
- `browser_fill`: 填充表单字段
- `browser_type`: 在当前焦点元素输入文本
- `browser_navigate`: 页面间导航
- `browser_screenshot`: 保存页面截图
- `browser_execute_js`: 执行JavaScript
- `browser_close`: 关闭浏览器

## Examples

### 基础浏览
```python
browser_open(url="https://www.example.com")
snapshot = browser_snapshot()
print(snapshot)
```

### 表单填写
```python
browser_fill(selector="#username", text="myuser")
browser_fill(selector="#password", text="mypassword")
browser_click(selector="button[type='submit']")
```

### 内容提取
```python
content = browser_execute_js("return document.title;")
print(f"页面标题: {content}")
```

## Setup
确保OpenClaw网关服务正在运行，并且浏览器控制服务可用。