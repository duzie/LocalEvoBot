import express from "express";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";
import qrcode from "qrcode-terminal";
import { HttpsProxyAgent } from "https-proxy-agent";
import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const localEnvPath = path.resolve(__dirname, "./.env");
const rootEnvPath = path.resolve(__dirname, "../.env");
if (fs.existsSync(localEnvPath)) dotenv.config({ path: localEnvPath, override: true });
if (fs.existsSync(rootEnvPath)) dotenv.config({ path: rootEnvPath, override: false });

function envFlag(name, defaultValue = false) {
  const raw = (process.env[name] ?? "").trim().toLowerCase();
  if (!raw) return defaultValue;
  return ["1", "true", "yes", "on"].includes(raw);
}

function envInt(name, defaultValue) {
  const raw = (process.env[name] ?? "").trim();
  if (!raw) return defaultValue;
  const v = Number.parseInt(raw, 10);
  return Number.isFinite(v) ? v : defaultValue;
}

function envStr(name, defaultValue = "") {
  const raw = process.env[name];
  if (raw == null) return defaultValue;
  const v = String(raw).trim();
  return v || defaultValue;
}

function splitCommaList(raw) {
  return String(raw || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function toUserJid(phoneOrJid) {
  const v = String(phoneOrJid || "").trim();
  if (!v) return "";
  if (v.includes("@")) return v;
  return `${v}@s.whatsapp.net`;
}

function isDirectUserChatJid(jid) {
  const v = String(jid || "");
  return v.endsWith("@s.whatsapp.net") || v.endsWith("@lid");
}

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

function clearAuthDir() {
  const dir = String(config.authDir || "").trim();
  if (!dir) return;
  if (!fs.existsSync(dir)) return;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const ent of entries) {
    const p = path.join(dir, ent.name);
    fs.rmSync(p, { recursive: true, force: true });
  }
}

const config = {
  httpHost: envStr("WA_GATEWAY_HOST", "127.0.0.1"),
  httpPort: envInt("WA_GATEWAY_PORT", 8787),
  apiToken: envStr("WA_GATEWAY_TOKEN", ""),
  webhookUrl: envStr("WA_WEBHOOK_URL", ""),
  webhookToken: envStr("WA_WEBHOOK_TOKEN", ""),
  authDir: envStr("WA_AUTH_DIR", "./auth"),
  allowFrom: new Set(splitCommaList(envStr("WA_ALLOW_FROM", ""))),
  dmEnabled: envFlag("WA_DM_ENABLED", true),
  proxyEnabled: envFlag("WA_PROXY_ENABLED", false),
  proxyUrl: envStr("WA_PROXY_URL", ""),
  textChunkLimit: envInt("WA_TEXT_CHUNK_LIMIT", 4000),
  printQr: envFlag("WA_PRINT_QR", true),
};

if (!config.apiToken) {
  process.stderr.write("Missing WA_GATEWAY_TOKEN\n");
  process.exit(1);
}

let sock = null;
let connectionState = { connection: "init", lastDisconnectReason: null };
let lastQrText = "";
let reconnectTimer = null;
let starting = false;
const recentInbound = [];
const maxInbound = 50;
const typingPresence = new Map();
const typingRefreshMs = Math.max(3000, envInt("WA_TYPING_REFRESH_MS", 8000));
const typingMaxMs = Math.max(typingRefreshMs, envInt("WA_TYPING_MAX_MS", 120000));

async function sendPresenceSafe(jid, state) {
  if (!sock || !jid || !state) return;
  try {
    await sock.sendPresenceUpdate(state, jid);
  } catch {}
}

async function stopTypingPresence(jid) {
  const v = String(jid || "").trim();
  if (!v) return;
  const entry = typingPresence.get(v);
  if (entry) {
    if (entry.intervalId) clearInterval(entry.intervalId);
    if (entry.timeoutId) clearTimeout(entry.timeoutId);
    typingPresence.delete(v);
  }
  await sendPresenceSafe(v, "paused");
}

async function startTypingPresence(jid) {
  const v = String(jid || "").trim();
  if (!v) return;
  await stopTypingPresence(v);
  await sendPresenceSafe(v, "composing");
  const intervalId = setInterval(() => {
    sendPresenceSafe(v, "composing");
  }, typingRefreshMs);
  const timeoutId = setTimeout(() => {
    stopTypingPresence(v);
  }, typingMaxMs);
  typingPresence.set(v, { intervalId, timeoutId });
}

function stopAllTypingPresence() {
  for (const jid of Array.from(typingPresence.keys())) {
    stopTypingPresence(jid);
  }
}

function isAllowedDm(e164) {
  if (!config.dmEnabled) return false;
  if (config.allowFrom.size === 0) return true;
  if (config.allowFrom.has("*")) return true;
  if (!e164) return false;
  return config.allowFrom.has(e164);
}

async function postWebhook(payload) {
  if (!config.webhookUrl) return;
  const headers = { "Content-Type": "application/json" };
  if (config.webhookToken) headers["Authorization"] = `Bearer ${config.webhookToken}`;
  try {
    await fetch(config.webhookUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
  } catch (e) {
    process.stderr.write(`Webhook post failed: ${e}\n`);
  }
}

async function startWhatsapp({ force = false } = {}) {
  if (starting) return;
  if (!force && sock) return;
  starting = true;
  try {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (sock) {
      try {
        sock.end();
      } catch {}
      sock = null;
    }

    const { state, saveCreds } = await useMultiFileAuthState(config.authDir);
    const { version } = await fetchLatestBaileysVersion();
    const agent =
      config.proxyEnabled && config.proxyUrl ? new HttpsProxyAgent(config.proxyUrl) : undefined;

    sock = makeWASocket({
      version,
      auth: state,
      agent,
    });

    sock.ev.on("creds.update", saveCreds);

    sock.ev.on("connection.update", async (u) => {
      const { connection, lastDisconnect, qr } = u || {};
      if (qr) {
        lastQrText = qr;
        if (config.printQr) qrcode.generate(qr, { small: true });
      }
      connectionState.connection = connection || connectionState.connection;
      const reason = lastDisconnect?.error?.output?.statusCode ?? null;
      connectionState.lastDisconnectReason = reason;

      if (connection === "close") {
        stopAllTypingPresence();
        const shouldReconnect = reason !== DisconnectReason.loggedOut;
        if (shouldReconnect) {
          if (!reconnectTimer) {
            reconnectTimer = setTimeout(() => {
              startWhatsapp({ force: true }).catch((e) => {
                process.stderr.write(`Reconnect failed: ${e}\n`);
              });
            }, 1200);
          }
        } else {
          process.stderr.write("Logged out. Re-link required.\n");
        }
      }
    });

    sock.ev.on("messages.upsert", async (m) => {
      const msgs = m?.messages || [];
      for (const msg of msgs) {
        const key = msg?.key || {};
        if (key.fromMe) continue;
        const remoteJid = String(key.remoteJid || "");
        if (!isDirectUserChatJid(remoteJid)) continue;

        const sender = remoteJid.split("@")[0];
        const e164 = remoteJid.endsWith("@s.whatsapp.net")
          ? sender.startsWith("+")
            ? sender
            : `+${sender}`
          : "";
        if (!isAllowedDm(e164)) {
          continue;
        }

        const messageId = String(key.id || "");
        const content = msg?.message || {};
        const text =
          content?.conversation ||
          content?.extendedTextMessage?.text ||
          content?.imageMessage?.caption ||
          content?.videoMessage?.caption ||
          "";

        if (!text) continue;

        const payload = {
          channel: "whatsapp",
          kind: "dm",
          chatJid: remoteJid,
          senderE164: e164,
          senderJid: remoteJid,
          messageId,
          text,
          ts: Date.now(),
        };
        await startTypingPresence(remoteJid);
        recentInbound.push(payload);
        if (recentInbound.length > maxInbound) recentInbound.splice(0, recentInbound.length - maxInbound);
        process.stdout.write(`[WA IN] ${e164} ${messageId} ${String(text).slice(0, 120).replace(/\s+/g, " ")}\n`);
        await postWebhook(payload);
      }
    });
  } finally {
    starting = false;
  }
}

const app = express();
app.use(express.json({ limit: "1mb" }));

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    connection: connectionState.connection,
    lastDisconnectReason: connectionState.lastDisconnectReason,
    dmEnabled: config.dmEnabled,
    allowFromCount: config.allowFrom.size,
    webhookEnabled: Boolean(config.webhookUrl),
    loggedIn: Boolean(sock && sock.user && sock.user.id),
    me: sock && sock.user ? sock.user : null,
  });
});

