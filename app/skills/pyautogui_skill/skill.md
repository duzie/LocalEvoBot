# Skill

## Name
pyautogui_skill

## Version
1.0.0

## Description
基于PyAutoGUI的桌面应用程序自动化工具集，提供鼠标控制、键盘输入、屏幕截图、窗口管理等功能。

## Entry
app.skills.pyautogui_skill.scripts

## Tools
- gui_click_element: 点击屏幕指定坐标
- gui_double_click: 双击屏幕指定坐标
- gui_right_click: 右键点击屏幕指定坐标
- gui_move_mouse: 移动鼠标到指定坐标
- gui_scroll: 滚动鼠标滚轮
- gui_type_text: 输入文本
- gui_press_key: 按下单个按键
- gui_hotkey: 按下组合键
- gui_wait: 等待指定秒数
- gui_get_screen_size: 获取屏幕尺寸
- gui_take_screenshot: 截取屏幕截图
- gui_find_and_click: 查找图像并点击
- gui_focus_window: 激活指定窗口

## Platforms
- Windows
- Linux
- macOS

## Dependencies
- pyautogui
- pygetwindow
- opencv-python (用于图像识别)

## References
- references/usage.md