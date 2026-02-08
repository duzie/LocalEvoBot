import json

from langchain_core.tools import tool

from . import _playwright_core as core
from ..filter import filter_ax_tree, ax_tree_to_text


def _error(message: str):
    return json.dumps({"error": message}, ensure_ascii=False)


def _format_ax_output(ax_tree, output: str = "text", user_instruction: str = ""):
    mode = (output or "text").lower()
    if mode == "raw":
        return json.dumps(ax_tree, ensure_ascii=False, indent=2)
    if mode == "auto":
        mode = "text"
    if mode == "text":
        text = ax_tree_to_text(ax_tree, user_instruction)
        return text if text else ""
    slim = filter_ax_tree(ax_tree)
    return json.dumps(slim, ensure_ascii=False, indent=2)


@tool
def playwright_accessibility_snapshot(interesting_only: bool = True, output: str = "text", user_instruction: str = ""):
    """
    获取当前页面的 AX 树快照。
    """
    core._sync_latest_page()
    if not core._page:
        return _error("browser_not_started")

    output_mode = (output or "text").lower()
    if output_mode != "text" and hasattr(core._page, "accessibility"):
        try:
            snapshot = core._page.accessibility.snapshot(interesting_only=bool(interesting_only))
            if snapshot:
                return _format_ax_output(snapshot, output, user_instruction)
        except Exception:
            pass

    nodes, err = core._get_cdp_ax_tree(core._page)
    if err:
        return _error(f"ax_tree_failed: {err}")
    return _format_ax_output({"nodes": nodes, "rootRef": None}, output, user_instruction)


@tool
def playwright_accessibility_snapshot_in_frame(frame_name: str = None, frame_url: str = None, frame_selector: str = None, interesting_only: bool = True, output: str = "text", user_instruction: str = ""):
    """
    获取指定 iframe 的 AX 树快照。
    """
    frame, err = core._resolve_frame(frame_name, frame_url, frame_selector)
    if err:
        return _error(err)

    output_mode = (output or "text").lower()
    if output_mode != "text" and hasattr(core._page, "accessibility"):
        try:
            element = frame.frame_element()
            snapshot = core._page.accessibility.snapshot(
                root=element, interesting_only=bool(interesting_only)
            )
            if snapshot:
                return _format_ax_output(snapshot, output, user_instruction)
        except Exception:
            pass

    frame_id = core._get_frame_id_from_cdp(core._page, frame)
    if not frame_id:
        return _error("ax_tree_failed: frame_id_missing")

    nodes, err = core._get_cdp_ax_tree(core._page, frame_id=frame_id)
    if err:
        return _error(f"ax_tree_failed: {err}")
    return _format_ax_output({"nodes": nodes, "rootRef": None}, output, user_instruction)


