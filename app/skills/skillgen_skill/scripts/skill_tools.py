from langchain_core.tools import tool
import os
import sys
import json
import re
import platform
import subprocess
import sqlite3
import hashlib
import uuid
import io
import csv
import py_compile
from datetime import datetime, timezone
try:
    import importlib.metadata as metadata
except Exception:
    metadata = None

RELOAD_SIGNAL = "__RELOAD_SKILLS__"

def _get_project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

def _get_devops_dir():
    base = os.path.join(_get_project_root(), "app", "data", "devops")
    os.makedirs(base, exist_ok=True)
    return base

def _get_db_path():
    return os.path.join(_get_devops_dir(), "change_history.sqlite3")

def _get_snapshots_dir():
    d = os.path.join(_get_devops_dir(), "snapshots")
    os.makedirs(d, exist_ok=True)
    return d

def _get_key_path():
    return os.path.join(_get_devops_dir(), "devops.key")

def _get_actor():
    return (os.getenv("LOCAL_USER_ID") or os.getenv("USER") or os.getenv("USERNAME") or "local_user").strip()

def _get_fernet():
    try:
        from cryptography.fernet import Fernet
    except Exception as e:
        raise RuntimeError(f"缺少依赖 cryptography: {e}")
    env_key = (os.getenv("DEVOPS_ENC_KEY") or os.getenv("AUDIT_LOG_KEY") or "").strip()
    key_path = _get_key_path()
    if env_key:
        key = env_key.encode("utf-8")
    elif os.path.exists(key_path):
        key = open(key_path, "rb").read().strip()
    else:
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
    return Fernet(key)

def _encrypt_bytes(data: bytes) -> bytes:
    if data is None:
        data = b""
    return _get_fernet().encrypt(data)

def _decrypt_bytes(token: bytes) -> bytes:
    if token is None:
        return b""
    return _get_fernet().decrypt(token)

def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data or b"")
    return h.hexdigest()

def _init_change_db():
    path = _get_db_path()
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS change_ops (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                log_blob BLOB NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_change_ops_created ON change_ops(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_change_ops_action ON change_ops(action)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_change_ops_status ON change_ops(status)")
        conn.commit()
    finally:
        conn.close()

def _new_op_id():
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:10]}"

def _write_change_op(op_id: str, actor: str, action: str, status: str, log_data: dict):
    _init_change_db()
    blob = _encrypt_bytes(json.dumps(log_data, ensure_ascii=False).encode("utf-8"))
    conn = sqlite3.connect(_get_db_path())
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO change_ops(id, created_at, actor, action, status, log_blob) VALUES(?, ?, ?, ?, ?, ?)",
            (op_id, log_data.get("created_at") or datetime.now(timezone.utc).isoformat(), actor, action, status, blob),
        )
        conn.commit()
    finally:
        conn.close()

def _read_change_op(op_id: str):
    _init_change_db()
    conn = sqlite3.connect(_get_db_path())
    try:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id, created_at, actor, action, status, log_blob FROM change_ops WHERE id = ?",
            (op_id,),
        ).fetchone()
        if not row:
            return None
        payload = json.loads(_decrypt_bytes(row[5]).decode("utf-8") or "{}")
        return {
            "id": row[0],
            "created_at": row[1],
            "actor": row[2],
            "action": row[3],
            "status": row[4],
            "log": payload,
        }
    finally:
        conn.close()

def _list_ops(limit: int = 10):
    _init_change_db()
    lim = max(1, min(int(limit or 10), 200))
    conn = sqlite3.connect(_get_db_path())
    try:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT id, created_at, actor, action, status, log_blob FROM change_ops ORDER BY created_at DESC LIMIT ?",
            (lim,),
        ).fetchall()
        items = []
        for r in rows:
            try:
                payload = json.loads(_decrypt_bytes(r[5]).decode("utf-8") or "{}")
            except Exception:
                payload = {}
            items.append({
                "id": r[0],
                "created_at": r[1],
                "actor": r[2],
                "action": r[3],
                "status": r[4],
                "log": payload
            })
        return items
    finally:
        conn.close()

