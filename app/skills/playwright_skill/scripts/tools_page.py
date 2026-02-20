import json
import os
import time
from datetime import datetime
from typing import Any, Dict

from langchain_core.tools import tool

from . import _playwright_core as core
from web.backend.shared import shared

def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _emit_event(tool_name: str, event: str, **fields):
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))

def _require_page(tool_name: str):
    core._sync_latest_page()
    if not core._page:
        err = _error_payload("browser_not_ready", "浏览器未启动，请先调用 playwright_open", tool=tool_name)
        _emit_event(tool_name, "error", error=err.get("error"))
        return None, err
    return core._page, None

def _wait_datagrid_ready(selector: str = "", timeout_ms: int = 10000):
    core._sync_latest_page()
    if not core._page:
        return
    sel = json.dumps(selector or "")
    try:
        core._page.wait_for_function(
            f"""() => {{
                if (!window.$ || !window.$.fn || !window.$.fn.datagrid) return false;
                const s = {sel};
                if (s && s.trim()) return window.$(s).length > 0;
                return window.$(".datagrid-f, .easyui-datagrid").length > 0;
            }}""",
            timeout=timeout_ms,
        )
    except Exception:
        pass

@tool
def playwright_open(url: str, headless: bool = False, user_data_dir: str = None, extension_dir: str = None):
    """
    使用 Playwright 打开指定网页并保持会话。
    
    Args:
        url: 目标网址
        headless: 是否无头模式 (默认 False，即显示浏览器)
        user_data_dir: 用户数据目录，传入后可持久化登录状态
        extension_dir: 扩展目录，传入后自动加载扩展
    """
    tool_name = "playwright_open"
    if not str(url or "").strip():
        return _error_payload("invalid_args", "url 不能为空", tool=tool_name)
    if not user_data_dir:
        user_data_dir = os.getenv("PLAYWRIGHT_USER_DATA_DIR")
    if not extension_dir:
        extension_dir = os.getenv("PLAYWRIGHT_EXTENSION_DIR")
    if not extension_dir:
        extension_dir = core._get_default_extension_dir()
    if user_data_dir:
        os.makedirs(user_data_dir, exist_ok=True)
    page, err = core._ensure_page(
        headless=headless, user_data_dir=user_data_dir, extension_dir=extension_dir
    )
    if err:
        _emit_event(tool_name, "error", error=str(err))
        return _error_payload("ensure_page_failed", str(err), tool=tool_name)
    try:
        auto = (os.getenv("PLAYWRIGHT_AUTO_LOAD_COOKIES") or "1").strip().lower()
        if auto in ("1", "true", "yes", "on"):
            try:
                from urllib.parse import urlparse

                hostname = urlparse(url).hostname
            except Exception:
                hostname = None
            if hostname:
                core._apply_cookies_for_domain(hostname, base_url=url)
        page.goto(url, timeout=30000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        _emit_event(tool_name, "open", url=page.url)
        return _ok_payload("已打开网页", url=page.url, title=page.title())
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("open_failed", str(e), tool=tool_name)


@tool
def playwright_navigate(url: str):
    """
    导航到新的网页地址。
    
    Args:
        url: 目标网址
    """
    tool_name = "playwright_navigate"
    if not str(url or "").strip():
        return _error_payload("invalid_args", "url 不能为空", tool=tool_name)
    page, err = core._ensure_page(headless=False)
    if err:
        _emit_event(tool_name, "error", error=str(err))
        return _error_payload("ensure_page_failed", str(err), tool=tool_name)
    try:
        page.goto(url, timeout=30000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        _emit_event(tool_name, "navigate", url=page.url)
        return _ok_payload("已导航到", url=page.url, title=page.title())
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("navigate_failed", str(e), tool=tool_name)


@tool
def playwright_click(selector: str):
    """
    点击页面元素。
    
    Args:
        selector: CSS 选择器或文本定位 (text=Login)
    """
    tool_name = "playwright_click"
    if not str(selector or "").strip():
        return _error_payload("invalid_args", "selector 不能为空", tool=tool_name)
    page, err = _require_page(tool_name)
    if err:
        return err
    try:
        page.click(selector, timeout=10000)
        core._maybe_wait_new_page(1200)
        _emit_event(tool_name, "click", selector=selector)
        return _ok_payload("已点击元素")
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("click_failed", str(e), tool=tool_name, selector=selector)


@tool
def playwright_type(selector: str, text: str, clear_first: bool = True):
    """
    在指定元素中输入文本。
    
    Args:
        selector: CSS 选择器
        text: 输入文本
        clear_first: 是否先清空 (默认 True)
    """
    tool_name = "playwright_type"
    if not str(selector or "").strip():
        return _error_payload("invalid_args", "selector 不能为空", tool=tool_name)
    page, err = _require_page(tool_name)
    if err:
        return err
    try:
        if clear_first:
            page.fill(selector, text, timeout=10000)
        else:
            page.type(selector, text, timeout=10000)
        _emit_event(tool_name, "type", selector=selector)
        return _ok_payload("已输入文本")
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("type_failed", str(e), tool=tool_name, selector=selector)


@tool
def playwright_fill(selector: str, text: str):
    """
    在指定元素中填充文本。
    
    Args:
        selector: CSS 选择器
        text: 输入文本
    """
    tool_name = "playwright_fill"
    if not str(selector or "").strip():
        return _error_payload("invalid_args", "selector 不能为空", tool=tool_name)
    page, err = _require_page(tool_name)
    if err:
        return err
    try:
        page.fill(selector, text, timeout=10000)
        _emit_event(tool_name, "fill", selector=selector)
        return _ok_payload("已填充文本")
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("fill_failed", str(e), tool=tool_name, selector=selector)


@tool
def playwright_execute_js(script: str):
    """
    在当前页面执行 JavaScript 代码。
    
    Args:
        script: JavaScript 代码
    """
    tool_name = "playwright_execute_js"
    if not str(script or "").strip():
        return _error_payload("invalid_args", "script 不能为空", tool=tool_name)
    page, err = _require_page(tool_name)
    if err:
        return err
    try:
        wrapped, err = core._wrap_script(script)
        if err:
            _emit_event(tool_name, "error", error=str(err))
            return _error_payload("invalid_script", str(err), tool=tool_name)
        result = page.evaluate(wrapped)
        _emit_event(tool_name, "execute_js")
        return _ok_payload("JS执行结果", result=result)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("execute_js_failed", str(e), tool=tool_name)


@tool
def playwright_snapshot():
    """
    获取当前页面的 DOM 快照与可交互元素摘要。
    """
    tool_name = "playwright_snapshot"
    page, err = _require_page(tool_name)
    if err:
        return err
    try:
        dom_content = page.content()
        title = page.title()
        url = page.url
        elements_script = """
        Array.from(document.querySelectorAll('a, button, input, textarea, select, [role="button"], [role="link"], [onclick], [tabindex]'))
        .filter(el => !el.disabled && el.offsetParent !== null)
        .map(el => ({
            tagName: el.tagName.toLowerCase(),
            id: el.id || null,
            className: el.className || null,
            text: (el.textContent || '').trim().substring(0, 100) || null,
            accessibleName: el.getAttribute('aria-label') || el.getAttribute('title') || null,
            role: el.getAttribute('role') || null,
            selector: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className ? '.' + el.className.split(' ')[0] : '')
        }))
        """
        elements = page.evaluate(elements_script)
        element_summary = f"共找到 {len(elements)} 个可交互元素"
        datagrids = page.evaluate(
            """
            () => {
                const getSelector = (el) => {
                    if (!el) return "";
                    if (el.id) return `#${el.id}`;
                    const cls = (el.className || "").toString().trim().split(/\\s+/).filter(Boolean);
                    if (cls.length) return `${el.tagName.toLowerCase()}.${cls[0]}`;
                    return el.tagName.toLowerCase();
                };
                const list = [];
                if (window.$ && window.$.fn && window.$.fn.datagrid) {
                    const $cands = window.$(".datagrid-f, .easyui-datagrid");
                    $cands.each(function () {
                        const sel = getSelector(this);
                        let rows = 0;
                        try {
                            rows = window.$(this).datagrid("getRows").length;
                        } catch (e) {}
                        list.push({ selector: sel, row_count: rows });
                    });
                } else {
                    const nodes = document.querySelectorAll(".datagrid-f, .easyui-datagrid");
                    nodes.forEach((el) => list.push({ selector: getSelector(el), row_count: 0 }));
                }
                return list;
            }
            """
        )
        dg_list = datagrids or []
        if dg_list:
            selectors = ", ".join([str(d.get("selector") or "") for d in dg_list])
            datagrid_summary = f"发现 {len(dg_list)} 个 datagrid: {selectors}"
        else:
            datagrid_summary = "未发现 datagrid"
        summary = f"页面标题: {title}\nURL: {url}\n{element_summary}\n{datagrid_summary}\n\n如需详细DOM结构，请使用 playwright_execute_js 获取特定内容。"
        _emit_event(tool_name, "snapshot", url=url)
        return _ok_payload(
            summary,
            title=title,
            url=url,
            element_count=len(elements),
            datagrid_count=len(dg_list),
        )
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("snapshot_failed", str(e), tool=tool_name)


@tool
def playwright_get_text(selector: str):
    """
    获取元素文本内容。
    
    Args:
        selector: CSS 选择器
    """
    tool_name = "playwright_get_text"
    if not str(selector or "").strip():
        return _error_payload("invalid_args", "selector 不能为空", tool=tool_name)
    page, err = _require_page(tool_name)
    if err:
        return err
    try:
        content = page.text_content(selector, timeout=10000)
        _emit_event(tool_name, "get_text", selector=selector)
        return _ok_payload("已获取文本", text=(content.strip() if content else ""))
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("get_text_failed", str(e), tool=tool_name, selector=selector)


@tool
def extract_easyui_datagrid(selector: str = "#goodsDg", max_rows: int = 200, include_hidden: bool = False):
    """
    抽取 easyui datagrid 的列与行数据。
    
    Args:
        selector: datagrid 选择器
        max_rows: 最多返回行数
        include_hidden: 是否包含隐藏列
    """
    tool_name = "extract_easyui_datagrid"
    page, err = _require_page(tool_name)
    if err:
        return _error_payload(
            "browser_not_ready",
            "浏览器未启动，请先调用 playwright_open",
            tool=tool_name,
            selector=selector,
            columns=[],
            rows=[],
            total=0,
        )
    try:
        _wait_datagrid_ready(selector, 10000)

        data = page.evaluate(
            """
            (payload) => {
                let sel = payload.selector;
                const maxRows = payload.max_rows;
                const includeHidden = payload.include_hidden;
                if (!window.$) return { error: "jquery_missing" };
                let $el = sel ? window.$(sel) : window.$();
                if (!$el.length) {
                    const $cand = window.$(".datagrid-f, .easyui-datagrid").first();
                    if (!$cand.length) return { error: "selector_not_found" };
                    $el = $cand;
                    sel = $cand.attr("id") ? `#${$cand.attr("id")}` : ".datagrid-f";
                }
                const opts = $el.datagrid("options") || {};
                const flatten = (arr) => {
                    if (!Array.isArray(arr)) return [];
                    const res = [];
                    for (const group of arr) {
                        if (Array.isArray(group)) {
                            for (const item of group) res.push(item);
                        }
                    }
                    return res;
                };
                const columns = flatten(opts.columns || []).map((c) => ({
                    field: c.field || "",
                    title: c.title || c.field || "",
                    hidden: !!c.hidden,
                    align: c.align || ""
                }));
                const frozen = flatten(opts.frozenColumns || []).map((c) => ({
                    field: c.field || "",
                    title: c.title || c.field || "",
                    hidden: !!c.hidden,
                    align: c.align || "",
                    frozen: true
                }));
                let allColumns = columns.concat(frozen);
                if (!includeHidden) {
                    allColumns = allColumns.filter((c) => !c.hidden);
                }
                const rows = ($el.datagrid("getRows") || []).slice(0, Math.max(0, maxRows));
                const data = $el.datagrid("getData") || {};
                const total = typeof data.total === "number" ? data.total : rows.length;
                return { columns: allColumns, rows, total, selector: sel };
            }
            """,
            {
                "selector": selector,
                "max_rows": max_rows,
                "include_hidden": include_hidden,
            },
        )
        if data.get("error"):
            raise Exception(data["error"])
        payload = {
            "success": True,
            "message": "datagrid 抽取成功",
            "selector": data.get("selector") or selector,
            "columns": data.get("columns") or [],
            "rows": data.get("rows") or [],
            "total": data.get("total", 0),
            "error": None
        }
        _emit_event(tool_name, "extract", selector=payload.get("selector"), total=payload.get("total"))
        payload.update(_ok_payload("datagrid 抽取成功", selector=payload.get("selector"), columns=payload.get("columns"), rows=payload.get("rows"), total=payload.get("total")))
        return payload
    except Exception as e:
        diag = {}
        try:
            diag = page.evaluate(
                """
                (sel) => {
                    const result = {
                        has_jquery: !!window.$,
                        has_datagrid: !!(window.$ && window.$.fn && window.$.fn.datagrid),
                        selector_count: 0,
                        candidates: [],
                        selector_error: ""
                    };
                    try {
                        if (sel) result.selector_count = document.querySelectorAll(sel).length;
                    } catch (err) {
                        result.selector_error = String(err);
                    }
                    const list = [];
                    document.querySelectorAll(".datagrid-f, .easyui-datagrid").forEach((el) => {
                        const id = el.id ? `#${el.id}` : "";
                        const cls = (el.className || "").toString().trim().split(/\\s+/).filter(Boolean);
                        const csel = id || (cls.length ? `${el.tagName.toLowerCase()}.${cls[0]}` : el.tagName.toLowerCase());
                        list.push(csel);
                    });
                    result.candidates = list.slice(0, 10);
                    return result;
                }
                """,
                selector,
            )
        except Exception:
            diag = {}
        _emit_event(tool_name, "error", error=str(e), selector=selector)
        payload = {
            "success": False,
            "message": f"datagrid 提取失败: {str(e)[:80]}",
            "selector": selector,
            "columns": [],
            "rows": [],
            "total": 0,
            "error": str(e),
            "diagnostics": diag
        }
        payload.update(_error_payload("datagrid_extract_failed", str(e), tool=tool_name, selector=selector, diagnostics=diag))
        return payload


@tool
def update_easyui_datagrid_row(
    selector: str,
    match_field: str = "",
    match_value: str = "",
    update_fields: Dict[str, Any] = None,
    row_index: int = -1
):
    """
    更新 easyui datagrid 指定行的字段值。
    
    Args:
        selector: datagrid 选择器
        match_field: 用于匹配行的字段名
        match_value: 用于匹配行的字段值（包含匹配）
        update_fields: 要更新的字段字典（键为字段名）
        row_index: 直接指定行索引（优先级高于 match_field/match_value）
    """
    tool_name = "update_easyui_datagrid_row"
    page, err = _require_page(tool_name)
    if err:
        return _error_payload(
            "browser_not_ready",
            "浏览器未启动，请先调用 playwright_open",
            tool=tool_name,
            selector=selector,
            row_index=-1,
            updated_fields={},
        )
    try:
        update_fields = update_fields or {}
        if not selector:
            raise Exception("selector_required")
        if row_index < 0 and (not match_field or match_value is None):
            raise Exception("match_required")
        _wait_datagrid_ready(selector, 10000)
        data = page.evaluate(
            """
            (payload) => {
                let sel = payload.selector;
                const matchField = payload.match_field;
                const matchValue = payload.match_value;
                const updates = payload.update_fields || {};
                const rowIndex = payload.row_index;
                if (!window.$) return { error: "jquery_missing" };
                let $dg = sel ? window.$(sel) : window.$();
                if (!$dg.length) {
                    const $cand = window.$(".datagrid-f, .easyui-datagrid").first();
                    if (!$cand.length) return { error: "selector_not_found" };
                    $dg = $cand;
                    sel = $cand.attr("id") ? `#${$cand.attr("id")}` : ".datagrid-f";
                }
                const rows = $dg.datagrid("getRows") || [];
                let idx = rowIndex;
                if (idx === undefined || idx === null || idx < 0) {
                    idx = -1;
                    for (let i = 0; i < rows.length; i++) {
                        const r = rows[i] || {};
                        const v = r[matchField];
                        if (v !== undefined && v !== null && String(v).includes(String(matchValue))) {
                            idx = i;
                            break;
                        }
                    }
                }
                if (idx < 0 || idx >= rows.length) return { error: "row_not_found", row_index: idx };
                $dg.datagrid("selectRow", idx);
                $dg.datagrid("beginEdit", idx);
                const setEditorValue = (editor, value) => {
                    if (!editor || value === undefined || value === null) return;
                    const $t = window.$(editor.target);
                    const setters = [
                        "numberbox",
                        "textbox",
                        "datebox",
                        "datetimebox",
                        "combobox",
                        "combotree",
                        "combogrid",
                        "timespinner",
                        "numberspinner"
                    ];
                    for (const name of setters) {
                        if (typeof $t[name] === "function") {
                            try {
                                $t[name]("setValue", value);
                                return;
                            } catch (e) {}
                        }
                    }
                    try {
                        $t.val(value);
                    } catch (e) {}
                };
                const updated = {};
                Object.keys(updates).forEach((field) => {
                    const editor = $dg.datagrid("getEditor", { index: idx, field });
                    if (!editor) return;
                    setEditorValue(editor, updates[field]);
                    updated[field] = updates[field];
                });
                $dg.datagrid("endEdit", idx);
                return { row_index: idx, updated_fields: updated, selector: sel };
            }
            """,
            {
                "selector": selector,
                "match_field": match_field,
                "match_value": match_value,
                "update_fields": update_fields,
                "row_index": row_index,
            },
        )
        if data.get("error"):
            raise Exception(data["error"])
        payload = {
            "success": True,
            "message": "datagrid 更新成功",
            "selector": data.get("selector") or selector,
            "row_index": data.get("row_index", -1),
            "updated_fields": data.get("updated_fields") or {},
            "error": None
        }
        _emit_event(tool_name, "update", selector=payload.get("selector"), row_index=payload.get("row_index"))
        payload.update(_ok_payload("datagrid 更新成功", selector=payload.get("selector"), row_index=payload.get("row_index"), updated_fields=payload.get("updated_fields")))
        return payload
    except Exception as e:
        diag = {}
        try:
            diag = page.evaluate(
                """
                (sel) => {
                    const result = {
                        has_jquery: !!window.$,
                        has_datagrid: !!(window.$ && window.$.fn && window.$.fn.datagrid),
                        selector_count: 0,
                        candidates: [],
                        selector_error: ""
                    };
                    try {
                        if (sel) result.selector_count = document.querySelectorAll(sel).length;
                    } catch (err) {
                        result.selector_error = String(err);
                    }
                    const list = [];
                    document.querySelectorAll(".datagrid-f, .easyui-datagrid").forEach((el) => {
                        const id = el.id ? `#${el.id}` : "";
                        const cls = (el.className || "").toString().trim().split(/\\s+/).filter(Boolean);
                        const csel = id || (cls.length ? `${el.tagName.toLowerCase()}.${cls[0]}` : el.tagName.toLowerCase());
                        list.push(csel);
                    });
                    result.candidates = list.slice(0, 10);
                    return result;
                }
                """,
                selector,
            )
        except Exception:
            diag = {}
        _emit_event(tool_name, "error", error=str(e), selector=selector)
        payload = {
            "success": False,
            "message": f"datagrid 更新失败: {str(e)[:80]}",
            "selector": selector,
            "row_index": row_index,
            "updated_fields": {},
            "error": str(e),
            "diagnostics": diag
        }
        payload.update(_error_payload("datagrid_update_failed", str(e), tool=tool_name, selector=selector, diagnostics=diag))
        return payload


@tool
def playwright_modal_snapshot(root_selector: str = "#updateModal"):
    """
    仅获取指定前景容器（模态框/遮罩/弹层）内的 DOM 片段与可交互元素摘要。
    
    Args:
        root_selector: 前景容器选择器（如 #updateModal / #commonModal / .overlay）
    """
    tool_name = "playwright_modal_snapshot"
    page, err = _require_page(tool_name)
    if err:
        return _error_payload(
            "browser_not_ready",
            "浏览器未启动，请先调用 playwright_open",
            tool=tool_name,
            selector=root_selector,
            title="",
            url="",
            elements=[],
            html="",
        )
    try:
        if root_selector and root_selector.strip():
            try:
                page.wait_for_selector(root_selector, timeout=10000, state="visible")
            except Exception:
                root_selector = ""
        if not root_selector:
            page.wait_for_function(
                """() => {
                    const isVisible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    };
                    const list = Array.from(document.querySelectorAll([
                        "[role='dialog']",
                        ".modal",
                        ".ui-dialog",
                        ".lhgdialog",
                        ".easyui-dialog",
                        ".dialog",
                        ".popup",
                        ".drawer",
                        ".panel",
                        ".layui-layer",
                        ".el-dialog",
                        ".ant-modal",
                        ".ivu-modal",
                        ".van-popup",
                        ".weui-dialog",
                        ".modal-backdrop",
                        ".mask",
                        ".overlay",
                        ".backdrop",
                        ".ui-widget-overlay",
                        "[aria-modal='true']",
                        "#commonModal",
                        "#updateModal"
                    ].join(',')));
                    return list.some(isVisible);
                }""",
                timeout=10000,
            )
        data = page.evaluate(
            """
            (sel) => {
                const isVisible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                };
                const interactiveSelector = 'a, button, input, textarea, select, [role="button"], [role="link"], [onclick], [tabindex]';
                const countInteractive = (root) => {
                    return Array.from(root.querySelectorAll(interactiveSelector))
                        .filter(el => !el.disabled && isVisible(el)).length;
                };
                const getZ = (el) => {
                    const z = window.getComputedStyle(el).zIndex || "0";
                    return parseInt(z, 10) || 0;
                };
                const isMask = (el) => {
                    const cls = (el.className || "").toString().toLowerCase();
                    return cls.includes("mask") || cls.includes("overlay") || cls.includes("backdrop");
                };
                const pickModal = () => {
                    if (sel && sel.trim()) {
                        const el = document.querySelector(sel);
                        if (el && isVisible(el)) return { el, used: sel };
                    }
                    const list = Array.from(document.querySelectorAll([
                        "[role='dialog']",
                        ".modal",
                        ".ui-dialog",
                        ".lhgdialog",
                        ".easyui-dialog",
                        ".dialog",
                        ".popup",
                        ".drawer",
                        ".panel",
                        ".layui-layer",
                        ".el-dialog",
                        ".ant-modal",
                        ".ivu-modal",
                        ".van-popup",
                        ".weui-dialog",
                        ".modal-backdrop",
                        ".mask",
                        ".overlay",
                        ".backdrop",
                        ".ui-widget-overlay",
                        "[aria-modal='true']",
                        "#commonModal",
                        "#updateModal"
                    ].join(',')));
                    const extra = Array.from(document.querySelectorAll("body *")).filter((el) => {
                        if (!isVisible(el)) return false;
                        const style = window.getComputedStyle(el);
                        if (style.position !== "fixed" && style.position !== "absolute") return false;
                        const z = getZ(el);
                        return z > 0;
                    });
                    const set = new Set();
                    const candidates = [];
                    for (const el of list.concat(extra)) {
                        if (set.has(el)) continue;
                        set.add(el);
                        candidates.push(el);
                    }
                    let best = null;
                    let bestRank = null;
                    for (const el of candidates) {
                        if (!isVisible(el)) continue;
                        const rect = el.getBoundingClientRect();
                        const area = rect.width * rect.height;
                        const interactive = countInteractive(el);
                        const z = getZ(el);
                        const penalty = isMask(el) && interactive === 0 ? 1 : 0;
                        const rank = [penalty, -z, -interactive, -area];
                        if (!bestRank || rank.toString() < bestRank.toString()) {
                            best = el;
                            bestRank = rank;
                        }
                    }
                    if (!best) return { el: null, used: sel || "" };
                    let used = best.id ? `#${best.id}` : best.tagName.toLowerCase();
                    if (best.className) {
                        const first = best.className.toString().trim().split(/\s+/)[0];
                        if (first) used += "." + first;
                    }
                    return { el: best, used };
                };
                const picked = pickModal();
                const root = picked.el;
                const usedSelector = picked.used || sel || "";
                if (!root) return { error: "modal_not_found", usedSelector };
                const elements = Array.from(root.querySelectorAll(
                    interactiveSelector
                ))
                .filter(el => !el.disabled && isVisible(el))
                .map(el => ({
                    tagName: el.tagName.toLowerCase(),
                    id: el.id || null,
                    className: el.className || null,
                    text: (el.textContent || "").trim().substring(0, 100) || null,
                    accessibleName: el.getAttribute("aria-label") || el.getAttribute("title") || null,
                    role: el.getAttribute("role") || null,
                    selector: el.tagName.toLowerCase()
                        + (el.id ? "#" + el.id : "")
                        + (el.className ? "." + el.className.split(" ")[0] : "")
                }));
                const html = root.outerHTML || "";
                return { elements, html, usedSelector };
            }
            """,
            root_selector,
        )
        if data.get("error"):
            raise Exception(data["error"])
        payload = {
            "success": True,
            "message": "模态框快照获取成功",
            "selector": data.get("usedSelector") or root_selector,
            "title": page.title(),
            "url": page.url,
            "elements": data.get("elements") or [],
            "html": data.get("html") or "",
            "error": None
        }
        _emit_event(tool_name, "snapshot", selector=payload.get("selector"), element_count=len(payload.get("elements") or []))
        payload.update(_ok_payload("模态框快照获取成功", selector=payload.get("selector"), title=payload.get("title"), url=payload.get("url"), elements=payload.get("elements"), html=payload.get("html")))
        return payload
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e), selector=root_selector)
        payload = {
            "success": False,
            "message": f"模态框快照获取失败: {str(e)[:80]}",
            "selector": root_selector,
            "title": "",
            "url": "",
            "elements": [],
            "html": "",
            "error": str(e)
        }
        payload.update(_error_payload("modal_snapshot_failed", str(e), tool=tool_name, selector=root_selector))
        return payload


