# Usage

## Scope
基于PyAutoGUI的桌面应用程序自动化操作，提供鼠标、键盘、窗口等底层GUI操作能力。

## Tools
- `gui_click_element`: 点击指定屏幕坐标
- `gui_double_click`: 双击指定屏幕坐标
- `gui_right_click`: 右键点击指定屏幕坐标
- `gui_move_mouse`: 移动鼠标到指定位置
- `gui_scroll`: 滚动鼠标滚轮
- `gui_type_text`: 输入文本
- `gui_press_key`: 按下单个按键
- `gui_hotkey`: 按下组合键
- `gui_wait`: 等待指定时间
- `gui_get_screen_size`: 获取屏幕分辨率
- `gui_take_screenshot`: 截取屏幕
- `gui_find_and_click`: 通过图像识别点击元素
- `gui_focus_window`: 激活特定窗口

## Examples

### 基础操作
```python
# 获取屏幕尺寸
screen_info = gui_get_screen_size()

# 点击坐标 (500, 300)
gui_click_element(x=500, y=300)

# 输入文本
gui_type_text(text="Hello World")

# 按下回车键
gui_press_key(key="enter")
```

### 窗口和截图操作
```python
# 激活特定窗口
gui_focus_window(title="caimomo")

# 截取屏幕
gui_take_screenshot(filename="my_screenshot.png")
```

### 组合操作
```python
# 按下 Ctrl+C 复制
gui_hotkey("ctrl", "c")

# 等待2秒
gui_wait(seconds=2.0)

# 粘贴 (Ctrl+V)
gui_hotkey("ctrl", "v")
```

## 注意事项
1. **安全区域**: 鼠标移动到屏幕左上角(0,0)可触发安全机制中断操作
2. **屏幕坐标**: 坐标原点为左上角(0,0)，X轴向右递增，Y轴向下递增
3. **等待时间**: 操作间有默认延迟，避免过快操作导致问题
4. **权限**: 某些应用程序可能需要特殊权限才能被自动化操作

## Setup
安装依赖:
```bash
pip install pyautogui pygetwindow opencv-python
```