from langchain_core.tools import tool
import time
import json
import os
from datetime import datetime, timezone

_driver = None
_driver_browser = None

def _load_selenium():
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
    except Exception as e:
        return None, f"未找到 Selenium 依赖: {e}"
    return (webdriver, By, Keys, WebDriverWait, EC, TimeoutException, StaleElementReferenceException), None

def _normalize_browser(browser: str):
    if not browser:
        return "chrome"
    b = browser.lower().strip()
    if b in ["chrome", "googlechrome", "google-chrome"]:
        return "chrome"
    if b in ["edge", "msedge", "microsoftedge", "microsoft-edge"]:
        return "edge"
    return b

def _create_driver(browser: str, headless: bool, user_data_dir: str, profile_dir: str):
    selenium_mod, err = _load_selenium()
    if err:
        return None, err
    webdriver, By, Keys, WebDriverWait, EC, TimeoutException, StaleElementReferenceException = selenium_mod
    if browser == "edge":
        options = webdriver.EdgeOptions()
        options.page_load_strategy = "eager"
        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1280,800")
        if user_data_dir:
            options.add_argument(f"--user-data-dir={user_data_dir}")
        if profile_dir:
            options.add_argument(f"--profile-directory={profile_dir}")
        try:
            driver = webdriver.Edge(options=options)
            driver.set_page_load_timeout(30)
            return driver, None
        except Exception as e:
            return None, f"启动 Edge 失败: {e}"
    if browser == "chrome":
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1280,800")
        if user_data_dir:
            options.add_argument(f"--user-data-dir={user_data_dir}")
        if profile_dir:
            options.add_argument(f"--profile-directory={profile_dir}")
        try:
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(30)
            return driver, None
        except Exception as e:
            return None, f"启动 Chrome 失败: {e}"
    return None, f"不支持的浏览器: {browser}"

def _ensure_driver(browser: str, headless: bool, user_data_dir: str, profile_dir: str):
    global _driver, _driver_browser
    browser = _normalize_browser(browser)
    if _driver is not None and _driver_browser != browser:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None
    if _driver is None:
        driver, err = _create_driver(browser, headless, user_data_dir, profile_dir)
        if err:
            return None, err
        _driver = driver
        _driver_browser = browser
    return _driver, None

def _reset_driver():
    global _driver, _driver_browser
    if _driver is not None:
        try:
            _driver.quit()
        except Exception:
            pass
    _driver = None
    _driver_browser = None

def _is_invalid_session(err: Exception):
    return "invalid session id" in str(err).lower()

def _get_by(selector_type: str):
    selenium_mod, err = _load_selenium()
    if err:
        return None, err
    webdriver, By, Keys, WebDriverWait, EC, TimeoutException, StaleElementReferenceException = selenium_mod
    st = (selector_type or "css").lower().strip()
    if st in ["css", "css_selector"]:
        return By.CSS_SELECTOR, None
    if st == "xpath":
        return By.XPATH, None
    if st == "id":
        return By.ID, None
    if st == "name":
        return By.NAME, None
    if st in ["class", "class_name"]:
        return By.CLASS_NAME, None
    if st in ["tag", "tag_name"]:
        return By.TAG_NAME, None
    if st == "link_text":
        return By.LINK_TEXT, None
    if st == "partial_link_text":
        return By.PARTIAL_LINK_TEXT, None
    return None, f"不支持的 selector_type: {selector_type}"

def _wait_for(selector: str, selector_type: str, wait_sec: int, condition: str = "visible"):
    selenium_mod, err = _load_selenium()
    if err:
        return None, err
    webdriver, By, Keys, WebDriverWait, EC, TimeoutException, StaleElementReferenceException = selenium_mod
    by, err = _get_by(selector_type)
    if err:
        return None, err
    if wait_sec is None or wait_sec <= 0:
        wait_sec = 1
    if condition == "clickable":
        cond = EC.element_to_be_clickable((by, selector))
    elif condition == "presence":
        cond = EC.presence_of_element_located((by, selector))
    else:
        cond = EC.visibility_of_element_located((by, selector))
    try:
        elem = WebDriverWait(_driver, wait_sec).until(cond)
        return elem, None
    except Exception as e:
        return None, f"等待元素失败: {e}"

