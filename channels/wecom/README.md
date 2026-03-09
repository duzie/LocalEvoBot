# 企业微信 WebSocket 集成 - 快速开始

## 📦 安装依赖

```bash
pip install websockets
```

## 🔧 配置

### 方式 1：环境变量（推荐）

在 `.env` 文件中添加：

```bash
# 企业微信配置
WECOM_BOT_ID=aiboT2pHPPXhAX6ic3OGWGNrAWD1_MTQsz8
WECOM_SECRET=SzOaJdgMn9DbULVWpxYnKlTBQPtHAFLYWoixa6aCN3t
WECOM_WS_URL=wss://openws.work.weixin.qq.com
WECOM_ENABLED=true
```

### 方式 2：代码中配置

```python
from channels.wecom import WeComChannel

channel = WeComChannel()
channel.start(
    botid="aiboT2pHPPXhAX6ic3OGWGNrAWD1_MTQsz8",
    secret="SzOaJdgMn9DbULVWpxYnKlTBQPtHAFLYWoixa6aCN3t",
    ws_url="wss://openws.work.weixin.qq.com"
)
```

## 🚀 集成到 main.py

在 `main.py` 中，Channel 已经自动加载。只需确保 `.env` 中有配置：

```python
# main.py 中已有的代码
try:
    from channels.wecom import WeComChannel
    CHANNELS_AVAILABLE['wecom'] = WeComChannel
except ImportError as e:
    print(f"⚠️  企业微信 Channel 未导入：{e}")
```

启动后会自动连接企业微信。

## 🧪 测试连接

创建测试脚本：

```python
# test_wecom.py
import asyncio
from channels.wecom.wecom_ws_client import WeComWebSocketClient, WeComMessage

async def test():
    def on_message(msg: WeComMessage):
        print(f"✅ 收到消息：{msg.content}")
    
    def on_connected():
        print("✅ 连接成功！")
    
    def on_disconnected(reason: str):
        print(f"⚠️  断开：{reason}")
    
    client = WeComWebSocketClient(
        bot_id="aiboT2pHPPXhAX6ic3OGWGNrAWD1_MTQsz8",
        secret="SzOaJdgMn9DbULVWpxYnKlTBQPtHAFLYWoixa6aCN3t",
        on_message=on_message,
        on_connected=on_connected,
        on_disconnected=on_disconnected
    )
    
    print("正在连接...")
    await client.connect()

if __name__ == "__main__":
    asyncio.run(test())
```

运行：
```bash
python test_wecom.py
```

## 📊 架构说明

```
┌─────────────────┐     WebSocket      ┌──────────────────┐
│  企业微信服务器  │ ←────────────────→ │  WeComChannel    │
│  wss://...      │   长连接           │  (Python)        │
└─────────────────┘                    └────────┬─────────┘
                                                │
                                                ↓
                                       ┌──────────────────┐
                                       │   Agent Executor  │
                                       │   (LangChain)     │
                                       └──────────────────┘
```

### 核心特性

- ✅ **无需公网服务器** - WebSocket 主动连接到企业微信
- ✅ **自动重连** - 网络断开自动重连（最多 100 次）
- ✅ **心跳保持** - 每 30 秒发送心跳包
- ✅ **实时消息** - 消息即时推送，无延迟
- ✅ **消息去重** - 避免重复处理

## 🔍 调试

查看日志：

```bash
# 详细日志
export LOG_LEVEL=DEBUG
python main.py
```

日志输出示例：
```
2026-03-09 20:45:00 - INFO - 正在连接企业微信 WebSocket: wss://openws.work.weixin.qq.com
2026-03-09 20:45:01 - INFO - ✅ 认证成功
2026-03-09 20:45:01 - INFO - ✅ 企业微信 WebSocket 连接成功
2026-03-09 20:45:01 - INFO - [OK] 企业微信 Channel 已启动（WebSocket 长连接）
2026-03-09 20:46:30 - INFO - [企业微信] 单聊 消息 from user123: 你好
2026-03-09 20:46:35 - INFO - [企业微信回复] 你好！有什么可以帮你的吗？
```

## ⚠️ 常见问题

### 1. 认证失败

**错误**: `认证失败：{"errcode": 40001, "errmsg": "invalid secret"}`

**解决**: 检查 `WECOM_SECRET` 是否正确

### 2. 连接断开

**错误**: `WebSocket 断开：Connection closed`

**解决**: 会自动重连，检查网络连接

### 3. 收不到消息

**可能原因**:
- 机器人未在企业微信后台配置
- Bot ID 或 Secret 错误
- 防火墙阻止 WebSocket 连接

**解决**: 
- 检查企业微信后台配置
- 确保 WebSocket 端口（443）未被阻止

## 📚 参考资料

- [OpenClaw WeCom 插件](https://github.com/WecomTeam/wecom-openclaw-plugin)
- [企业微信智能机器人](https://open.work.weixin.qq.com/help2/pc/cat?doc_id=21657)

## 🎉 完成！

现在你的项目已经支持企业微信 WebSocket 长连接，无需公网服务器！🦞
