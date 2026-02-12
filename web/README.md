# web

Web 控制台与后端服务目录，提供聊天、日志、配置与模板等页面与接口。

## 目录结构
- backend/: FastAPI 服务端（WebSocket 与配置接口）
- frontend/public/: 静态页面与控制台入口
- extension/cookie_relay/: Playwright 扩展，用于 Cookie 同步

## 启动说明
Web 服务由仓库根目录 main.py 启动，默认端口可在 .env 中配置。
