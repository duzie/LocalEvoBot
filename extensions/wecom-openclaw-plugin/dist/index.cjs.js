'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

var pluginSdk = require('openclaw/plugin-sdk');
var aibotNodeSdk = require('@wecom/aibot-node-sdk');
var fileType = require('file-type');
var os = require('node:os');
var path = require('node:path');

let runtime = null;
function setWeComRuntime(r) {
    runtime = r;
}
function getWeComRuntime() {
    if (!runtime) {
        throw new Error("WeCom runtime not initialized - plugin not registered");
    }
    return runtime;
}

/**
 * 企业微信渠道常量定义
 */
/**
 * 企业微信渠道 ID
 */
const CHANNEL_ID = "wecom";
/**
 * 企业微信 WebSocket 命令枚举
 */
var WeComCommand;
(function (WeComCommand) {
    /** 认证订阅 */
    WeComCommand["SUBSCRIBE"] = "aibot_subscribe";
    /** 心跳 */
    WeComCommand["PING"] = "ping";
    /** 企业微信推送消息 */
    WeComCommand["AIBOT_CALLBACK"] = "aibot_callback";
    /** clawdbot 响应消息 */
    WeComCommand["AIBOT_RESPONSE"] = "aibot_response";
})(WeComCommand || (WeComCommand = {}));
// ============================================================================
// 超时和重试配置
// ============================================================================
/** 图片下载超时时间（毫秒） */
const IMAGE_DOWNLOAD_TIMEOUT_MS = 30000;
/** 文件下载超时时间（毫秒） */
const FILE_DOWNLOAD_TIMEOUT_MS = 60000;
/** 消息发送超时时间（毫秒） */
const REPLY_SEND_TIMEOUT_MS = 15000;
/** 消息处理总超时时间（毫秒） */
const MESSAGE_PROCESS_TIMEOUT_MS = 5 * 60 * 1000;
/** WebSocket 心跳间隔（毫秒） */
const WS_HEARTBEAT_INTERVAL_MS = 30000;
/** WebSocket 最大重连次数 */
const WS_MAX_RECONNECT_ATTEMPTS = 100;
// ============================================================================
// 消息状态管理配置
// ============================================================================
/** messageStates Map 条目的最大 TTL（毫秒），防止内存泄漏 */
const MESSAGE_STATE_TTL_MS = 10 * 60 * 1000;
/** messageStates Map 清理间隔（毫秒） */
const MESSAGE_STATE_CLEANUP_INTERVAL_MS = 60000;
/** messageStates Map 最大条目数 */
const MESSAGE_STATE_MAX_SIZE = 500;
// ============================================================================
// 消息模板
// ============================================================================
/** "思考中"流式消息占位内容 */
const THINKING_MESSAGE = "<think></think>";
/** 仅包含图片时的消息占位符 */
const MEDIA_IMAGE_PLACEHOLDER = "<media:image>";
/** 仅包含文件时的消息占位符 */
const MEDIA_DOCUMENT_PLACEHOLDER = "<media:document>";
// ============================================================================
// 默认值
// ============================================================================
/** 默认媒体大小上限（MB） */
const DEFAULT_MEDIA_MAX_MB = 5;
/** 文本分块大小上限 */
const TEXT_CHUNK_LIMIT = 4000;

/**
 * 企业微信消息内容解析模块
 *
 * 负责从 WsFrame 中提取文本、图片、引用等内容
 */
// ============================================================================
// 解析函数
// ============================================================================
/**
 * 解析消息内容（支持单条消息、图文混排和引用消息）
 * @returns 提取的文本数组、图片URL数组和引用消息内容
 */
function parseMessageContent(body) {
    const textParts = [];
    const imageUrls = [];
    const imageAesKeys = new Map();
    const fileUrls = [];
    const fileAesKeys = new Map();
    let quoteContent;
    // 处理图文混排消息
    if (body.msgtype === "mixed" && body.mixed?.msg_item) {
        for (const item of body.mixed.msg_item) {
            if (item.msgtype === "text" && item.text?.content) {
                textParts.push(item.text.content);
            }
            else if (item.msgtype === "image" && item.image?.url) {
                imageUrls.push(item.image.url);
                if (item.image.aeskey) {
                    imageAesKeys.set(item.image.url, item.image.aeskey);
                }
            }
        }
    }
    else {
        // 处理单条消息
        if (body.text?.content) {
            textParts.push(body.text.content);
        }
        // 处理语音消息（语音转文字后的文本内容）
        if (body.msgtype === "voice" && body.voice?.content) {
            textParts.push(body.voice.content);
        }
        if (body.image?.url) {
            imageUrls.push(body.image.url);
            if (body.image.aeskey) {
                imageAesKeys.set(body.image.url, body.image.aeskey);
            }
        }
        // 处理文件消息
        if (body.msgtype === "file" && body.file?.url) {
            fileUrls.push(body.file.url);
            if (body.file.aeskey) {
                fileAesKeys.set(body.file.url, body.file.aeskey);
            }
        }
    }
    // 处理引用消息
    if (body.quote) {
        if (body.quote.msgtype === "text" && body.quote.text?.content) {
            quoteContent = body.quote.text.content;
        }
        else if (body.quote.msgtype === "voice" && body.quote.voice?.content) {
            quoteContent = body.quote.voice.content;
        }
        else if (body.quote.msgtype === "image" && body.quote.image?.url) {
            // 引用的图片消息：将图片 URL 加入下载列表
            imageUrls.push(body.quote.image.url);
            if (body.quote.image.aeskey) {
                imageAesKeys.set(body.quote.image.url, body.quote.image.aeskey);
            }
        }
        else if (body.quote.msgtype === "file" && body.quote.file?.url) {
            // 引用的文件消息：将文件 URL 加入下载列表
            fileUrls.push(body.quote.file.url);
            if (body.quote.file.aeskey) {
                fileAesKeys.set(body.quote.file.url, body.quote.file.aeskey);
            }
        }
    }
    return { textParts, imageUrls, imageAesKeys, fileUrls, fileAesKeys, quoteContent };
}

/**
 * 超时控制工具模块
 *
 * 为异步操作提供统一的超时保护机制
 */
/**
 * 为 Promise 添加超时保护
 *
 * @param promise - 原始 Promise
 * @param timeoutMs - 超时时间（毫秒）
 * @param message - 超时错误消息
 * @returns 带超时保护的 Promise
 */
function withTimeout(promise, timeoutMs, message) {
    if (timeoutMs <= 0 || !Number.isFinite(timeoutMs)) {
        return promise;
    }
    let timeoutId;
    const timeoutPromise = new Promise((_, reject) => {
        timeoutId = setTimeout(() => {
            reject(new TimeoutError(message ?? `Operation timed out after ${timeoutMs}ms`));
        }, timeoutMs);
    });
    return Promise.race([promise, timeoutPromise]).finally(() => {
        clearTimeout(timeoutId);
    });
}
/**
 * 超时错误类型
 */
class TimeoutError extends Error {
    constructor(message) {
        super(message);
        this.name = "TimeoutError";
    }
}

/**
 * 企业微信消息发送模块
 *
 * 负责通过 WSClient 发送回复消息，包含超时保护
 */
// ============================================================================
// 消息发送
// ============================================================================
/**
 * 发送企业微信回复消息
 * 供 monitor 内部和 channel outbound 使用
 *
 * @returns messageId (streamId)
 */
async function sendWeComReply(params) {
    const { wsClient, frame, text, runtime, finish = true, streamId: existingStreamId } = params;
    if (!text) {
        return "";
    }
    const streamId = existingStreamId || aibotNodeSdk.generateReqId("stream");
    if (!wsClient.isConnected) {
        runtime.error?.(`[WeCom] WSClient not connected, cannot send reply`);
        throw new Error("WSClient not connected");
    }
    // 使用 SDK 的 replyStream 方法发送消息，带超时保护
    await withTimeout(wsClient.replyStream(frame, streamId, text, finish), REPLY_SEND_TIMEOUT_MS, `Reply send timed out (streamId=${streamId})`);
    runtime.log?.(`[WeCom] Sent reply: streamId=${streamId}, finish=${finish}`);
    return streamId;
}

