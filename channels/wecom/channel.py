"""
WeCom Channel - 企业微信消息频道 (OpenClaw Plugin)

使用 WebSocket 长连接，通过 WeCom OpenClaw Plugin 接入。
"""

import os
import json
import time
import logging
import threading
from typing import Optional, Dict, Any

try:
    from lark_oapi.ws import Client as WsClient
except ImportError:
    pass  # 这里不是飞书

logger = logging.getLogger(__name__)

class WeComChannel:
    """
    企业微信消息频道
    
    依赖: 
    - aibot-node-sdk (或者我们自己实现 WebSocket 逻辑)
    - 环境变量 WECOM_BOT_ID, WECOM_SECRET
    """
    
    def __init__(self):
        self.ws = None # 我们将使用 websocket-client 或者自行实现
        self.running = False
        self.message_count = 0
        self.agent_executor = None
        self.bot_id = None
        self.secret = None
        self.ws_url = "wss://openws.work.weixin.qq.com/aibot"
        self.processed_messages = set()
        self.reconnect_count = 0
        self.max_reconnect_delay = 60
        
    def set_agent(self, agent_executor):
        self.agent_executor = agent_executor
        
    def start(self, bot_id: str = None, secret: str = None):
        """
        启动企业微信 Channel
        """
        self.bot_id = (bot_id or os.getenv("WECOM_BOT_ID") or "").strip()
        self.secret = (secret or os.getenv("WECOM_SECRET") or "").strip()
        
        if not self.bot_id or not self.secret:
            logger.error("缺少企业微信配置（WECOM_BOT_ID, WECOM_SECRET）")
            return
            
        self.running = True
        thread = threading.Thread(target=self._run_forever, daemon=True)
        thread.start()
        logger.info(f"企业微信 Channel 已启动 (Bot ID: {self.bot_id})")

    def _run_forever(self):
        import websocket
        while self.running:
            try:
                self._connect(websocket)
            except Exception as e:
                logger.error(f"企业微信连接断开: {e}")
                
            if self.running:
                delay = min(self.max_reconnect_delay, 2 ** self.reconnect_count)
                logger.info(f"将在 {delay} 秒后重连...")
                time.sleep(delay)
                self.reconnect_count += 1

    def _connect(self, websocket):
        # WeCom AI Bot WebSocket 协议
        # 参考 @wecom/aibot-node-sdk
        
        url = self.ws_url
        
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        self.ws.run_forever(ping_interval=30)

    def _on_open(self, ws):
        logger.info("企业微信 WebSocket 已连接")
        self.reconnect_count = 0
        # 发送认证信息 (WeCom AI Bot Protocol)
        # @wecom/aibot-node-sdk 发送的是:
        # { "command": "aibot_subscribe", "bot_id": "...", "secret": "..." }
        auth_payload = {
            "command": "aibot_subscribe",
            "bot_id": self.bot_id,
            "secret": self.secret
        }
        ws.send(json.dumps(auth_payload))

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "message":
                self._handle_incoming_message(data)
            elif msg_type == "auth_ack":
                logger.info("企业微信认证成功")
                
        except Exception as e:
            logger.error(f"解析消息失败: {e}")

    def _handle_incoming_message(self, data):
        sender = data.get("from", {}).get("user_id", "unknown")
        content = data.get("content", "")
        msg_id = data.get("msg_id", "")
        chat_id = data.get("chat_id", "")
        
        if msg_id in self.processed_messages:
            return
        self.processed_messages.add(msg_id)
        
        logger.info(f"[企业微信] {sender}: {content[:50]}")
        
        if self.agent_executor:
            # 调用 Agent
            response = self.agent_executor.invoke({
                "input": f"企业微信用户 {sender} 说：{content}",
                "chat_history": [] # 简化处理，实际应维护上下文
            })
            reply = response.get("output", "")
            if reply:
                self._send_reply(chat_id, reply)

    def _send_reply(self, chat_id, text):
        if not self.ws or not self.ws.sock or not self.ws.sock.connected:
            logger.error("WebSocket 未连接，无法发送回复")
            return
            
        payload = {
            "command": "send_message",
            "chat_id": chat_id,
            "content": text,
            "msg_type": "text"
        }
        self.ws.send(json.dumps(payload))

    def _on_error(self, ws, error):
        logger.error(f"企业微信 WebSocket 错误: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info("企业微信 WebSocket 连接关闭")

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()