def _get_latest_stable_op_id():
    _init_change_db()
    conn = sqlite3.connect(_get_db_path())
    try:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id FROM change_ops WHERE status = ? AND action != ? ORDER BY created_at DESC LIMIT 1",
            ("stable", "rollback"),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()

def _safe_rel_path(abs_path: str):
    root = _get_project_root()
    try:
        rel = os.path.relpath(abs_path, root)
    except Exception:
        rel = abs_path
    rel = rel.replace("\\", "/")
    rel = rel.replace("..", "__")
    return rel

def _snapshot_file(op_id: str, abs_path: str):
    snapshots_dir = _get_snapshots_dir()
    op_dir = os.path.join(snapshots_dir, op_id)
    os.makedirs(op_dir, exist_ok=True)
    rel = _safe_rel_path(abs_path)
    snap_path = os.path.join(op_dir, rel.replace("/", "__") + ".bin")
    before_exists = os.path.exists(abs_path)
    before_bytes = open(abs_path, "rb").read() if before_exists else b""
    enc = _encrypt_bytes(before_bytes)
    with open(snap_path, "wb") as f:
        f.write(enc)
    return {
        "path": abs_path,
        "rel_path": rel,
        "snapshot_path": snap_path,
        "before_exists": before_exists,
        "before_sha256": _sha256_bytes(before_bytes),
    }

def _restore_snapshot(file_item: dict):
    abs_path = file_item.get("path")
    before_exists = bool(file_item.get("before_exists"))
    snap_path = file_item.get("snapshot_path")
    if before_exists:
        enc = open(snap_path, "rb").read()
        raw = _decrypt_bytes(enc)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(raw)
    else:
        if abs_path and os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except Exception:
                pass

def _trim_ops(max_versions: int = 10):
    keep = max(1, min(int(max_versions or 10), 50))
    _init_change_db()
    conn = sqlite3.connect(_get_db_path())
    try:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT id FROM change_ops ORDER BY created_at DESC LIMIT ?",
            (keep,),
        ).fetchall()
        keep_ids = {r[0] for r in rows}
        all_rows = cur.execute("SELECT id FROM change_ops").fetchall()
        remove_ids = [r[0] for r in all_rows if r[0] not in keep_ids]
        if remove_ids:
            cur.executemany("DELETE FROM change_ops WHERE id = ?", [(x,) for x in remove_ids])
            conn.commit()
        for op_id in remove_ids:
            op_dir = os.path.join(_get_snapshots_dir(), op_id)
            if os.path.isdir(op_dir):
                try:
                    for name in os.listdir(op_dir):
                        p = os.path.join(op_dir, name)
                        try:
                            os.remove(p)
                        except Exception:
                            pass
                    os.rmdir(op_dir)
                except Exception:
                    pass
    finally:
        conn.close()

def _validate_python_files(paths: list):
    for p in paths:
        if not p:
            continue
        if str(p).lower().endswith(".py") and os.path.exists(p):
            py_compile.compile(p, doraise=True)

def _rollback_op(op_id: str):
    item = _read_change_op(op_id)
    if not item:
        return f"未找到版本: {op_id}"
    log_data = item.get("log") or {}
    action = item.get("action")
    files = log_data.get("files") or []
    move = log_data.get("move") or {}
    if action == "promote_skill" and move:
        src = move.get("src")
        dst = move.get("dst")
        if dst and src and os.path.exists(dst) and not os.path.exists(src):
            os.makedirs(os.path.dirname(src), exist_ok=True)
            import shutil
            shutil.move(dst, src)
    for f in files:
        _restore_snapshot(f)
    new_log = {
        "id": _new_op_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "actor": _get_actor(),
        "action": "rollback",
        "target_id": op_id,
        "files": files,
    }
    _write_change_op(new_log["id"], new_log["actor"], "rollback", "stable", new_log)
    return f"已回滚到版本: {op_id}"

