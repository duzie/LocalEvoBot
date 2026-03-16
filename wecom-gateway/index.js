/**
 * WeCom Gateway - 企业微信网关服务
 * 
 * 基于官方 @wecom/aibot-node-sdk 实现稳定的 WebSocket 长连接
 * 架构与 WhatsApp Gateway 保持一致
 * 
 * API:
 * - GET  /health     - 健康检查
 * - POST /send       - 发送消息
 * - GET  /inbox      - 最近收到的消息
 */

import express from "express";
import dotenv from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
import AiBot from "@wecom/aibot-node-sdk";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 加载环境变量
const envCandidates = [
  path.resolve(__dirname, "../.env"),
  path.resolve(__dirname, "./.env"),
];
for (const p of envCandidates) {
  if (fs.existsSync(p)) dotenv.config({ path: p });
}

function envStr(name, defaultValue = "") {
  const raw = process.env[name];
  if (raw == null) return defaultValue;
  const v = String(raw).trim();
  return v || defaultValue;
}

function envInt(name, defaultValue) {
  const raw = (process.env[name] ?? "").trim();
  if (!raw) return defaultValue;
  const v = Number.parseInt(raw, 10);
  return Number.isFinite(v) ? v : defaultValue;
}

function envFlag(name, defaultValue = false) {
  const raw = (process.env[name] ?? "").trim().toLowerCase();
  if (!raw) return defaultValue;
  return ["1", "true", "yes", "on"].includes(raw);
}

