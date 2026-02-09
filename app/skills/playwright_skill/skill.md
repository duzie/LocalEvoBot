# Skill

## Name
playwright_skill

## Version
1.0.1

## Description
基于 Playwright 的现代浏览器自动化。支持前景层（模态/遮罩/弹层）内结构抽取与操作、iframe 内点击与脚本执行、easyui datagrid 抽取等。

## Entry
app.skills.playwright_skill.scripts

## Tools
- playwright_open: 打开网页并保持会话（可加载扩展与持久化目录）
- playwright_navigate: 导航到新的网页地址
- playwright_click: 点击页面元素
- playwright_fill: 填充表单元素
- playwright_type: 输入文本到页面元素
- playwright_get_text: 获取元素文本
- playwright_execute_js: 执行JavaScript代码
- extract_easyui_datagrid: 抽取 easyui datagrid 的列与行数据
- update_easyui_datagrid_row: 更新 easyui datagrid 行数据（按行索引或字段匹配）
- playwright_modal_snapshot: 获取前景容器内的 DOM 与可交互元素摘要（自动识别）
- playwright_snapshot: 获取页面DOM快照
- playwright_accessibility_snapshot: 获取页面AX树快照
- playwright_list_frames: 列出 iframe 列表
- playwright_execute_js_in_frame: 在 iframe 内执行 JavaScript
- playwright_click_in_frame: 在 iframe 内点击元素
- playwright_snapshot_in_frame: 获取 iframe DOM 快照
- playwright_accessibility_snapshot_in_frame: 获取 iframe AX 树快照
- playwright_list_cookies: 获取 Cookies
- playwright_set_cookies: 设置 Cookies
- playwright_clear_cookies: 清空 Cookies
- playwright_apply_cookies: 从本地保存的 Cookie 文件加载
- playwright_get_storage: 获取 localStorage 或 sessionStorage
- playwright_set_storage: 设置 localStorage 或 sessionStorage
- playwright_start_network_capture: 开始抓包
- playwright_stop_network_capture: 停止抓包
- playwright_get_network_logs: 获取抓包日志
- playwright_clear_network_logs: 清空抓包日志
- playwright_screenshot: 保存页面截图
- playwright_run_steps: 执行测试步骤并输出报告
- playwright_close: 关闭浏览器会话

## Platforms
- Windows
- Linux
- macOS

## Dependencies
- playwright

## References
- references/usage.md
