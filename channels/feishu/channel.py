"""
Feishu Channel - 飞书消息频道

使用 WebSocket 长连接，实时接收和发送消息。
无需公网服务器，无需 HTTPS。

适配新版 lark_oapi SDK (1.5.3)
"""

import os
import logging
import threading
from typing import Optional, Dict, Any

try:
    from lark_oapi import Client as LarkClient
    from lark_oapi.ws import Client as WsClient
    from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
    from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
    from lark_oapi.api.im.v1.model.reply_message_request import ReplyMessageRequest
    from lark_oapi.core.enum import LogLevel
except ImportError:
    raise ImportError("请先安装飞书 SDK: pip install lark-oapi")

logger = logging.getLogger(__name__)


class FeishuChannel:
    """
    飞书消息频道
    
    用法:
        channel = FeishuChannel()
        channel.start(app_id, app_secret)
        # 后台自动运行，接收消息 → Agent → 回复
    """
    
    def __init__(self):
        self.ws_client: Optional[WsClient] = None
        self.api_client: Optional[LarkClient] = None
        self.running = False
        self.message_count = 0
        self.agent_executor = None
        self.processed_messages = set()  # 消息去重集合
    
    def set_agent(self, agent_executor):
        """设置 Agent 执行器"""
        self.agent_executor = agent_executor
    
    def _handle_message(self, req):
        """处理接收到的消息"""
        try:
            # req 是 P2ImMessageReceiveV1 对象，直接使用 event 属性
            if hasattr(req, 'event'):
                event = req.event
                self._on_message(event)
            else:
                logger.error(f"无效的请求：没有 event 属性，type={type(req)}")
        except Exception as e:
            logger.error(f"处理飞书消息失败：{e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def start(self, app_id: str = None, app_secret: str = None):
        """
        启动飞书 Channel（WebSocket 长连接）
        
        Args:
            app_id: 飞书应用 ID（或环境变量 FEISHU_APP_ID）
            app_secret: 飞书应用密钥（或环境变量 FEISHU_APP_SECRET）
        """
        # 获取配置
        app_id = (app_id or os.getenv("FEISHU_APP_ID") or "").strip()
        app_secret = (app_secret or os.getenv("FEISHU_APP_SECRET") or "").strip()
        
        if not app_id or not app_secret:
            logger.error("缺少飞书配置（FEISHU_APP_ID, FEISHU_APP_SECRET）")
            self.running = False
            return
        
        logger.info(f"正在初始化飞书 Channel (App ID: {app_id[:8]}...)")
        
        try:
            # 创建 API 客户端（用于发送消息）
            self.api_client = LarkClient.builder() \
                .app_id(app_id) \
                .app_secret(app_secret) \
                .log_level(LogLevel.INFO) \
                .build()
            
            # 创建事件处理器（使用 builder 模式注册事件）
            event_handler = EventDispatcherHandler.builder("", "") \
                .register_p2_im_message_receive_v1(self._handle_message) \
                .register_p2_im_message_message_read_v1(self._handle_message_read) \
                .build()
            
            # 创建 WebSocket 客户端（直接实例化）
            self.ws_client = WsClient(
                app_id=app_id,
                app_secret=app_secret,
                event_handler=event_handler,
                log_level=LogLevel.INFO,
                auto_reconnect=True
            )
            
            # 启动 WebSocket 连接（后台线程）
            self.running = True
            thread = threading.Thread(target=self._run_ws, daemon=True)
            thread.start()
            
            logger.info("[OK] 飞书 Channel 启动命令已发送，正在建立 WebSocket 连接...")
            
        except Exception as e:
            logger.error(f"启动飞书 Channel 失败：{e}")
            self.running = False
            import traceback
            logger.error(traceback.format_exc())
    
    def _run_ws(self):
        """运行 WebSocket 连接"""
        try:
            logger.info("正在连接飞书 WebSocket 服务器...")
            self.ws_client.start()
            logger.info("WebSocket 连接已关闭")
        except Exception as e:
            logger.error(f"WebSocket 连接异常：{e}")
            import traceback
            logger.error(traceback.format_exc())
            self.running = False
    
    def _handle_message_read(self, event):
        """
        消息已读事件处理（空实现，避免报错）
        
        Args:
            event: 飞书事件数据
        """
        pass
    
    def _on_message(self, event):
        """
        消息接收回调
        
        Args:
            event: 飞书事件数据（P2ImMessageReceiveV1Data 对象）
        """
        try:
            # event 是 P2ImMessageReceiveV1Data 对象
            sender = event.sender
            message = event.message
            
            # 获取消息信息
            msg_id = message.message_id if hasattr(message, 'message_id') else ""
            chat_id = message.chat_id if hasattr(message, 'chat_id') else ""
            msg_type = message.message_type if hasattr(message, 'message_type') else "text"
            content_raw = message.content if hasattr(message, 'content') else "{}"
            
            # 消息去重：避免重复处理同一条消息
            if msg_id in self.processed_messages:
                logger.debug(f"消息已处理过，跳过：{msg_id}")
                return
            self.processed_messages.add(msg_id)
            
            # 限制去重集合大小，避免内存泄漏
            if len(self.processed_messages) > 1000:
                self.processed_messages.clear()
                logger.debug("清空消息去重集合")
            
            # 获取发送者信息
            sender_type = sender.sender_type if hasattr(sender, 'sender_type') else "user"
            sender_id_obj = sender.sender_id if hasattr(sender, 'sender_id') else None
            
            # UserId 对象有 open_id, union_id, user_id 三个属性
            sender_id = None
            if sender_id_obj:
                if hasattr(sender_id_obj, 'open_id') and sender_id_obj.open_id:
                    sender_id = sender_id_obj.open_id
                elif hasattr(sender_id_obj, 'user_id') and sender_id_obj.user_id:
                    sender_id = sender_id_obj.user_id
                elif hasattr(sender_id_obj, 'union_id') and sender_id_obj.union_id:
                    sender_id = sender_id_obj.union_id
            
            sender_name = f"用户_{sender_id[-8:]}" if sender_id and len(sender_id) > 8 else "未知用户"
            
            # 跳过机器人自己的消息
            if sender_type == "bot":
                return
            
            # 只处理文本消息
            if msg_type != "text":
                return
            
            # 解析消息内容
            import json
            try:
                content_obj = json.loads(content_raw)
                content = content_obj.get("text", content_raw)
            except Exception:
                content = content_raw
            
            self.message_count += 1
            logger.info(f"[飞书] {sender_name}: {content[:100]}")
            
            # 调用 Agent 处理
            if self.agent_executor:
                response = self.agent_executor.invoke({
                    "input": f"飞书用户 {sender_name} 发来消息：{content}"
                })
                reply_text = response.get("output", "收到你的消息了")
            else:
                reply_text = "收到你的消息了"
            
            # 回复消息
            self._reply(chat_id, msg_id, reply_text)
            
            logger.info(f"[飞书回复] {reply_text[:100]}")
            
        except Exception as e:
            logger.error(f"处理飞书消息失败：{e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _reply(self, chat_id: str, msg_id: str, text: str):
        """
        回复消息
        
        Args:
            chat_id: 群聊 ID
            msg_id: 原消息 ID
            text: 回复内容
        """
        try:
            import json
            
            content = {"text": text}
            
            # 使用回复消息接口：/open-apis/im/v1/messages/:message_id/reply
            # 参考：https://open.feishu.cn/document/server-docs/im-v1/message/reply
            request = ReplyMessageRequest.builder() \
                .message_id(msg_id) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .msg_type("text")
                    .content(json.dumps(content, ensure_ascii=False))
                    .build()
                ) \
                .build()
            
            # 调试：打印请求信息
            logger.info(f"准备发送回复，chat_id={chat_id}, msg_id={msg_id}")
            logger.info(f"请求 message_id: {request.message_id}")
            logger.info(f"请求 body type: {type(request.body)}")
            if hasattr(request.body, '__dict__'):
                logger.info(f"请求 body attrs: {request.body.__dict__}")
            
            response = self.api_client.im.v1.message.reply(request)
            
            if not response.success():
                logger.error(f"回复失败：{response.code} - {response.msg}")
                if hasattr(response, 'data') and response.data:
                    logger.error(f"响应数据：{response.data}")
            else:
                logger.info(f"回复成功，message_id={response.data.message_id if hasattr(response, 'data') else 'N/A'}")
            
        except Exception as e:
            logger.error(f"回复消息异常：{e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def stop(self):
        """停止 Channel"""
        self.running = False
        if self.ws_client:
            try:
                self.ws_client.stop()
            except Exception:
                pass
        logger.info("✅ 飞书 Channel 已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取 Channel 状态"""
        return {
            "running": self.running,
            "message_count": self.message_count,
            "client_connected": self.ws_client is not None
        }
