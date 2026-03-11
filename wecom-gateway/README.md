# WeCom Gateway - 企业微信网关服务

基于官方 `@wecom/aibot-node-sdk` 实现的企业微信 WebSocket 长连接网关。

架构与 WhatsApp Gateway (`gateway/index.js`) 保持一致。

## ✨ 特性

- 🔗 **官方 SDK** - 使用 `@wecom/aibot-node-sdk`，稳定可靠
- 💓 **自动重连** - 指数退避重连策略，无限重连
- 📨 **Webhook 转发** - 收到消息后自动转发到指定 URL
- 📤 **HTTP API** - 提供发送消息接口
- 🔐 **Token 认证** - API 访问需要 Bearer Token

## 🚀 快速开始

### 1. 安装依赖

```bash
cd D:\dfCode\langchain\wecom-gateway
npm install
```

### 2. 配置环境变量

在 `D:\dfCode\langchain\.env` 或 `wecom-gateway/.env` 中添加：

```bash
# 企业微信机器人配置
WECOM_BOT_ID=your_bot_id
WECOM_SECRET=your_bot_secret

# Gateway 配置
WECOM_GATEWAY_HOST=127.0.0.1
WECOM_GATEWAY_PORT=8788
WECOM_GATEWAY_TOKEN=your_api_token

# Webhook 配置（可选）
WECOM_WEBHOOK_URL=http://localhost:3000/wecom-webhook
WECOM_WEBHOOK_TOKEN=your_webhook_token

# 其他配置
WECOM_DM_ENABLED=true
WECOM_ALLOW_FROM=*
WECOM_TEXT_CHUNK_LIMIT=4000
```

### 3. 启动服务

```bash
npm start
```

或开发模式（文件变化自动重启）：

```bash
npm run dev
```

## 📡 API 接口

### GET /health

健康检查

```bash
curl http://127.0.0.1:8788/health
```

响应：
```json
{
  "ok": true,
  "connected": true,
  "dmEnabled": true,
  "allowFromCount": 0,
  "webhookEnabled": true,
  "loggedIn": true
}
```

### POST /send

发送文本消息

```bash
curl -X POST http://127.0.0.1:8788/send \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{
    "chatid": "userid123",
    "text": "Hello from WeCom Gateway!",
    "msgtype": "text"
  }'
```

### POST /send/markdown

发送 Markdown 消息

```bash
curl -X POST http://127.0.0.1:8788/send/markdown \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{
    "chatid": "userid123",
    "content": "这是一条 **Markdown** 消息"
  }'
```

### GET /inbox

获取最近收到的消息

```bash
curl http://127.0.0.1:8788/inbox \
  -H "Authorization: Bearer your_api_token"
```

### POST /reset

重置连接

```bash
curl -X POST http://127.0.0.1:8788/reset \
  -H "Authorization: Bearer your_api_token"
```

## 🔌 集成到 LangChain

在你的 LangChain 主程序中，通过 Webhook 接收企业微信消息：

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/wecom-webhook', methods=['POST'])
def wecom_webhook():
    data = request.json
    
    # 验证 webhook token
    # ...
    
    # 提取消息
    channel = data.get('channel')  # "wecom"
    userid = data.get('senderUserid')
    text = data.get('text')
    
    # 调用 Agent 处理
    response = agent_executor.invoke({
        "input": f"企业微信用户 {userid}: {text}"
    })
    
    # 通过 Gateway API 发送回复
    import requests
    requests.post(
        "http://127.0.0.1:8788/send",
        headers={"Authorization": "Bearer your_api_token"},
        json={
            "chatid": userid,
            "text": response.get("output", "收到")
        }
    )
    
    return jsonify({"ok": True})
```

## 📊 与 WhatsApp Gateway 对比

| 特性 | WhatsApp Gateway | WeCom Gateway |
|------|-----------------|---------------|
| SDK | `@whiskeysockets/baileys` | `@wecom/aibot-node-sdk` |
| 连接方式 | WebSocket (Baileys) | WebSocket (官方) |
| 认证方式 | QR 扫码 | Bot ID + Secret |
| 端口 | 8787 | 8788 |
| 消息格式 | WhatsApp JID | 企业微信 UserID |

## ⚙️ 配置项

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `WECOM_BOT_ID` | 企业微信机器人 ID | 必填 |
| `WECOM_SECRET` | 企业微信机器人 Secret | 必填 |
| `WECOM_GATEWAY_HOST` | HTTP 监听地址 | `127.0.0.1` |
| `WECOM_GATEWAY_PORT` | HTTP 监听端口 | `8788` |
| `WECOM_GATEWAY_TOKEN` | API 访问令牌 | 必填 |
| `WECOM_WEBHOOK_URL` | 消息回调 URL | 可选 |
| `WECOM_WEBHOOK_TOKEN` | Webhook 认证令牌 | 可选 |
| `WECOM_DM_ENABLED` | 是否允许私聊 | `true` |
| `WECOM_ALLOW_FROM` | 允许的 UserID 白名单（逗号分隔） | `*` (全部) |
| `WECOM_TEXT_CHUNK_LIMIT` | 文本分块长度限制 | `4000` |

## 🎯 下一步

1. 启动 Gateway：`npm start`
2. 配置 Webhook 指向你的 LangChain 应用
3. 在 LangChain 中处理消息并调用 `/send` API 回复

## 📄 License

MIT
