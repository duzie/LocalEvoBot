"""
MQTT Channel - MQTT消息频道

使用 MQTT 协议建立长连接，接收和发送消息。
支持通过 appid, appsecret, url 与服务器建立连接。
"""

import os
import json
import logging
import threading
import time
from typing import Optional, Dict, Any
import ssl

try:
    import paho.mqtt.client as mqtt
except ImportError:
    raise ImportError("请先安装MQTT库: pip install paho-mqtt")

logger = logging.getLogger(__name__)


class MqttChannel:
    """
    MQTT消息频道
    
    用法:
        channel = MqttChannel()
        channel.start(server_url, app_id, app_secret)
        # 后台自动运行，接收消息 → Agent → 回复
    """
    
    def __init__(self):
        self.mqtt_client: Optional[mqtt.Client] = None
        self.running = False
        self.message_count = 0
        self.agent_executor = None
        self.processed_messages = set()  # 消息去重集合
        self.server_url = ""
        self.app_id = ""
        self.app_secret = ""
        self.topic_subscribe = "agent/incoming"  # 默认订阅主题
        self.topic_publish = "agent/outgoing"    # 默认发布主题
        
    def set_agent(self, agent_executor):
        """设置 Agent 执行器"""
        self.agent_executor = agent_executor
        logger.info("MQTT Channel: Agent 执行器已设置")
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT连接成功回调"""
        if rc == 0:
            logger.info(f"[MQTT] 连接成功到服务器 {self.server_url}")
            # 订阅消息主题
            result, mid = client.subscribe(self.topic_subscribe)
            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"[MQTT] 已订阅主题: {self.topic_subscribe}")
            else:
                logger.error(f"[MQTT] 订阅主题失败: {result}")
        else:
            logger.error(f"[MQTT] 连接失败，返回码: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT断开连接回调"""
        logger.info(f"[MQTT] 与服务器断开连接，返回码: {rc}")
        if self.running and rc != 0:
            # 非正常断开，尝试重连
            logger.info("[MQTT] 尝试重新连接...")
            time.sleep(5)  # 等待5秒后重连
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"[MQTT] 重连失败: {e}")
    
    def _on_message(self, client, userdata, msg):
        """
        MQTT消息接收回调
        
        Args:
            client: MQTT客户端
            userdata: 用户数据
            msg: 接收到的消息对象
        """
        try:
            logger.info(f"[MQTT] 接收到消息，主题: {msg.topic}")
            
            # 解析消息内容
            try:
                payload = msg.payload.decode('utf-8')
                message_data = json.loads(payload)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(f"[MQTT] 消息解析失败: {e}, 原始内容: {msg.payload}")
                return
            
            # 提取消息ID，用于去重
            msg_id = message_data.get('message_id') or f"{time.time()}"
            
            # 检查是否已处理过此消息
            if msg_id in self.processed_messages:
                logger.debug(f"[MQTT] 消息已处理过，跳过: {msg_id}")
                return
            
            self.processed_messages.add(msg_id)
            self.message_count += 1
            
            # 提取用户消息内容
            user_message = message_data.get('content') or message_data.get('message') or str(message_data)
            user_id = message_data.get('user_id', 'unknown')
            session_id = message_data.get('session_id', f'session_{user_id}')
            
            logger.info(f"[MQTT] 用户 {user_id}: {user_message}")
            
            # 调用 Agent 处理消息
            if self.agent_executor:
                try:
                    logger.info(f"[MQTT] 正在调用 Agent 处理消息...")
                    
                    # 准备Agent输入
                    agent_input = {
                        "input": user_message,
                        "user_id": user_id,
                        "session_id": session_id,
                        "channel": "mqtt",
                        "original_message": message_data
                    }
                    
                    # 调用 Agent
                    result = self.agent_executor.invoke(agent_input)
                    
                    # 获取Agent响应
                    response_text = result.get('output', '') if isinstance(result, dict) else str(result)
                    
                    logger.info(f"[MQTT] Agent 处理完成，准备回复")
                    
                    # 发送回复
                    self._send_reply(client, response_text, user_id, session_id, msg_id)
                    
                except Exception as e:
                    error_msg = f"Agent 处理消息时出错: {str(e)}"
                    logger.error(error_msg)
                    logger.exception(e)  # 记录详细堆栈信息
                    
                    # 发送错误回复
                    self._send_reply(client, error_msg, user_id, session_id, msg_id, is_error=True)
            else:
                logger.warning("[MQTT] Agent 执行器未设置")
                
        except Exception as e:
            logger.error(f"[MQTT] 处理消息时出错: {e}")
            logger.exception(e)
    
    def _send_reply(self, client, response_text, user_id, session_id, request_msg_id, is_error=False):
        """
        发送回复消息
        
        Args:
            client: MQTT客户端
            response_text: 回复内容
            user_id: 用户ID
            session_id: 会话ID
            request_msg_id: 请求消息ID
            is_error: 是否为错误回复
        """
        try:
            # 构建回复消息
            reply_data = {
                'type': 'reply',
                'message_id': f'reply_{request_msg_id}',
                'response_to': request_msg_id,
                'user_id': user_id,
                'session_id': session_id,
                'content': response_text,
                'timestamp': int(time.time()),
                'is_error': is_error
            }
            
            # 序列化为JSON
            reply_payload = json.dumps(reply_data, ensure_ascii=False)
            
            # 发布回复消息
            result = client.publish(self.topic_publish, reply_payload)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"[MQTT] 回复已发送到主题 {self.topic_publish}, 用户: {user_id}")
            else:
                logger.error(f"[MQTT] 发送回复失败，错误码: {result.rc}")
                
        except Exception as e:
            logger.error(f"[MQTT] 发送回复时出错: {e}")
            logger.exception(e)
    
    def start(self, server_url: str = None, app_id: str = None, app_secret: str = None, 
              topic_subscribe: str = None, topic_publish: str = None):
        """
        启动 MQTT Channel（MQTT 长连接）
        
        Args:
            server_url: MQTT 服务器 URL（或环境变量 MQTT_SERVER_URL）
            app_id: 应用 ID（或环境变量 MQTT_APP_ID）
            app_secret: 应用密钥（或环境变量 MQTT_APP_SECRET）
            topic_subscribe: 订阅主题（或环境变量 MQTT_SUBSCRIBE_TOPIC）
            topic_publish: 发布主题（或环境变量 MQTT_PUBLISH_TOPIC）
        """
        # 获取配置
        self.server_url = server_url or os.getenv("MQTT_SERVER_URL") or os.getenv("MQTT_BROKER_URL") or "tcp://localhost:1883"
        self.app_id = app_id or os.getenv("MQTT_APP_ID") or os.getenv("MQTT_CLIENT_ID") or ""
        self.app_secret = app_secret or os.getenv("MQTT_APP_SECRET") or os.getenv("MQTT_PASSWORD") or ""
        
        # 获取主题配置
        self.topic_subscribe = topic_subscribe or os.getenv("MQTT_SUBSCRIBE_TOPIC") or "agent/incoming"
        self.topic_publish = topic_publish or os.getenv("MQTT_PUBLISH_TOPIC") or "agent/outgoing"
        
        if not self.server_url:
            logger.error("缺少 MQTT 服务器配置（MQTT_SERVER_URL）")
            self.running = False
            return
        
        logger.info(f"正在初始化 MQTT Channel (Server: {self.server_url})")
        
        try:
            # 解析服务器URL (支持 tcp://, ssl://, ws:// 等协议)
            protocol = "tcp"
            hostname = "localhost"
            port = 1883
            
            if "://" in self.server_url:
                protocol, addr = self.server_url.split("://", 1)
                if ":" in addr:
                    hostname, port_str = addr.rsplit(":", 1)
                    port = int(port_str)
                else:
                    hostname = addr
            else:
                # 纯主机名或IP
                if ":" in self.server_url:
                    hostname, port_str = self.server_url.rsplit(":", 1)
                    port = int(port_str)
                else:
                    hostname = self.server_url
            
            # 创建 MQTT 客户端
            client_id = self.app_id or f"langchain_mqtt_agent_{int(time.time())}"
            self.mqtt_client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
            
            # 设置用户名密码（如果提供）
            if self.app_id and self.app_secret:
                self.mqtt_client.username_pw_set(self.app_id, self.app_secret)
                logger.info(f"已设置认证信息 (Client ID: {client_id})")
            
            # 设置TLS/SSL（如果使用ssl协议）
            if protocol.lower() in ['ssl', 'tls', 'mqtts']:
                self.mqtt_client.tls_set(
                    cert_reqs=ssl.CERT_NONE,
                    tls_version=ssl.PROTOCOL_TLS,
                )
                logger.info("已设置TLS/SSL连接")
            
            # 设置回调函数
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.on_message = self._on_message
            
            # 设置遗嘱消息
            self.mqtt_client.will_set(
                topic=f"agent/status/{client_id}",
                payload=json.dumps({"status": "offline", "timestamp": int(time.time())}),
                qos=1,
                retain=True
            )
            
            # 连接到 MQTT 服务器
            self.mqtt_client.connect(hostname, port, 60)
            
            # 启动网络循环（后台线程）
            self.running = True
            self.mqtt_client.loop_start()
            
            logger.info(f"[OK] MQTT Channel 已启动，连接到 {self.server_url}")
            logger.info(f"[OK] 订阅主题: {self.topic_subscribe}")
            logger.info(f"[OK] 发布主题: {self.topic_publish}")
            
        except Exception as e:
            logger.error(f"启动 MQTT Channel 失败：{e}")
            self.running = False
            logger.exception(e)
    
    def stop(self):
        """停止 MQTT Channel"""
        if self.mqtt_client and self.running:
            try:
                # 发布离线状态
                client_id = self.mqtt_client._client_id.decode('utf-8') if isinstance(self.mqtt_client._client_id, bytes) else self.mqtt_client._client_id
                offline_msg = json.dumps({
                    "status": "offline", 
                    "timestamp": int(time.time()),
                    "message": "Agent 已断开连接"
                })
                self.mqtt_client.publish(f"agent/status/{client_id}", offline_msg, qos=1, retain=True)
                
                # 断开连接
                self.mqtt_client.disconnect()
                self.mqtt_client.loop_stop()
                
                logger.info("[MQTT] Channel 已停止")
            except Exception as e:
                logger.error(f"[MQTT] 停止过程中出错: {e}")
            
        self.running = False
    
    def get_status(self):
        """获取 MQTT Channel 状态"""
        status = {
            'running': self.running,
            'server_url': self.server_url,
            'app_id': self.app_id,
            'message_count': self.message_count,
            'processed_messages_count': len(self.processed_messages),
            'client_connected': self.mqtt_client.is_connected() if self.mqtt_client else False
        }
        return status