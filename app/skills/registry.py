import importlib
import pkgutil
import inspect
from typing import List, Dict, Any
from langchain_core.tools import BaseTool

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

    # 2. 遍历包下的所有模块
    # pkgutil.walk_packages 会递归查找子包，这里我们只查找直接子模块即可，或者根据需要递归
    if hasattr(package, "__path__"):
        for _, module_name, _ in pkgutil.iter_modules(package.__path__):
            full_module_name = f"{package_name}.{module_name}"
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

    # 去重 (根据 name)
    unique_tools = {t.name: t for t in tools}
    return list(unique_tools.values())
