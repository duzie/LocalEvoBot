"""
Dingtalk Channel - 钉钉消息频道

使用 WebSocket 长连接，实时接收和发送消息。
无需公网服务器，无需 HTTPS。

钉钉 SDK: https://pypi.org/project/dingtalk-stream/
"""

import os
import logging
import threading
from typing import Optional, Dict, Any

try:
    import dingtalk_stream
except ImportError:
    raise ImportError("请先安装钉钉 SDK: pip install dingtalk-stream")

logger = logging.getLogger(__name__)


class DingtalkHandler(dingtalk_stream.ChatbotHandler):
    """钉钉消息处理器"""
    
    def __init__(self, agent_executor=None):
        super().__init__()
        self.agent_executor = agent_executor
    
    async def process(self, callback: dingtalk_stream.CallbackMessage):
        """处理钉钉消息"""
        try:
            # 解析消息
            conversation = callback.data.get('conversation', {})
            sender = callback.data.get('sender', {})
            text = callback.data.get('text', {}).get('content', '')
            
            chat_id = conversation.get('conversationId', '')
            sender_name = sender.get('nick', '未知用户')
            sender_type = sender.get('type', 'user')
            
            # 跳过机器人自己的消息
            if sender_type == 'bot':
                return
            
            logger.info(f"[钉钉] {sender_name}: {text[:100]}")
            
            # 调用 Agent 处理
            if self.agent_executor:
                response = self.agent_executor.invoke({
                    "input": f"钉钉用户 {sender_name} 发来消息：{text}"
                })
                reply_text = response.get("output", "收到你的消息了")
            else:
                reply_text = "收到你的消息了"
            
            # 回复消息
            await self.reply_text(reply_text, conversation)
            
            logger.info(f"[钉钉回复] {reply_text[:100]}")
            
        except Exception as e:
            logger.error(f"处理钉钉消息失败：{e}")


class DingtalkChannel:
    """
    钉钉消息频道
    
    用法:
        channel = DingtalkChannel()
        channel.start(client_id, client_secret)
        # 后台自动运行，接收消息 → Agent → 回复
    """
    
    def __init__(self):
        self.client: Optional[dingtalk_stream.StreamClient] = None
        self.handler: Optional[DingtalkHandler] = None
        self.running = False
        self.message_count = 0
        self.agent_executor = None
    
    def set_agent(self, agent_executor):
        """设置 Agent 执行器"""
        self.agent_executor = agent_executor
        if self.handler:
            self.handler.agent_executor = agent_executor
    
    def start(self, client_id: str = None, client_secret: str = None):
        """
        启动钉钉 Channel（WebSocket 长连接）
        
        Args:
            client_id: 钉钉应用 Client ID（或环境变量 DINGTALK_CLIENT_ID）
            client_secret: 钉钉应用 Client Secret（或环境变量 DINGTALK_CLIENT_SECRET）
        """
        # 获取配置
        client_id = (client_id or os.getenv("DINGTALK_CLIENT_ID") or "").strip()
        client_secret = (client_secret or os.getenv("DINGTALK_CLIENT_SECRET") or "").strip()
        
        if not client_id or not client_secret:
            logger.error("缺少钉钉配置（DINGTALK_CLIENT_ID, DINGTALK_CLIENT_SECRET）")
            return
        
        try:
            # 创建处理器
            self.handler = DingtalkHandler(self.agent_executor)
            
            # 创建客户端
            credential = dingtalk_stream.Credential(client_id, client_secret)
            self.client = dingtalk_stream.StreamClient(credential)
            
            # 注册处理器
            self.client.register_callback_handler(dingtalk_stream.ChatbotMessage.TOPIC, self.handler)
            
            # 启动 WebSocket 连接（后台线程）
            self.running = True
            thread = threading.Thread(target=self._run_stream, daemon=True)
            thread.start()
            
            logger.info("[OK] 钉钉 Channel 已启动（WebSocket 长连接）")
            
        except Exception as e:
            logger.error(f"启动钉钉 Channel 失败：{e}")
            self.running = False
    
    def _run_stream(self):
        """运行钉钉流"""
        try:
            logger.info("正在连接钉钉 WebSocket...")
            self.client.start()
        except Exception as e:
            logger.error(f"钉钉连接异常：{e}")
            self.running = False
    
    def stop(self):
        """停止 Channel"""
        self.running = False
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        logger.info("✅ 钉钉 Channel 已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取 Channel 状态"""
        return {
            "running": self.running,
            "message_count": self.message_count,
            "client_connected": self.client is not None
        }