app.get("/qr", (req, res) => {
  const auth = String(req.headers.authorization || "");
  if (auth !== `Bearer ${config.apiToken}`) return res.status(401).json({ ok: false });
  res.json({ ok: true, qr: lastQrText || "" });
});

app.get("/qr-ascii", (req, res) => {
  const auth = String(req.headers.authorization || "");
  if (auth !== `Bearer ${config.apiToken}`) return res.status(401).json({ ok: false });
  if (!lastQrText) return res.json({ ok: true, ascii: "" });
  try {
    qrcode.generate(lastQrText, { small: true }, (ascii) => {
      res.json({ ok: true, ascii: String(ascii || "") });
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: String(e) });
  }
});

app.use((req, res, next) => {
  const auth = String(req.headers.authorization || "");
  if (auth !== `Bearer ${config.apiToken}`) return res.status(401).json({ ok: false });
  next();
});

app.post("/send", async (req, res) => {
  if (!sock) return res.status(503).json({ ok: false, error: "not_ready" });

  const to = toUserJid(req.body?.to);
  const text = String(req.body?.text || "").trim();
  if (!to || !text) return res.status(400).json({ ok: false, error: "bad_request" });

  const parts = chunkText(text, config.textChunkLimit);
  try {
    for (const part of parts) {
      await sock.sendMessage(to, { text: part });
    }
    res.json({ ok: true, parts: parts.length });
  } catch (e) {
    res.status(500).json({ ok: false, error: String(e) });
  } finally {
    await stopTypingPresence(to);
  }
});

app.post("/reset", async (_req, res) => {
  try {
    if (sock && typeof sock.logout === "function") {
      try {
        await sock.logout();
      } catch {}
    }
    if (sock) {
      try {
        sock.end();
      } catch {}
      sock = null;
    }
    stopAllTypingPresence();
    lastQrText = "";
    connectionState = { connection: "init", lastDisconnectReason: null };
    clearAuthDir();
    await startWhatsapp({ force: true });
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ ok: false, error: String(e) });
  }
});

app.get("/inbox", (req, res) => {
  res.json({ ok: true, messages: recentInbound.slice(-maxInbound) });
});

await startWhatsapp();
app.listen(config.httpPort, config.httpHost, () => {
  process.stdout.write(`WA Gateway listening on http://${config.httpHost}:${config.httpPort}\n`);
});

