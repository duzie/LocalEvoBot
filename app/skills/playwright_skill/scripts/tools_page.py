import json
import os
import time
from typing import Any, Dict

from langchain_core.tools import tool

from . import _playwright_core as core

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
        return err
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
        return f"已打开网页: {page.url}"
    except Exception as e:
        return f"打开网页失败: {e}"


@tool
def playwright_navigate(url: str):
    """
    导航到新的网页地址。
    
    Args:
        url: 目标网址
    """
    page, err = core._ensure_page(headless=False)
    if err:
        return err
    try:
        page.goto(url, timeout=30000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        return f"已导航到: {page.url}"
    except Exception as e:
        return f"导航失败: {e}"


@tool
def playwright_click(selector: str):
    """
    点击页面元素。
    
    Args:
        selector: CSS 选择器或文本定位 (text=Login)
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        core._page.click(selector, timeout=10000)
        core._maybe_wait_new_page(1200)
        return "已点击元素"
    except Exception as e:
        return f"点击失败: {e}"


@tool
def playwright_type(selector: str, text: str, clear_first: bool = True):
    """
    在指定元素中输入文本。
    
    Args:
        selector: CSS 选择器
        text: 输入文本
        clear_first: 是否先清空 (默认 True)
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        if clear_first:
            core._page.fill(selector, text, timeout=10000)
        else:
            core._page.type(selector, text, timeout=10000)
        return f"已输入文本: {text}"
    except Exception as e:
        return f"输入失败: {e}"


@tool
def playwright_fill(selector: str, text: str):
    """
    在指定元素中填充文本。
    
    Args:
        selector: CSS 选择器
        text: 输入文本
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        core._page.fill(selector, text, timeout=10000)
        return f"已填充文本: {text}"
    except Exception as e:
        return f"填充失败: {e}"


@tool
def playwright_execute_js(script: str):
    """
    在当前页面执行 JavaScript 代码。
    
    Args:
        script: JavaScript 代码
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        wrapped, err = core._wrap_script(script)
        if err:
            return f"执行失败: {err}"
        result = core._page.evaluate(wrapped)
        return f"JS执行结果: {result}"
    except Exception as e:
        return f"执行失败: {e}"


@tool
def playwright_snapshot():
    """
    获取当前页面的 DOM 快照与可交互元素摘要。
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        dom_content = core._page.content()
        title = core._page.title()
        url = core._page.url
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
        elements = core._page.evaluate(elements_script)
        element_summary = f"共找到 {len(elements)} 个可交互元素"
        datagrids = core._page.evaluate(
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
        _ = dom_content
        return f"页面标题: {title}\nURL: {url}\n{element_summary}\n{datagrid_summary}\n\n如需详细DOM结构，请使用 playwright_execute_js 获取特定内容。"
    except Exception as e:
        return f"获取快照失败: {e}"


@tool
def playwright_get_text(selector: str):
    """
    获取元素文本内容。
    
    Args:
        selector: CSS 选择器
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        content = core._page.text_content(selector, timeout=10000)
        return content.strip() if content else ""
    except Exception as e:
        return f"获取文本失败: {e}"


@tool
def extract_easyui_datagrid(selector: str = "#goodsDg", max_rows: int = 200, include_hidden: bool = False):
    """
    抽取 easyui datagrid 的列与行数据。
    
    Args:
        selector: datagrid 选择器
        max_rows: 最多返回行数
        include_hidden: 是否包含隐藏列
    """
    core._sync_latest_page()
    if not core._page:
        return {
            "success": False,
            "message": "浏览器未启动，请先调用 playwright_open",
            "selector": selector,
            "columns": [],
            "rows": [],
            "total": 0,
            "error": "no_page"
        }
    try:
        _wait_datagrid_ready(selector, 10000)

        data = core._page.evaluate(
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
        return {
            "success": True,
            "message": "datagrid 提取成功",
            "selector": data.get("selector") or selector,
            "columns": data.get("columns") or [],
            "rows": data.get("rows") or [],
            "total": data.get("total") or 0,
            "error": None
        }
    except Exception as e:
        diag = {}
        try:
            diag = core._page.evaluate(
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
        return {
            "success": False,
            "message": f"datagrid 提取失败: {str(e)[:80]}",
            "selector": selector,
            "columns": [],
            "rows": [],
            "total": 0,
            "error": str(e),
            "diagnostics": diag
        }


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
    core._sync_latest_page()
    if not core._page:
        return {
            "success": False,
            "message": "浏览器未启动，请先调用 playwright_open",
            "selector": selector,
            "row_index": -1,
            "updated_fields": {},
            "error": "no_page"
        }
    try:
        update_fields = update_fields or {}
        if not selector:
            raise Exception("selector_required")
        if row_index < 0 and (not match_field or match_value is None):
            raise Exception("match_required")
        _wait_datagrid_ready(selector, 10000)
        data = core._page.evaluate(
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
        return {
            "success": True,
            "message": "datagrid 更新成功",
            "selector": data.get("selector") or selector,
            "row_index": data.get("row_index", -1),
            "updated_fields": data.get("updated_fields") or {},
            "error": None
        }
    except Exception as e:
        diag = {}
        try:
            diag = core._page.evaluate(
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
        return {
            "success": False,
            "message": f"datagrid 更新失败: {str(e)[:80]}",
            "selector": selector,
            "row_index": row_index,
            "updated_fields": {},
            "error": str(e),
            "diagnostics": diag
        }


@tool
def playwright_modal_snapshot(root_selector: str = "#updateModal"):
    """
    仅获取指定前景容器（模态框/遮罩/弹层）内的 DOM 片段与可交互元素摘要。
    
    Args:
        root_selector: 前景容器选择器（如 #updateModal / #commonModal / .overlay）
    """
    core._sync_latest_page()
    if not core._page:
        return {
            "success": False,
            "message": "浏览器未启动，请先调用 playwright_open",
            "selector": root_selector,
            "title": "",
            "url": "",
            "elements": [],
            "html": "",
            "error": "no_page"
        }
    try:
        if root_selector and root_selector.strip():
            try:
                core._page.wait_for_selector(root_selector, timeout=10000, state="visible")
            except Exception:
                root_selector = ""
        if not root_selector:
            core._page.wait_for_function(
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
        data = core._page.evaluate(
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
        return {
            "success": True,
            "message": "模态框快照获取成功",
            "selector": data.get("usedSelector") or root_selector,
            "title": core._page.title(),
            "url": core._page.url,
            "elements": data.get("elements") or [],
            "html": data.get("html") or "",
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"模态框快照获取失败: {str(e)[:80]}",
            "selector": root_selector,
            "title": "",
            "url": "",
            "elements": [],
            "html": "",
            "error": str(e)
        }


@tool
def playwright_screenshot(save_path: str):
    """
    保存当前页面截图。
    
    Args:
        save_path: 保存路径 (如 reports/screenshot.png)
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        path = os.path.abspath(save_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        core._page.screenshot(path=path)
        return f"已保存截图: {path}"
    except Exception as e:
        return f"截图失败: {e}"


@tool
def playwright_close():
    """
    关闭浏览器会话。
    """
    try:
        core._reset_browser()
        return "已关闭浏览器"
    except Exception as e:
        return f"关闭失败: {e}"


@tool
def playwright_run_steps(steps: list, screenshot_dir: str = "reports/screenshots"):
    """
    批量执行 Playwright 操作步骤。
    
    Args:
        steps: 步骤列表，每个步骤为 dict，包含 action 和参数
               actions: open, click, type, get_text, screenshot, wait
        screenshot_dir: 失败时截图保存目录
    """
    results = []

    for i, step in enumerate(steps):
        action = step.get("action")
        try:
            if action == "open":
                url = step.get("url")
                headless = step.get("headless", False)
                res = playwright_open(url, headless)
                results.append(f"Step {i+1} [open]: {res}")

            elif action == "click":
                selector = step.get("selector")
                res = playwright_click(selector)
                results.append(f"Step {i+1} [click]: {res}")

            elif action == "type":
                selector = step.get("selector")
                text = step.get("text")
                res = playwright_type(selector, text)
                results.append(f"Step {i+1} [type]: {res}")

            elif action == "fill":
                selector = step.get("selector")
                text = step.get("text")
                res = playwright_fill(selector, text)
                results.append(f"Step {i+1} [fill]: {res}")

            elif action == "get_text":
                selector = step.get("selector")
                text = playwright_get_text(selector)
                results.append(f"Step {i+1} [get_text]: {text}")

            elif action == "navigate":
                url = step.get("url")
                res = playwright_navigate(url)
                results.append(f"Step {i+1} [navigate]: {res}")

            elif action == "screenshot":
                path = step.get("path", f"{screenshot_dir}/step_{i+1}.png")
                res = playwright_screenshot(path)
                results.append(f"Step {i+1} [screenshot]: {res}")

            elif action == "execute_js":
                script = step.get("script")
                res = playwright_execute_js(script)
                results.append(f"Step {i+1} [execute_js]: {res}")

            elif action == "wait":
                sec = step.get("seconds", 1)
                time.sleep(sec)
                results.append(f"Step {i+1} [wait]: Waited {sec}s")

            else:
                results.append(f"Step {i+1} [unknown]: Unknown action {action}")

        except Exception as e:
            err_msg = f"Step {i+1} [{action}] Failed: {e}"
            results.append(err_msg)
            try:
                if core._page:
                    fail_path = os.path.abspath(
                        os.path.join(screenshot_dir, f"fail_step_{i+1}.png")
                    )
                    os.makedirs(os.path.dirname(fail_path), exist_ok=True)
                    core._page.screenshot(path=fail_path)
                    results.append(f"Failure screenshot saved to {fail_path}")
            except Exception:
                pass
            return "\n".join(results)

    return "\n".join(results)
