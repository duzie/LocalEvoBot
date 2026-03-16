import mqtt from 'mqtt';
import crypto from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import { emptyPluginConfigSchema, DEFAULT_ACCOUNT_ID, readJsonFileWithFallback, writeJsonFileAtomically } from 'openclaw/plugin-sdk';

const CHANNEL_ID = 'mqtt';
let runtime = null;
const mqttClientsByAccountId = new Map();
let mqttUid = null;
let mqttUidPromise = null;
function setRuntime(r) {
    runtime = r;
}
function getRuntime() {
    if (!runtime) {
        throw new Error('MQTT runtime not initialized - plugin not registered');
    }
    return runtime;
}
async function getOrCreateMqttUid() {
    if (mqttUid)
        return mqttUid;
    if (mqttUidPromise)
        return mqttUidPromise;
    mqttUidPromise = (async () => {
        const configFilePath = path.join(os.homedir(), '.openclaw', 'openclaw.json');
        const { value } = await readJsonFileWithFallback(configFilePath, {});
        const cfg = value && typeof value === 'object' ? value : {};
        const channels = (cfg.channels ??= {});
        const mqttConfig = (channels[CHANNEL_ID] ??= {});
        const existing = mqttConfig.mqttUid;
        if (typeof existing === 'string' && existing.trim()) {
            mqttUid = existing.trim();
            return mqttUid;
        }
        const next = typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : crypto.randomBytes(16).toString('hex');
        mqttConfig.mqttUid = next;
        await writeJsonFileAtomically(configFilePath, cfg);
        mqttUid = next;
        return mqttUid;
    })()
        .catch((err) => {
        const r = runtime;
        r?.error?.(`[mqtt] Failed to persist mqttUid: ${String(err)}`);
        return null;
    })
        .finally(() => {
        mqttUidPromise = null;
    });
    return mqttUidPromise;
}
function resolveMqttAccount(cfg) {
    const mqttConfig = (cfg.channels?.[CHANNEL_ID] ?? {});
    return {
        accountId: DEFAULT_ACCOUNT_ID,
        name: mqttConfig.name ?? 'MQTT',
        enabled: mqttConfig.enabled ?? false,
        brokerUrl: mqttConfig.brokerUrl ?? '',
        agentId: mqttConfig.agentId ?? '',
        clientId: mqttConfig.clientId ?? '',
        username: mqttConfig.username ?? '',
        password: mqttConfig.password ?? '',
        config: mqttConfig,
    };
}
async function startMqttAccount(ctx) {
    const account = ctx.account;
    const cfg = ctx.cfg;
    const runtime = ctx.runtime;
    const abortSignal = ctx.abortSignal;
    const core = getRuntime();
    const mqttUidReady = getOrCreateMqttUid();
    return new Promise((resolve, reject) => {
        if (!account.brokerUrl?.trim() || !account.agentId?.trim()) {
            reject(new Error('channels.mqtt.brokerUrl and channels.mqtt.agentId are required'));
            return;
        }
        const client = mqtt.connect(account.brokerUrl, {
            clientId: account.clientId?.trim() || `openclaw-mqtt-${Date.now()}`,
            clean: true,
            reconnectPeriod: 5000,
            connectTimeout: 30000,
            username: account.username?.trim() || undefined,
            password: account.password?.trim() || undefined,
        });
        mqttClientsByAccountId.set(account.accountId, client);
        const safeEnd = () => {
            if (mqttClientsByAccountId.get(account.accountId) === client) {
                mqttClientsByAccountId.delete(account.accountId);
            }
            client.end(true, () => resolve());
        };
        if (abortSignal) {
            abortSignal.addEventListener('abort', () => safeEnd(), { once: true });
        }
        const processTopic = `agent/process/${account.agentId}`;
        client.on('connect', () => {
            runtime.log?.(`[mqtt] Connected to broker ${account.brokerUrl}`);
            client.subscribe(processTopic, { qos: 1 }, (err) => {
                if (err) {
                    runtime.error?.(`[mqtt] Failed to subscribe ${processTopic}: ${String(err)}`);
                    return;
                }
                runtime.log?.(`[mqtt] Subscribed ${processTopic}`);
            });
            void mqttUidReady.then((uid) => {
                const registration = {
                    AgentId: account.agentId,
                    MqttUid: uid ?? undefined,
                    SupportedAppIds: [],
                    RegistrationTime: new Date().toISOString(),
                    Description: 'OpenClaw MQTT Agent',
                };
                client.publish('agent/register', JSON.stringify(registration), { qos: 1 });
                if (uid) {
                    runtime.log?.(`[mqtt] mqttUid=${uid}`);
                }
            });
        });
        client.on('error', (err) => {
            runtime.error?.(`[mqtt] MQTT error: ${String(err)}`);
        });
        client.on('message', async (topic, message) => {
            if (topic !== processTopic)
                return;
            const raw = message.toString();
            let parsed;
            try {
                parsed = JSON.parse(raw);
            }
            catch (err) {
                runtime.error?.(`[mqtt] Invalid JSON on ${topic}: ${String(err)}`);
                return;
            }
            const userId = String(parsed?.UserId ?? '').trim();
            const text = String(parsed?.Message ?? '').trim();
            if (!userId || !text)
                return;
            const originalClientId = String(parsed?.OriginalClientId ?? parsed?.ClientId ?? userId).trim() || userId;
            const requestId = parsed?.RequestId ? String(parsed.RequestId) : undefined;
            const route = core.channel.routing.resolveAgentRoute({
                cfg,
                channel: CHANNEL_ID,
                accountId: account.accountId,
                peer: { kind: 'direct', id: userId },
            });
            const messageSid = requestId || `${Date.now()}`;
            const fromLabel = `user:${userId}`;
            const inboundCtx = core.channel.reply.finalizeInboundContext({
                Body: text,
                RawBody: text,
                CommandBody: text,
                MessageSid: messageSid,
                From: `${CHANNEL_ID}:${userId}`,
                To: `${CHANNEL_ID}:${account.agentId}`,
                SenderId: userId,
                SessionKey: route.sessionKey,
                AccountId: account.accountId,
                ChatType: 'direct',
                ConversationLabel: fromLabel,
                Timestamp: Date.now(),
                Provider: CHANNEL_ID,
                Surface: CHANNEL_ID,
                OriginatingChannel: CHANNEL_ID,
                OriginatingTo: `${CHANNEL_ID}:${account.agentId}`,
                CommandAuthorized: true,
                ReqId: requestId,
                MqttMessage: parsed,
            });
            let accumulatedText = '';
            try {
                await core.channel.reply.dispatchReplyWithBufferedBlockDispatcher({
                    ctx: inboundCtx,
                    cfg,
                    dispatcherOptions: {
                        deliver: async (payload) => {
                            accumulatedText += String(payload?.text ?? '');
                        },
                        onError: (err, info) => {
                            runtime.error?.(`[mqtt] ${String(info?.kind ?? 'reply')} failed: ${String(err)}`);
                        },
                    },
                });
            }
            catch (err) {
                runtime.error?.(`[mqtt] Failed to dispatch reply: ${String(err)}`);
            }
            const outgoing = {
                OriginalClientId: originalClientId,
                UserId: userId,
                Response: accumulatedText || '抱歉，处理失败',
                Timestamp: new Date().toISOString(),
                RequestId: requestId,
            };
            client.publish('agent/outgoing', JSON.stringify(outgoing), { qos: 1 });
        });
        client.on('close', () => {
            runtime.log?.('[mqtt] MQTT connection closed');
        });
    });
}
const mqttChannelPlugin = {
    id: CHANNEL_ID,
    meta: {
        label: 'MQTT',
        selectionLabel: 'MQTT Channel',
        detailLabel: 'MQTT 消息通道',
        docsPath: `/channels/${CHANNEL_ID}`,
        docsLabel: CHANNEL_ID,
        blurb: 'MQTT 消息通道插件',
        systemImage: 'message.fill',
    },
    capabilities: {
        chatTypes: ['direct'],
        reactions: false,
        threads: false,
        media: false,
        nativeCommands: false,
        blockStreaming: false,
    },
    reload: { configPrefixes: [`channels.${CHANNEL_ID}`] },
    config: {
        listAccountIds: () => [DEFAULT_ACCOUNT_ID],
        resolveAccount: (cfg) => resolveMqttAccount(cfg),
        defaultAccountId: () => DEFAULT_ACCOUNT_ID,
        setAccountEnabled: ({ cfg, enabled }) => {
            const mqttConfig = (cfg.channels?.[CHANNEL_ID] ?? {});
            return {
                ...cfg,
                channels: {
                    ...cfg.channels,
                    [CHANNEL_ID]: {
                        ...mqttConfig,
                        enabled,
                    },
                },
            };
        },
        deleteAccount: ({ cfg }) => {
            const mqttConfig = (cfg.channels?.[CHANNEL_ID] ?? {});
            const { brokerUrl, agentId, clientId, username, password, ...rest } = mqttConfig;
            return {
                ...cfg,
                channels: {
                    ...cfg.channels,
                    [CHANNEL_ID]: rest,
                },
            };
        },
        isConfigured: (account) => Boolean(account.brokerUrl?.trim() && account.agentId?.trim()),
        describeAccount: (account) => ({
            accountId: account.accountId,
            name: account.name,
            enabled: account.enabled,
            configured: Boolean(account.brokerUrl?.trim() && account.agentId?.trim()),
            brokerUrl: account.brokerUrl,
            agentId: account.agentId,
        }),
    },
    messaging: {
        normalizeTarget: (target) => {
            const trimmed = target.trim();
            if (!trimmed)
                return undefined;
            return trimmed;
        },
        targetResolver: {
            looksLikeId: (id) => Boolean(id?.trim()),
            hint: '<clientId|userId>',
        },
    },
    directory: {
        self: async () => null,
        listPeers: async () => [],
        listGroups: async () => [],
    },
    outbound: {
        deliveryMode: 'direct',
        sendText: async ({ to, text, accountId }) => {
            const client = mqttClientsByAccountId.get(String(accountId ?? DEFAULT_ACCOUNT_ID));
            if (!client) {
                throw new Error('MQTT client not connected');
            }
            const outgoing = {
                OriginalClientId: String(to),
                UserId: String(to),
                Response: String(text ?? ''),
                Timestamp: new Date().toISOString(),
            };
            client.publish('agent/outgoing', JSON.stringify(outgoing), { qos: 1 });
            return { ok: true };
        },
    },
    gateway: {
        startAccount: async (ctx) => startMqttAccount(ctx),
    },
};
const plugin = {
    id: 'mqtt-openclaw-plugin',
    name: 'MQTT',
    description: 'MQTT OpenClaw 插件',
    configSchema: emptyPluginConfigSchema(),
    register(api) {
        setRuntime(api.runtime);
        void getOrCreateMqttUid().then((uid) => {
            if (uid) {
                api.runtime?.log?.(`[mqtt] mqttUid=${uid}`);
            }
        });
        api.registerChannel({ plugin: mqttChannelPlugin });
    },
};

export { plugin as default };
//# sourceMappingURL=index.esm.js.map