@tool
def list_change_versions(n: int = 10):
    """
    列出最近的变更版本记录。

    Args:
        n: 返回数量上限
    """
    items = _list_ops(n)
    simplified = []
    for it in items:
        log_data = it.get("log") or {}
        simplified.append({
            "id": it.get("id"),
            "created_at": it.get("created_at"),
            "actor": it.get("actor"),
            "action": it.get("action"),
            "status": it.get("status"),
            "summary": log_data.get("summary") or "",
            "files": [f.get("rel_path") or f.get("path") for f in (log_data.get("files") or [])],
            "target_id": log_data.get("target_id") or ""
        })
    return json.dumps(simplified, ensure_ascii=False, indent=2)

@tool
def rollback_change(change_id: str = None):
    """
    回滚到指定版本或最近稳定版本。

    Args:
        change_id: 目标版本 ID，空则回滚到最近稳定版本
    """
    target = (change_id or "").strip()
    if not target:
        target = _get_latest_stable_op_id()
    if not target:
        return "没有可回滚的稳定版本"
    return _rollback_op(target)

@tool
def search_change_logs(keyword: str, limit: int = 20):
    """
    按关键词搜索变更日志。

    Args:
        keyword: 搜索关键词
        limit: 返回数量上限
    """
    kw = str(keyword or "").strip()
    if not kw:
        return json.dumps([], ensure_ascii=False)
    items = _list_ops(200)
    hits = []
    for it in items:
        if len(hits) >= max(1, min(int(limit or 20), 200)):
            break
        text = json.dumps(it.get("log") or {}, ensure_ascii=False)
        if kw in text:
            hits.append({
                "id": it.get("id"),
                "created_at": it.get("created_at"),
                "actor": it.get("actor"),
                "action": it.get("action"),
                "status": it.get("status"),
                "summary": (it.get("log") or {}).get("summary") or ""
            })
    return json.dumps(hits, ensure_ascii=False, indent=2)

@tool
def export_change_logs(fmt: str = "json", limit: int = 100):
    """
    导出变更日志。

    Args:
        fmt: 导出格式，支持 json 或 csv
        limit: 返回数量上限
    """
    items = _list_ops(limit)
    export_items = []
    for it in items:
        log_data = it.get("log") or {}
        export_items.append({
            "id": it.get("id"),
            "created_at": it.get("created_at"),
            "actor": it.get("actor"),
            "action": it.get("action"),
            "status": it.get("status"),
            "summary": log_data.get("summary") or "",
            "files": [f.get("rel_path") or "" for f in (log_data.get("files") or [])],
            "target_id": log_data.get("target_id") or ""
        })
    f = (fmt or "json").strip().lower()
    if f == "csv":
        out = io.StringIO()
        w = csv.DictWriter(out, fieldnames=["id", "created_at", "actor", "action", "status", "summary", "files", "target_id"])
        w.writeheader()
        for row in export_items:
            row = dict(row)
            row["files"] = "|".join(row.get("files") or [])
            w.writerow(row)
        return out.getvalue()
    return json.dumps(export_items, ensure_ascii=False, indent=2)

