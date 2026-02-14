from langchain_core.tools import tool, BaseTool
import os
import re
import importlib
import pkgutil
import inspect
from typing import Dict, Any, List, Tuple

def _get_project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

def _find_skill_dir(skill_name: str) -> Tuple[str, str]:
    root = _get_project_root()
    skills_dir = os.path.join(root, "app", "skills", skill_name)
    auto_dir = os.path.join(root, "app", "auto_skills", skill_name)
    if os.path.isdir(skills_dir):
        return skills_dir, "app.skills"
    if os.path.isdir(auto_dir):
        return auto_dir, "app.auto_skills"
    return "", ""

def _read_skill_md(skill_dir: str) -> Dict[str, Any]:
    info = {"entry": "", "description": "", "tools": []}
    path = os.path.join(skill_dir, "skill.md")
    if not os.path.exists(path):
        return info
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception:
        return info
    entry = ""
    desc = ""
    tools = []
    in_tools = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s.lower() == "## entry":
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                entry = lines[j].strip()
        if s.lower() == "## description":
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                desc = lines[j].strip()
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
        desc_item = ""
        if item.startswith("**"):
            end = item.find("**", 2)
            if end != -1:
                name = item[2:end].strip()
                rest = item[end + 2 :].strip()
                if rest.startswith(":"):
                    desc_item = rest[1:].strip()
            else:
                name = item.strip("*").strip()
        else:
            if ":" in item:
                parts = item.split(":", 1)
                name = parts[0].strip()
                desc_item = parts[1].strip()
            else:
                name = item.strip()
        if name:
            tools.append({"name": name, "description": desc_item})
    info["entry"] = entry
    info["description"] = desc
    info["tools"] = tools
    return info

def _discover_tools(entry: str) -> Tuple[List[str], List[str]]:
    errors = []
    tools = []
    try:
        scripts_module = importlib.import_module(entry)
    except Exception as e:
        return [], [f"导入入口失败: {e}"]
    def _collect_from_module(mod):
        for _, obj in inspect.getmembers(mod):
            if isinstance(obj, BaseTool):
                tools.append(obj)
            elif inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                try:
                    tools.append(obj())
                except Exception:
                    pass
    if hasattr(scripts_module, "__path__"):
        for _, module_name, _ in pkgutil.iter_modules(scripts_module.__path__):
            full_module_name = f"{entry}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
                _collect_from_module(module)
            except Exception as e:
                errors.append(f"模块加载失败: {full_module_name} ({e})")
    else:
        _collect_from_module(scripts_module)
    names = []
    for t in tools:
        n = getattr(t, "name", "") or ""
        if n:
            names.append(n)
    return sorted(set(names)), errors

def _load_tools(entry: str) -> Tuple[List[BaseTool], List[str]]:
    errors = []
    tools = []
    try:
        scripts_module = importlib.import_module(entry)
    except Exception as e:
        return [], [f"导入入口失败: {e}"]
    def _collect_from_module(mod):
        for _, obj in inspect.getmembers(mod):
            if isinstance(obj, BaseTool):
                tools.append(obj)
            elif inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                try:
                    tools.append(obj())
                except Exception:
                    pass
    if hasattr(scripts_module, "__path__"):
        for _, module_name, _ in pkgutil.iter_modules(scripts_module.__path__):
            full_module_name = f"{entry}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
                _collect_from_module(module)
            except Exception as e:
                errors.append(f"模块加载失败: {full_module_name} ({e})")
    else:
        _collect_from_module(scripts_module)
    return tools, errors

def _split_requirements(text: str) -> List[str]:
    if not text:
        return []
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s:
            s = re.sub(r"^[\-\*\d\.\)\s]+", "", s).strip()
            if s:
                lines.append(s)
    if len(lines) <= 1:
        raw = lines[0] if lines else text.strip()
        parts = re.split(r"[;；。\.]\s*", raw)
        lines = [p.strip() for p in parts if p.strip()]
    return lines

