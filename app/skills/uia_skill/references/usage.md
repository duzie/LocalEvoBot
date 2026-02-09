# Usage

## Scope
在窗口控件层级中定位与操作控件。

## Tools
- uia_find_control
- uia_click_control
- uia_list_controls
- uia_list_windows
- uia_dump_tree
- uia_activate_window

## Examples
- 使用 uia_list_windows 查找进程名为 "notepad" 的窗口标题
- 激活微信窗口后枚举控件树，再点击输入框
- 通过控件类型为 Edit 定位浏览器地址栏
- 使用 uia_dump_tree 获取窗口的完整 XML 结构进行分层分析
- 当窗口最小化时，先调用 uia_activate_window 还原窗口
