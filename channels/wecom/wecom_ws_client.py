"""
WeCom WebSocket Client - 企业微信 WebSocket 客户端

基于 websockets 库实现长连接，无需公网服务器。
参考：@wecom/aibot-node-sdk (https://www.npmjs.com/package/@wecom/aibot-node-sdk)

用法:
    client = WeComWebSocketClient(bot_id, secret)
    await client.connect()
    await client.send_message(chat_id, "Hello")
"""

import asyncio
import json
import uuid
import time
import logging
from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass, asdict

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:
    raise ImportError("请先安装 websockets: pip install websockets")

logger = logging.getLogger(__name__)


@dataclass
class WeComMessage:
    """企业微信消息"""
    msgid: str
    chatid: str
    chattype: str  # "single" or "group"
    from_userid: str
    content: str
    msgtype: str = "text"
    timestamp: int = 0
    response_url: str = ""
    req_id: str = ""  # WebSocket 请求 ID
    frame_data: dict = None  # 完整的 frame 数据，用于回复
    
    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = int(time.time())


class WeComWebSocketClient:
    """
    企业微信 WebSocket 客户端
    
    功能:
    - 自动认证和重连
    - 心跳保持
    - 消息收发
    - 事件回调
    """
    
    # 企业微信 WebSocket 服务器
    DEFAULT_WS_URL = "wss://openws.work.weixin.qq.com"
    
    # 心跳间隔（毫秒）
    HEARTBEAT_INTERVAL_MS = 30000
    
    # 最大重连次数
    MAX_RECONNECT_ATTEMPTS = 100
    
    # 重连间隔（秒）
    RECONNECT_DELAY = 5
    
    def __init__(
        self,
        bot_id: str,
        secret: str,
        ws_url: Optional[str] = None,
        on_message: Optional[Callable[[WeComMessage], Any]] = None,
        on_connected: Optional[Callable[[], Any]] = None,
        on_disconnected: Optional[Callable[[str], Any]] = None,
    ):
        """
        初始化客户端
        
        Args:
            bot_id: 机器人 ID
            secret: 机器人 Secret
            ws_url: WebSocket 服务器地址（默认官方地址）
            on_message: 收到消息时的回调
            on_connected: 连接成功时的回调
            on_disconnected: 断开连接时的回调
        """
        self.bot_id = bot_id
        self.secret = secret
        self.ws_url = ws_url or self.DEFAULT_WS_URL
        
        self.on_message = on_message
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        
        self._ws: Optional[WebSocketClientProtocol] = None
        self._running = False
        self._connected = False
        self._reconnect_attempts = 0
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
    
    async def connect(self):
        """建立 WebSocket 连接"""
        self._running = True
        
        while self._running and self._reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
            try:
                logger.info(f"正在连接企业微信 WebSocket: {self.ws_url}")
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws
                    self._reconnect_attempts = 0
                    
                    # 认证
                    if await self._authenticate():
                        self._connected = True
                        logger.info("✅ 企业微信 WebSocket 连接成功")
                        
                        if self.on_connected:
                            self.on_connected()
                        
                        # 启动心跳和消息接收
                        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                        self._receive_task = asyncio.create_task(self._receive_loop())
                        
                        # 等待连接断开
                        await ws.wait_closed()
                    
                    self._connected = False
                    if self.on_disconnected:
                        self.on_disconnected("认证失败")
                    
            except websockets.exceptions.ConnectionClosed as e:
                self._connected = False
                logger.warning(f"连接断开：{e}")
                if self.on_disconnected:
                    self.on_disconnected(str(e))
                    
            except Exception as e:
                self._connected = False
                logger.error(f"连接异常：{e}")
                if self.on_disconnected:
                    self.on_disconnected(str(e))
            
            # 重连
            if self._running and self._reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
                self._reconnect_attempts += 1
                logger.info(f"将在 {self.RECONNECT_DELAY} 秒后重连 (尝试 {self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS})")
                await asyncio.sleep(self.RECONNECT_DELAY)
        
        if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
            logger.error("达到最大重连次数，停止重连")
    
    async def disconnect(self):
        """断开连接"""
        self._running = False
        self._connected = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            await self._ws.close()
        
        logger.info("✅ 企业微信 WebSocket 已断开")
    
    async def _authenticate(self) -> bool:
        """
        认证
        
        Returns:
            认证成功返回 True
        """
        try:
            auth_msg = {
                "cmd": "aibot_subscribe",
                "headers": {
                    "req_id": self._generate_req_id()
                },
                "body": {
                    "secret": self.secret,
                    "bot_id": self.bot_id
                }
            }
            
            await self._ws.send(json.dumps(auth_msg))
            response = await self._ws.recv()
            resp_data = json.loads(response)
            
            if resp_data.get("errcode", -1) == 0:
                logger.info("✅ 认证成功")
                return True
            else:
                logger.error(f"❌ 认证失败：{resp_data}")
                return False
                
        except Exception as e:
            logger.error(f"认证异常：{e}")
            return False
    
    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._running and self._connected:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL_MS / 1000)
                
                if self._ws and self._connected:
                    ping_msg = {
                        "cmd": "ping",
                        "headers": {
                            "req_id": self._generate_req_id()
                        },
                        "body": {}
                    }
                    await self._ws.send(json.dumps(ping_msg))
                    logger.debug("❤️ 发送心跳")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳发送失败：{e}")
    
    async def _receive_loop(self):
        """接收消息循环"""
        while self._running and self._connected:
            try:
                message = await self._ws.recv()
                await self._handle_message(message)
                
            except asyncio.CancelledError:
                break
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"接收消息异常：{e}")
    
    async def _handle_message(self, message: str):
        """
        处理收到的消息
        
        Args:
            message: WebSocket 消息
        """
        try:
            data = json.loads(message)
            cmd = data.get("cmd", "")
            
            # 调试：打印所有收到的消息
            logger.info(f"[DEBUG] 收到 WebSocket 消息：cmd={cmd}")
            logger.debug(f"[DEBUG] 完整数据：{json.dumps(data, ensure_ascii=False)}")
            
            # 只处理推送消息（支持两种 cmd 格式）
            if cmd in ("aibot_callback", "aibot_msg_callback"):
                body = data.get("body", {})
                
                # 调试：打印完整 body
                logger.info(f"[DEBUG] body 完整内容：{json.dumps(body, ensure_ascii=False)}")
                
                # 提取消息内容
                msgid = body.get("msgid", "")
                chattype = body.get("chattype", "single")
                from_userid = body.get("from", {}).get("userid", "")
                msgtype = body.get("msgtype", "text")
                
                # chatid 字段可能不存在，需要从其他字段推导
                chatid = body.get("chatid", "")
                if not chatid:
                    # 单聊：使用 userid 作为 chatid
                    # 群聊：需要从其他地方获取（但目前 body 中没有群 ID）
                    if chattype == "single":
                        chatid = from_userid
                    else:
                        chatid = from_userid  # 临时使用 userid
                
                logger.info(f"[DEBUG] chatid={chatid}, chattype={chattype}, from_userid={from_userid}")
                
                # 提取文本内容
                content = ""
                if msgtype == "text":
                    content = body.get("text", {}).get("content", "")
                elif msgtype == "mixed":
                    # 图文混排消息
                    mixed = body.get("mixed", {})
                    items = mixed.get("msg_item", [])
                    texts = []
                    for item in items:
                        if item.get("msgtype") == "text":
                            texts.append(item.get("text", {}).get("content", ""))
                    content = "\n".join(texts)
                
                # 提取 response_url（如果有）
                response_url = body.get("response_url", "")
                
                # 提取 req_id（如果有）
                req_id = data.get("headers", {}).get("req_id", "")
                
                # 保存完整的 frame 数据用于回复
                frame_data = {
                    "headers": data.get("headers", {}),
                    "body": body
                }
                
                # 构建消息对象
                wecom_msg = WeComMessage(
                    msgid=msgid,
                    chatid=chatid,
                    chattype=chattype,
                    from_userid=from_userid,
                    content=content,
                    msgtype=msgtype,
                    response_url=response_url,
                    req_id=req_id,
                    frame_data=frame_data
                )
                
                logger.info(f"[企业微信] {chattype} 消息 from {from_userid}: {content[:100]}")
                
                # 调用回调
                if self.on_message:
                    self.on_message(wecom_msg)
            
            # 处理心跳响应
            elif cmd == "pong":
                logger.debug("💓 收到心跳响应")
            
            # 处理认证响应
            elif cmd == "aibot_subscribe":
                errcode = data.get("errcode", -1)
                if errcode == 0:
                    logger.info("✅ 认证成功")
                else:
                    logger.error(f"❌ 认证失败：{data}")
            
            else:
                logger.debug(f"收到未知消息：{cmd}")
                
        except Exception as e:
            logger.error(f"处理消息失败：{e}")
    
    async def send_thinking_response(self, response_url: str, msgid: str):
        """
        发送"思考中"响应（保持连接）
        
        Args:
            response_url: 响应 URL
            msgid: 原消息 ID
        """
        try:
            import aiohttp
            # 发送空的文本响应，表示开始处理
            body = {
                "msgtype": "text",
                "quote_msgid": msgid,
                "text": {"content": "<think></think>"}  # 思考中标记
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(response_url, json=body) as resp:
                    result = await resp.json()
                    if result.get('errcode') == 0:
                        logger.debug("[企业微信] '思考中'响应成功")
                    else:
                        logger.debug(f"[企业微信] '思考中'响应：{result}")
        except Exception as e:
            logger.debug(f"'思考中'响应失败：{e}")
    
    async def send_wechat_reply(self, frame_data: dict, content: str, finish: bool = True, stream_id: str = None):
        """
        通过 WebSocket 发送回复（参考 OpenClaw 插件的 replyStream 方法）
        
        Args:
            frame_data: 原消息的 frame 数据
            content: 回复内容
            finish: 是否为最终消息
            stream_id: 流式 ID
        """
        import uuid
        
        if not self._connected or not self._ws:
            raise RuntimeError("WebSocket 未连接")
        
        try:
            # 生成 stream_id
            stream_id = stream_id or str(uuid.uuid4()).replace("-", "")
            
            # 构建流式响应消息
            # 参考 OpenClaw 插件：wsClient.replyStream(frame, streamId, text, finish)
            send_msg = {
                "cmd": "aibot_response",
                "headers": {
                    "req_id": frame_data.get("headers", {}).get("req_id", self._generate_req_id())
                },
                "body": {
                    "msgtype": "stream",
                    "stream": {
                        "id": stream_id,
                        "finish": finish,
                        "content": content
                    }
                }
            }
            
            logger.info(f"[企业微信] WebSocket 流式发送：stream_id={stream_id}, finish={finish}")
            logger.debug(f"[DEBUG] 发送内容：{json.dumps(send_msg, ensure_ascii=False)[:300]}")
            
            await self._ws.send(json.dumps(send_msg))
            logger.info(f"[企业微信] 流式发送成功")
            
            return stream_id
            
        except Exception as e:
            logger.error(f"流式发送失败：{e}")
            raise
    
    async def send_message(self, chat_id: str, content: str, msgtype: str = "text", response_url: str = None, msgid: str = None, req_id: str = None):
        """
        发送消息（已弃用，请使用 send_http_response）
        """
        logger.warning("send_message 已弃用，请使用 send_http_response")
        await self.send_http_response(response_url, msgid, content)
    
    def _generate_req_id(self) -> str:
        """生成请求 ID"""
        return str(uuid.uuid4()).replace("-", "")
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected


# ============================================================================
# 使用示例
# ============================================================================

async def example():
    """使用示例"""
    
    def on_message(msg: WeComMessage):
        print(f"收到消息：{msg.content}")
    
    def on_connected():
        print("连接成功！")
    
    def on_disconnected(reason: str):
        print(f"连接断开：{reason}")
    
    client = WeComWebSocketClient(
        bot_id="your_bot_id",
        secret="your_secret",
        on_message=on_message,
        on_connected=on_connected,
        on_disconnected=on_disconnected
    )
    
    try:
        await client.connect()
    except KeyboardInterrupt:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(example())