def _extract_tokens(text: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", text or "")
    return tokens if tokens else [text.strip()]

@tool
def test_skill_loadability(skill_name: str) -> Dict[str, Any]:
    """
    验证技能是否可加载，并检查工具发现与声明的一致性。
    """
    skill_dir, scope = _find_skill_dir(skill_name)
    if not skill_dir:
        return {"ok": False, "error": "技能目录不存在", "skill_name": skill_name}
    info = _read_skill_md(skill_dir)
    entry = info.get("entry") or f"{scope}.{skill_name}.scripts"
    discovered, errors = _discover_tools(entry)
    declared = [t.get("name") for t in info.get("tools") or [] if t.get("name")]
    missing = [n for n in declared if n not in discovered]
    extra = [n for n in discovered if n not in declared]
    ok = not errors
    return {
        "ok": ok,
        "skill_name": skill_name,
        "skill_dir": skill_dir,
        "entry": entry,
        "tools_declared": declared,
        "tools_found": discovered,
        "missing_tools": missing,
        "extra_tools": extra,
        "errors": errors
    }

@tool
def evaluate_skill_requirements(skill_name: str, requirement_text: str) -> Dict[str, Any]:
    """
    对照需求文本评估技能覆盖情况。
    """
    skill_dir, scope = _find_skill_dir(skill_name)
    if not skill_dir:
        return {"ok": False, "error": "技能目录不存在", "skill_name": skill_name}
    info = _read_skill_md(skill_dir)
    entry = info.get("entry") or f"{scope}.{skill_name}.scripts"
    discovered, errors = _discover_tools(entry)
    tools = info.get("tools") or []
    requirement_items = _split_requirements(requirement_text)
    tool_text = " ".join([t.get("name", "") + " " + t.get("description", "") for t in tools])
    desc_text = info.get("description") or ""
    haystack = (desc_text + " " + tool_text).lower()
    results = []
    for item in requirement_items:
        tokens = [t.lower() for t in _extract_tokens(item) if t]
        matched_tools = []
        for tool_item in tools:
            name = tool_item.get("name", "")
            desc = tool_item.get("description", "")
            tool_hay = (name + " " + desc).lower()
            hit = False
            for token in tokens:
                if token and token in tool_hay:
                    hit = True
                    break
            if hit:
                matched_tools.append(name)
        covered = False
        if item.lower() in haystack:
            covered = True
        elif matched_tools:
            covered = True
        results.append({
            "requirement": item,
            "covered": covered,
            "matched_tools": matched_tools
        })
    covered_count = len([r for r in results if r.get("covered")])
    if not results:
        coverage = "unknown"
    elif covered_count == len(results):
        coverage = "passed"
    elif covered_count == 0:
        coverage = "failed"
    else:
        coverage = "partial"
    return {
        "ok": not errors,
        "skill_name": skill_name,
        "entry": entry,
        "tools_found": discovered,
        "coverage": coverage,
        "items": results,
        "errors": errors
    }

def _invoke_tool(tool_obj: BaseTool, args: Dict[str, Any]):
    if hasattr(tool_obj, "invoke"):
        return tool_obj.invoke(args or {})
    return tool_obj(**(args or {}))

@tool
def run_skill_test_cases(skill_name: str, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    执行工具用例，验证技能功能是否符合预期。
    """
    skill_dir, scope = _find_skill_dir(skill_name)
    if not skill_dir:
        return {"ok": False, "error": "技能目录不存在", "skill_name": skill_name}
    entry = _read_skill_md(skill_dir).get("entry") or f"{scope}.{skill_name}.scripts"
    tools, errors = _load_tools(entry)
    tool_map = {getattr(t, "name", ""): t for t in tools if getattr(t, "name", "")}
    results = []
    passed = 0
    for case in (test_cases or []):
        tool_name = (case or {}).get("tool") or ""
        args = (case or {}).get("args") or {}
        expect_contains = (case or {}).get("expect_contains")
        expect_regex = (case or {}).get("expect_regex")
        if not tool_name:
            results.append({"tool": tool_name, "ok": False, "error": "缺少 tool"})
            continue
        tool_obj = tool_map.get(tool_name)
        if not tool_obj:
            results.append({"tool": tool_name, "ok": False, "error": "未找到工具"})
            continue
        try:
            output = _invoke_tool(tool_obj, args)
            out_text = str(output)
            ok = True
            if expect_contains is not None:
                ok = expect_contains in out_text
            if expect_regex:
                ok = bool(re.search(expect_regex, out_text))
            if ok:
                passed += 1
            results.append({
                "tool": tool_name,
                "ok": ok,
                "output": output
            })
        except Exception as e:
            results.append({"tool": tool_name, "ok": False, "error": str(e)})
    return {
        "ok": not errors,
        "skill_name": skill_name,
        "entry": entry,
        "errors": errors,
        "passed": passed,
        "total": len(results),
        "results": results
    }
