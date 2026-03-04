=== 浏览器自动化提示 ===
1) Playwright 操作：统一使用 playwright_* 工具；等待优先使用 wait_for_selector/wait_for_function；元素作用域限定在容器内。
2) 弹层与遮罩：仅抽取前景层结构，使用 playwright_modal_snapshot；必要时传 root_selector，否则自动识别前景层。
3) 表格数据：优先使用 extract_easyui_datagrid 获取结构化数据；大量数据使用分页工具或接口抓包。