/**
 * 企业微信媒体（图片）下载和保存模块
 *
 * 负责下载、检测格式、保存图片到本地，包含超时保护
 */
// ============================================================================
// 图片格式检测辅助函数（基于 file-type 包）
// ============================================================================
/**
 * 检查 Buffer 是否为有效的图片格式
 */
async function isImageBuffer(data) {
    const type = await fileType.fileTypeFromBuffer(data);
    return type?.mime.startsWith("image/") ?? false;
}
/**
 * 检测 Buffer 的图片内容类型
 */
async function detectImageContentType(data) {
    const type = await fileType.fileTypeFromBuffer(data);
    if (type?.mime.startsWith("image/")) {
        return type.mime;
    }
    return "application/octet-stream";
}
// ============================================================================
// 图片下载和保存
// ============================================================================
/**
 * 下载并保存所有图片到本地，每张图片的下载带超时保护
 */
async function downloadAndSaveImages(params) {
    const { imageUrls, config, runtime, wsClient } = params;
    const core = getWeComRuntime();
    const mediaList = [];
    for (const imageUrl of imageUrls) {
        try {
            runtime.log?.(`[WeCom] Downloading image from: ${imageUrl}`);
            const mediaMaxMb = config.agents?.defaults?.mediaMaxMb ?? DEFAULT_MEDIA_MAX_MB;
            const maxBytes = mediaMaxMb * 1024 * 1024;
            let imageBuffer;
            let imageContentType;
            let originalFilename;
            const imageAesKey = params.imageAesKeys?.get(imageUrl);
            try {
                // 优先使用 SDK 的 downloadFile 方法下载（带超时保护）
                const result = await withTimeout(wsClient.downloadFile(imageUrl, imageAesKey), IMAGE_DOWNLOAD_TIMEOUT_MS, `Image download timed out: ${imageUrl}`);
                imageBuffer = result.buffer;
                originalFilename = result.filename;
                imageContentType = await detectImageContentType(imageBuffer);
                runtime.log?.(`[WeCom] Image downloaded via SDK: size=${imageBuffer.length}, contentType=${imageContentType}${originalFilename ? `, filename=${originalFilename}` : ""}`);
            }
            catch (sdkError) {
                // 如果 SDK 方法失败，回退到原有方式（带超时保护）
                runtime.log?.(`[WeCom] SDK download failed, falling back to manual download: ${String(sdkError)}`);
                const fetched = await withTimeout(core.channel.media.fetchRemoteMedia({ url: imageUrl }), IMAGE_DOWNLOAD_TIMEOUT_MS, `Manual image download timed out: ${imageUrl}`);
                runtime.log?.(`[WeCom] Image fetched: contentType=${fetched.contentType}, size=${fetched.buffer.length}, first4Bytes=${fetched.buffer.slice(0, 4).toString("hex")}`);
                imageBuffer = fetched.buffer;
                imageContentType = fetched.contentType ?? "application/octet-stream";
                const isValidImage = await isImageBuffer(fetched.buffer);
                if (!isValidImage) {
                    runtime.log?.(`[WeCom] WARN: Image does not appear to be a valid image format`);
                }
            }
            const saved = await core.channel.media.saveMediaBuffer(imageBuffer, imageContentType, "inbound", maxBytes, originalFilename);
            mediaList.push({ path: saved.path, contentType: saved.contentType });
            runtime.log?.(`[WeCom] Image saved to ${saved.path}, finalContentType=${saved.contentType}`);
        }
        catch (err) {
            runtime.error?.(`[WeCom] Failed to download image: ${String(err)}`);
        }
    }
    return mediaList;
}
/**
 * 下载并保存所有文件到本地，每个文件的下载带超时保护
 */
async function downloadAndSaveFiles(params) {
    const { fileUrls, config, runtime, wsClient } = params;
    const core = getWeComRuntime();
    const mediaList = [];
    for (const fileUrl of fileUrls) {
        try {
            runtime.log?.(`[WeCom] Downloading file from: ${fileUrl}`);
            const mediaMaxMb = config.agents?.defaults?.mediaMaxMb ?? DEFAULT_MEDIA_MAX_MB;
            const maxBytes = mediaMaxMb * 1024 * 1024;
            let fileBuffer;
            let fileContentType;
            let originalFilename;
            const fileAesKey = params.fileAesKeys?.get(fileUrl);
            try {
                // 使用 SDK 的 downloadFile 方法下载（带超时保护）
                const result = await withTimeout(wsClient.downloadFile(fileUrl, fileAesKey), FILE_DOWNLOAD_TIMEOUT_MS, `File download timed out: ${fileUrl}`);
                fileBuffer = result.buffer;
                originalFilename = result.filename;
                // 检测文件类型
                const type = await fileType.fileTypeFromBuffer(fileBuffer);
                fileContentType = type?.mime ?? "application/octet-stream";
                runtime.log?.(`[WeCom] File downloaded via SDK: size=${fileBuffer.length}, contentType=${fileContentType}${originalFilename ? `, filename=${originalFilename}` : ""}`);
            }
            catch (sdkError) {
                // 如果 SDK 方法失败，回退到 fetchRemoteMedia（带超时保护）
                runtime.log?.(`[WeCom] SDK file download failed, falling back to manual download: ${String(sdkError)}`);
                const fetched = await withTimeout(core.channel.media.fetchRemoteMedia({ url: fileUrl }), FILE_DOWNLOAD_TIMEOUT_MS, `Manual file download timed out: ${fileUrl}`);
                runtime.log?.(`[WeCom] File fetched: contentType=${fetched.contentType}, size=${fetched.buffer.length}`);
                fileBuffer = fetched.buffer;
                fileContentType = fetched.contentType ?? "application/octet-stream";
            }
            const saved = await core.channel.media.saveMediaBuffer(fileBuffer, fileContentType, "inbound", maxBytes, originalFilename);
            mediaList.push({ path: saved.path, contentType: saved.contentType });
            runtime.log?.(`[WeCom] File saved to ${saved.path}, finalContentType=${saved.contentType}`);
        }
        catch (err) {
            runtime.error?.(`[WeCom] Failed to download file: ${String(err)}`);
        }
    }
    return mediaList;
}

/**
 * 企业微信群组访问控制模块
 *
 * 负责群组策略检查（groupPolicy、群组白名单、群内发送者白名单）
 */
// ============================================================================
// 内部辅助函数
// ============================================================================
/**
 * 解析企业微信群组配置
 */
function resolveWeComGroupConfig(params) {
    const groups = params.cfg?.groups ?? {};
    const wildcard = groups["*"];
    const groupId = params.groupId?.trim();
    if (!groupId) {
        return undefined;
    }
    const direct = groups[groupId];
    if (direct) {
        return direct;
    }
    const lowered = groupId.toLowerCase();
    const matchKey = Object.keys(groups).find((key) => key.toLowerCase() === lowered);
    if (matchKey) {
        return groups[matchKey];
    }
    return wildcard;
}
/**
 * 检查群组是否在允许列表中
 */
function isWeComGroupAllowed(params) {
    const { groupPolicy } = params;
    if (groupPolicy === "disabled") {
        return false;
    }
    if (groupPolicy === "open") {
        return true;
    }
    // allowlist 模式：检查群组是否在允许列表中
    const normalizedAllowFrom = params.allowFrom.map((entry) => String(entry).replace(new RegExp(`^${CHANNEL_ID}:`, "i"), "").trim());
    if (normalizedAllowFrom.includes("*")) {
        return true;
    }
    const normalizedGroupId = params.groupId.trim();
    return normalizedAllowFrom.some((entry) => entry === normalizedGroupId || entry.toLowerCase() === normalizedGroupId.toLowerCase());
}
/**
 * 检查群组内发送者是否在允许列表中
 */
