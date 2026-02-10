import json
import os
import platform
import re
import shutil
import time
from datetime import datetime, timezone

_playwright = None
_browser = None
_context = None
_page = None
_persistent_dir = None
_extension_dir = None
_network_capture_on = False
_network_logs = []
_network_log_limit = 500
_network_capture_page = None


def _get_playwright_module():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright, None
    except ImportError:
        return None, "Playwright 未安装。请运行 `pip install playwright` 和 `playwright install`。"


def _append_network_log(item: dict):
    global _network_logs, _network_log_limit
    _network_logs.append(item)
    if len(_network_logs) > _network_log_limit:
        _network_logs = _network_logs[-_network_log_limit:]


def _on_request(request):
    if not _network_capture_on:
        return
    try:
        body = None
        try:
            body = request.post_data()
        except Exception:
            body = None
        if body and len(body) > 2000:
            body = body[:2000] + "...(truncated)"
        _append_network_log(
            {
                "type": "request",
                "method": request.method,
                "url": request.url,
                "headers": dict(request.headers or {}),
                "body": body,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception:
        pass


def _on_response(response):
    if not _network_capture_on:
        return
    try:
        req = response.request
        _append_network_log(
            {
                "type": "response",
                "method": req.method if req else None,
                "url": response.url,
                "status": response.status,
                "headers": dict(response.headers or {}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception:
        pass


def _ensure_network_listeners(page):
    global _network_capture_page
    if page is None:
        return
    if _network_capture_page is page:
        return
    try:
        page.on("request", _on_request)
        page.on("response", _on_response)
        _network_capture_page = page
    except Exception:
        pass


def _sync_latest_page():
    global _context, _page
    if not _context:
        return
    try:
        pages = _context.pages
    except Exception:
        return
    if not pages:
        return
    latest = pages[-1]
    if _page is None or _page != latest:
        try:
            latest.title()
            _page = latest
            if _network_capture_on:
                _ensure_network_listeners(latest)
        except Exception:
            pass


def _maybe_wait_new_page(timeout_ms: int = 1000):
    global _context, _page
    if not _context:
        return
    try:
        new_page = _context.wait_for_event("page", timeout=timeout_ms)
        _page = new_page
        try:
            new_page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        if _network_capture_on:
            _ensure_network_listeners(new_page)
    except Exception:
        pass


def _wrap_script(script: str):
    text = str(script or "").strip()
    if not text:
        return None, "脚本为空"
    if (
        re.match(r"^\s*(\(\s*async\s*\)|\(\s*\)|async\s+function|function)\b", text)
        or text.startswith("() =>")
        or text.startswith("(function")
    ):
        return text, None
    has_return = re.search(r"\breturn\b", text) is not None
    is_multiline = "\n" in text or ";" in text
    if has_return or is_multiline:
        return f"() => {{ {text} }}", None
    return f"() => ( {text} )", None


def _resolve_frame(frame_name: str = None, frame_url: str = None, frame_selector: str = None):
    global _page
    _sync_latest_page()
    if not _page:
        return None, "浏览器未启动，请先调用 playwright_open"
    frame = None
    if frame_name:
        frame = _page.frame(name=frame_name)
    if frame is None and frame_url:
        try:
            for f in _page.frames:
                if re.search(frame_url, f.url or ""):
                    frame = f
                    break
        except Exception:
            frame = None
    if frame is None and frame_selector:
        try:
            handle = _page.query_selector(frame_selector)
            if handle:
                frame = handle.content_frame()
        except Exception:
            frame = None
    if frame is None:
        return None, "未找到匹配的 iframe"
    return frame, None


def _reset_browser():
    global _playwright, _browser, _context, _page, _persistent_dir, _extension_dir
    if _context:
        try:
            _context.close()
        except Exception:
            pass
    if _browser:
        try:
            _browser.close()
        except Exception:
            pass
    if _playwright:
        try:
            _playwright.stop()
        except Exception:
            pass

    _context = None
    _browser = None
    _playwright = None
    _page = None
    _persistent_dir = None
    _extension_dir = None


def _get_default_user_data_dir():
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )
    data_dir = os.path.join(base_dir, "app", "data", "playwright_user_data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _get_default_extension_dir():
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )
    path = os.path.join(base_dir, "web", "extension", "cookie_relay")
    return path if os.path.isdir(path) else None


def _ensure_page(headless: bool = False, user_data_dir: str = None, extension_dir: str = None):
    global _playwright, _browser, _context, _page, _persistent_dir, _extension_dir

    if _page:
        try:
            _sync_latest_page()
            _page.title()
            return _page, None
        except Exception:
            _reset_browser()

    sync_playwright, err = _get_playwright_module()
    if err:
        return None, err

    try:
        if not _playwright:
            _playwright = sync_playwright().start()
        if extension_dir:
            extension_dir = os.path.abspath(os.path.expanduser(extension_dir))
            if not os.path.isdir(extension_dir):
                return None, f"扩展目录不存在: {extension_dir}"
            if headless:
                return None, "扩展模式不支持 headless，请设置 headless=False"
            if not user_data_dir:
                user_data_dir = _get_default_user_data_dir()
        if user_data_dir:
            user_data_dir = os.path.abspath(os.path.expanduser(user_data_dir))
            os.makedirs(user_data_dir, exist_ok=True)
        if extension_dir and _extension_dir and os.path.abspath(_extension_dir) != extension_dir:
            _reset_browser()
        if user_data_dir and _persistent_dir and os.path.abspath(_persistent_dir) != user_data_dir:
            _reset_browser()

        if user_data_dir:
            _persistent_dir = user_data_dir
            _extension_dir = extension_dir
            if not _context:
                args = []
                if extension_dir:
                    args = [
                        f"--disable-extensions-except={extension_dir}",
                        f"--load-extension={extension_dir}",
                    ]
                try:
                    _context = _playwright.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=headless,
                        slow_mo=50,
                        viewport={"width": 1280, "height": 800},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        args=args,
                    )
                except Exception:
                    _reset_browser()
                    _clear_chromium_singletons(user_data_dir)
                    if not _playwright:
                        _playwright = sync_playwright().start()
                    _context = _playwright.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=headless,
                        slow_mo=50,
                        viewport={"width": 1280, "height": 800},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        args=args,
                    )
        else:
            _persistent_dir = None
            _extension_dir = None
            if not _browser:
                _browser = _playwright.chromium.launch(headless=headless, slow_mo=50)
            if not _context:
                _context = _browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )

        if not _page:
            _sync_latest_page()
            if not _page:
                _page = _context.new_page()

        return _page, None
    except Exception as e:
        return None, f"启动浏览器失败: {e}"


def _clear_chromium_singletons(user_data_dir: str):
    if not user_data_dir:
        return
    try:
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            path = os.path.join(user_data_dir, name)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
    except Exception:
        pass


def _get_tesseract_cmd():
    if shutil.which("tesseract"):
        return None

    paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"D:\Program Files\Tesseract-OCR\tesseract.exe",
        r"E:\Program Files\Tesseract-OCR\tesseract.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def _setup_tesseract(language: str = "chi_sim"):
    try:
        import pytesseract
    except ImportError:
        return None, "未安装 pytesseract，请运行 pip install pytesseract pillow"

    cmd = _get_tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    else:
        cmd = shutil.which("tesseract")

    if cmd:
        tessdata_dir = os.path.join(os.path.dirname(cmd), "tessdata")
        if not os.path.exists(tessdata_dir):
            alt_dir = os.path.join(os.path.dirname(cmd), "share", "tessdata")
            if os.path.exists(alt_dir):
                tessdata_dir = alt_dir

        if os.path.exists(tessdata_dir):
            os.environ["TESSDATA_PREFIX"] = os.path.dirname(tessdata_dir)

            if language and "chi_sim" in language:
                lang_file = os.path.join(tessdata_dir, "chi_sim.traineddata")
                if not os.path.exists(lang_file):
                    return (
                        None,
                        f"OCR 识别失败: 缺少中文语言包。请检查 {lang_file} 是否存在。\n解决方法: 重新安装 Tesseract 并勾选 'Additional language data -> Chinese (Simplified)'。",
                    )

    return pytesseract, None


def _get_cookie_store_dir():
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )
    data_dir = os.path.join(base_dir, "app", "data", "cookies")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _sanitize_filename(value: str):
    text = str(value or "").strip().replace(" ", "_")
    cleaned = "".join(ch for ch in text if ch.isalnum() or ch in ("_", "-", "."))
    return cleaned or "default"