function splitCommaList(raw) {
  return String(raw || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

// 配置
const config = {
  httpHost: envStr("WECOM_GATEWAY_HOST", "127.0.0.1"),
  httpPort: envInt("WECOM_GATEWAY_PORT", 8788),
  apiToken: envStr("WECOM_GATEWAY_TOKEN", ""),
  webhookUrl: envStr("WECOM_WEBHOOK_URL", ""),
  webhookToken: envStr("WECOM_WEBHOOK_TOKEN", ""),
  botId: envStr("WECOM_BOT_ID", ""),
  secret: envStr("WECOM_SECRET", ""),
  allowFrom: new Set(splitCommaList(envStr("WECOM_ALLOW_FROM", ""))),
  dmEnabled: envFlag("WECOM_DM_ENABLED", true),
  textChunkLimit: envInt("WECOM_TEXT_CHUNK_LIMIT", 4000),
};

// 验证配置
if (!config.botId || !config.secret) {
  process.stderr.write("Missing WECOM_BOT_ID or WECOM_SECRET\n");
  process.exit(1);
}

if (!config.apiToken) {
  process.stderr.write("Missing WECOM_GATEWAY_TOKEN\n");
  process.exit(1);
}

// 状态
let wsClient = null;
let connectionState = { connected: false, lastDisconnectReason: null };
const recentInbound = [];
const maxInbound = 50;

// 检查是否允许接收消息
function isAllowedDm(userid) {
  if (!config.dmEnabled) return false;
  if (config.allowFrom.size === 0) return true;
  if (config.allowFrom.has("*")) return true;
  if (!userid) return false;
  return config.allowFrom.has(userid);
}

// 发送 webhook
async function postWebhook(payload) {
  if (!config.webhookUrl) return;
  const headers = { "Content-Type": "application/json" };
  if (config.webhookToken) headers["Authorization"] = `Bearer ${config.webhookToken}`;
  const body = JSON.stringify(payload);
  const fallbackUrl = (() => {
    try {
      const u = new URL(config.webhookUrl);
      if (u.pathname === "/api/chat/wecom/webhook") return "";
      u.pathname = "/api/chat/wecom/webhook";
      u.search = "";
      u.hash = "";
      return u.toString();
    } catch {
      return "";
    }
  })();
  try {
    const resp = await fetch(config.webhookUrl, {
      method: "POST",
      headers,
      body,
    });
    if ((resp.status === 404 || resp.status === 405) && fallbackUrl) {
      const retryResp = await fetch(fallbackUrl, {
        method: "POST",
        headers,
        body,
      });
      if (!retryResp.ok) {
        let retryRaw = "";
        try {
          retryRaw = await retryResp.text();
        } catch {}
        process.stderr.write(`[WeCom] Webhook retry failed ${retryResp.status}: ${retryRaw || retryResp.statusText}\n`);
      }
      return;
    }
    if (!resp.ok) {
      let raw = "";
      try {
        raw = await resp.text();
      } catch {}
      process.stderr.write(`[WeCom] Webhook failed ${resp.status}: ${raw || resp.statusText}\n`);
    }
  } catch (e) {
    process.stderr.write(`Webhook post failed: ${e}\n`);
  }
}

// 分块文本
function chunkText(text, limit) {
  const s = String(text || "");
  if (!s) return [];
  if (!limit || s.length <= limit) return [s];
  const out = [];
  let i = 0;
  while (i < s.length) {
    out.push(s.slice(i, i + limit));
    i += limit;
  }
  return out;
}

// 启动企业微信连接
async function startWeCom() {
  if (wsClient) {
    try {
      wsClient.disconnect();
    } catch {}
    wsClient = null;
  }

  process.stdout.write(`[WeCom] 正在连接企业微信 WebSocket...\n`);

  wsClient = new AiBot.WSClient({
    botId: config.botId,
    secret: config.secret,
    heartbeatInterval: 30000,
    maxReconnectAttempts: -1, // 无限重连
    reconnectInterval: 3000,
  });

  // 监听连接事件
  wsClient.on("connected", () => {
    process.stdout.write("[WeCom] ✅ WebSocket 已连接\n");
  });

  wsClient.on("authenticated", () => {
    process.stdout.write("[WeCom] ✅ 认证成功\n");
    connectionState.connected = true;
  });

  wsClient.on("disconnected", (reason) => {
    process.stdout.write(`[WeCom] ⚠️  连接断开：${reason}\n`);
    connectionState.connected = false;
    connectionState.lastDisconnectReason = reason;
  });

  wsClient.on("reconnecting", (attempt) => {
    process.stdout.write(`[WeCom] 🔄 正在重连 (尝试 ${attempt})...\n`);
  });

  wsClient.on("error", (error) => {
    process.stderr.write(`[WeCom] ❌ 错误：${error.message}\n`);
  });

  // 监听进入会话事件（发送欢迎语）
  wsClient.on("event.enter_chat", async (frame) => {
    const userid = frame.body.from?.userid;
    process.stdout.write(`[WeCom] 用户 ${userid} 进入会话\n`);

    try {
      await wsClient.replyWelcome(frame, {
        msgtype: "text",
        text: { content: "您好！我是智能助手，有什么可以帮您的吗？🤖" },
      });
    } catch (e) {
      process.stderr.write(`[WeCom] 欢迎语发送失败：${e.message}\n`);
    }
  });

  // 监听文本消息
  wsClient.on("message.text", async (frame) => {
    const body = frame.body;
    const userid = body.from?.userid;
    const content = body.text?.content;
    const msgid = body.msgid;
    const chatid = body.chatid || userid;
    const chattype = body.chattype || "single";

    if (!isAllowedDm(userid)) {
      process.stdout.write(`[WeCom] 忽略未授权用户 ${userid}\n`);
      return;
    }

    if (!content) {
      process.stdout.write(`[WeCom] 忽略空消息\n`);
      return;
    }

    process.stdout.write(`[WeCom IN] ${chattype} ${userid} ${msgid} ${content.slice(0, 100)}\n`);

    // 记录消息
    const payload = {
      channel: "wecom",
      kind: chattype === "single" ? "dm" : "group",
      chatid: chatid,
      senderUserid: userid,
      msgid: msgid,
      text: content,
      ts: Date.now(),
      frame: {
        headers: frame.headers,
        body: body,
      },
    };

    recentInbound.push(payload);
    if (recentInbound.length > maxInbound) {
      recentInbound.splice(0, recentInbound.length - maxInbound);
    }

    // 发送 webhook
    await postWebhook(payload);

    // 自动回复"正在思考"（可选）
    // const streamId = AiBot.generateReqId("thinking");
    // await wsClient.replyStream(frame, streamId, "🤖 正在思考中，请稍候...", false);
  });

  // 监听图片消息
  wsClient.on("message.image", async (frame) => {
    const body = frame.body;
    const userid = body.from?.userid;
    const imageUrl = body.image?.url;
    const aesKey = body.image?.aeskey;

    if (!isAllowedDm(userid)) return;

    process.stdout.write(`[WeCom IN] ${userid} 发送图片：${imageUrl}\n`);

    const payload = {
      channel: "wecom",
      kind: "dm",
      chatid: userid,
      senderUserid: userid,
      msgid: body.msgid,
      msgtype: "image",
      image: { url: imageUrl, aeskey: aesKey },
      ts: Date.now(),
    };

    recentInbound.push(payload);
    if (recentInbound.length > maxInbound) {
      recentInbound.splice(0, recentInbound.length - maxInbound);
    }

    await postWebhook(payload);
  });

  // 连接
  wsClient.connect();
}

// 创建 Express 应用
const app = express();
app.use(express.json({ limit: "1mb" }));

// 健康检查
app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    connected: connectionState.connected,
    lastDisconnectReason: connectionState.lastDisconnectReason,
    dmEnabled: config.dmEnabled,
    allowFromCount: config.allowFrom.size,
    webhookEnabled: Boolean(config.webhookUrl),
    loggedIn: Boolean(wsClient && wsClient.isConnected),
  });
});