function isGroupSenderAllowed(params) {
    const { senderId, groupId, wecomConfig } = params;
    const groupConfig = resolveWeComGroupConfig({
        cfg: wecomConfig,
        groupId,
    });
    const perGroupSenderAllowFrom = (groupConfig?.allowFrom ?? []).map((v) => String(v));
    if (perGroupSenderAllowFrom.length === 0) {
        return true;
    }
    if (perGroupSenderAllowFrom.includes("*")) {
        return true;
    }
    return perGroupSenderAllowFrom.some((entry) => {
        const normalized = entry.replace(new RegExp(`^${CHANNEL_ID}:`, "i"), "").trim();
        return normalized === senderId || normalized === `user:${senderId}`;
    });
}
// ============================================================================
// 公开 API
// ============================================================================
/**
 * 检查群组策略访问控制
 * @returns 检查结果，包含是否允许继续处理
 */
function checkGroupPolicy(params) {
    const { chatId, senderId, account, config, runtime } = params;
    const wecomConfig = (config.channels?.[CHANNEL_ID] ?? {});
    const defaultGroupPolicy = config.channels?.[CHANNEL_ID]?.groupPolicy;
    const groupPolicy = account.config.groupPolicy ?? defaultGroupPolicy ?? "open";
    // const { groupPolicy, providerMissingFallbackApplied } = resolveOpenProviderRuntimeGroupPolicy({
    //   providerConfigPresent: config.channels?.[CHANNEL_ID] !== undefined,
    //   groupPolicy: wecomConfig.groupPolicy,
    //   defaultGroupPolicy,
    // });
    // warnMissingProviderGroupPolicyFallbackOnce({
    //   providerMissingFallbackApplied,
    //   providerKey: CHANNEL_ID,
    //   accountId: account.accountId,
    //   log: (msg) => runtime.log?.(msg),
    // });
    const groupAllowFrom = wecomConfig.groupAllowFrom ?? [];
    const groupAllowed = isWeComGroupAllowed({
        groupPolicy,
        allowFrom: groupAllowFrom,
        groupId: chatId,
    });
    if (!groupAllowed) {
        runtime.log?.(`[WeCom] Group ${chatId} not allowed (groupPolicy=${groupPolicy})`);
        return { allowed: false };
    }
    const senderAllowed = isGroupSenderAllowed({
        senderId,
        groupId: chatId,
        wecomConfig,
    });
    if (!senderAllowed) {
        runtime.log?.(`[WeCom] Sender ${senderId} not in group ${chatId} sender allowlist`);
        return { allowed: false };
    }
    return { allowed: true };
}
/**
 * 检查发送者是否在允许列表中（通用）
 */
function isSenderAllowed(senderId, allowFrom) {
    if (allowFrom.includes("*")) {
        return true;
    }
    return allowFrom.some((entry) => {
        const normalized = entry.replace(new RegExp(`^${CHANNEL_ID}:`, "i"), "").trim();
        return normalized === senderId || normalized === `user:${senderId}`;
    });
}

/**
 * 企业微信 DM（私聊）访问控制模块
 *
 * 负责私聊策略检查、配对流程
 */
// ============================================================================
// 公开 API
// ============================================================================
/**
 * 检查 DM Policy 访问控制
 * @returns 检查结果，包含是否允许继续处理
 */
async function checkDmPolicy(params) {
    const { senderId, isGroup, account, wsClient, frame, runtime } = params;
    const core = getWeComRuntime();
    // 群聊消息不检查 DM Policy
    if (isGroup) {
        return { allowed: true };
    }
    const dmPolicy = account.config.dmPolicy ?? "pairing";
    const configAllowFrom = (account.config.allowFrom ?? []).map((v) => String(v));
    // 如果 dmPolicy 是 disabled，直接拒绝
    if (dmPolicy === "disabled") {
        runtime.log?.(`[WeCom] Blocked DM from ${senderId} (dmPolicy=disabled)`);
        return { allowed: false };
    }
    // 如果是 open 模式，允许所有人
    if (dmPolicy === "open") {
        return { allowed: true };
    }
    // OpenClaw <= 2026.2.19 signature: readAllowFromStore(channel, env?, accountId?)
    const oldStoreAllowFrom = await core.channel.pairing.readAllowFromStore('wecom', undefined, account.accountId).catch(() => []);
    // Compatibility fallback for newer OpenClaw implementations.
    const newStoreAllowFrom = await core.channel.pairing
        .readAllowFromStore({ channel: CHANNEL_ID, accountId: account.accountId })
        .catch(() => []);
    // 检查发送者是否在允许列表中
    const storeAllowFrom = [...oldStoreAllowFrom, ...newStoreAllowFrom];
    const effectiveAllowFrom = [...configAllowFrom, ...storeAllowFrom];
    const senderAllowedResult = isSenderAllowed(senderId, effectiveAllowFrom);
    if (senderAllowedResult) {
        return { allowed: true };
    }
    // 处理未授权用户
    if (dmPolicy === "pairing") {
        const { code, created } = await core.channel.pairing.upsertPairingRequest({
            channel: CHANNEL_ID,
            id: senderId,
            accountId: account.accountId,
            meta: { name: senderId },
        });
        if (created) {
            runtime.log?.(`[WeCom] Pairing request created for sender=${senderId}`);
            try {
                await sendWeComReply({
                    wsClient,
                    frame,
                    text: core.channel.pairing.buildPairingReply({
                        channel: CHANNEL_ID,
                        idLine: `您的企业微信用户ID: ${senderId}`,
                        code,
                    }),
                    runtime,
                    finish: true,
                });
            }
            catch (err) {
                runtime.error?.(`[WeCom] Failed to send pairing reply to ${senderId}: ${String(err)}`);
            }
        }
        else {
            runtime.log?.(`[WeCom] Pairing request already exists for sender=${senderId}`);
        }
        return { allowed: false, pairingSent: created };
    }
    // allowlist 模式：直接拒绝未授权用户
    runtime.log?.(`[WeCom] Blocked unauthorized sender ${senderId} (dmPolicy=${dmPolicy})`);
    return { allowed: false };
}

