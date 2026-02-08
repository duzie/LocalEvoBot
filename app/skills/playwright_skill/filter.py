import re


def _normalize_ax_tree(ax_tree):
    if isinstance(ax_tree, list):
        return {"nodes": ax_tree, "rootRef": None}
    if isinstance(ax_tree, dict):
        if "nodes" in ax_tree:
            return {"nodes": ax_tree.get("nodes") or [], "rootRef": ax_tree.get("rootRef")}
        return {"nodes": [], "rootRef": None}
    return {"nodes": [], "rootRef": None}


def _properties_to_map(props):
    if isinstance(props, dict):
        return props
    if isinstance(props, list):
        mapped = {}
        for item in props:
            name = item.get("name")
            value = item.get("value")
            if isinstance(value, dict):
                value = value.get("value")
            if name:
                mapped[name] = value
        return mapped
    return {}


def _get_role(node):
    role = node.get("role", {})
    if isinstance(role, dict):
        name = role.get("name") or role.get("value") or ""
        if isinstance(name, dict):
            name = name.get("value") or ""
        return str(name).lower()
    if isinstance(role, str):
        return role.lower()
    return ""


def _get_name(node):
    name = node.get("name", {})
    if isinstance(name, dict):
        value = name.get("value") or name.get("name") or ""
        if isinstance(value, dict):
            value = value.get("value") or ""
        return str(value)
    if isinstance(name, str):
        return name
    return ""


def _get_ref(node):
    return node.get("ref") or node.get("nodeId") or node.get("backendDOMNodeId") or node.get("id")


def _get_node_id(node):
    return node.get("nodeId") or node.get("ref") or node.get("backendDOMNodeId") or node.get("id")


def _get_parent_id(node):
    return node.get("parentId") or node.get("parentId", None)


def _get_position(node):
    pos = node.get("position", {})
    if isinstance(pos, dict):
        in_view = pos.get("inViewport")
        if isinstance(in_view, dict):
            return in_view.get("value")
        return in_view
    return None


def _get_bounds(node):
    bounds = node.get("bounds")
    if isinstance(bounds, dict):
        x = bounds.get("x")
        y = bounds.get("y")
        w = bounds.get("width")
        h = bounds.get("height")
        if x is not None and y is not None and w is not None and h is not None:
            return (x, y, w, h)
    return None


def _get_value(node):
    value = node.get("value")
    if isinstance(value, dict):
        v = value.get("value")
        if isinstance(v, dict):
            v = v.get("value")
        return v
    return value


def _get_center(bounds):
    if not bounds:
        return None
    return (bounds[0] + bounds[2] / 2, bounds[1] + bounds[3] / 2)


def _join_names(names, limit=6):
    seen = set()
    result = []
    for name in names:
        if not name:
            continue
        key = name.strip()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append(key)
        if len(result) >= limit:
            break
    return " ".join(result)


def _row_text(candidates, center, row_tol):
    if not center:
        return ""
    cx, cy = center
    items = []
    for c in candidates:
        cc = c.get("center")
        if not cc:
            continue
        if abs(cc[1] - cy) <= row_tol and cc[0] < cx:
            items.append(c)
    items.sort(key=lambda x: x["center"][0])
    return _join_names([c["name"] for c in items])


def _col_text(candidates, center, col_tol):
    if not center:
        return ""
    cx, cy = center
    items = []
    for c in candidates:
        cc = c.get("center")
        if not cc:
            continue
        if abs(cc[0] - cx) <= col_tol and cc[1] < cy:
            items.append(c)
    items.sort(key=lambda x: x["center"][1])
    return _join_names([c["name"] for c in items])


def _infer_row_col(bounds, text_candidates):
    center = _get_center(bounds)
    if not center:
        return "", ""
    row_tol = max(8, bounds[3] * 0.6)
    col_tol = max(8, bounds[2] * 0.6)
    row_header = [c for c in text_candidates if c["role"] in ["rowheader", "heading", "label", "statictext"]]
    col_header = [c for c in text_candidates if c["role"] in ["columnheader", "heading", "label", "statictext"]]
    row_text = _row_text(row_header, center, row_tol)
    col_text = _col_text(col_header, center, col_tol)
    if not row_text:
        row_text = _row_text(text_candidates, center, row_tol)
    if not col_text:
        col_text = _col_text(text_candidates, center, col_tol)
    return row_text, col_text


def _pick_text_from_nodes(nodes):
    for n in nodes:
        if not n:
            continue
        role = _get_role(n)
        name = _get_name(n)
        if name:
            if role in ["statictext", "text", "label", "rowheader", "columnheader", "heading"]:
                return name
    for n in nodes:
        if not n:
            continue
        name = _get_name(n)
        if name:
            return name
    return ""