@tool
def playwright_semantic_snapshot(max_elements: int = 200, include_ax_tree: bool = True, ax_output: str = "text", ax_task: str = ""):
    """
    获取增强语义快照：DOM 结构、可交互元素与页面状态。
    """
    core._sync_latest_page()
    if not core._page:
        return _error("browser_not_started")
    try:
        safe_max = max(1, min(int(max_elements or 200), 2000))
    except Exception:
        safe_max = 200
    try:
        script = f"""
        () => {{
            const maxElements = {safe_max};
            const maxDepth = 8;
            const maxNodes = 800;
            const viewport = {{ width: window.innerWidth, height: window.innerHeight }};
            const readyState = document.readyState;
            const isVisible = (el) => {{
                const style = window.getComputedStyle(el);
                if (!style || style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {{
                    return false;
                }}
                const rect = el.getBoundingClientRect();
                if (!rect || rect.width <= 0 || rect.height <= 0) {{
                    return false;
                }}
                if (rect.bottom < 0 || rect.right < 0 || rect.top > viewport.height || rect.left > viewport.width) {{
                    return false;
                }}
                if (!el.getClientRects().length) {{
                    return false;
                }}
                const cx = Math.min(Math.max(rect.left + rect.width / 2, 0), viewport.width - 1);
                const cy = Math.min(Math.max(rect.top + rect.height / 2, 0), viewport.height - 1);
                const topEl = document.elementFromPoint(cx, cy);
                if (topEl && !el.contains(topEl) && !topEl.contains(el)) {{
                    return false;
                }}
                return true;
            }};
            const getName = (el) => {{
                const aria = el.getAttribute("aria-label");
                if (aria) return aria.trim();
                const labelledBy = el.getAttribute("aria-labelledby");
                if (labelledBy) {{
                    const ref = document.getElementById(labelledBy);
                    if (ref && ref.innerText) return ref.innerText.trim();
                }}
                const title = el.getAttribute("title");
                if (title) return title.trim();
                const alt = el.getAttribute("alt");
                if (alt) return alt.trim();
                const placeholder = el.getAttribute("placeholder");
                if (placeholder) return placeholder.trim();
                const text = (el.innerText || "").trim();
                if (text) return text.slice(0, 200);
                return "";
            }};
            const roleFromTag = (el) => {{
                const role = el.getAttribute("role");
                if (role) return role;
                const tag = el.tagName.toLowerCase();
                if (tag === "a") return "link";
                if (tag === "button") return "button";
                if (tag === "input") {{
                    const t = (el.getAttribute("type") || "").toLowerCase();
                    if (t === "checkbox") return "checkbox";
                    if (t === "radio") return "radio";
                    if (t === "submit" || t === "button" || t === "image") return "button";
                    return "input";
                }}
                if (tag === "select") return "select";
                if (tag === "textarea") return "textarea";
                return "element";
            }};
            const buildSelector = (el) => {{
                if (el.id) return "#" + el.id;
                const testid = el.getAttribute("data-testid") || el.getAttribute("data-test-id") || el.getAttribute("data-qa");
                if (testid) return `[data-testid="${{testid}}"]`;
                if (el.name) return `${{el.tagName.toLowerCase()}}[name="${{el.name}}"]`;
                return el.tagName.toLowerCase();
            }};
            const elements = [];
            const all = Array.from(document.querySelectorAll('a,button,input,textarea,select,[role="button"],[role="link"],[onclick],[tabindex]'));
            for (const el of all) {{
                if (elements.length >= maxElements) break;
                if (el.disabled) continue;
                if (!isVisible(el)) continue;
                const rect = el.getBoundingClientRect();
                elements.push({{
                    ref: elements.length + 1,
                    tag: el.tagName.toLowerCase(),
                    role: roleFromTag(el),
                    name: getName(el),
                    selector: buildSelector(el),
                    bbox: {{ x: rect.left, y: rect.top, width: rect.width, height: rect.height }},
                    visible: true,
                    disabled: !!el.disabled,
                    required: el.required || el.getAttribute("aria-required") === "true",
                    href: el.getAttribute("href") || null,
                    value: el.value !== undefined ? String(el.value).slice(0, 200) : null
                }});
            }}

            let nodeCount = 0;
            const maxText = 120;
            const pickAttrs = (el) => {{
                const attrs = {{}};
                const id = el.getAttribute("id");
                const cls = el.getAttribute("class");
                if (id) attrs.id = id;
                if (cls) attrs.class = cls;
                const role = el.getAttribute("role");
                if (role) attrs.role = role;
                const name = el.getAttribute("name");
                if (name) attrs.name = name;
                const type = el.getAttribute("type");
                if (type) attrs.type = type;
                const href = el.getAttribute("href");
                if (href) attrs.href = href;
                const aria = el.getAttribute("aria-label");
                if (aria) attrs["aria-label"] = aria;
                return attrs;
            }};
            const buildTree = (el, depth) => {{
                if (!el || nodeCount >= maxNodes || depth > maxDepth) return null;
                if (el.nodeType !== 1) return null;
                const tag = el.tagName.toLowerCase();
                const visible = isVisible(el);
                const text = (el.innerText || "").trim();
                const hasText = text && text.length > 0;
                const isInteractive = el.matches('a,button,input,textarea,select,[role="button"],[role="link"],[onclick],[tabindex]');
                if (!visible && !isInteractive && !hasText) return null;
                nodeCount += 1;
                const childNodes = [];
                const children = Array.from(el.children || []);
                for (const child of children) {{
                    if (nodeCount >= maxNodes) break;
                    const childNode = buildTree(child, depth + 1);
                    if (childNode) childNodes.push(childNode);
                }}
                return {{
                    tag,
                    attrs: pickAttrs(el),
                    text: hasText ? text.slice(0, maxText) : null,
                    visible: !!visible,
                    children: childNodes
                }};
            }};
            const domTree = buildTree(document.body, 0);
            return {{
                page: {{
                    url: location.href,
                    title: document.title,
                    ready_state: readyState,
                    viewport,
                    scroll: {{ x: window.scrollX, y: window.scrollY }},
                    interactive_count: elements.length
                }},
                dom_tree: domTree,
                elements
            }};
        }}
        """
        data = core._page.evaluate(script)
        if include_ax_tree:
            nodes, err = core._get_cdp_ax_tree(core._page)
            if err:
                data["ax_tree_error"] = err
            else:
                ax_pack = {"nodes": nodes, "rootRef": None}
                mode = (ax_output or "text").lower()
                if mode == "raw":
                    data["ax_tree"] = nodes
                elif mode == "text":
                    data["ax_text"] = ax_tree_to_text(ax_pack, ax_task)
                else:
                    data["ax_tree"] = filter_ax_tree(ax_pack)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return _error(f"semantic_snapshot_failed: {e}")


@tool
def playwright_ax_text(user_instruction: str = ""):
    """
    获取 AX 树并按任务指令过滤后输出精简文本，降低 token。
    """
    core._sync_latest_page()
    if not core._page:
        return _error("browser_not_started")
    try:
        nodes, err = core._get_cdp_ax_tree(core._page)
        if err:
            return _error(f"ax_tree_failed: {err}")
        ax_pack = {"nodes": nodes, "rootRef": None}
        text = ax_tree_to_text(ax_pack, user_instruction)
        return text if text else ""
    except Exception as e:
        return _error(f"ax_text_failed: {e}")