// ============================================================================
// 常量
// ============================================================================
const DEFAULT_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 天
const DEFAULT_MEMORY_MAX_SIZE = 200;
const DEFAULT_FILE_MAX_ENTRIES = 500;
const DEFAULT_FLUSH_DEBOUNCE_MS = 1000;
const DEFAULT_LOCK_OPTIONS = {
    stale: 60000,
    retries: {
        retries: 6,
        factor: 1.35,
        minTimeout: 8,
        maxTimeout: 180,
        randomize: true,
    },
};
// ============================================================================
// 状态目录解析
// ============================================================================
function resolveStateDirFromEnv(env = process.env) {
    const stateOverride = env.OPENCLAW_STATE_DIR?.trim() || env.CLAWDBOT_STATE_DIR?.trim();
    if (stateOverride) {
        return stateOverride;
    }
    if (env.VITEST || env.NODE_ENV === "test") {
        return path.join(os.tmpdir(), ["openclaw-vitest", String(process.pid)].join("-"));
    }
    return path.join(os.homedir(), ".openclaw");
}
function resolveReqIdFilePath(accountId) {
    const safe = accountId.replace(/[^a-zA-Z0-9_-]/g, "_");
    return path.join(resolveStateDirFromEnv(), "wecom", `reqid-map-${safe}.json`);
}
// ============================================================================
// 核心实现
// ============================================================================
function createPersistentReqIdStore(accountId, options) {
    const ttlMs = DEFAULT_TTL_MS;
    const memoryMaxSize = DEFAULT_MEMORY_MAX_SIZE;
    const fileMaxEntries = DEFAULT_FILE_MAX_ENTRIES;
    const flushDebounceMs = DEFAULT_FLUSH_DEBOUNCE_MS;
    const filePath = resolveReqIdFilePath(accountId);
    // 内存层：chatId → ReqIdEntry
    const memory = new Map();
    // 防抖写入相关
    let dirty = false;
    let flushTimer = null;
    // ========== 内部辅助函数 ==========
    /** 检查条目是否过期 */
    function isExpired(entry, now) {
        return now - entry.ts >= ttlMs;
    }
    /** 验证磁盘条目的合法性 */
    function isValidEntry(entry) {
        return (typeof entry === "object" &&
            entry !== null &&
            typeof entry.reqId === "string" &&
            typeof entry.ts === "number" &&
            Number.isFinite(entry.ts));
    }
    /** 清理磁盘数据中的无效值，返回干净的 Record */
    function sanitizeData(value) {
        if (!value || typeof value !== "object") {
            return {};
        }
        const out = {};
        for (const [key, entry] of Object.entries(value)) {
            if (isValidEntry(entry)) {
                out[key] = entry;
            }
        }
        return out;
    }
    /**
     * 内存容量控制：淘汰最旧的条目。
     * 利用 Map 的插入顺序 + touch(先 delete 再 set) 实现类 LRU 效果。
     */
    function pruneMemory() {
        if (memory.size <= memoryMaxSize)
            return;
        const sorted = [...memory.entries()].sort((a, b) => a[1].ts - b[1].ts);
        const toRemove = sorted.slice(0, memory.size - memoryMaxSize);
        for (const [key] of toRemove) {
            memory.delete(key);
        }
    }
    /** 磁盘数据容量控制：先清过期，再按时间淘汰超量 */
    function pruneFileData(data, now) {
        {
            for (const [key, entry] of Object.entries(data)) {
                if (now - entry.ts >= ttlMs) {
                    delete data[key];
                }
            }
        }
        const keys = Object.keys(data);
        if (keys.length <= fileMaxEntries)
            return;
        keys
            .sort((a, b) => data[a].ts - data[b].ts)
            .slice(0, keys.length - fileMaxEntries)
            .forEach((key) => delete data[key]);
    }
    /** 防抖写入磁盘 */
    function scheduleDiskFlush() {
        dirty = true;
        if (flushTimer)
            return;
        flushTimer = setTimeout(async () => {
            flushTimer = null;
            if (!dirty)
                return;
            await flushToDisk();
        }, flushDebounceMs);
    }
    /** 立即写入磁盘（带文件锁，参考 createPersistentDedupe 的 checkAndRecordInner） */
    async function flushToDisk() {
        dirty = false;
        const now = Date.now();
        try {
            await pluginSdk.withFileLock(filePath, DEFAULT_LOCK_OPTIONS, async () => {
                // 读取现有磁盘数据并合并
                const { value } = await pluginSdk.readJsonFileWithFallback(filePath, {});
                const data = sanitizeData(value);
                // 将内存中未过期的数据合并到磁盘数据（内存优先）
                for (const [chatId, entry] of memory) {
                    if (!isExpired(entry, now)) {
                        data[chatId] = entry;
                    }
                }
                // 清理过期和超量
                pruneFileData(data, now);
                // 原子写入
                await pluginSdk.writeJsonFileAtomically(filePath, data);
            });
        }
        catch (error) {
            // 磁盘写入失败不影响内存使用，降级到纯内存模式
            // console.error(`[WeCom] reqid-store: flush to disk failed: ${String(error)}`);
        }
    }
    // ========== 公开 API ==========
    function set(chatId, reqId) {
        const entry = { reqId, ts: Date.now() };
        // touch：先删再设，保持 Map 插入顺序（类 LRU）
        memory.delete(chatId);
        memory.set(chatId, entry);
        pruneMemory();
        scheduleDiskFlush();
    }
    async function get(chatId) {
        const now = Date.now();
        // 1. 先查内存
        const memEntry = memory.get(chatId);
        if (memEntry && !isExpired(memEntry, now)) {
            return memEntry.reqId;
        }
        if (memEntry) {
            memory.delete(chatId); // 过期则删除
        }
        // 2. 内存 miss，回查磁盘并回填内存
        try {
            const { value } = await pluginSdk.readJsonFileWithFallback(filePath, {});
            const data = sanitizeData(value);
            const diskEntry = data[chatId];
            if (diskEntry && !isExpired(diskEntry, now)) {
                // 回填内存
                memory.set(chatId, diskEntry);
                return diskEntry.reqId;
            }
        }
        catch {
            // 磁盘读取失败，降级返回 undefined
        }
        return undefined;
    }
    function getSync(chatId) {
        const now = Date.now();
        const entry = memory.get(chatId);
        if (entry && !isExpired(entry, now)) {
            return entry.reqId;
        }
        if (entry) {
            memory.delete(chatId);
        }
        return undefined;
    }
    function del(chatId) {
        memory.delete(chatId);
        scheduleDiskFlush();
    }
    async function warmup(onError) {
        const now = Date.now();
        try {
            const { value } = await pluginSdk.readJsonFileWithFallback(filePath, {});
            const data = sanitizeData(value);
            let loaded = 0;
            for (const [chatId, entry] of Object.entries(data)) {
                if (!isExpired(entry, now)) {
                    memory.set(chatId, entry);
                    loaded++;
                }
            }
            pruneMemory();
            return loaded;
        }
        catch (error) {
            onError?.(error);
            return 0;
        }
    }
    async function flush() {
        if (flushTimer) {
            clearTimeout(flushTimer);
            flushTimer = null;
        }
        await flushToDisk();
    }
    function clearMemory() {
        memory.clear();
    }
    function memorySize() {
        return memory.size;
    }
    return {
        set,
        get,
        getSync,
        delete: del,
        warmup,
        flush,
        clearMemory,
        memorySize,
    };
}

/**
 * 企业微信全局状态管理模块
 *
 * 负责管理 WSClient 实例、消息状态（带 TTL 清理）、ReqId 存储
 * 解决全局 Map 的内存泄漏问题
 */
// ============================================================================
// WSClient 实例管理
// ============================================================================
/** WSClient 实例管理 */
const wsClientInstances = new Map();
/**
 * 获取指定账户的 WSClient 实例
 */
function getWeComWebSocket(accountId) {
    return wsClientInstances.get(accountId) ?? null;
}
/**
 * 设置指定账户的 WSClient 实例
 */
function setWeComWebSocket(accountId, client) {
    wsClientInstances.set(accountId, client);
}
/** 消息状态管理 */
const messageStates = new Map();
/** 定期清理定时器 */
let cleanupTimer = null;
/**
 * 启动消息状态定期清理（自动 TTL 清理 + 容量限制）
 */
function startMessageStateCleanup() {
    if (cleanupTimer)
        return;
    cleanupTimer = setInterval(() => {
        pruneMessageStates();
    }, MESSAGE_STATE_CLEANUP_INTERVAL_MS);
    // 允许进程退出时不阻塞
    if (cleanupTimer && typeof cleanupTimer === "object" && "unref" in cleanupTimer) {
        cleanupTimer.unref();
    }
}
/**
 * 停止消息状态定期清理
 */
function stopMessageStateCleanup() {
    if (cleanupTimer) {
        clearInterval(cleanupTimer);
        cleanupTimer = null;
    }
}
/**
 * 清理过期和超量的消息状态条目
 */
function pruneMessageStates() {
    const now = Date.now();
    // 1. 清理过期条目
    for (const [key, entry] of messageStates) {
        if (now - entry.createdAt >= MESSAGE_STATE_TTL_MS) {
            messageStates.delete(key);
        }
    }
    // 2. 容量限制：如果仍超过最大条目数，按时间淘汰最旧的
    if (messageStates.size > MESSAGE_STATE_MAX_SIZE) {
        const sorted = [...messageStates.entries()].sort((a, b) => a[1].createdAt - b[1].createdAt);
        const toRemove = sorted.slice(0, messageStates.size - MESSAGE_STATE_MAX_SIZE);
        for (const [key] of toRemove) {
            messageStates.delete(key);
        }
    }
}
/**
 * 设置消息状态
 */
function setMessageState(messageId, state) {
    messageStates.set(messageId, {
        state,
        createdAt: Date.now(),
    });
}
/**
 * 删除消息状态
 */
function deleteMessageState(messageId) {
    messageStates.delete(messageId);
}
// ============================================================================
// ReqId 持久化存储管理（按 accountId 隔离）
// ============================================================================
/**
 * ReqId 持久化存储管理
 * 参考 createPersistentDedupe 模式：内存 + 磁盘双层、文件锁、原子写入、TTL 过期、防抖写入
 * 重启后可从磁盘恢复，确保主动推送消息时能获取到 reqId
 */
