let mqttClient = null;
let config = null;
async function connectToMqtt(api, cfg) {
    try {
        const mqtt = await import('mqtt');
        const options = {
            clientId: cfg.clientId || `openclaw-mqtt-${Date.now()}`,
            clean: true,
            reconnectPeriod: 5000,
            connectTimeout: 30000,
        };
        if (cfg.username && cfg.password) {
            options.username = cfg.username;
            options.password = cfg.password;
        }
        mqttClient = mqtt.default.connect(cfg.brokerUrl, options);
        mqttClient.on('connect', () => {
            api.log.info('[MQTT] ✅ Connected to MQTT broker');
            // 订阅 agent/process/{agentId} 主题
            const processTopic = `agent/process/${cfg.agentId}`;
            mqttClient.subscribe(processTopic, { qos: 1 }, (err) => {
                if (err) {
                    api.log.error(`[MQTT] ❌ Failed to subscribe to ${processTopic}:`, err);
                    return;
                }
                api.log.info(`[MQTT] ✅ Subscribed to ${processTopic}`);
            });
        });
        mqttClient.on('error', (err) => {
            api.log.error('[MQTT] Connection error:', err);
        });
        mqttClient.on('message', async (topic, message) => {
            try {
                api.log.info(`[MQTT] Received message on ${topic}: ${message.toString()}`);
                // 处理 agent/process/{agentId} 主题的消息
                const expectedTopic = `agent/process/${cfg.agentId}`;
                if (topic === expectedTopic) {
                    const msg = JSON.parse(message.toString());
                    // 验证消息格式
                    if (!msg.UserId || !msg.Message) {
                        api.log.warn('[MQTT] Invalid message format:', message.toString());
                        return;
                    }
                    try {
                        // 使用 sessions.send 发送消息到主会话
                        const sessionKey = `agent:main:mqtt:${msg.UserId}`;
                        api.log.info(`[MQTT] Sending message to session: ${sessionKey}, message: ${msg.Message}`);
                        const response = await api.sessions.send({
                            sessionKey,
                            message: msg.Message,
                            timeoutSeconds: 120,
                        });
                        api.log.info(`[MQTT] Received response from agent: ${response}`);
                        // 发送响应到 agent/outgoing
                        sendResponse(msg.OriginalClientId || msg.UserId, msg.UserId, response || '抱歉，无法处理', msg.RequestId);
                    }
                    catch (err) {
                        api.log.error('[MQTT] Error processing message:', err);
                        sendResponse(msg.OriginalClientId || msg.UserId, msg.UserId, `错误: ${err.message}`, msg.RequestId);
                    }
                }
            }
            catch (error) {
                api.log.error('[MQTT] Error handling message:', error);
            }
        });
    }
    catch (error) {
        api.log.error('[MQTT] Failed to initialize MQTT client:', error);
        throw error;
    }
}
function sendResponse(clientId, userId, response, requestId) {
    if (!mqttClient) {
        api.log.warn('[MQTT] Cannot send: not connected');
        return;
    }
    const payload = JSON.stringify({
        OriginalClientId: clientId,
        UserId: userId,
        Response: response,
        Timestamp: new Date().toISOString(),
        RequestId: requestId,
    });
    mqttClient.publish('agent/outgoing', payload, { qos: 1 });
    api.log.info(`[MQTT] ✅ Published to agent/outgoing: ${payload}`);
}
export default async function main(api) {
    api.log.info('[MQTT] Initializing MQTT plugin...');
    // 从配置中获取MQTT设置
    config = api.config;
    if (!config?.brokerUrl || !config?.agentId) {
        throw new Error('Invalid MQTT configuration: brokerUrl and agentId are required');
    }
    api.log.info(`[MQTT] Config: ${JSON.stringify(config)}`);
    // 连接到MQTT Broker
    await connectToMqtt(api, config);
    // 注册清理函数
    api.registerCleanup(async () => {
        if (mqttClient) {
            mqttClient.end(true);
            api.log.info('[MQTT] Disconnected from MQTT broker');
        }
    });
}
//# sourceMappingURL=index.js.map