def _semantic_name(node_id, nodes_by_id, parent_map, children_map, text_candidates, bounds):
    node = nodes_by_id.get(node_id)
    if not node:
        return "", "", "", "", ""
    name = _get_name(node)
    if name:
        row_text, col_text = _infer_row_col(bounds, text_candidates)
        return name, "", "", row_text, col_text
    props = _properties_to_map(node.get("properties", {}))
    label = props.get("label") or props.get("description") or props.get("placeholder") or props.get("value")
    if label:
        text = str(label)
        row_text, col_text = _infer_row_col(bounds, text_candidates)
        return text, "属性", text, row_text, col_text
    parent_id = parent_map.get(node_id)
    if parent_id:
        siblings = [nodes_by_id.get(cid) for cid in children_map.get(parent_id, []) if cid != node_id]
        sibling_name = _pick_text_from_nodes(siblings)
        if sibling_name:
            row_text, col_text = _infer_row_col(bounds, text_candidates)
            return sibling_name, "兄弟", sibling_name, row_text, col_text
        parent = nodes_by_id.get(parent_id)
        parent_name = _pick_text_from_nodes([parent])
        if parent_name:
            row_text, col_text = _infer_row_col(bounds, text_candidates)
            return parent_name, "父级", parent_name, row_text, col_text
    current = parent_id
    depth = 0
    while current and depth < 3:
        depth += 1
        parent = nodes_by_id.get(current)
        if parent:
            parent_name = _pick_text_from_nodes([parent])
            if parent_name:
                row_text, col_text = _infer_row_col(bounds, text_candidates)
                return parent_name, "祖先", parent_name, row_text, col_text
            siblings = [nodes_by_id.get(cid) for cid in children_map.get(current, []) if cid != node_id]
            sibling_name = _pick_text_from_nodes(siblings)
            if sibling_name:
                row_text, col_text = _infer_row_col(bounds, text_candidates)
                return sibling_name, "邻近", sibling_name, row_text, col_text
        current = parent_map.get(current)
    row_text, col_text = _infer_row_col(bounds, text_candidates)
    return "", "", "", row_text, col_text


def _format_state(node, props):
    parts = []
    visible = props.get("visible")
    enabled = props.get("enabled")
    if visible is None:
        visible = not bool(node.get("ignored"))
    if enabled is None:
        enabled = True
    parts.append("可见" if visible else "不可见")
    parts.append("可用" if enabled else "不可用")
    checked = props.get("checked")
    if checked is not None:
        parts.append("已勾选" if checked else "未勾选")
    selected = props.get("selected")
    if selected is not None:
        parts.append("已选择" if selected else "未选择")
    expanded = props.get("expanded")
    if expanded is not None:
        parts.append("已展开" if expanded else "未展开")
    pressed = props.get("pressed")
    if pressed is not None:
        parts.append("已按下" if pressed else "未按下")
    required = props.get("required")
    if required is not None:
        parts.append("必填" if required else "非必填")
    invalid = props.get("invalid")
    if invalid is not None:
        parts.append("无效" if invalid else "有效")
    readonly = props.get("readonly")
    if readonly is not None:
        parts.append("只读" if readonly else "可编辑")
    value = props.get("value")
    if value is None:
        value = _get_value(node)
    if value not in [None, ""]:
        parts.append(f"值:{value}")
    return ",".join(parts)


def filter_ax_tree(ax_tree):
    """过滤 AX 树：只保留可交互元素，剔除冗余"""
    keep_roles = [
        "button", "textbox", "combobox", "select", "textarea",
        "link", "checkbox", "radio", "listbox", "option"
    ]
    normalized = _normalize_ax_tree(ax_tree)
    filtered_nodes = []
    for node in normalized.get("nodes", []):
        role = _get_role(node)
        props = _properties_to_map(node.get("properties", {}))
        visible = props.get("visible")
        enabled = props.get("enabled")
        if visible is None:
            visible = not bool(node.get("ignored"))
        if enabled is None:
            enabled = True
        if (role in keep_roles) and visible and enabled:
            filtered_node = {
                "ref": _get_ref(node),
                "role": role,
                "name": _get_name(node),
                "enabled": enabled,
                "visible": visible,
                "position": _get_position(node)
            }
            filtered_nodes.append(filtered_node)
    return {"nodes": filtered_nodes, "rootRef": normalized.get("rootRef")}