def _normalize_same_site(value: str):
    v = (value or "").strip().lower()
    if v in ("lax", "lax_mode", "lax-mode"):
        return "Lax"
    if v in ("strict", "strict_mode", "strict-mode"):
        return "Strict"
    if v in ("none", "no_restriction", "no-restriction", "unspecified"):
        return "None"
    return None


def _load_cookies_from_file(domain: str, base_url: str = None):
    if not domain:
        return None, "domain 不能为空"
    fname = _sanitize_filename(domain) + ".json"
    path = os.path.join(_get_cookie_store_dir(), fname)
    if not os.path.exists(path):
        return None, f"未找到 Cookie 文件: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cookies = data.get("cookies") if isinstance(data, dict) else None
        if not isinstance(cookies, list):
            return None, "Cookie 文件格式不正确"
        normalized = []
        for c in cookies:
            if not isinstance(c, dict):
                continue
            name = c.get("name")
            value = c.get("value")
            if not name or value is None:
                continue
            item = {
                "name": name,
                "value": value,
                "domain": c.get("domain") or domain,
                "path": c.get("path") or "/",
                "httpOnly": bool(c.get("httpOnly")),
                "secure": bool(c.get("secure")),
            }
            if base_url and not item.get("url"):
                try:
                    from urllib.parse import urlparse

                    u = urlparse(base_url)
                    scheme = u.scheme or ("https" if item["secure"] else "http")
                    host = u.hostname or domain
                    path = item["path"] or "/"
                    if not path.startswith("/"):
                        path = "/" + path
                    item["url"] = f"{scheme}://{host}{path}"
                    if "domain" in item:
                        del item["domain"]
                    if "path" in item:
                        del item["path"]
                except Exception:
                    pass
            same_site = _normalize_same_site(c.get("sameSite"))
            if same_site:
                item["sameSite"] = same_site
            expires = c.get("expirationDate")
            if expires:
                try:
                    item["expires"] = float(expires)
                except Exception:
                    pass
            if item.get("url") or (item.get("domain") and item.get("path")):
                normalized.append(item)
        if not normalized:
            return None, "没有可用的 Cookie"
        return normalized, None
    except Exception as e:
        return None, f"加载 Cookie 失败: {e}"


