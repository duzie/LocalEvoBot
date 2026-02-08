import json

from langchain_core.tools import tool

from . import _playwright_core as core


@tool
def playwright_start_network_capture(clear_logs: bool = True, max_entries: int = 500):
    """
    开始抓包并记录请求响应日志。
    """
    _, err = core._ensure_page(headless=False)
    if err:
        return err
    try:
        core._network_log_limit = max(50, min(int(max_entries or 500), 5000))
        if clear_logs:
            core._network_logs = []
        core._network_capture_on = True
        core._ensure_network_listeners(core._page)
        return "已开始抓包"
    except Exception as e:
        return f"抓包启动失败: {e}"


@tool
def playwright_stop_network_capture():
    """
    停止抓包。
    """
    core._network_capture_on = False
    return "已停止抓包"


@tool
def playwright_get_network_logs(limit: int = 200, as_json: bool = True):
    """
    获取抓包日志。
    """
    try:
        safe_limit = max(1, min(int(limit or 200), 2000))
        data = core._network_logs[-safe_limit:]
        if as_json:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return "\n".join(
            [f"{d.get('type')} {d.get('method')} {d.get('status','')} {d.get('url')}" for d in data]
        )
    except Exception as e:
        return f"获取抓包日志失败: {e}"


@tool
def playwright_clear_network_logs():
    """
    清空抓包日志。
    """
    core._network_logs = []
    return "已清空抓包日志"

