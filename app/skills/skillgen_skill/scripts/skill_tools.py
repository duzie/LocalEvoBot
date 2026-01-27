from langchain_core.tools import tool
import os
import sys
import json
import re
import platform
try:
    import importlib.metadata as metadata
except Exception:
    metadata = None

RELOAD_SIGNAL = "__RELOAD_SKILLS__"

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
    skills_root = os.path.join(project_root, "app", "skills")
    auto_skills_root = os.path.join(project_root, "app", "auto_skills")
    skills = []
    auto_skills = []
    if os.path.isdir(skills_root):
        for name in os.listdir(skills_root):
            skill_dir = os.path.join(skills_root, name)
            if os.path.isdir(skill_dir) and os.path.exists(os.path.join(skill_dir, "skill.md")):
                skills.append(name)
    if os.path.isdir(auto_skills_root):
        for name in os.listdir(auto_skills_root):
            skill_dir = os.path.join(auto_skills_root, name)
            if os.path.isdir(skill_dir) and os.path.exists(os.path.join(skill_dir, "skill.md")):
                auto_skills.append(name)
    return json.dumps({
        "os": platform.system(),
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "project_root": project_root,
        "requirements": requirements,
        "installed_packages": packages,
        "skills": sorted(skills),
        "auto_skills": sorted(auto_skills)
    }, ensure_ascii=False, indent=2)

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
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    skills_root = os.path.join(project_root, "app", "auto_skills")
    skill_dir = os.path.join(skills_root, skill_name)
    scripts_dir = os.path.join(skill_dir, "scripts")
    refs_dir = os.path.join(skill_dir, "references")
    if os.path.exists(skill_dir) and not overwrite:
        return f"技能目录已存在: {skill_dir}"
    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(refs_dir, exist_ok=True)
    auto_root_init = os.path.join(skills_root, "__init__.py")
    if not os.path.exists(auto_root_init):
        with open(auto_root_init, "w", encoding="utf-8") as f:
            f.write("")
    skill_init = os.path.join(skill_dir, "__init__.py")
    if not os.path.exists(skill_init):
        with open(skill_init, "w", encoding="utf-8") as f:
            f.write("")
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
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))
        created.append(file_path)
    skill_md = os.path.join(skill_dir, "skill.md")
    usage_md = os.path.join(refs_dir, "usage.md")
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
    return json.dumps({
        "skill_dir": skill_dir,
        "created_files": created + [skill_md, usage_md],
        "tools": tool_names
    }, ensure_ascii=False, indent=2)

@tool
def write_tool_code(file_path: str, code: str):
    """
    写入或覆盖工具实现代码。
    """
    if not file_path or not code:
        return "file_path 与 code 不能为空"
    p = os.path.abspath(file_path)
    if not os.path.exists(p):
        return f"文件不存在: {p}"
    try:
        content = code
        if "def " in content:
            lines = content.splitlines()
            has_tool_import = any(l.strip() == "from langchain_core.tools import tool" for l in lines)
            if not has_tool_import:
                lines.insert(0, "from langchain_core.tools import tool")
            if "@tool" not in content:
                insert_idx = None
                for idx, line in enumerate(lines):
                    if line.strip().startswith("def "):
                        insert_idx = idx
                        break
                if insert_idx is not None:
                    lines.insert(insert_idx, "@tool")
            content = "\n".join(lines)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"已写入: {p}"
    except Exception as e:
        return f"写入失败: {e}"

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
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
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
                
        return f"成功：技能 '{skill_name}' 已迁移至 app/skills 目录。请调用 reload_skills 使其生效。"
        
    except Exception as e:
        return f"迁移失败: {e}"