@tool
def inspect_environment(max_packages: int = 120):
    """
    获取当前环境与可用技能信息。

    Args:
        max_packages: 最大返回包数量
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    requirements_path = os.path.join(project_root, "requirements.txt")
    requirements = []
    if os.path.exists(requirements_path):
        try:
            with open(requirements_path, "r", encoding="utf-8") as f:
                for line in f.read().splitlines():
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    requirements.append(s)
        except Exception:
            requirements = []
    packages = []
    if metadata:
        try:
            names = []
            for dist in metadata.distributions():
                name = dist.metadata.get("Name") or dist.name
                if name:
                    names.append(name)
            packages = sorted(set(names))
        except Exception:
            packages = []
    if max_packages and max_packages > 0:
        packages = packages[:max_packages]
    def _parse_skill_tools(skill_md_path: str):
        tools_list = []
        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except Exception:
            return tools_list
        in_tools = False
        for line in lines:
            s = line.strip()
            if not in_tools:
                if s.lower() == "## tools":
                    in_tools = True
                continue
            if not s:
                continue
            if s.startswith("## "):
                break
            if not s.startswith("-"):
                continue
            item = s.lstrip("-").strip()
            name = ""
            desc = ""
            if item.startswith("**"):
                end = item.find("**", 2)
                if end != -1:
                    name = item[2:end].strip()
                    rest = item[end + 2 :].strip()
                    if rest.startswith(":"):
                        desc = rest[1:].strip()
                else:
                    name = item.strip("*").strip()
            else:
                if ":" in item:
                    parts = item.split(":", 1)
                    name = parts[0].strip()
                    desc = parts[1].strip()
                else:
                    name = item.strip()
            if not name:
                continue
            tools_list.append({"name": name, "description": desc})
        return tools_list

    skills_root = os.path.join(project_root, "app", "skills")
    auto_skills_root = os.path.join(project_root, "app", "auto_skills")
    skills = []
    auto_skills = []
    tools_info = []
    if os.path.isdir(skills_root):
        for name in os.listdir(skills_root):
            skill_dir = os.path.join(skills_root, name)
            skill_md_path = os.path.join(skill_dir, "skill.md")
            if os.path.isdir(skill_dir) and os.path.exists(skill_md_path):
                skills.append(name)
                for tool_item in _parse_skill_tools(skill_md_path):
                    tools_info.append({
                        "name": tool_item.get("name") or "",
                        "description": tool_item.get("description") or "",
                        "skill": name,
                        "scope": "skills"
                    })
    if os.path.isdir(auto_skills_root):
        for name in os.listdir(auto_skills_root):
            skill_dir = os.path.join(auto_skills_root, name)
            skill_md_path = os.path.join(skill_dir, "skill.md")
            if os.path.isdir(skill_dir) and os.path.exists(skill_md_path):
                auto_skills.append(name)
                for tool_item in _parse_skill_tools(skill_md_path):
                    tools_info.append({
                        "name": tool_item.get("name") or "",
                        "description": tool_item.get("description") or "",
                        "skill": name,
                        "scope": "auto_skills"
                    })
    return json.dumps({
        "os": platform.system(),
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "project_root": project_root,
        "requirements": requirements,
        "installed_packages": packages,
        "skills": sorted(skills),
        "auto_skills": sorted(auto_skills),
        "tools": tools_info
    }, ensure_ascii=False, indent=2)

@tool
def install_packages(packages: list, upgrade: bool = False):
    """
    安装 Python 依赖包。

    Args:
        packages: 依赖包列表，例如 ["python-pptx"]
        upgrade: 是否升级到最新版本
    """
    if not packages:
        return "packages 不能为空"
    if isinstance(packages, str):
        packages = [packages]
    if not isinstance(packages, list):
        return "packages 必须为列表或字符串"
    clean = []
    for item in packages:
        if not item:
            continue
        name = str(item).strip()
        if not name:
            continue
        if any(ch in name for ch in [";", "&", "|", "`"]):
            return f"非法包名: {name}"
        clean.append(name)
    if not clean:
        return "packages 不能为空"
    cmd = [sys.executable, "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")
    cmd.extend(clean)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            return f"安装失败:\n{output.strip()}"
        return f"安装成功:\n{output.strip()}"
    except Exception as e:
        return f"安装失败: {e}"

@tool
def scaffold_skill(skill_name: str, tools: list, description: str = None, overwrite: bool = False):
    """
    生成新 Skill 目录与工具脚手架。

    Args:
        skill_name: 技能名称，例如 "db_skill"
        tools: 工具列表 [{"name": "...", "description": "...", "args": [{"name": "...", "type": "str", "default": null, "description": "..."}]}]
        description: Skill 描述
        overwrite: 是否覆盖已有文件
    """
    if not skill_name:
        return "skill_name 不能为空"
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", skill_name):
        return "skill_name 仅支持字母、数字与下划线，且以字母开头"
    if not isinstance(tools, list) or not tools:
        return "tools 必须为非空列表"
    project_root = _get_project_root()
    skills_root = os.path.join(project_root, "app", "auto_skills")
    skill_dir = os.path.join(skills_root, skill_name)
    scripts_dir = os.path.join(skill_dir, "scripts")
    refs_dir = os.path.join(skill_dir, "references")
    if os.path.exists(skill_dir) and not overwrite:
        return f"技能目录已存在: {skill_dir}"
    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(refs_dir, exist_ok=True)
    actor = _get_actor()
    op_id = _new_op_id()
    snapshot_map = {}
    def _snap(fp: str):
        abs_fp = os.path.abspath(fp)
        if abs_fp not in snapshot_map:
            snapshot_map[abs_fp] = _snapshot_file(op_id, abs_fp)
        return snapshot_map[abs_fp]
    auto_root_init = os.path.join(skills_root, "__init__.py")
    if not os.path.exists(auto_root_init):
        _snap(auto_root_init)
        with open(auto_root_init, "w", encoding="utf-8") as f:
            f.write("")
    skill_init = os.path.join(skill_dir, "__init__.py")
    if not os.path.exists(skill_init):
        _snap(skill_init)
        with open(skill_init, "w", encoding="utf-8") as f:
            f.write("")
    _snap(os.path.join(scripts_dir, "__init__.py"))
    with open(os.path.join(scripts_dir, "__init__.py"), "w", encoding="utf-8") as f:
        f.write("")
    def _format_args(args_list):
        if not args_list:
            return ""
        parts = []
        type_map = {
            "str": "str",
            "int": "int",
            "float": "float",
            "bool": "bool",
            "list": "list",
            "dict": "dict"
        }
        for a in args_list:
            name = a.get("name")
            if not name:
                continue
            t = type_map.get(str(a.get("type") or "str").lower(), "str")
            if "default" in a:
                default = a.get("default")
                if isinstance(default, str):
                    default_repr = json.dumps(default, ensure_ascii=False)
                elif isinstance(default, bool):
                    default_repr = "true" if default else "false"
                elif default is None:
                    default_repr = "None"
                else:
                    default_repr = str(default)
                parts.append(f"{name}: {t} = {default_repr}")
            else:
                parts.append(f"{name}: {t}")
        return ", ".join(parts)
    created = []
    tool_names = []
    for tool in tools:
        tool_name = tool.get("name")
        tool_desc = tool.get("description") or "工具"
        args = tool.get("args") or []
        impl = tool.get("impl")
        if not tool_name or not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", tool_name):
            continue
        tool_names.append(tool_name)
        args_sig = _format_args(args)
        args_doc = "\n".join([f"        {a.get('name')}: {a.get('description') or ''}" for a in args if a.get("name")])
        if args_doc:
            args_doc = f"\n    Args:\n{args_doc}"
        header = [
            "from langchain_core.tools import tool",
            "",
            "@tool",
            f"def {tool_name}({args_sig}):",
            '    """',
            f"    {tool_desc}{args_doc}",
            '    """',
        ]
        body = []
        if impl and isinstance(impl, str) and impl.strip():
            impl_lines = impl.splitlines()
            first_non_empty = ""
            for line in impl_lines:
                if line.strip():
                    first_non_empty = line.strip()
                    break
            is_full_impl = first_non_empty.startswith("def ") or first_non_empty.startswith("@tool") or first_non_empty.startswith("import ") or first_non_empty.startswith("from ")
            if is_full_impl:
                content = impl_lines[:]
                has_tool_import = any(l.strip() == "from langchain_core.tools import tool" for l in content)
                if not has_tool_import:
                    content.insert(0, "from langchain_core.tools import tool")
                has_tool_decorator = any(l.strip().startswith("@tool") for l in content)
                if not has_tool_decorator:
                    insert_idx = 0
                    for idx, line in enumerate(content):
                        if line.strip().startswith("def "):
                            insert_idx = idx
                            break
                    content.insert(insert_idx, "@tool")
                content.append("")
                file_path = os.path.join(scripts_dir, f"{tool_name}.py")
                _snap(file_path)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(content))
                created.append(file_path)
                continue
            for line in impl_lines:
                body.append(f"    {line}")
        else:
            body.append('    return "未实现"')
        content = header + body + [""]
        file_path = os.path.join(scripts_dir, f"{tool_name}.py")
        _snap(file_path)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))
        created.append(file_path)
    skill_md = os.path.join(skill_dir, "skill.md")
    usage_md = os.path.join(refs_dir, "usage.md")
    _snap(skill_md)
    _snap(usage_md)
    skill_desc = description or "自动生成技能"
    skill_md_content = [
        "# Skill",
        "",
        "## Name",
        skill_name,
        "",
        "## Version",
        "1.0.0",
        "",
        "## Description",
        skill_desc,
        "",
        "## Entry",
        f"app.auto_skills.{skill_name}.scripts",
        "",
        "## Tools"
    ] + [f"- {n}" for n in tool_names] + [
        "",
        "## Platforms",
        "- Windows",
        "",
        "## References",
        "- references/usage.md"
    ]
    with open(skill_md, "w", encoding="utf-8") as f:
        f.write("\n".join(skill_md_content))
    usage_md_content = [
        "# Usage",
        "",
        "## Scope",
        skill_desc,
        "",
        "## Tools"
    ] + [f"- {n}" for n in tool_names] + [
        "",
        "## Examples",
        "- 调用对应工具完成任务"
    ]
    with open(usage_md, "w", encoding="utf-8") as f:
        f.write("\n".join(usage_md_content))
    file_items = []
    for abs_fp, item in snapshot_map.items():
        after_bytes = open(abs_fp, "rb").read() if os.path.exists(abs_fp) else b""
        item["after_exists"] = os.path.exists(abs_fp)
        item["after_sha256"] = _sha256_bytes(after_bytes)
        file_items.append(item)
    try:
        _validate_python_files([p for p in created if str(p).lower().endswith(".py")])
        status = "stable"
    except Exception:
        try:
            for it in file_items:
                _restore_snapshot(it)
        except Exception:
            pass
        status = "rolled_back"
    log_data = {
        "id": op_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": "scaffold_skill",
        "status": status,
        "summary": f"scaffold_skill {skill_name}",
        "files": file_items
    }
    _write_change_op(op_id, actor, "scaffold_skill", status, log_data)
    _trim_ops(10)
    return json.dumps({
        "skill_dir": skill_dir,
        "created_files": created + [skill_md, usage_md],
        "tools": tool_names
    }, ensure_ascii=False, indent=2)

