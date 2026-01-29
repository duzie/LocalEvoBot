from langchain_core.tools import tool
import os
import json
import time
import base64
import hmac
import hashlib
import urllib.request
import urllib.parse
from typing import Optional, List, Dict, Any


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


def _signed_url(webhook_url: str, secret: str) -> str:
    timestamp_ms = str(int(time.time() * 1000))
    string_to_sign = f"{timestamp_ms}\n{secret}".encode("utf-8")
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    sep = "&" if "?" in webhook_url else "?"
    return f"{webhook_url}{sep}timestamp={timestamp_ms}&sign={sign}"


@tool
def dingtalk_send_text(
    text: str,
    webhook_url: Optional[str] = None,
    secret: Optional[str] = None,
    at_mobiles: Optional[List[str]] = None,
    at_all: bool = False,
) -> Dict[str, Any]:
    """
    通过钉钉自定义机器人 Webhook 发送文本消息。

    环境变量:
        DINGTALK_WEBHOOK_URL: 机器人 Webhook 地址
        DINGTALK_SECRET: 机器人“加签”密钥（可选）
    """
    url = (webhook_url or os.getenv("DINGTALK_WEBHOOK_URL") or "").strip()
    if not url:
        return {"success": False, "message": "缺少 webhook_url（或环境变量 DINGTALK_WEBHOOK_URL）"}

    sec = (secret or os.getenv("DINGTALK_SECRET") or "").strip()
    if sec:
        url = _signed_url(url, sec)

    payload = {
        "msgtype": "text",
        "text": {"content": text},
        "at": {"isAtAll": bool(at_all), "atMobiles": at_mobiles or []},
    }
    resp = _http_post_json(url, payload)
    if not resp.get("ok"):
        return {"success": False, "message": "请求失败", "error": resp.get("error")}

    result: Dict[str, Any] = {"success": True, "status_code": resp.get("status_code"), "raw": resp.get("text")}
    try:
        data = json.loads(resp.get("text") or "{}")
        result["data"] = data
        if isinstance(data, dict) and data.get("errcode") not in (0, "0", None):
            result["success"] = False
            result["message"] = data.get("errmsg") or "钉钉返回错误"
    except Exception:
        pass
    return result

