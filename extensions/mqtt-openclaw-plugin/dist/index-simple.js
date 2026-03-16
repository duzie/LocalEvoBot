import mqtt from 'mqtt';
export const CHANNEL_ID = 'mqtt';
export default function mqttPlugin(api) {
    let mqttClient = null;
    let config = null;
    let currentSessionKey = null;
    return {
        id: 'mqtt-openclaw-plugin',
        channels: [CHANNEL_ID],
        config: {
            async load() {
                const channelConfig = await api.config.getChannelConfig(CHANNEL_ID);
                config = {
                    brokerUrl: channelConfig.brokerUrl || 'mqtt://broker.emqx.io:1883',
                    agentId: channelConfig.agentId || 'openclaw-main',
                };
                return config;
            },
            async validate() {
                return [];
            },
        },
        messaging: {
            async start(_, handlers) {
                if (!config) {
                    throw new Error('MQTT not configured');
                }
                api.log.info(`[MQTT] Connecting to ${config.brokerUrl}`);
                mqttClient = mqtt.connect(config.brokerUrl, {
                    clientId: `openclaw-${Date.now()}`,
                    clean: true,
                    reconnectPeriod: 5000,
                });
                mqttClient.on('connect', () => {
                    api.log.info('[MQTT] Connected');
                    const processTopic = `agent/process/${config.agentId}`;
                    mqttClient.subscribe(processTopic, { qos: 1 }, (err) => {
                        if (err) {
                            api.log.error('[MQTT] Subscribe failed:', err);
                        }
                        else {
                            api.log.info(`[MQTT] Subscribed to ${processTopic}`);
                        }
                    });
                    // 注册 Agent
                    registerAgent(config.agentId);
                });
                mqttClient.on('message', async (topic, message) => {
                    const msg = JSON.parse(message.toString());
                    api.log.info(`[MQTT] Received: ${msg.UserId} - ${msg.Message}`);
                    // 创建会话
                    const sessionKey = `agent:main:mqtt:${msg.UserId}`;
                    currentSessionKey = sessionKey;
                    // 调用 AI 处理
                    try {
                        const result = await api.agent.run({
                            sessionKey,
                            message: {
                                role: 'user',
                                content: msg.Message || '',
                            },
                            meta: {
                                channel: CHANNEL_ID,
                                userId: msg.UserId,
                                requestId: msg.RequestId,
                            },
                        });
                        // 发送响应
                        if (result && typeof result === 'string') {
                            sendResponse(msg.OriginalClientId || msg.UserId || 'unknown', msg.UserId || 'unknown', result, msg.RequestId);
                        }
                    }
                    catch (err) {
                        api.log.error('[MQTT] AI processing failed:', err);
                        sendResponse(msg.OriginalClientId || msg.UserId || 'unknown', msg.UserId || 'unknown', '抱歉，处理失败', msg.RequestId);
                    }
                });
                mqttClient.on('error', (err) => {
                    api.log.error('[MQTT] Error:', err);
                });
                return {
                    stop: async () => {
                        mqttClient?.end();
                    },
                };
            },
        },
        outbound: {
            async sendMessage(_, target, message) {
                api.log.info(`[MQTT] Outbound to ${target.clientId}`);
                sendResponse(target.clientId || 'unknown', target.userId || 'unknown', message.content);
                return { messageId: 'ok' };
            },
        },
        async shutdown() {
            mqttClient?.end();
        },
    };
    function registerAgent(agentId) {
        if (!mqttClient)
            return;
        const registration = {
            AgentId: agentId,
            SupportedAppIds: [],
            RegistrationTime: new Date().toISOString(),
            Description: 'OpenClaw MQTT Agent',
        };
        mqttClient.publish('agent/register', JSON.stringify(registration), { qos: 1 });
        api.log.info(`[MQTT] Registered agent ${agentId}`);
    }
    function sendResponse(clientId, userId, response, requestId) {
        if (!mqttClient)
            return;
        const payload = JSON.stringify({
            OriginalClientId: clientId,
            UserId: userId,
            Response: response,
            Timestamp: new Date().toISOString(),
            RequestId: requestId,
        });
        mqttClient.publish('agent/outgoing', payload, { qos: 1 });
        api.log.info(`[MQTT] Sent response to ${clientId}`);
    }
}
//# sourceMappingURL=index-simple.js.map