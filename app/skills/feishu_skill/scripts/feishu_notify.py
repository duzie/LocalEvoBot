from langchain_core.tools import tool
import os
import json
import time
import base64
import hmac
import hashlib
import urllib.request
from typing import Optional, Dict, Any


def _http_post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            return {"ok": True, "status_code": resp.status, "text": text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _feishu_sign(timestamp_s: int, secret: str) -> str:
    string_to_sign = f"{timestamp_s}\n{secret}".encode("utf-8")
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign, digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


@tool
def feishu_send_text(
    text: str,
    webhook_url: Optional[str] = None,
    secret: Optional[str] = None,
) -> Dict[str, Any]:
    """
    通过飞书自定义机器人 Webhook 发送文本消息。

    环境变量:
        FEISHU_WEBHOOK_URL: 机器人 Webhook 地址
        FEISHU_SECRET: 机器人“签名校验”密钥（可选）
    """
    url = (webhook_url or os.getenv("FEISHU_WEBHOOK_URL") or "").strip()
    if not url:
        return {"success": False, "message": "缺少 webhook_url（或环境变量 FEISHU_WEBHOOK_URL）"}

    payload: Dict[str, Any] = {"msg_type": "text", "content": {"text": text}}

    sec = (secret or os.getenv("FEISHU_SECRET") or "").strip()
    if sec:
        ts = int(time.time())
        payload["timestamp"] = ts
        payload["sign"] = _feishu_sign(ts, sec)

    resp = _http_post_json(url, payload)
    if not resp.get("ok"):
        return {"success": False, "message": "请求失败", "error": resp.get("error")}

    result: Dict[str, Any] = {"success": True, "status_code": resp.get("status_code"), "raw": resp.get("text")}
    try:
        data = json.loads(resp.get("text") or "{}")
        result["data"] = data
        if isinstance(data, dict):
            code = data.get("code")
            if code is None:
                code = data.get("StatusCode")
            if code not in (0, "0", None):
                result["success"] = False
                result["message"] = data.get("msg") or data.get("StatusMessage") or "飞书返回错误"
    except Exception:
        pass

    return result