// 认证中间件
app.use((req, res, next) => {
  const auth = String(req.headers.authorization || "");
  if (auth !== `Bearer ${config.apiToken}`) {
    return res.status(401).json({ ok: false, error: "unauthorized" });
  }
  next();
});

// 发送消息
app.post("/send", async (req, res) => {
  if (!wsClient || !wsClient.isConnected) {
    return res.status(503).json({ ok: false, error: "not_ready" });
  }

  const { chatid, text, msgtype = "text" } = req.body;

  if (!chatid || !text) {
    return res.status(400).json({ ok: false, error: "bad_request" });
  }

  try {
    if (msgtype === "text") {
      // 文本消息 - 使用流式回复
      const streamId = AiBot.generateReqId("send");
      const parts = chunkText(text, config.textChunkLimit);
      
      for (let i = 0; i < parts.length; i++) {
        const isLast = i === parts.length - 1;
        // 注意：sendMessage 需要完整的 frame，这里用主动发送
        await wsClient.sendMessage(chatid, {
          msgtype: "markdown",
          markdown: { content: parts[i] },
        });
      }
      
      res.json({ ok: true, parts: parts.length });
    } else if (msgtype === "markdown") {
      await wsClient.sendMessage(chatid, {
        msgtype: "markdown",
        markdown: { content: text },
      });
      res.json({ ok: true });
    } else {
      res.status(400).json({ ok: false, error: "unsupported_msgtype" });
    }
  } catch (e) {
    process.stderr.write(`[WeCom] 发送失败：${e.message}\n`);
    res.status(500).json({ ok: false, error: e.message });
  }
});

// 主动发送 Markdown 消息
app.post("/send/markdown", async (req, res) => {
  if (!wsClient || !wsClient.isConnected) {
    return res.status(503).json({ ok: false, error: "not_ready" });
  }

  const { chatid, content } = req.body;

  if (!chatid || !content) {
    return res.status(400).json({ ok: false, error: "bad_request" });
  }

  try {
    await wsClient.sendMessage(chatid, {
      msgtype: "markdown",
      markdown: { content },
    });
    res.json({ ok: true });
  } catch (e) {
    process.stderr.write(`[WeCom] 发送失败：${e.message}\n`);
    res.status(500).json({ ok: false, error: e.message });
  }
});

// 获取最近消息
app.get("/inbox", (req, res) => {
  res.json({ ok: true, messages: recentInbound });
});

// 重置连接
app.post("/reset", async (_req, res) => {
  try {
    connectionState = { connected: false, lastDisconnectReason: null };
    await startWeCom();
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// 启动服务
async function main() {
  await startWeCom();

  app.listen(config.httpPort, config.httpHost, () => {
    process.stdout.write(
      `[WeCom Gateway] 监听于 http://${config.httpHost}:${config.httpPort}\n`
    );
  });
}

main().catch((e) => {
  process.stderr.write(`[WeCom Gateway] 启动失败：${e.message}\n`);
  process.exit(1);
});