def _get_driver():
    if _driver is None:
        return None, "浏览器未启动，请先调用 selenium_open_url"
    return _driver, None

def _save_report(report: dict, report_path: str):
    if not report_path:
        return None
    path = os.path.abspath(report_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=2))
    return path

def _take_screenshot(save_path: str):
    driver, err = _get_driver()
    if err:
        return None, err
    try:
        path = os.path.abspath(save_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        driver.save_screenshot(path)
        return path, None
    except Exception as e:
        return None, f"截图失败: {e}"

def _retry_click(selector: str, selector_type: str, wait_sec: int, retries: int = 2):
    selenium_mod, err = _load_selenium()
    if err:
        return False, err, None
    webdriver, By, Keys, WebDriverWait, EC, TimeoutException, StaleElementReferenceException = selenium_mod
    last_err = None
    for _ in range(retries + 1):
        elem, err = _wait_for(selector, selector_type, wait_sec, condition="clickable")
        if err:
            return False, err, None
        try:
            elem.click()
            return True, "已点击元素", None
        except Exception as e:
            if isinstance(e, StaleElementReferenceException):
                last_err = e
                time.sleep(0.2)
                continue
            return False, f"点击失败: {e}", None
    return False, f"点击失败: 元素已失效 {last_err}", None

def _retry_type(selector: str, text: str, selector_type: str, clear_first: bool, press_enter: bool, wait_sec: int, retries: int = 2):
    selenium_mod, err = _load_selenium()
    if err:
        return False, err, None
    webdriver, By, Keys, WebDriverWait, EC, TimeoutException, StaleElementReferenceException = selenium_mod
    last_err = None
    for _ in range(retries + 1):
        elem, err = _wait_for(selector, selector_type, wait_sec, condition="visible")
        if err:
            return False, err, None
        try:
            if clear_first:
                elem.clear()
            elem.send_keys(text)
            if press_enter:
                elem.send_keys(Keys.ENTER)
            return True, "已输入文本", None
        except Exception as e:
            if isinstance(e, StaleElementReferenceException):
                last_err = e
                time.sleep(0.2)
                continue
            return False, f"输入失败: {e}", None
    return False, f"输入失败: 元素已失效 {last_err}", None

def _retry_get_text(selector: str, selector_type: str, wait_sec: int, retries: int = 2):
    selenium_mod, err = _load_selenium()
    if err:
        return False, err, None
    webdriver, By, Keys, WebDriverWait, EC, TimeoutException, StaleElementReferenceException = selenium_mod
    last_err = None
    for _ in range(retries + 1):
        elem, err = _wait_for(selector, selector_type, wait_sec, condition="presence")
        if err:
            return False, err, None
        try:
            text = (elem.text or "").strip()
            if not text:
                text = (elem.get_attribute("value") or "").strip()
            return True, "已读取文本", text
        except Exception as e:
            if isinstance(e, StaleElementReferenceException):
                last_err = e
                time.sleep(0.2)
                continue
            return False, f"读取文本失败: {e}", None
    return False, f"读取文本失败: 元素已失效 {last_err}", None

def _retry_assert_text(selector: str, expected: str, selector_type: str, match: str, wait_sec: int, retries: int = 2):
    ok, msg, actual = _retry_get_text(selector, selector_type, wait_sec, retries=retries)
    if not ok:
        return False, msg, None
    if match == "equals":
        if actual == expected:
            return True, "断言通过", None
        return False, f"断言失败: 期望等于 '{expected}', 实际 '{actual}'", actual
    if expected in actual:
        return True, "断言通过", None
    return False, f"断言失败: 期望包含 '{expected}', 实际 '{actual}'", actual

@tool
def selenium_open_url(url: str, browser: str = "chrome", headless: bool = False, user_data_dir: str = None, profile_dir: str = None, page_load_timeout: int = 20):
    """
    打开指定网页并保持浏览器会话。

    Args:
        url: 目标网址
        browser: 浏览器类型，chrome 或 edge
        headless: 是否无头模式
        user_data_dir: 浏览器用户数据目录
        profile_dir: 浏览器配置目录
        page_load_timeout: 页面加载超时秒数
    """
    driver, err = _ensure_driver(browser, headless, user_data_dir, profile_dir)
    if err:
        return err
    try:
        if page_load_timeout and page_load_timeout > 0:
            driver.set_page_load_timeout(page_load_timeout)
        driver.get(url)
        return f"已打开网页: {driver.current_url}"
    except Exception as e:
        if _is_invalid_session(e):
            _reset_driver()
            driver, err = _ensure_driver(browser, headless, user_data_dir, profile_dir)
            if err:
                return err
            try:
                if page_load_timeout and page_load_timeout > 0:
                    driver.set_page_load_timeout(page_load_timeout)
                driver.get(url)
                return f"已重新打开网页: {driver.current_url}"
            except Exception as retry_err:
                return f"打开网页失败: {retry_err}"
        selenium_mod, load_err = _load_selenium()
        if not load_err:
            webdriver, By, Keys, WebDriverWait, EC, TimeoutException = selenium_mod
            if isinstance(e, TimeoutException):
                try:
                    driver.execute_script("window.stop();")
                except Exception:
                    pass
                return f"页面加载超时，已停止加载: {url}"
        return f"打开网页失败: {e}"

@tool
def selenium_click(selector: str, selector_type: str = "css", wait_sec: int = 10):
    """
    点击页面元素。

    Args:
        selector: 元素选择器
        selector_type: css 或 xpath 等
        wait_sec: 等待元素可点击的超时秒数
    """
    if _driver is None:
        return "浏览器未启动，请先调用 selenium_open_url"
    ok, msg, _ = _retry_click(selector, selector_type, wait_sec)
    return msg

@tool
def selenium_type(selector: str, text: str, selector_type: str = "css", clear_first: bool = True, press_enter: bool = False, wait_sec: int = 10):
    """
    在指定元素中输入文本。

    Args:
        selector: 元素选择器
        text: 输入文本
        selector_type: css 或 xpath 等
        clear_first: 是否先清空输入框
        press_enter: 输入后是否回车
        wait_sec: 等待元素可见的超时秒数
    """
    if _driver is None:
        return "浏览器未启动，请先调用 selenium_open_url"
    ok, msg, _ = _retry_type(selector, text, selector_type, clear_first, press_enter, wait_sec)
    return msg

@tool
def selenium_get_text(selector: str, selector_type: str = "css", wait_sec: int = 10):
    """
    获取元素文本内容。

    Args:
        selector: 元素选择器
        selector_type: css 或 xpath 等
        wait_sec: 等待元素出现的超时秒数
    """
    if _driver is None:
        return "浏览器未启动，请先调用 selenium_open_url"
    ok, msg, text = _retry_get_text(selector, selector_type, wait_sec)
    if ok:
        return text
    return msg

@tool
def selenium_close():
    """
    关闭浏览器会话。
    """
    global _driver, _driver_browser
    if _driver is None:
        return "浏览器未启动"
    try:
        _driver.quit()
        _driver = None
        _driver_browser = None
        return "已关闭浏览器"
    except Exception as e:
        return f"关闭失败: {e}"

@tool
def selenium_wait_for(selector: str, selector_type: str = "css", condition: str = "visible", wait_sec: int = 10):
    """
    等待元素满足条件。

    Args:
        selector: 元素选择器
        selector_type: css 或 xpath 等
        condition: visible, presence, clickable
        wait_sec: 等待超时秒数
    """
    if _driver is None:
        return "浏览器未启动，请先调用 selenium_open_url"
    elem, err = _wait_for(selector, selector_type, wait_sec, condition=condition)
    if err:
        return err
    return "已满足等待条件"

@tool
def selenium_assert_text(selector: str, expected: str, selector_type: str = "css", match: str = "contains", wait_sec: int = 10):
    """
    断言元素文本内容。

    Args:
        selector: 元素选择器
        expected: 期望文本
        selector_type: css 或 xpath 等
        match: contains 或 equals
        wait_sec: 等待超时秒数
    """
    if _driver is None:
        return "浏览器未启动，请先调用 selenium_open_url"
    ok, msg, _ = _retry_assert_text(selector, expected, selector_type, match, wait_sec)
    return msg

@tool
def selenium_assert_title(expected: str, match: str = "contains"):
    """
    断言页面标题。

    Args:
        expected: 期望标题
        match: contains 或 equals
    """
    if _driver is None:
        return "浏览器未启动，请先调用 selenium_open_url"
    try:
        actual = (_driver.title or "").strip()
        if match == "equals":
            if actual == expected:
                return "断言通过"
            return f"断言失败: 期望等于 '{expected}', 实际 '{actual}'"
        if expected in actual:
            return "断言通过"
        return f"断言失败: 期望包含 '{expected}', 实际 '{actual}'"
    except Exception as e:
        return f"断言失败: {e}"

@tool
def selenium_take_screenshot(save_path: str):
    """
    保存当前页面截图。

    Args:
        save_path: 保存路径
    """
    path, err = _take_screenshot(save_path)
    if err:
        return err
    return f"已保存截图: {path}"

def _run_step(step: dict, default_wait: int):
    action = (step.get("action") or "").strip()
    if not action:
        return False, "缺少 action", None
    action = action.lower()
    if action == "open_url":
        url = step.get("url")
        if not url:
            return False, "缺少 url", None
        browser = step.get("browser", "chrome")
        headless = bool(step.get("headless", False))
        user_data_dir = step.get("user_data_dir")
        profile_dir = step.get("profile_dir")
        page_load_timeout = step.get("page_load_timeout", 20)
        driver, err = _ensure_driver(browser, headless, user_data_dir, profile_dir)
        if err:
            return False, err, None
        try:
            if page_load_timeout and page_load_timeout > 0:
                driver.set_page_load_timeout(page_load_timeout)
            driver.get(url)
            return True, f"已打开网页: {driver.current_url}", None
        except Exception as e:
            if _is_invalid_session(e):
                _reset_driver()
                driver, err = _ensure_driver(browser, headless, user_data_dir, profile_dir)
                if err:
                    return False, err, None
                try:
                    if page_load_timeout and page_load_timeout > 0:
                        driver.set_page_load_timeout(page_load_timeout)
                    driver.get(url)
                    return True, f"已重新打开网页: {driver.current_url}", None
                except Exception as retry_err:
                    return False, f"打开网页失败: {retry_err}", None
            selenium_mod, load_err = _load_selenium()
            if not load_err:
                webdriver, By, Keys, WebDriverWait, EC, TimeoutException, StaleElementReferenceException = selenium_mod
                if isinstance(e, TimeoutException):
                    try:
                        driver.execute_script("window.stop();")
                    except Exception:
                        pass
                    return True, f"页面加载超时，已停止加载: {url}", None
            return False, f"打开网页失败: {e}", None
    if action == "click":
        selector = step.get("selector")
        selector_type = step.get("selector_type", "css")
        wait_sec = step.get("wait_sec", default_wait)
        if not selector:
            return False, "缺少 selector", None
        if _driver is None:
            return False, "浏览器未启动", None
        ok, msg, _ = _retry_click(selector, selector_type, wait_sec)
        return ok, msg, None
    if action == "type":
        selector = step.get("selector")
        text = step.get("text", "")
        selector_type = step.get("selector_type", "css")
        clear_first = bool(step.get("clear_first", True))
        press_enter = bool(step.get("press_enter", False))
        wait_sec = step.get("wait_sec", default_wait)
        if not selector:
            return False, "缺少 selector", None
        if _driver is None:
            return False, "浏览器未启动", None
        ok, msg, _ = _retry_type(selector, text, selector_type, clear_first, press_enter, wait_sec)
        return ok, msg, None
    if action == "wait_for":
        selector = step.get("selector")
        selector_type = step.get("selector_type", "css")
        condition = step.get("condition", "visible")
        wait_sec = step.get("wait_sec", default_wait)
        if not selector:
            return False, "缺少 selector", None
        if _driver is None:
            return False, "浏览器未启动", None
        elem, err = _wait_for(selector, selector_type, wait_sec, condition=condition)
        if err:
            return False, err, None
        return True, "已满足等待条件", None
    if action == "assert_text":
        selector = step.get("selector")
        expected = step.get("expected", "")
        selector_type = step.get("selector_type", "css")
        match = step.get("match", "contains")
        wait_sec = step.get("wait_sec", default_wait)
        if not selector:
            return False, "缺少 selector", None
        if _driver is None:
            return False, "浏览器未启动", None
        ok, msg, actual = _retry_assert_text(selector, expected, selector_type, match, wait_sec)
        return ok, msg, actual
    if action == "assert_title":
        expected = step.get("expected", "")
        match = step.get("match", "contains")
        if _driver is None:
            return False, "浏览器未启动", None
        actual = (_driver.title or "").strip()
        if match == "equals":
            if actual == expected:
                return True, "断言通过", None
            return False, f"断言失败: 期望等于 '{expected}', 实际 '{actual}'", actual
        if expected in actual:
            return True, "断言通过", None
        return False, f"断言失败: 期望包含 '{expected}', 实际 '{actual}'", actual
    if action == "get_text":
        selector = step.get("selector")
        selector_type = step.get("selector_type", "css")
        wait_sec = step.get("wait_sec", default_wait)
        if not selector:
            return False, "缺少 selector", None
        if _driver is None:
            return False, "浏览器未启动", None
        ok, msg, actual = _retry_get_text(selector, selector_type, wait_sec)
        return ok, msg, actual
    if action == "execute_script":
        script = step.get("script")
        args = step.get("args", [])
        if not script:
            return False, "缺少 script", None
        if _driver is None:
            return False, "浏览器未启动", None
        try:
            result = _driver.execute_script(script, *args)
            return True, "脚本执行成功", result
        except Exception as e:
            return False, f"脚本执行失败: {e}", None
    if action == "take_screenshot":
        save_path = step.get("save_path")
        if not save_path:
            return False, "缺少 save_path", None
        path, err = _take_screenshot(save_path)
        if err:
            return False, err, None
        return True, f"已保存截图: {path}", None
    if action == "sleep":
        seconds = step.get("seconds", 1)
        try:
            time.sleep(float(seconds))
            return True, "已等待", None
        except Exception as e:
            return False, f"等待失败: {e}", None
    return False, f"不支持的 action: {action}", None

@tool
def selenium_run_steps(steps: list, browser: str = "chrome", headless: bool = False, user_data_dir: str = None, profile_dir: str = None, report_path: str = None, stop_on_fail: bool = True, screenshot_on_fail: bool = True, default_wait: int = 10, screenshot_dir: str = "reports\\screenshots"):
    """
    执行一组测试步骤并输出报告。

    Args:
        steps: 步骤列表，每步包含 action 与参数
        browser: 浏览器类型，chrome 或 edge
        headless: 是否无头模式
        user_data_dir: 浏览器用户数据目录
        profile_dir: 浏览器配置目录
        report_path: 报告保存路径
        stop_on_fail: 失败是否立即停止
        screenshot_on_fail: 失败时是否截图
        default_wait: 默认等待秒数
        screenshot_dir: 失败截图保存目录
    """
    started_at = datetime.now(timezone.utc).isoformat()
    results = []
    overall_status = "passed"
    if not isinstance(steps, list):
        return "steps 必须为列表"
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            results.append({
                "index": index,
                "status": "failed",
                "action": None,
                "message": "步骤必须为对象",
                "extra": None,
                "screenshot": None
            })
            overall_status = "failed"
            if stop_on_fail:
                break
            continue
        step_action = step.get("action")
        if step_action == "open_url":
            step["browser"] = step.get("browser", browser)
            step["headless"] = step.get("headless", headless)
            step["user_data_dir"] = step.get("user_data_dir", user_data_dir)
            step["profile_dir"] = step.get("profile_dir", profile_dir)
        ok, message, extra = _run_step(step, default_wait)
        screenshot = None
        if not ok:
            overall_status = "failed"
            if screenshot_on_fail and _driver is not None:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
                filename = f"step_{index}_{ts}.png"
                path = os.path.join(screenshot_dir, filename)
                screenshot, _ = _take_screenshot(path)
        results.append({
            "index": index,
            "status": "passed" if ok else "failed",
            "action": step_action,
            "message": message,
            "extra": extra,
            "screenshot": screenshot
        })
        if not ok and stop_on_fail:
            break
    ended_at = datetime.now(timezone.utc).isoformat()
    duration_sec = None
    try:
        start_dt = datetime.fromisoformat(started_at)
        end_dt = datetime.fromisoformat(ended_at)
        duration_sec = (end_dt - start_dt).total_seconds()
    except Exception:
        duration_sec = None
    report = {
        "status": overall_status,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_sec": duration_sec,
        "steps": results
    }
    saved_path = _save_report(report, report_path)
    if saved_path:
        report["report_path"] = saved_path
    return json.dumps(report, ensure_ascii=False, indent=2)