@tool
def write_tool_code(file_path: str, code: str = None, content: str = None):
    """
    写入或覆盖工具实现代码。
    """
    final_code = code if code is not None else content
    if not file_path or not final_code:
        return "file_path 与 code/content 不能为空"
    p = os.path.abspath(file_path)
    if not os.path.exists(p):
        return f"文件不存在: {p}"
    actor = _get_actor()
    op_id = _new_op_id()
    snap = _snapshot_file(op_id, p)
    try:
        content_to_write = final_code
        if "def " in content_to_write:
            lines = content_to_write.splitlines()
            has_tool_import = any(l.strip() == "from langchain_core.tools import tool" for l in lines)
            if not has_tool_import:
                lines.insert(0, "from langchain_core.tools import tool")
            if "@tool" not in content_to_write:
                insert_idx = None
                for idx, line in enumerate(lines):
                    if line.strip().startswith("def "):
                        insert_idx = idx
                        break
                if insert_idx is not None:
                    lines.insert(insert_idx, "@tool")
            content_to_write = "\n".join(lines)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content_to_write)
        _validate_python_files([p])
        after_bytes = open(p, "rb").read() if os.path.exists(p) else b""
        snap["after_exists"] = os.path.exists(p)
        snap["after_sha256"] = _sha256_bytes(after_bytes)
        log_data = {
            "id": op_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": "write_tool_code",
            "status": "stable",
            "summary": f"write_tool_code {snap.get('rel_path')}",
            "files": [snap]
        }
        _write_change_op(op_id, actor, "write_tool_code", "stable", log_data)
        _trim_ops(10)
        return f"已写入: {p}"
    except Exception as e:
        try:
            _restore_snapshot(snap)
        except Exception:
            pass
        log_data = {
            "id": op_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": "write_tool_code",
            "status": "rolled_back",
            "summary": f"write_tool_code failed {snap.get('rel_path')}",
            "error": str(e),
            "files": [snap]
        }
        _write_change_op(op_id, actor, "write_tool_code", "rolled_back", log_data)
        _trim_ops(10)
        return f"写入失败(已自动回滚): {e}"

