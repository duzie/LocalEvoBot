# OpenClaw MQTT Plugin

MQTT 消息通道插件，用于将 OpenClaw 连接到 MQTT Broker。

## 功能

- ✅ 连接 MQTT Broker
- ✅ 订阅 `agent/process/{agentId}` 主题接收消息
- ✅ 发布响应到 `agent/reply/{clientId}` 主题
- ✅ 自动重连
- ✅ Agent 注册

## 安装

### 方式 1：本地安装（开发）

```bash
cd D:\dfCode\openclaw-mqtt-plugin
npm run build

# 在 OpenClaw 中安装
openclaw plugins install D:\dfCode\openclaw-mqtt-plugin
```

### 方式 2：从 npm 安装（发布后）

```bash
openclaw plugins install @openclaw/mqtt-plugin
```

## 配置

在 `openclaw.json` 中添加：

```json5
{
  "channels": {
    "mqtt": {
      "enabled": true,
      "brokerUrl": "mqtt://your-broker:8099",
      "agentId": "openclaw-main",
      "token": "your-token",  // 可选
      "clientId": "openclaw-1"  // 可选
    }
  },
  "bindings": [
    {
      "match": { "channel": "mqtt" },
      "agentId": "main"
    }
  ]
}
```

## 配置说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `brokerUrl` | ✅ | MQTT Broker 地址 |
| `agentId` | ✅ | Agent 唯一标识 |
| `token` | ❌ | 认证 Token（如果 Broker 需要） |
| `clientId` | ❌ | MQTT 客户端 ID（默认自动生成） |
| `username` | ❌ | MQTT 用户名（如果需要认证） |
| `password` | ❌ | MQTT 密码（如果需要认证） |

## 消息格式

### 接收消息（订阅 `agent/process/{agentId}`）

```json
{
  "OriginalClientId": "client-001",
  "UserId": "user-001",
  "Message": "你好",
  "RequestId": "req-001",
  "Timestamp": "2026-03-12T11:00:00Z"
}
```

### 发送响应（发布到 `agent/reply/{clientId}`）

```json
{
  "OriginalClientId": "client-001",
  "UserId": "user-001",
  "Response": "你好！有什么可以帮你？",
  "Timestamp": "2026-03-12T11:00:01Z",
  "RequestId": "req-001"
}
```

## 主题说明

| 主题 | 方向 | 说明 |
|------|------|------|
| `agent/incoming` | 接收 | 客户端发送的原始消息 |
| `agent/process/{agentId}` | 接收 | 路由到此 Agent 的消息 |
| `agent/outgoing` | 发送 | Agent 的响应消息 |
| `agent/reply/{clientId}` | 发送 | 路由到特定客户端的响应 |
| `agent/register` | 发送 | Agent 注册消息 |

## 日志

插件会在 OpenClaw 日志中输出：

```
[MQTT] Connecting to mqtt://broker:8099
[MQTT] Connected to broker
[MQTT] Agent openclaw-main registered
[MQTT] Subscribed to agent/process/openclaw-main
[MQTT] Received message on agent/process/openclaw-main: {...}
[MQTT] Processing message from user-001
[MQTT] Published to agent/reply/client-001
```

## 开发

```bash
# 开发模式（监听变化）
npm run dev

# 构建生产版本
npm run build

# 清理
npm run clean
```

## 故障排查

### 无法连接 Broker

1. 检查 `brokerUrl` 是否正确
2. 检查网络连通性：`telnet broker 8099`
3. 检查防火墙设置

### 收不到消息

1. 确认 `agentId` 配置正确
2. 检查 MQTT Server 的路由配置
3. 查看 OpenClaw 日志

### 响应发送失败

1. 确认 MQTT 连接状态
2. 检查 `OriginalClientId` 是否正确
3. 查看 Broker 日志

## License

MIT