# 调用示例：
# original_ax_tree = 你的原始 AX 树数据
# slim_ax_tree = filter_ax_tree(original_ax_tree)
# 再把 slim_ax_tree 传给 AI，token 直接砍到 1/10

def _extract_keywords(user_instruction, task_keywords=None):
    keywords = []
    if task_keywords:
        keywords.extend([k for k in task_keywords if isinstance(k, str) and k.strip()])
    if isinstance(user_instruction, str) and user_instruction.strip():
        text = user_instruction.strip()
        keywords.append(text)
        parts = [p.strip() for p in re.split(r"[\s,，。；;、:：|/\\-]+", text) if p.strip()]
        keywords.extend([p for p in parts if len(p) >= 2])
    seen = set()
    result = []
    for k in keywords:
        key = k.lower()
        if key not in seen:
            seen.add(key)
            result.append(k)
    return result


def filter_by_task(ax_tree, user_instruction, task_keywords=None):
    """按任务过滤：比如“入库单”只保留表单相关元素"""
    slim_ax_tree = filter_ax_tree(ax_tree)
    keywords = _extract_keywords(user_instruction, task_keywords)
    if not keywords:
        return slim_ax_tree
    task_nodes = []
    for node in slim_ax_tree["nodes"]:
        node_name = (node.get("name") or "").lower()
        if any(k.lower() in node_name for k in keywords):
            task_nodes.append(node)
    return {"nodes": task_nodes, "rootRef": slim_ax_tree.get("rootRef")}

# 调用示例：
# user_instruction = "录入入库单：鸡腿 50 个"
# task_ax_tree = filter_by_task(original_ax_tree, user_instruction)

def ax_tree_to_text(ax_tree, user_instruction: str = ""):
    normalized = _normalize_ax_tree(ax_tree)
    nodes = normalized.get("nodes", [])
    if not nodes:
        return ""
    keywords = _extract_keywords(user_instruction)
    nodes_by_id = {}
    parent_map = {}
    children_map = {}
    text_candidates = []
    for node in nodes:
        node_id = _get_node_id(node)
        if node_id is None:
            continue
        nodes_by_id[node_id] = node
        parent_id = node.get("parentId")
        if parent_id is not None:
            parent_map[node_id] = parent_id
            children_map.setdefault(parent_id, []).append(node_id)
        role = _get_role(node)
        name = _get_name(node)
        bounds = _get_bounds(node)
        if name and role in ["statictext", "text", "label", "rowheader", "columnheader", "heading"]:
            text_candidates.append({
                "id": node_id,
                "name": name,
                "role": role,
                "bounds": bounds,
                "center": _get_center(bounds)
            })
    text_lines = []
    for node in nodes:
        role = _get_role(node)
        props = _properties_to_map(node.get("properties", {}))
        visible = props.get("visible")
        enabled = props.get("enabled")
        if visible is None:
            visible = not bool(node.get("ignored"))
        if enabled is None:
            enabled = True
        if role in ["button", "textbox", "combobox", "select", "textarea", "link", "checkbox", "radio", "listbox", "option"]:
            ref = _get_ref(node)
            node_id = _get_node_id(node)
            bounds = _get_bounds(node)
            name, source, source_value, row_text, col_text = _semantic_name(node_id, nodes_by_id, parent_map, children_map, text_candidates, bounds)
            if not name:
                name = _get_name(node)
            state = _format_state(node, props)
            parts = [f"[ref:{ref}] {role}：{name}"]
            if state:
                parts.append(f"状态:{state}")
            if source and source_value:
                parts.append(f"关联:{source}={source_value}")
            if row_text:
                parts.append(f"行:{row_text}")
            if col_text:
                parts.append(f"列:{col_text}")
            if not name and (row_text or col_text):
                parts[0] = f"[ref:{ref}] {role}：{row_text or col_text}"
            if bounds:
                parts.append(f"位置:{bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}")
            line = " | ".join(parts)
            if not keywords or any(k.lower() in line.lower() for k in keywords):
                text_lines.append(line)
        elif "role" in node and "name" in node and "visible" in node and "enabled" in node:
            ref = node.get("ref")
            name = node.get("name")
            state = _format_state(node, props)
            parts = [f"[ref:{ref}] {role}：{name}"]
            if state:
                parts.append(f"状态:{state}")
            line = " | ".join(parts)
            if not keywords or any(k.lower() in line.lower() for k in keywords):
                text_lines.append(line)
    return "\n".join(text_lines)

# 调用示例：
# slim_ax_tree = filter_ax_tree(original_ax_tree)
# ax_text = ax_tree_to_text(slim_ax_tree)
# 传给 AI 的是文本，而非 JSON，token 大幅减少
