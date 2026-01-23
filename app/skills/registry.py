import importlib
import pkgutil
import inspect
import os
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

def load_skills(package_name: str = "app.skills") -> List[BaseTool]:
    """
    动态加载指定包下的所有 Skills (BaseTool 的实例或子类)。
    
    Args:
        package_name: 存放 skills 的包名，例如 "app.skills"
        
    Returns:
        List[BaseTool]: 加载到的所有 Tool 实例列表
    """
    tools = []
    
    # 1. 导入包
    try:
        package = importlib.import_module(package_name)
    except ImportError as e:
        print(f"Warning: Could not import package {package_name}: {e}")
        return []

    packages_to_scan = []
    if package_name.endswith(".scripts"):
        packages_to_scan = [package_name]
    elif hasattr(package, "__path__"):
        base_paths = list(package.__path__)
        for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
            if not is_pkg:
                continue
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
                packages_to_scan.append(f"{package_name}.{module_name}.scripts")

    # 2. 遍历包下的所有模块
    # pkgutil.walk_packages 会递归查找子包，这里我们只查找直接子模块即可，或者根据需要递归
    for scripts_package in packages_to_scan:
        try:
            scripts_module = importlib.import_module(scripts_package)
        except Exception:
            continue
        if hasattr(scripts_module, "__path__"):
            for _, module_name, _ in pkgutil.iter_modules(scripts_module.__path__):
                full_module_name = f"{scripts_package}.{module_name}"
                try:
                    module = importlib.import_module(full_module_name)
                    
                    # 3. 扫描模块中的 Tool
                    # 我们查找所有是 BaseTool 实例的对象，或者被 @tool 装饰过的函数 (它们会被转为 BaseTool)
                    for name, obj in inspect.getmembers(module):
                        # 情况 A: 对象本身就是 BaseTool 的实例 (通常是 @tool 装饰后的结果)
                        if isinstance(obj, BaseTool):
                            tools.append(obj)
                        # 情况 B: 对象是 BaseTool 的子类 (用户自定义 Tool 类)
                        elif inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                            # 实例化它，这里假设没有必填参数
                            try:
                                tools.append(obj())
                            except Exception:
                                pass # 忽略无法直接实例化的类
                                
                except Exception as e:
                    print(f"Warning: Failed to load module {full_module_name}: {e}")
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

    # 去重 (根据 name)
    unique_tools = {t.name: t for t in tools}
    return list(unique_tools.values())
