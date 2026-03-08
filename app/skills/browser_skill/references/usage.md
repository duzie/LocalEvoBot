# browser_skill 使用指南

## 快速开始

### 1. 基本用法

```python
# 打开网页
browser_open.invoke({"url": "https://taobao.com"})

# 获取页面结构（自动分配 ref）
result = browser_snapshot.invoke({})
# 返回：{"ok": True, "refs": {"e1": "登录按钮", "e2": "用户名输入框"}}

# 点击元素
browser_act.invoke({"kind": "click", "ref": "e1"})

# 输入文本
browser_act.invoke({"kind": "type", "ref": "e2", "text": "用户名"})

# 截图
browser_screenshot.invoke({})
```

### 2. 完整示例

```python
# 淘宝登录流程
browser_open.invoke({"url": "https://taobao.com"})

# 获取页面结构
snapshot = browser_snapshot.invoke({})
print(snapshot["refs"])
# {"e1": "登录按钮", "e2": "用户名", "e3": "密码", "e4": "提交"}

# 执行操作
browser_act.invoke({"kind": "click", "ref": "e1"})  # 点击登录
browser_act.invoke({"kind": "type", "ref": "e2", "text": "user123"})
browser_act.invoke({"kind": "type", "ref": "e3", "text": "pass456"})
browser_act.invoke({"kind": "click", "ref": "e4"})  # 提交

# 保存截图
browser_screenshot.invoke({"path": "login_success.png"})
```

### 3. 便捷工具

```python
# 便捷点击
browser_click.invoke({"ref": "e1"})

# 便捷输入
browser_type.invoke({"ref": "e2", "text": "用户名"})
```

---

## 参数说明

### browser_open

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | ✅ | 目标网址 |
| headless | boolean | ❌ | 无头模式（默认 False） |
| user_data_dir | string | ❌ | 用户数据目录（持久化登录） |
| extension_dir | string | ❌ | 扩展目录 |

### browser_snapshot

无需参数

**返回**:
```json
{
  "ok": true,
  "url": "https://...",
  "title": "页面标题",
  "refs": {
    "e1": "登录按钮",
    "e2": "用户名输入框"
  },
  "elements": [...]
}
```

### browser_act

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| kind | string | ✅ | 操作类型：click/type/fill/press/hover |
| ref | string | ❌ | 元素 ref（如 "e1"） |
| text | string | ❌ | 输入文本（type/fill 需要） |
| key | string | ❌ | 按键名称（press 需要，如 "Enter"） |
| selector | string | ❌ | 备用 CSS Selector |

### browser_screenshot

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | ❌ | 保存路径（默认自动生成） |
| full_page | boolean | ❌ | 全页面截图（默认 False） |

---

## 最佳实践

### 1. 先 snapshot 再操作

```python
# ❌ 错误：不知道 ref 就直接操作
browser_act.invoke({"kind": "click", "ref": "e1"})

# ✅ 正确：先获取页面结构
snapshot = browser_snapshot.invoke({})
print(snapshot["refs"])  # 查看可用的 ref
browser_act.invoke({"kind": "click", "ref": "e1"})
```

### 2. 使用便捷工具

```python
# 繁琐方式
browser_act.invoke({"kind": "click", "ref": "e1"})
browser_act.invoke({"kind": "type", "ref": "e2", "text": "user"})

# 简洁方式
browser_click.invoke({"ref": "e1"})
browser_type.invoke({"ref": "e2", "text": "user"})
```

### 3. 错误处理

```python
result = browser_act.invoke({"kind": "click", "ref": "e999"})
if not result.get("ok"):
    print(f"操作失败：{result.get('error')}")
    # 重新获取 snapshot
    snapshot = browser_snapshot.invoke({})
```

### 4. 等待元素

```python
# 如果元素可能未加载，先获取 snapshot
snapshot = browser_snapshot.invoke({})

# 如果找不到需要的元素，等待后重试
if "e1" not in snapshot["refs"]:
    import time
    time.sleep(2)
    snapshot = browser_snapshot.invoke({})
```

---

## 与 playwright_skill 对比

| 维度 | browser_skill | playwright_skill |
|------|---------------|------------------|
| **定位方式** | ARIA + ref | CSS Selector |
| **工具数量** | 5-6 个 | 40+ 个 |
| **学习成本** | 低（1 小时） | 高（1 天） |
| **代码简洁** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **功能全面** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **特殊场景** | ❌ 不支持 | ✅ 支持（iframe/抓包等） |

**选择建议**:
- 快速原型 → browser_skill
- 复杂场景 → playwright_skill

---

## 常见问题

### Q: ref 是什么？

A: ref 是自动分配的元素标识符，如 "e1", "e2", "e3"。通过 `browser_snapshot` 获取。

### Q: ref 会变化吗？

A: 每次 `browser_snapshot` 都会重新分配 ref。建议在操作前立即获取 snapshot。

### Q: 找不到元素怎么办？

A: 
1. 检查页面是否加载完成
2. 重新调用 `browser_snapshot`
3. 使用 `selector` 参数作为备用

### Q: 可以和 playwright_skill 混用吗？

A: 可以！它们共享同一个浏览器会话。

---

## 示例场景

### 场景 1: 自动登录

```python
browser_open.invoke({"url": "https://github.com/login"})
snapshot = browser_snapshot.invoke({})

# 查看可用的 ref
print(snapshot["refs"])
# {"e1": "用户名", "e2": "密码", "e3": "登录按钮"}

browser_type.invoke({"ref": "e1", "text": "user"})
browser_type.invoke({"ref": "e2", "text": "pass"})
browser_click.invoke({"ref": "e3"})
```

### 场景 2: 数据抓取

```python
browser_open.invoke({"url": "https://example.com/products"})
snapshot = browser_snapshot.invoke({})

# 找到产品列表
for ref, name in snapshot["refs"].items():
    if "产品" in name:
        browser_click.invoke({"ref": ref})
        browser_screenshot.invoke({"path": f"product_{ref}.png"})
```

### 场景 3: 表单填写

```python
browser_open.invoke({"url": "https://example.com/form"})
snapshot = browser_snapshot.invoke({})

# 填写表单
browser_type.invoke({"ref": "e1", "text": "张三"})  # 姓名
browser_type.invoke({"ref": "e2", "text": "zhangsan@email.com"})  # 邮箱
browser_act.invoke({"kind": "select", "ref": "e3", "value": "beijing"})  # 城市
browser_click.invoke({"ref": "e4"})  # 提交
```

---

_享受简洁的浏览器自动化！_ 🦞