const reqIdStores = new Map();
function getOrCreateReqIdStore(accountId) {
    let store = reqIdStores.get(accountId);
    if (!store) {
        store = createPersistentReqIdStore(accountId);
        reqIdStores.set(accountId, store);
    }
    return store;
}
// ============================================================================
// ReqId 操作函数
// ============================================================================
/**
 * 设置 chatId 对应的 reqId（写入内存 + 防抖写磁盘）
 */
function setReqIdForChat(chatId, reqId, accountId = "default") {
    getOrCreateReqIdStore(accountId).set(chatId, reqId);
}
/**
 * 启动时预热 reqId 缓存（从磁盘加载到内存）
 */
async function warmupReqIdStore(accountId = "default", log) {
    const store = getOrCreateReqIdStore(accountId);
    return store.warmup((error) => {
        log?.(`[WeCom] reqid-store warmup error: ${String(error)}`);
    });
}
// ============================================================================
// 全局 cleanup（断开连接时释放所有资源）
// ============================================================================
/**
 * 清理指定账户的所有资源
 */
async function cleanupAccount(accountId) {
    // 1. 断开 WSClient
    const wsClient = wsClientInstances.get(accountId);
    if (wsClient) {
        try {
            wsClient.disconnect();
        }
        catch {
            // 忽略断开连接时的错误
        }
        wsClientInstances.delete(accountId);
    }
    // 2. flush reqId 存储到磁盘
    const store = reqIdStores.get(accountId);
    if (store) {
        try {
            await store.flush();
        }
        catch {
            // 忽略 flush 错误
        }
        // 注意：不删除 store，因为重连后可能还需要
    }
}

/**
 * 企业微信 WebSocket 监控器主模块
 *
 * 负责：
 * - 建立和管理 WebSocket 连接
 * - 协调消息处理流程（解析→策略检查→下载图片→路由回复）
 * - 资源生命周期管理
 *
 * 子模块：
 * - message-parser.ts  : 消息内容解析
 * - message-sender.ts  : 消息发送（带超时保护）
 * - media-handler.ts   : 图片下载和保存（带超时保护）
 * - group-policy.ts    : 群组访问控制
 * - dm-policy.ts       : 私聊访问控制
 * - state-manager.ts   : 全局状态管理（带 TTL 清理）
 * - timeout.ts         : 超时工具
 */
// ============================================================================
// 消息上下文构建
// ============================================================================
/**
 * 构建消息上下文
 */
function buildMessageContext(frame, account, config, text, mediaList, quoteContent) {
    const core = getWeComRuntime();
    const body = frame.body;
    const chatId = body.chatid || body.from.userid;
    const chatType = body.chattype === "group" ? "group" : "direct";
    // 解析路由信息
    const route = core.channel.routing.resolveAgentRoute({
        cfg: config,
        channel: CHANNEL_ID,
        accountId: account.accountId,
        peer: {
            kind: chatType,
            id: chatId,
        },
    });
    // 构建会话标签
    const fromLabel = chatType === "group" ? `group:${chatId}` : `user:${body.from.userid}`;
    // 当只有媒体没有文本时，使用占位符标识媒体类型
    const hasImages = mediaList.some((m) => m.contentType?.startsWith("image/"));
    const messageBody = text || (mediaList.length > 0 ? (hasImages ? MEDIA_IMAGE_PLACEHOLDER : MEDIA_DOCUMENT_PLACEHOLDER) : "");
    // 构建多媒体数组
    const mediaPaths = mediaList.length > 0 ? mediaList.map((m) => m.path) : undefined;
    const mediaTypes = mediaList.length > 0
        ? mediaList.map((m) => m.contentType).filter(Boolean)
        : undefined;
    // 构建标准消息上下文
    return core.channel.reply.finalizeInboundContext({
        Body: messageBody,
        RawBody: messageBody,
        CommandBody: messageBody,
        MessageSid: body.msgid,
        From: chatType === "group" ? `${CHANNEL_ID}:group:${chatId}` : `${CHANNEL_ID}:${body.from.userid}`,
        To: `${CHANNEL_ID}:${chatId}`,
        SenderId: body.from.userid,
        SessionKey: route.sessionKey,
        AccountId: account.accountId,
        ChatType: chatType,
        ConversationLabel: fromLabel,
        Timestamp: Date.now(),
        Provider: CHANNEL_ID,
        Surface: CHANNEL_ID,
        OriginatingChannel: CHANNEL_ID,
        OriginatingTo: `${CHANNEL_ID}:${chatId}`,
        CommandAuthorized: true,
        ResponseUrl: body.response_url,
        ReqId: frame.headers.req_id,
        WeComFrame: frame,
        MediaPath: mediaList[0]?.path,
        MediaType: mediaList[0]?.contentType,
        MediaPaths: mediaPaths,
        MediaTypes: mediaTypes,
        MediaUrls: mediaPaths,
        ReplyToBody: quoteContent,
    });
}
// ============================================================================
// 消息处理和回复
// ============================================================================
/**
 * 发送"思考中"消息
 */
async function sendThinkingReply(params) {
    const { wsClient, frame, streamId, runtime } = params;
    runtime.log?.(`[WeCom] Sending thinking message`);
    try {
        await sendWeComReply({
            wsClient,
            frame,
            text: THINKING_MESSAGE,
            runtime,
            finish: false,
            streamId,
        });
    }
    catch (err) {
        runtime.error?.(`[WeCom] Failed to send thinking message: ${String(err)}`);
    }
}
/**
 * 路由消息到核心处理流程并处理回复
 */
async function routeAndDispatchMessage(params) {
    const { ctxPayload, config, wsClient, frame, state, runtime, onCleanup } = params;
    const core = getWeComRuntime();
    // 防止 onCleanup 被多次调用（onError 回调与 catch 块可能重复触发）
    let cleanedUp = false;
    const safeCleanup = () => {
        if (!cleanedUp) {
            cleanedUp = true;
            onCleanup();
        }
    };
    try {
        await core.channel.reply.dispatchReplyWithBufferedBlockDispatcher({
            ctx: ctxPayload,
            cfg: config,
            dispatcherOptions: {
                deliver: async (payload, info) => {
                    state.accumulatedText += payload.text;
                    if (info.kind !== "final") {
                        await sendWeComReply({
                            wsClient,
                            frame,
                            text: state.accumulatedText,
                            runtime,
                            finish: false,
                            streamId: state.streamId,
                        });
                    }
                },
                onError: (err, info) => {
                    runtime.error?.(`[WeCom] ${info.kind} reply failed: ${String(err)}`);
                    // 仅记录错误，不立即 cleanup，让外层 try/catch 统一处理最终回复和 cleanup
                },
            },
        });
        // 发送最终消息
        await sendWeComReply({
            wsClient,
            frame,
            text: state.accumulatedText,
            runtime,
            finish: true,
            streamId: state.streamId,
        });
        safeCleanup();
    }
    catch (err) {
        runtime.error?.(`[WeCom] Failed to process message: ${String(err)}`);
        safeCleanup();
    }
}
/**
 * 处理企业微信消息（主函数）
 *
 * 处理流程：
 * 1. 解析消息内容（文本、图片、引用）
 * 2. 群组策略检查（仅群聊）
 * 3. DM Policy 访问控制检查（仅私聊）
 * 4. 下载并保存图片
 * 5. 初始化消息状态
 * 6. 发送"思考中"消息
 * 7. 路由消息到核心处理流程
 *
 * 整体带超时保护，防止单条消息处理阻塞过久
 */
