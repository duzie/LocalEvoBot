# WeCom 企业微信集成指南

## 📖 概述

企业微信智能机器人支持 **WebSocket 长连接**，无需公网服务器即可实时收发消息。

### 架构对比

| 方案 | 是否需要公网 | 实现难度 | 推荐度 |
|------|-------------|---------|--------|
| **WebSocket 长连接** | ❌ 不需要 | 中等 | ⭐⭐⭐⭐⭐ |
| HTTP 回调 + ngrok | ✅ 需要内网穿透 | 简单 | ⭐⭐⭐ |
| HTTP 回调 + 公网服务器 | ✅ 需要公网 IP | 中等 | ⭐⭐⭐ |

## 🔑 核心参数

从你提供的信息：
- **Bot ID**: `aiboT2pHPPXhAX6ic3OGWGNrAWD1_MTQsz8`
- **Secret**: `SzOaJdgMn9DbULVWpxYnKlTBQPtHAFLYWoixa6aCN3t`
- **WebSocket URL**: `wss://openws.work.weixin.qq.com`

## 📦 方案选择

### 方案 A：使用 OpenClaw 官方插件（最简单）

如果你的项目能迁移到 OpenClaw 架构：

```bash
# 1. 安装 OpenClaw
npm install -g openclaw

# 2. 安装企业微信插件
openclaw plugins install @wecom/wecom-openclaw-plugin

# 3. 配置
openclaw config set channels.wecom.botId aiboT2pHPPXhAX6ic3OGWGNrAWD1_MTQsz8
openclaw config set channels.wecom.secret SzOaJdgMn9DbULVWpxYnKlTBQPtHAFLYWoixa6aCN3t
openclaw config set channels.wecom.enabled true

# 4. 重启
openclaw gateway restart
```

### 方案 B：Python 实现 WebSocket 客户端（推荐你的项目）

用 Python 重写 WebSocket 连接逻辑，集成到现有的 `channels/wecom/channel.py`。

**依赖：**
```bash
pip install websockets requests
```

**核心实现：**
- 使用 `websockets` 库建立长连接
- 实现认证、心跳、消息收发
- 集成到现有的 Channel 系统

### 方案 C：使用 Node.js 网关（折中方案）

创建一个独立的 Node.js 服务，通过 HTTP 与 Python 主程序通信。

**架构：**
```
企业微信 WebSocket ↔ Node.js 网关 ↔ HTTP ↔ Python Agent
```

## 🚀 推荐实施步骤

### 第一步：测试 WebSocket 连接

创建测试脚本验证连接：

```python
# test_wecom_ws.py
import asyncio
import websockets
import json

BOT_ID = "aiboT2pHPPXhAX6ic3OGWGNrAWD1_MTQsz8"
SECRET = "SzOaJdgMn9DbULVWpxYnKlTBQPtHAFLYWoixa6aCN3t"
WS_URL = "wss://openws.work.weixin.qq.com"

async def test_connection():
    async with websockets.connect(WS_URL) as ws:
        # 发送认证请求
        auth_msg = {
            "cmd": "aibot_subscribe",
            "headers": {"req_id": "test-001"},
            "body": {
                "secret": SECRET,
                "bot_id": BOT_ID
            }
        }
        await ws.send(json.dumps(auth_msg))
        
        # 接收响应
        response = await ws.recv()
        print(f"认证响应：{response}")
        
        # 保持连接，接收消息
        async for message in ws:
            print(f"收到消息：{message}")

asyncio.run(test_connection())
```

### 第二步：集成到 Channel 系统

修改 `channels/wecom/channel.py`，实现完整的 WebSocket 客户端。

### 第三步：配置和启动

在 `.env` 中添加：
```bash
WECOM_BOT_ID=aiboT2pHPPXhAX6ic3OGWGNrAWD1_MTQsz8
WECOM_SECRET=SzOaJdgMn9DbULVWpxYnKlTBQPtHAFLYWoixa6aCN3t
WECOM_WS_URL=wss://openws.work.weixin.qq.com
WECOM_ENABLED=true
```

## 📚 参考资料

- [OpenClaw WeCom 插件源码](https://github.com/WecomTeam/wecom-openclaw-plugin)
- [企业微信智能机器人文档](https://open.work.weixin.qq.com/help2/pc/cat?doc_id=21657)
- [@wecom/aibot-node-sdk](https://www.npmjs.com/package/@wecom/aibot-node-sdk)

## ⚠️ 注意事项

1. **Secret 安全**：不要将 Secret 提交到 Git
2. **心跳保持**：需要定期发送心跳包保持连接
3. **重连机制**：网络断开时自动重连
4. **消息去重**：避免重复处理同一条消息

## 🤔 下一步？

我可以帮你：
1. ✅ 完整实现 Python WebSocket 客户端（推荐）
2. 创建 Node.js 网关服务
3. 直接测试连接看看是否可行

需要我实现哪个方案？🦞
