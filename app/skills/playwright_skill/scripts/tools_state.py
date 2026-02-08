import json
import os

from langchain_core.tools import tool

from . import _playwright_core as core


@tool
def playwright_apply_cookies(domain: str, headless: bool = False, user_data_dir: str = None):
    """
    从本地文件加载并应用 Cookie（用于复用登录态）。
    
    Args:
        domain: 目标域名，例如 example.com
        headless: 是否无头模式 (默认 False，即显示浏览器)
        user_data_dir: 用户数据目录，传入后可持久化登录状态
    """
    if not domain:
        return "domain 不能为空"
    if not user_data_dir:
        user_data_dir = os.getenv("PLAYWRIGHT_USER_DATA_DIR")
    if user_data_dir:
        os.makedirs(user_data_dir, exist_ok=True)
    _, err = core._ensure_page(headless=headless, user_data_dir=user_data_dir)
    if err:
        return err
    base_url = None
    try:
        base_url = core._page.url if core._page else None
    except Exception:
        base_url = None
    return core._apply_cookies_for_domain(domain, base_url=base_url)


@tool
def playwright_list_cookies(urls: list = None):
    """
    获取当前上下文的 Cookies。
    """
    _, err = core._ensure_page(headless=False)
    if err:
        return err
    try:
        if isinstance(urls, str):
            text = urls.strip()
            if text:
                if text.startswith("["):
                    urls = json.loads(text)
                else:
                    urls = [u.strip() for u in text.split(",") if u.strip()]
            else:
                urls = None
        cookies = core._context.cookies(urls) if urls else core._context.cookies()
        return json.dumps(cookies, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"获取 Cookies 失败: {e}"


@tool
def playwright_set_cookies(cookies):
    """
    设置 Cookies 到当前上下文。
    """
    _, err = core._ensure_page(headless=False)
    if err:
        return err
    try:
        data = cookies
        if isinstance(cookies, str):
            data = json.loads(cookies)
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return "cookies 必须是列表或可解析的 JSON"
        core._context.add_cookies(data)
        return f"已设置 Cookies: {len(data)}"
    except Exception as e:
        return f"设置 Cookies 失败: {e}"


@tool
def playwright_clear_cookies():
    """
    清空当前上下文的 Cookies。
    """
    _, err = core._ensure_page(headless=False)
    if err:
        return err
    try:
        core._context.clear_cookies()
        return "已清空 Cookies"
    except Exception as e:
        return f"清空 Cookies 失败: {e}"


@tool
def playwright_get_storage(storage: str = "local"):
    """
    获取 localStorage 或 sessionStorage。
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    kind = (storage or "local").strip().lower()
    if kind not in ("local", "session"):
        return "storage 只能是 local 或 session"
    try:
        target = "localStorage" if kind == "local" else "sessionStorage"
        script = f"""
        () => {{
            const s = window.{target};
            const data = {{}};
            for (let i = 0; i < s.length; i++) {{
                const k = s.key(i);
                data[k] = s.getItem(k);
            }}
            return data;
        }}
        """
        result = core._page.evaluate(script)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"获取存储失败: {e}"


@tool
def playwright_set_storage(items, storage: str = "local", clear: bool = False):
    """
    设置 localStorage 或 sessionStorage。
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    kind = (storage or "local").strip().lower()
    if kind not in ("local", "session"):
        return "storage 只能是 local 或 session"
    try:
        data = items
        if isinstance(items, str):
            data = json.loads(items)
        if not isinstance(data, dict):
            return "items 必须是字典或可解析的 JSON"
        target = "localStorage" if kind == "local" else "sessionStorage"
        payload = json.dumps(data, ensure_ascii=False)
        script = f"""
        () => {{
            const s = window.{target};
            const data = {payload};
            if ({str(bool(clear)).lower()}) {{
                s.clear();
            }}
            Object.keys(data).forEach(k => s.setItem(k, String(data[k])));
            return true;
        }}
        """
        core._page.evaluate(script)
        return f"已设置 {kind}Storage: {len(data)}"
    except Exception as e:
        return f"设置存储失败: {e}"

