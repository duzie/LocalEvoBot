import importlib
import pkgutil
import inspect
import os
import sys
from typing import List, Dict, Any
from langchain_core.tools import BaseTool

def _read_skill_entry(skill_md_path: str):
    try:
        with open(skill_md_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]
    except Exception:
        return None
    for idx, line in enumerate(lines):
        if line.lower() == "## entry":
            j = idx + 1
            while j < len(lines) and not lines[j]:
                j += 1
            if j < len(lines):
                entry = lines[j].strip()
                return entry or None
            return None
    return None

def load_skills(package_name: str = "app.skills", auto_package_name: str = "app.auto_skills") -> List[BaseTool]:
    """
    动态加载指定包下的所有 Skills (BaseTool 的实例或子类)。
    
    Args:
        package_name: 存放 skills 的包名，例如 "app.skills"
        auto_package_name: 存放自动生成 skills 的包名，例如 "app.auto_skills"
        
    Returns:
        List[BaseTool]: 加载到的所有 Tool 实例列表
    """
    def _load_from_package(pkg_name: str) -> List[BaseTool]:
        tools = []
        if auto_package_name and pkg_name == auto_package_name:
            # 强制清理父包缓存，确保 pkgutil 能扫描到新目录
            if pkg_name in sys.modules:
                del sys.modules[pkg_name]
            importlib.invalidate_caches()
        try:
            package = importlib.import_module(pkg_name)
            if auto_package_name and pkg_name == auto_package_name:
                 print(f"Registry: Loaded package {pkg_name} from {package.__file__ if hasattr(package, '__file__') else 'unknown'}")
        except ImportError as e:
            print(f"Warning: Could not import package {pkg_name}: {e}")
            return []

        packages_to_scan = []
        if pkg_name.endswith(".scripts"):
            packages_to_scan = [pkg_name]
        elif hasattr(package, "__path__"):
            base_paths = list(package.__path__)
            for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
                if not is_pkg:
                    continue
                # print(f"Registry: Scanning potential skill {module_name}")
                entry = None
                for base_path in base_paths:
                    skill_md_path = os.path.join(base_path, module_name, "skill.md")
                    if os.path.exists(skill_md_path):
                        entry = _read_skill_entry(skill_md_path)
                        if entry:
                            break
                if entry:
                    packages_to_scan.append(entry)
                else:
                    packages_to_scan.append(f"{pkg_name}.{module_name}.scripts")

        for scripts_package in packages_to_scan:
            print(f"Registry: Processing scripts package {scripts_package}")
            if auto_package_name and pkg_name == auto_package_name:
                prefixes = [scripts_package]
                if scripts_package.endswith(".scripts"):
                    prefixes.append(scripts_package.rsplit(".scripts", 1)[0])
                for name in list(sys.modules.keys()):
                    for prefix in prefixes:
                        if name == prefix or name.startswith(prefix + "."):
                            del sys.modules[name]
                            break
            try:
                scripts_module = importlib.import_module(scripts_package)
            except Exception as e:
                print(f"Registry Warning: Failed to import scripts package {scripts_package}: {e}")
                continue
            
            if hasattr(scripts_module, "__path__"):
                print(f"Registry: Scanning modules in {scripts_package}")
                for _, module_name, _ in pkgutil.iter_modules(scripts_module.__path__):
                    full_module_name = f"{scripts_package}.{module_name}"
                    # print(f"Registry: Found script module {full_module_name}")
                    try:
                        module = importlib.import_module(full_module_name)
                        found_tools = 0
                        for name, obj in inspect.getmembers(module):
                            if isinstance(obj, BaseTool):
                                tools.append(obj)
                                found_tools += 1
                            elif inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                                try:
                                    tools.append(obj())
                                    found_tools += 1
                                except Exception:
                                    pass
                        if found_tools > 0:
                            print(f"Registry: Loaded {found_tools} tools from {full_module_name}")
                        else:
                            print(f"Registry: No tools found in {full_module_name}")
                    except Exception as e:
                        print(f"Registry Warning: Failed to load module {full_module_name}: {e}")
            else:
                try:
                    module = importlib.import_module(scripts_package)
                    for name, obj in inspect.getmembers(module):
                        if isinstance(obj, BaseTool):
                            tools.append(obj)
                        elif inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                            try:
                                tools.append(obj())
                            except Exception:
                                pass
                except Exception:
                    continue
        return tools

    tools = []
    tools.extend(_load_from_package(package_name))
    if auto_package_name and auto_package_name != package_name:
        tools.extend(_load_from_package(auto_package_name))

    # 去重 (根据 name)
    unique_tools = {t.name: t for t in tools}
    return list(unique_tools.values())