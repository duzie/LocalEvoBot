from __future__ import annotations

import json
import os
import uuid
import urllib.request
import urllib.error

from langchain_core.tools import tool


def _get_env_path() -> str:
    p = os.path.abspath(__file__)
    for _ in range(4):
        p = os.path.dirname(p)
    return os.path.join(p, ".env")


def _read_env(key: str) -> str | None:
    value = os.getenv(key)
    if value is None or str(value).strip() == "":
        try:
            from dotenv import dotenv_values

            env_path = _get_env_path()
            env = dotenv_values(env_path) if os.path.exists(env_path) else {}
            value = env.get(key)
        except Exception:
            value = None
    if value is None:
        return None
    stripped = str(value).strip().strip("'\"")
    return stripped or None


@tool
def ask_coupon_agent(query: str, window_id: str | None = None, timeout_seconds: int = 30) -> str:
    """
    调用 .env 中 AISerAgent 指定的 CRM.CRMChat 接口，询问“活动/发券”相关问题并返回回复。

    Args:
        query: 用户问题
        window_id: (可选) 会话窗口ID，不传则自动生成
        timeout_seconds: (可选) 请求超时秒数
    """
    url = _read_env("AISerAgent")
    if not url:
        return "未配置 AISerAgent，请在 .env 中设置接口地址。"
    cookie = _read_env("AICookie")
    if not cookie:
        return "未配置 AICookie，请在 .env 中设置 Cookie（用于请求头）。"

    wid = (window_id or "").strip() or str(uuid.uuid4())
    payload = {"query": str(query or ""), "window_id": wid}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0",
            "Cookie": cookie,
        },
        method="POST",
    )

    last_error: str | None = None
    attempts = 3
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=max(1, int(timeout_seconds or 30))) as resp:
                raw = resp.read()
            text = raw.decode("utf-8", errors="ignore")
            last_error = None
            break
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", errors="ignore")
            except Exception:
                detail = ""
            detail = (detail or "").strip()
            if len(detail) > 300:
                detail = detail[:300] + "..."
            last_error = f"发券 Agent 接口请求失败: HTTP {e.code} {e.reason}{(' - ' + detail) if detail else ''}"
            if int(getattr(e, "code", 0) or 0) in (429, 502, 503, 504):
                continue
            return last_error
        except Exception as e:
            last_error = f"发券 Agent 接口请求失败: {e}"
            continue
    else:
        text = ""

    if last_error:
        return last_error

    try:
        data = json.loads(text)
        if isinstance(data, dict) and "ResultCode" in data:
            if data.get("ResultCode") == 0:
                reply = data.get("Data") or ""
            else:
                reply = data.get("Message") or ""
        else:
            reply = text
    except Exception:
        reply = text

    reply = str(reply or "").replace("\\n", "\n").strip()
    return reply or "抱歉，发券 Agent 未返回有效回复。"

