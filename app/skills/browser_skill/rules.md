=== 浏览器自动化提示 (Browser) ===
1) Browser 操作：统一使用 browser_* 工具；等待页面加载完成再进行下一步操作；元素定位优先使用明确的选择器。
2) 兼容性考虑：Browser工具基于OpenClaw实现，在某些复杂网页上可能不如Playwright稳定；如遇问题可切换至 playwright_* 工具。
3) 页面状态：操作前确认页面已加载完成，可使用 browser_snapshot 检查页面状态；必要时使用 browser_execute_js 执行特定逻辑。
4) 资源管理：完成操作后使用 browser_close 释放浏览器资源，避免长时间占用系统资源。