@tool(return_direct=True)
def reload_skills():
    """
    触发技能热加载。调用此工具后，Agent 会立即停止当前回合，等待系统重载完成后在下一轮继续。
    """
    return f"已触发技能重载\n{RELOAD_SIGNAL}"

@tool
def promote_skill(skill_name: str):
    """
    将自动生成的技能从 auto_skills 迁移到 skills 目录（转正）。
    迁移后会自动更新 skill.md 中的 Entry 路径。
    
    Args:
        skill_name: 技能名称
    """
    import shutil
    
    project_root = _get_project_root()
    auto_skills_dir = os.path.join(project_root, "app", "auto_skills")
    skills_dir = os.path.join(project_root, "app", "skills")
    
    src_path = os.path.join(auto_skills_dir, skill_name)
    dst_path = os.path.join(skills_dir, skill_name)
    
    if not os.path.exists(src_path):
        return f"错误：在 auto_skills 中未找到技能 '{skill_name}'"
        
    if os.path.exists(dst_path):
        return f"错误：skills 目录中已存在同名技能 '{skill_name}'"
        
    try:
        # 1. 移动目录
        shutil.move(src_path, dst_path)
        
        # 2. 更新 skill.md 中的 Entry
        skill_md_path = os.path.join(dst_path, "skill.md")
        if os.path.exists(skill_md_path):
            with open(skill_md_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 替换 Entry 路径
            # 原: app.auto_skills.xxx.scripts
            # 新: app.skills.xxx.scripts
            new_content = content.replace(f"app.auto_skills.{skill_name}", f"app.skills.{skill_name}")
            
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        actor = _get_actor()
        op_id = _new_op_id()
        log_data = {
            "id": op_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": "promote_skill",
            "status": "stable",
            "summary": f"promote_skill {skill_name}",
            "move": {"src": src_path, "dst": dst_path},
            "files": []
        }
        _write_change_op(op_id, actor, "promote_skill", "stable", log_data)
        _trim_ops(10)
        return f"成功：技能 '{skill_name}' 已迁移至 app/skills 目录。请调用 reload_skills 使其生效。"
        
    except Exception as e:
        try:
            if os.path.exists(dst_path) and not os.path.exists(src_path):
                shutil.move(dst_path, src_path)
        except Exception:
            pass
        try:
            actor = _get_actor()
            op_id = _new_op_id()
            log_data = {
                "id": op_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "actor": actor,
                "action": "promote_skill",
                "status": "rolled_back",
                "summary": f"promote_skill failed {skill_name}",
                "error": str(e),
                "move": {"src": src_path, "dst": dst_path},
                "files": []
            }
            _write_change_op(op_id, actor, "promote_skill", "rolled_back", log_data)
            _trim_ops(10)
        except Exception:
            pass
        return f"迁移失败: {e}"
