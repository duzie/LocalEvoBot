# gateway

WhatsApp 网关服务（基于 Baileys），负责登录、收发消息与 Webhook 转发。

## 启动方式
在网关目录下运行：
```bash
npm install
copy .env.example .env
npm start
```

## 关键配置（.env）
- 优先读取 `gateway/.env`，未配置项再回退到项目根目录 `.env`
- WA_GATEWAY_TOKEN: 网关 API 访问令牌（必填）
- WA_GATEWAY_HOST / WA_GATEWAY_PORT: HTTP 监听地址与端口
- WA_AUTH_DIR: 登录态存储目录
- WA_DM_ENABLED: 是否允许私聊消息进入
- WA_ALLOW_FROM: 允许的手机号白名单（逗号分隔，或 *）
- WA_WEBHOOK_URL / WA_WEBHOOK_TOKEN: 收到消息后的回调地址与鉴权
- WA_PROXY_ENABLED / WA_PROXY_URL: 代理配置
- WA_TYPING_REFRESH_MS / WA_TYPING_MAX_MS: typing presence 刷新与最大保持时长