def _apply_cookies_for_domain(domain: str, base_url: str = None):
    cookies, err = _load_cookies_from_file(domain, base_url=base_url)
    if err:
        parts = str(domain).split(".")
        if len(parts) > 2:
            parent = ".".join(parts[-2:])
            cookies, err = _load_cookies_from_file(parent, base_url=base_url)
            if err:
                return err
    _context.add_cookies(cookies)
    return f"已加载 Cookie: {domain} (数量: {len(cookies)})"


def _get_cdp_session(page):
    try:
        return page.context.new_cdp_session(page)
    except Exception:
        return None


def _get_frame_id_from_cdp(page, frame_obj):
    try:
        session = _get_cdp_session(page)
        if not session:
            return None
        tree = session.send("Page.getFrameTree")

        exact = None
        url_matches = []

        def walk(node):
            nonlocal exact, url_matches
            if not node or exact:
                return
            f = node.get("frame", {})
            fid = f.get("id")
            furl = f.get("url")
            fname = f.get("name")

            if fid:
                if frame_obj.name and fname == frame_obj.name and furl == frame_obj.url:
                    exact = fid
                    return
                if furl == frame_obj.url:
                    url_matches.append(fid)

            for child in node.get("childFrames", []) or []:
                walk(child)

        walk(tree.get("frameTree", {}))
        if exact:
            return exact
        if len(url_matches) == 1:
            return url_matches[0]
        return url_matches[0] if url_matches else None
    except Exception:
        return None


def _get_cdp_ax_tree(page, frame_id=None):
    try:
        session = _get_cdp_session(page)
        if not session:
            return None, "无法创建 CDP 会话"
        params = {}
        if frame_id:
            params["frameId"] = frame_id
        res = session.send("Accessibility.getFullAXTree", params)
        return res.get("nodes", []), None
    except Exception as e:
        return None, str(e)
