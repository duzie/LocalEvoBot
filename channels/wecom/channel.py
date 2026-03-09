"""
WeCom Channel - 企业微信消息频道

使用 WebSocket 长连接模式，无需公网服务器。

企业微信 API: https://work.weixin.qq.com/api/doc
"""

import os
import logging
import threading
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    from .wecom_ws_client import WeComWebSocketClient, WeComMessage
except ImportError:
    raise ImportError("请先安装 websockets: pip install websockets")


class WeComChannel:
    """
    企业微信消息频道（WebSocket 长连接模式）
    
    用法:
        channel = WeComChannel()
        channel.start(bot_id, secret)
        # 后台自动运行，WebSocket 长连接 → 接收消息 → Agent → 回复
    
    注意：WebSocket 长连接模式无需公网服务器
    """
    
    def __init__(self):
        self.bot_id = ""
        self.secret = ""
        self.ws_url = ""
        
        self.running = False
        self.message_count = 0
        self.agent_executor = None
        self.ws_client: Optional[WeComWebSocketClient] = None
        self._connect_thread: Optional[threading.Thread] = None
    
    def set_agent(self, agent_executor):
        """设置 Agent 执行器"""
        self.agent_executor = agent_executor
    
    def _on_message(self, msg: WeComMessage):
        """
        收到消息回调
        
        Args:
            msg: 企业微信消息
        """
        import asyncio
        import threading
        
        try:
            self.message_count += 1
            logger.info(f"[DEBUG] _on_message 被调用：from={msg.from_userid}, content={msg.content[:100]}")
            
            # 注意：不发送 ACK，因为 response_url 可能只能用一次
            
            # 调用 Agent 处理（在后台线程中）
            def process_and_reply():
                if self.agent_executor:
                    logger.info(f"[企业微信] 处理消息：{msg.content[:100]}")
                    
                    try:
                        response = self.agent_executor.invoke({
                            "input": f"企业微信用户 {msg.from_userid} 发来消息：{msg.content}"
                        })
                        reply_text = response.get("output", "收到你的消息了")
                        
                        # 通过 HTTP response_url 发送最终回复
                        if msg.response_url:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                # 尝试 markdown 格式
                                body = {"msgtype": "markdown", "markdown": {"content": reply_text}}
                                result = loop.run_until_complete(self._http_post(msg.response_url, body))
                                logger.info(f"[DEBUG] HTTP 响应：{result}")
                                if result and result.get('errcode') == 0:
                                    logger.info(f"[企业微信回复] {reply_text[:100]}")
                                else:
                                    logger.error(f"[企业微信] 回复失败：{result}")
                            except Exception as e:
                                logger.error(f"HTTP 回复失败：{e}")
                            finally:
                                loop.close()
                        else:
                            logger.warning("没有 response_url，无法发送回复")
                    except Exception as e:
                        logger.error(f"Agent 处理失败：{e}")
                else:
                    logger.warning("Agent executor 未设置")
            
            # 在后台线程中处理
            process_thread = threading.Thread(target=process_and_reply, daemon=True)
            process_thread.start()
            
        except Exception as e:
            logger.error(f"处理企业微信消息失败：{e}")
    
    async def _http_post(self, url: str, body: dict):
        """HTTP POST 请求"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body) as resp:
                return await resp.json()
    
    def _on_connected(self):
        """连接成功回调"""
        logger.info("✅ 企业微信 WebSocket 已连接")
    
    def _on_disconnected(self, reason: str):
        """断开连接回调"""
        logger.warning(f"⚠️ 企业微信 WebSocket 断开：{reason}")
    
    def start(self, botid: str = None, secret: str = None, ws_url: str = None):
        """
        启动企业微信 Channel（WebSocket 长连接模式）
        
        Args:
            botid: 机器人 ID（或环境变量 WECOM_BOT_ID）
            secret: 机器人 Secret（或环境变量 WECOM_SECRET）
            ws_url: WebSocket 服务器地址（或环境变量 WECOM_WS_URL）
        """
        # 获取配置
        self.bot_id = (botid or os.getenv("WECOM_BOT_ID") or "").strip()
        self.secret = (secret or os.getenv("WECOM_SECRET") or "").strip()
        self.ws_url = (ws_url or os.getenv("WECOM_WS_URL") or "wss://openws.work.weixin.qq.com").strip()
        
        if not self.bot_id or not self.secret:
            logger.error("缺少企业微信配置（WECOM_BOT_ID, WECOM_SECRET）")
            return
        
        try:
            self.running = True
            
            # 创建 WebSocket 客户端
            self.ws_client = WeComWebSocketClient(
                bot_id=self.bot_id,
                secret=self.secret,
                ws_url=self.ws_url,
                on_message=self._on_message,
                on_connected=self._on_connected,
                on_disconnected=self._on_disconnected
            )
            
            # 在后台线程中启动连接
            self._connect_thread = threading.Thread(
                target=self._runWebSocket,
                daemon=True
            )
            self._connect_thread.start()
            
            logger.info("[OK] 企业微信 Channel 已启动（WebSocket 长连接）")
            logger.info("[注意] WebSocket 长连接模式无需公网服务器")
            
        except Exception as e:
            logger.error(f"启动企业微信 Channel 失败：{e}")
            self.running = False
    
    def _runWebSocket(self):
        """运行 WebSocket 连接（在后台线程中）"""
        import asyncio
        
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.ws_client.connect())
        except Exception as e:
            logger.error(f"WebSocket 连接异常：{e}")
        finally:
            loop.close()
    
    def stop(self):
        """停止 Channel"""
        self.running = False
        if self.ws_client:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.ws_client.disconnect())
            except Exception as e:
                logger.error(f"断开连接失败：{e}")
            finally:
                loop.close()
        
        logger.info("✅ 企业微信 Channel 已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取 Channel 状态"""
        return {
            "running": self.running,
            "message_count": self.message_count,
            "connected": self.ws_client.is_connected if self.ws_client else False,
            "mode": "websocket"
        }