async function processWeComMessage(params) {
    const { frame, account, config, runtime, wsClient } = params;
    const body = frame.body;
    const chatId = body.chatid || body.from.userid;
    const chatType = body.chattype === "group" ? "group" : "direct";
    const messageId = body.msgid;
    const reqId = frame.headers.req_id;
    // Step 1: 解析消息内容
    const { textParts, imageUrls, imageAesKeys, fileUrls, fileAesKeys, quoteContent } = parseMessageContent(body);
    let text = textParts.join("\n").trim();
    // 群聊中移除 @机器人 的提及标记
    if (body.chattype === "group") {
        text = text.replace(/@\S+/g, "").trim();
    }
    // 如果文本为空但存在引用消息，使用引用消息内容
    if (!text && quoteContent) {
        text = quoteContent;
        runtime.log?.("[WeCom] Using quote content as message body (user only mentioned bot)");
    }
    // 如果既没有文本也没有图片也没有文件也没有引用内容，则跳过
    if (!text && imageUrls.length === 0 && fileUrls.length === 0) {
        runtime.log?.("[WeCom] Skipping empty message (no text, image, file or quote)");
        return;
    }
    runtime.log?.(`[WeCom] Processing ${chatType} message from chat: ${chatId} user: ${body.from.userid} reqId: ${reqId}${imageUrls.length > 0 ? ` (with ${imageUrls.length} image(s))` : ""}${fileUrls.length > 0 ? ` (with ${fileUrls.length} file(s))` : ""}${quoteContent ? ` (with quote)` : ""}`);
    // Step 2: 群组策略检查（仅群聊）
    if (chatType === "group") {
        const groupPolicyResult = checkGroupPolicy({
            chatId,
            senderId: body.from.userid,
            account,
            config,
            runtime,
        });
        if (!groupPolicyResult.allowed) {
            return;
        }
    }
    // Step 3: DM Policy 访问控制检查（仅私聊）
    const dmPolicyResult = await checkDmPolicy({
        senderId: body.from.userid,
        isGroup: chatType === "group",
        account,
        wsClient,
        frame,
        runtime,
    });
    if (!dmPolicyResult.allowed) {
        return;
    }
    // Step 4: 下载并保存图片和文件
    const [imageMediaList, fileMediaList] = await Promise.all([
        downloadAndSaveImages({
            imageUrls,
            imageAesKeys,
            account,
            config,
            runtime,
            wsClient,
        }),
        downloadAndSaveFiles({
            fileUrls,
            fileAesKeys,
            account,
            config,
            runtime,
            wsClient,
        }),
    ]);
    const mediaList = [...imageMediaList, ...fileMediaList];
    // Step 5: 初始化消息状态
    setReqIdForChat(chatId, reqId, account.accountId);
    const streamId = aibotNodeSdk.generateReqId("stream");
    const state = { accumulatedText: "", streamId };
    setMessageState(messageId, state);
    const cleanupState = () => {
        deleteMessageState(messageId);
    };
    // Step 6: 发送"思考中"消息
    const shouldSendThinking = account.sendThinkingMessage ?? true;
    if (shouldSendThinking) {
        await sendThinkingReply({ wsClient, frame, streamId, runtime });
    }
    // Step 7: 构建上下文并路由到核心处理流程（带整体超时保护）
    const ctxPayload = buildMessageContext(frame, account, config, text, mediaList, quoteContent);
    try {
        await withTimeout(routeAndDispatchMessage({
            ctxPayload,
            config,
            wsClient,
            frame,
            state,
            runtime,
            onCleanup: cleanupState,
        }), MESSAGE_PROCESS_TIMEOUT_MS, `Message processing timed out (msgId=${messageId})`);
    }
    catch (err) {
        runtime.error?.(`[WeCom] Message processing failed or timed out: ${String(err)}`);
        cleanupState();
    }
}
// ============================================================================
// 创建 SDK Logger 适配器
// ============================================================================
/**
 * 创建适配 RuntimeEnv 的 Logger
 */
function createSdkLogger(runtime, accountId) {
    return {
        debug: (message, ...args) => {
            runtime.log?.(`[${accountId}] ${message}`, ...args);
        },
        info: (message, ...args) => {
            runtime.log?.(`[${accountId}] ${message}`, ...args);
        },
        warn: (message, ...args) => {
            runtime.log?.(`[${accountId}] WARN: ${message}`, ...args);
        },
        error: (message, ...args) => {
            runtime.error?.(`[${accountId}] ${message}`, ...args);
        },
    };
}
// ============================================================================
// 主函数
// ============================================================================
/**
 * 监听企业微信 WebSocket 连接
 * 使用 aibot-node-sdk 简化连接管理
 */
async function monitorWeComProvider(options) {
    const { account, config, runtime, abortSignal } = options;
    runtime.log?.(`[${account.accountId}] Initializing WSClient with SDK...`);
    // 启动消息状态定期清理
    startMessageStateCleanup();
    return new Promise((resolve, reject) => {
        const logger = createSdkLogger(runtime, account.accountId);
        const wsClient = new aibotNodeSdk.WSClient({
            botId: account.botId,
            secret: account.secret,
            wsUrl: account.websocketUrl,
            logger,
            heartbeatInterval: WS_HEARTBEAT_INTERVAL_MS,
            maxReconnectAttempts: WS_MAX_RECONNECT_ATTEMPTS,
        });
        // 清理函数：确保所有资源被释放
        const cleanup = async () => {
            stopMessageStateCleanup();
            await cleanupAccount(account.accountId);
        };
        // 处理中止信号
        if (abortSignal) {
            abortSignal.addEventListener("abort", async () => {
                runtime.log?.(`[${account.accountId}] Connection aborted`);
                await cleanup();
                resolve();
            });
        }
        // 监听连接事件
        wsClient.on("connected", () => {
            runtime.log?.(`[${account.accountId}] WebSocket connected`);
        });
        // 监听认证成功事件
        wsClient.on("authenticated", () => {
            runtime.log?.(`[${account.accountId}] Authentication successful`);
            setWeComWebSocket(account.accountId, wsClient);
        });
        // 监听断开事件
        wsClient.on("disconnected", (reason) => {
            runtime.log?.(`[${account.accountId}] WebSocket disconnected: ${reason}`);
        });
        // 监听重连事件
        wsClient.on("reconnecting", (attempt) => {
            runtime.log?.(`[${account.accountId}] Reconnecting attempt ${attempt}...`);
        });
        // 监听错误事件
        wsClient.on("error", (error) => {
            runtime.error?.(`[${account.accountId}] WebSocket error: ${error.message}`);
            // 认证失败时拒绝 Promise
            if (error.message.includes("Authentication failed")) {
                cleanup().finally(() => reject(error));
            }
        });
        // 监听所有消息
        wsClient.on("message", async (frame) => {
            try {
                await processWeComMessage({
                    frame,
                    account,
                    config,
                    runtime,
                    wsClient,
                });
            }
            catch (err) {
                runtime.error?.(`[${account.accountId}] Failed to process message: ${String(err)}`);
            }
        });
        // 启动前预热 reqId 缓存，确保完成后再建立连接，避免 getSync 在预热完成前返回 undefined
        warmupReqIdStore(account.accountId, (...args) => runtime.log?.(...args))
            .then((count) => {
            runtime.log?.(`[${account.accountId}] Warmed up ${count} reqId entries from disk`);
        })
            .catch((err) => {
            runtime.error?.(`[${account.accountId}] Failed to warmup reqId store: ${String(err)}`);
        })
            .finally(() => {
            // 无论预热成功或失败，都建立连接
            wsClient.connect();
        });
    });
}

/**
 * 企业微信公共工具函数
 */
const DefaultWsUrl = "wss://openws.work.weixin.qq.com";
/**
 * 解析企业微信账户配置
 */
function resolveWeComAccount(cfg) {
    const wecomConfig = (cfg.channels?.[CHANNEL_ID] ?? {});
    return {
        accountId: pluginSdk.DEFAULT_ACCOUNT_ID,
        name: wecomConfig.name ?? "企业微信",
        enabled: wecomConfig.enabled ?? false,
        websocketUrl: wecomConfig.websocketUrl || DefaultWsUrl,
        botId: wecomConfig.botId ?? "",
        secret: wecomConfig.secret ?? "",
        sendThinkingMessage: wecomConfig.sendThinkingMessage ?? true,
        config: wecomConfig,
    };
}
/**
 * 设置企业微信账户配置
 */
