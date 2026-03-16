import mqtt, { MqttClient } from 'mqtt';

// ============================================================================
// 简单的 MQTT 监听器 - 用于测试
// ============================================================================

const BROKER_URL = 'mqtt://broker.emqx.io:1883';
const AGENT_ID = 'openclaw-main';

const TOPICS = {
  PROCESS: `agent/process/${AGENT_ID}`,
  OUTGOING: 'agent/outgoing',
};

console.log('[MQTT Test] Connecting to', BROKER_URL);

const client = mqtt.connect(BROKER_URL, {
  clientId: `openclaw-test-${Date.now()}`,
  clean: true,
  reconnectPeriod: 5000,
});

client.on('connect', () => {
  console.log('[MQTT Test] Connected!');
  
  // 订阅处理队列
  client.subscribe(TOPICS.PROCESS, { qos: 1 }, (err) => {
    if (err) {
      console.error('[MQTT Test] Failed to subscribe:', err);
    } else {
      console.log('[MQTT Test] Subscribed to', TOPICS.PROCESS);
    }
  });
});

client.on('message', (topic, message) => {
  const msg = JSON.parse(message.toString());
  console.log('[MQTT Test] Received message:', JSON.stringify(msg, null, 2));
  
  // 模拟 AI 回复
  const response = {
    OriginalClientId: msg.OriginalClientId || 'test-client',
    UserId: msg.UserId || 'unknown',
    Response: `收到你的消息了：${msg.Message}。这是测试回复！`,
    Timestamp: new Date().toISOString(),
    RequestId: msg.RequestId,
  };
  
  console.log('[MQTT Test] Sending response:', JSON.stringify(response, null, 2));
  
  client.publish(TOPICS.OUTGOING, JSON.stringify(response), { qos: 1 }, (err) => {
    if (err) {
      console.error('[MQTT Test] Failed to publish:', err);
    } else {
      console.log('[MQTT Test] Response sent!');
    }
  });
});

client.on('error', (err) => {
  console.error('[MQTT Test] Error:', err);
});

client.on('close', () => {
  console.log('[MQTT Test] Connection closed');
});

// 保持进程运行
process.on('SIGINT', () => {
  console.log('[MQTT Test] Shutting down...');
  client.end();
  process.exit(0);
});