@tool
def playwright_screenshot(save_path: str):
    """
    保存当前页面截图。
    
    Args:
        save_path: 保存路径 (如 reports/screenshot.png)
    """
    tool_name = "playwright_screenshot"
    if not str(save_path or "").strip():
        return _error_payload("invalid_args", "save_path 不能为空", tool=tool_name)
    page, err = _require_page(tool_name)
    if err:
        return err
    try:
        path = os.path.abspath(save_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        page.screenshot(path=path)
        _emit_event(tool_name, "screenshot", path=path)
        return _ok_payload("已保存截图", path=path)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("screenshot_failed", str(e), tool=tool_name)


@tool
def playwright_close():
    """
    关闭浏览器会话。
    """
    try:
        core._reset_browser()
        _emit_event("playwright_close", "close")
        return _ok_payload("已关闭浏览器")
    except Exception as e:
        _emit_event("playwright_close", "error", error=str(e))
        return _error_payload("close_failed", str(e), tool="playwright_close")


@tool
def playwright_run_steps(steps: list, screenshot_dir: str = "reports/screenshots"):
    """
    批量执行 Playwright 操作步骤。
    
    Args:
        steps: 步骤列表，每个步骤为 dict，包含 action 和参数
               actions: open, click, type, get_text, screenshot, wait
        screenshot_dir: 失败时截图保存目录
    """
    tool_name = "playwright_run_steps"
    results = []

    for i, step in enumerate(steps):
        action = step.get("action")
        try:
            if action == "open":
                url = step.get("url")
                headless = step.get("headless", False)
                res = playwright_open(url, headless)
                results.append({"step": i + 1, "action": "open", "result": res})

            elif action == "click":
                selector = step.get("selector")
                res = playwright_click(selector)
                results.append({"step": i + 1, "action": "click", "result": res})

            elif action == "type":
                selector = step.get("selector")
                text = step.get("text")
                res = playwright_type(selector, text)
                results.append({"step": i + 1, "action": "type", "result": res})

            elif action == "fill":
                selector = step.get("selector")
                text = step.get("text")
                res = playwright_fill(selector, text)
                results.append({"step": i + 1, "action": "fill", "result": res})

            elif action == "get_text":
                selector = step.get("selector")
                text = playwright_get_text(selector)
                results.append({"step": i + 1, "action": "get_text", "result": text})

            elif action == "navigate":
                url = step.get("url")
                res = playwright_navigate(url)
                results.append({"step": i + 1, "action": "navigate", "result": res})

            elif action == "screenshot":
                path = step.get("path", f"{screenshot_dir}/step_{i+1}.png")
                res = playwright_screenshot(path)
                results.append({"step": i + 1, "action": "screenshot", "result": res})

            elif action == "execute_js":
                script = step.get("script")
                res = playwright_execute_js(script)
                results.append({"step": i + 1, "action": "execute_js", "result": res})

            elif action == "wait":
                sec = step.get("seconds", 1)
                time.sleep(sec)
                results.append({"step": i + 1, "action": "wait", "result": _ok_payload("等待完成", seconds=sec)})

            else:
                results.append({"step": i + 1, "action": "unknown", "result": _error_payload("unknown_action", f"Unknown action {action}", tool=tool_name)})

        except Exception as e:
            err_msg = f"{e}"
            results.append({"step": i + 1, "action": action, "result": _error_payload("step_failed", err_msg, tool=tool_name)})
            try:
                if core._page:
                    fail_path = os.path.abspath(
                        os.path.join(screenshot_dir, f"fail_step_{i+1}.png")
                    )
                    os.makedirs(os.path.dirname(fail_path), exist_ok=True)
                    core._page.screenshot(path=fail_path)
                    results.append({"step": i + 1, "action": "screenshot", "result": _ok_payload("已保存失败截图", path=fail_path)})
            except Exception:
                pass
            _emit_event(tool_name, "error", error=err_msg)
            return _error_payload("run_steps_failed", err_msg, tool=tool_name, results=results)

    _emit_event(tool_name, "done", steps=len(results))
    return _ok_payload("批量步骤执行完成", results=results)
