# Usage

## Scope
当 UIA 无法准确识别控件（如 HwndHost/WebView/自绘 UI）时，使用视觉能力定位与点击。

## Tools
- eyes_find_text
- eyes_find_ui
- eyes_find_multiple
- eyes_map_ui
- eyes_click_ui

## Examples
```python
# 定位文字
eyes_find_text(window_title="KeyPos", target_text="确认")

# 按描述定位元素
eyes_find_ui(window_title="KeyPos", description="右下角 OK 按钮")

# 批量定位
eyes_find_multiple(window_title="KeyPos", descriptions=["确认", "取消", "设置"])

# 按功能语义一次性返回多个 UI 坐标
eyes_map_ui(
    window_title="KeyPos",
    functions=["登录按钮", "门店号输入框", "数字键盘", "确认按钮"]
)

# 一键视觉定位并点击
eyes_click_ui(window_title="KeyPos", description="确认按钮")
```