function setWeComAccount(cfg, account) {
    const existing = (cfg.channels?.[CHANNEL_ID] ?? {});
    const merged = {
        enabled: account.enabled ?? existing?.enabled ?? true,
        botId: account.botId ?? existing?.botId ?? "",
        secret: account.secret ?? existing?.secret ?? "",
        allowFrom: account.allowFrom ?? existing?.allowFrom,
        dmPolicy: account.dmPolicy ?? existing?.dmPolicy,
        // 以下字段仅在已有配置值或显式传入时才写入，onboarding 时不主动生成
        ...(account.websocketUrl || existing?.websocketUrl
            ? { websocketUrl: account.websocketUrl ?? existing?.websocketUrl }
            : {}),
        ...(account.name || existing?.name
            ? { name: account.name ?? existing?.name }
            : {}),
        ...(account.sendThinkingMessage !== undefined || existing?.sendThinkingMessage !== undefined
            ? { sendThinkingMessage: account.sendThinkingMessage ?? existing?.sendThinkingMessage }
            : {}),
    };
    return {
        ...cfg,
        channels: {
            ...cfg.channels,
            [CHANNEL_ID]: merged,
        },
    };
}

/**
 * 企业微信 onboarding adapter for CLI setup wizard.
 */
const channel = CHANNEL_ID;
/**
 * 企业微信设置帮助说明
 */
async function noteWeComSetupHelp(prompter) {
    await prompter.note([
        "企业微信机器人需要以下配置信息：",
        "1. Bot ID: 企业微信机器人id",
        "2. Secret: 企业微信机器人密钥",
    ].join("\n"), "企业微信设置");
}
/**
 * 提示输入 Bot ID
 */
async function promptBotId(prompter, account) {
    return String(await prompter.text({
        message: "企业微信机器人 Bot ID",
        initialValue: account?.botId ?? "",
        validate: (value) => (value?.trim() ? undefined : "Required"),
    })).trim();
}
/**
 * 提示输入 Secret
 */
async function promptSecret(prompter, account) {
    return String(await prompter.text({
        message: "企业微信机器人 Secret",
        initialValue: account?.secret ?? "",
        validate: (value) => (value?.trim() ? undefined : "Required"),
    })).trim();
}
/**
 * 设置企业微信 dmPolicy
 */
function setWeComDmPolicy(cfg, dmPolicy) {
    const account = resolveWeComAccount(cfg);
    const existingAllowFrom = account.config.allowFrom ?? [];
    const allowFrom = dmPolicy === "open"
        ? pluginSdk.addWildcardAllowFrom(existingAllowFrom.map((x) => String(x)))
        : existingAllowFrom.map((x) => String(x));
    return setWeComAccount(cfg, {
        dmPolicy,
        allowFrom,
    });
}
const dmPolicy = {
    label: "企业微信",
    channel,
    policyKey: `channels.${CHANNEL_ID}.dmPolicy`,
    allowFromKey: `channels.${CHANNEL_ID}.allowFrom`,
    getCurrent: (cfg) => {
        const account = resolveWeComAccount(cfg);
        return account.config.dmPolicy ?? "pairing";
    },
    setPolicy: (cfg, policy) => {
        return setWeComDmPolicy(cfg, policy);
    },
    promptAllowFrom: async ({ cfg, prompter }) => {
        const account = resolveWeComAccount(cfg);
        const existingAllowFrom = account.config.allowFrom ?? [];
        const entry = await prompter.text({
            message: "企业微信允许来源（用户ID或群组ID，每行一个，推荐用于安全控制）",
            placeholder: "user123 或 group456",
            initialValue: existingAllowFrom[0] ? String(existingAllowFrom[0]) : undefined,
        });
        const allowFrom = String(entry ?? "")
            .split(/[\n,;]+/g)
            .map((s) => s.trim())
            .filter(Boolean);
        return setWeComAccount(cfg, { allowFrom });
    },
};
const wecomOnboardingAdapter = {
    channel,
    getStatus: async ({ cfg }) => {
        const account = resolveWeComAccount(cfg);
        const configured = Boolean(account.botId?.trim() &&
            account.secret?.trim());
        return {
            channel,
            configured,
            statusLines: [`企业微信: ${configured ? "已配置" : "需要 Bot ID 和 Secret"}`],
            selectionHint: configured ? "已配置" : "需要设置",
        };
    },
    configure: async ({ cfg, prompter, forceAllowFrom }) => {
        const account = resolveWeComAccount(cfg);
        if (!account.botId?.trim() || !account.secret?.trim()) {
            await noteWeComSetupHelp(prompter);
        }
        // 提示输入必要的配置信息：Bot ID 和 Secret
        const botId = await promptBotId(prompter, account);
        const secret = await promptSecret(prompter, account);
        // 使用默认值配置其他选项
        const cfgWithAccount = setWeComAccount(cfg, {
            botId,
            secret,
            enabled: true,
            dmPolicy: account.config.dmPolicy ?? "pairing",
            allowFrom: account.config.allowFrom ?? [],
        });
        return { cfg: cfgWithAccount };
    },
    dmPolicy,
    disable: (cfg) => {
        return setWeComAccount(cfg, { enabled: false });
    },
};

/**
 * 使用 SDK 的 sendMessage 主动发送企业微信消息
 * 无需依赖 reqId，直接向指定会话推送消息
 */
