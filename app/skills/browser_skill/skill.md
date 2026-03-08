# Skill

## Name
browser_skill

## Version
1.0.0

## Description
基于 ARIA 树的智能浏览器自动化。使用 ref 自动定位元素，无需手写 CSS Selector。

## Entry
app.skills.browser_skill.scripts

## Tools
- browser_open: 打开网页
- browser_snapshot: 获取页面 ARIA 树（自动分配 ref）
- browser_act: 执行操作（点击/输入/按键等）
- browser_screenshot: 截图
- browser_close: 关闭页面

## Platforms
- Windows
- Linux
- macOS

## Dependencies
- playwright
- playwright-stealth (可选，防检测)

## When to Use
- 需要智能元素定位时
- 不想手写 CSS Selector 时
- 快速原型开发时

## When NOT to Use
- 需要精细控制（超时/等待）时使用 playwright_skill
- 需要网络抓包时使用 playwright_skill
- 需要操作 iframe 时使用 playwright_skill

## References
- references/usage.md