async function sendWeComMessage({ to, content, accountId, }) {
    const resolvedAccountId = accountId ?? pluginSdk.DEFAULT_ACCOUNT_ID;
    // 从 to 中提取 chatId（格式是 "${CHANNEL_ID}:chatId" 或直接是 chatId）
    const channelPrefix = new RegExp(`^${CHANNEL_ID}:`, "i");
    const chatId = to.replace(channelPrefix, "");
    console.log(`[WeCom] sendWeComMessage: ${JSON.stringify({ to, content, accountId })}`);
    // 获取 WSClient 实例
    const wsClient = getWeComWebSocket(resolvedAccountId);
    if (!wsClient) {
        throw new Error(`WSClient not connected for account ${resolvedAccountId}`);
    }
    // 使用 SDK 的 sendMessage 主动发送 markdown 消息
    const result = await wsClient.sendMessage(chatId, {
        msgtype: 'markdown',
        markdown: { content },
    });
    const messageId = result?.headers?.req_id ?? `wecom-${Date.now()}`;
    console.log(`[WeCom] Sent message to ${chatId}, messageId=${messageId}`);
    return {
        channel: CHANNEL_ID,
        messageId,
        chatId,
    };
}
// 企业微信频道元数据
const meta = {
    id: CHANNEL_ID,
    label: "企业微信",
    selectionLabel: "企业微信 (WeCom)",
    detailLabel: "企业微信智能机器人",
    docsPath: `/channels/${CHANNEL_ID}`,
    docsLabel: CHANNEL_ID,
    blurb: "企业微信智能机器人接入插件",
    systemImage: "message.fill",
};
const wecomPlugin = {
    id: CHANNEL_ID,
    meta: {
        ...meta,
        quickstartAllowFrom: true,
    },
    pairing: {
        idLabel: "wecomUserId",
        normalizeAllowEntry: (entry) => entry.replace(new RegExp(`^(${CHANNEL_ID}|user):`, "i"), "").trim(),
        notifyApproval: async ({ cfg, id }) => {
            // sendWeComMessage({
            //   to: id,
            //   content: " pairing approved",
            //   accountId: cfg.accountId,
            // });
            console.log(`[WeCom] Pairing approved for user: ${id}`);
        },
    },
    onboarding: wecomOnboardingAdapter,
    capabilities: {
        chatTypes: ["direct", "group"],
        reactions: false,
        threads: false,
        media: true,
        nativeCommands: false,
        blockStreaming: true,
    },
    reload: { configPrefixes: [`channels.${CHANNEL_ID}`] },
    config: {
        // 列出所有账户 ID（最小实现只支持默认账户）
        listAccountIds: () => [pluginSdk.DEFAULT_ACCOUNT_ID],
        // 解析账户配置
        resolveAccount: (cfg) => resolveWeComAccount(cfg),
        // 获取默认账户 ID
        defaultAccountId: () => pluginSdk.DEFAULT_ACCOUNT_ID,
        // 设置账户启用状态
        setAccountEnabled: ({ cfg, enabled }) => {
            const wecomConfig = (cfg.channels?.[CHANNEL_ID] ?? {});
            return {
                ...cfg,
                channels: {
                    ...cfg.channels,
                    [CHANNEL_ID]: {
                        ...wecomConfig,
                        enabled,
                    },
                },
            };
        },
        // 删除账户
        deleteAccount: ({ cfg }) => {
            const wecomConfig = (cfg.channels?.[CHANNEL_ID] ?? {});
            const { botId, secret, ...rest } = wecomConfig;
            return {
                ...cfg,
                channels: {
                    ...cfg.channels,
                    [CHANNEL_ID]: rest,
                },
            };
        },
        // 检查是否已配置
        isConfigured: (account) => Boolean(account.botId?.trim() && account.secret?.trim()),
        // 描述账户信息
        describeAccount: (account) => ({
            accountId: account.accountId,
            name: account.name,
            enabled: account.enabled,
            configured: Boolean(account.botId?.trim() && account.secret?.trim()),
            botId: account.botId,
            websocketUrl: account.websocketUrl,
        }),
        // 解析允许来源列表
        resolveAllowFrom: ({ cfg }) => {
            const account = resolveWeComAccount(cfg);
            return (account.config.allowFrom ?? []).map((entry) => String(entry));
        },
        // 格式化允许来源列表
        formatAllowFrom: ({ allowFrom }) => allowFrom
            .map((entry) => String(entry).trim())
            .filter(Boolean),
    },
    security: {
        resolveDmPolicy: ({ account }) => {
            const basePath = `channels.${CHANNEL_ID}.`;
            return {
                policy: account.config.dmPolicy ?? "pairing",
                allowFrom: account.config.allowFrom ?? [],
                policyPath: `${basePath}dmPolicy`,
                allowFromPath: basePath,
                approveHint: pluginSdk.formatPairingApproveHint(CHANNEL_ID),
                normalizeEntry: (raw) => raw.replace(new RegExp(`^${CHANNEL_ID}:`, "i"), "").trim(),
            };
        },
        collectWarnings: ({ account, cfg }) => {
            const warnings = [];
            // DM 策略警告
            const dmPolicy = account.config.dmPolicy ?? "pairing";
            if (dmPolicy === "open") {
                const hasWildcard = (account.config.allowFrom ?? []).some((entry) => String(entry).trim() === "*");
                if (!hasWildcard) {
                    warnings.push(`- 企业微信私信：dmPolicy="open" 但 allowFrom 未包含 "*"。任何人都可以发消息，但允许列表为空可能导致意外行为。建议设置 channels.${CHANNEL_ID}.allowFrom=["*"] 或使用 dmPolicy="pairing"。`);
                }
            }
            // 群组策略警告
            const defaultGroupPolicy = cfg.channels?.defaults?.groupPolicy;
            const groupPolicy = account.config.groupPolicy ?? defaultGroupPolicy ?? "open";
            // const { groupPolicy } = resolveOpenProviderRuntimeGroupPolicy({
            //   providerConfigPresent: true,
            //   groupPolicy: account.config.groupPolicy,
            //   defaultGroupPolicy,
            // });
            if (groupPolicy === "open") {
                warnings.push(`- 企业微信群组：groupPolicy="open" 允许所有群组中的成员触发。设置 channels.${CHANNEL_ID}.groupPolicy="allowlist" + channels.${CHANNEL_ID}.groupAllowFrom 来限制群组。`);
            }
            return warnings;
        },
    },
    messaging: {
        normalizeTarget: (target) => {
            const trimmed = target.trim();
            if (!trimmed)
                return undefined;
            return trimmed;
        },
        targetResolver: {
            looksLikeId: (id) => {
                const trimmed = id?.trim();
                return Boolean(trimmed);
            },
            hint: "<userId|groupId>",
        },
    },
    directory: {
        self: async () => null,
        listPeers: async () => [],
        listGroups: async () => [],
    },
    outbound: {
        deliveryMode: "direct",
        chunker: (text, limit) => getWeComRuntime().channel.text.chunkMarkdownText(text, limit),
        textChunkLimit: TEXT_CHUNK_LIMIT,
        sendText: async ({ to, text, accountId, ...rest }) => {
            console.log(`[WeCom] sendText: ${JSON.stringify({ to, text, accountId, ...rest })}`);
            return sendWeComMessage({ to, content: text, accountId: accountId ?? undefined });
        },
        sendMedia: async ({ to, text, mediaUrl, accountId, ...rest }) => {
            console.log(`[WeCom] sendMedia: ${JSON.stringify({ to, text, mediaUrl, accountId, ...rest })}`);
            const content = `Sending attachments is not supported yet\n${text ? `${text}\n${mediaUrl}` : (mediaUrl ?? "")}`;
            return sendWeComMessage({ to, content, accountId: accountId ?? undefined });
        },
    },
    status: {
        defaultRuntime: {
            accountId: pluginSdk.DEFAULT_ACCOUNT_ID,
            running: false,
            lastStartAt: null,
            lastStopAt: null,
            lastError: null,
        },
        collectStatusIssues: (accounts) => accounts.flatMap((entry) => {
            const accountId = String(entry.accountId ?? pluginSdk.DEFAULT_ACCOUNT_ID);
            const enabled = entry.enabled !== false;
            const configured = entry.configured === true;
            if (!enabled) {
                return [];
            }
            const issues = [];
            if (!configured) {
                issues.push({
                    channel: CHANNEL_ID,
                    accountId,
                    kind: "config",
                    message: "企业微信机器人 ID 或 Secret 未配置",
                    fix: "Run: openclaw channels add wecom --bot-id <id> --secret <secret>",
                });
            }
            return issues;
        }),
        buildChannelSummary: ({ snapshot }) => ({
            configured: snapshot.configured ?? false,
            running: snapshot.running ?? false,
            lastStartAt: snapshot.lastStartAt ?? null,
            lastStopAt: snapshot.lastStopAt ?? null,
            lastError: snapshot.lastError ?? null,
        }),
        probeAccount: async () => {
            return { ok: true, status: 200 };
        },
        buildAccountSnapshot: ({ account, runtime }) => {
            const configured = Boolean(account.botId?.trim() &&
                account.secret?.trim());
            return {
                accountId: account.accountId,
                name: account.name,
                enabled: account.enabled,
                configured,
                running: runtime?.running ?? false,
                lastStartAt: runtime?.lastStartAt ?? null,
                lastStopAt: runtime?.lastStopAt ?? null,
                lastError: runtime?.lastError ?? null,
            };
        },
    },
    gateway: {
        startAccount: async (ctx) => {
            const account = ctx.account;
            // 启动 WebSocket 监听
            return monitorWeComProvider({
                account,
                config: ctx.cfg,
                runtime: ctx.runtime,
                abortSignal: ctx.abortSignal,
            });
        },
        logoutAccount: async ({ cfg }) => {
            const nextCfg = { ...cfg };
            const wecomConfig = (cfg.channels?.[CHANNEL_ID] ?? {});
            const nextWecom = { ...wecomConfig };
            let cleared = false;
            let changed = false;
            if (nextWecom.botId || nextWecom.secret) {
                delete nextWecom.botId;
                delete nextWecom.secret;
                cleared = true;
                changed = true;
            }
            if (changed) {
                if (Object.keys(nextWecom).length > 0) {
                    nextCfg.channels = { ...nextCfg.channels, [CHANNEL_ID]: nextWecom };
                }
                else {
                    const nextChannels = { ...nextCfg.channels };
                    delete nextChannels[CHANNEL_ID];
                    if (Object.keys(nextChannels).length > 0) {
                        nextCfg.channels = nextChannels;
                    }
                    else {
                        delete nextCfg.channels;
                    }
                }
                await getWeComRuntime().config.writeConfigFile(nextCfg);
            }
            const resolved = resolveWeComAccount(changed ? nextCfg : cfg);
            const loggedOut = !resolved.botId && !resolved.secret;
            return { cleared, envToken: false, loggedOut };
        },
    },
};

const plugin = {
    id: "wecom",
    name: "企业微信",
    description: "企业微信 OpenClaw 插件",
    configSchema: pluginSdk.emptyPluginConfigSchema(),
    register(api) {
        setWeComRuntime(api.runtime);
        api.registerChannel({ plugin: wecomPlugin });
    },
};

exports.default = plugin;
//# sourceMappingURL=index.cjs.js.map
