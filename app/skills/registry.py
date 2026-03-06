import importlib
import importlib.util
import pkgutil
import inspect
import os
import sys
import json
import re
from datetime import datetime
from typing import List, Dict, Any
from langchain_core.tools import BaseTool
from web.backend.shared import shared
from app.skills.common import SkillException, error_payload as _common_error_payload, ok_payload as _common_ok_payload, emit_event as _common_emit_event

# Kept for backward compatibility if any other modules import these
def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    return _common_error_payload(code, message, **fields)

def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    return _common_ok_payload(message, **fields)

def _emit_event(tool_name: str, event: str, **fields):
    return _common_emit_event(tool_name, event, **fields)

def _normalize_result(result: Any, tool_name: str, scope: str) -> Dict[str, Any]:
    if isinstance(result, dict):
        if "ok" in result:
            return result
        if "success" in result:
            ok = bool(result.get("success"))
            rest = {k: v for k, v in result.items() if k != "success"}
            if ok:
                rest["ok"] = True
                return rest
            msg = str(result.get("error") or result.get("message") or "执行失败")
            return _error_payload("tool_failed", msg, tool=tool_name, scope=scope, data=rest)
        if "status" in result:
            status = result.get("status")
            if isinstance(status, str):
                ok = status.strip().lower() in ["ok", "success", "succeeded", "done", "passed", "true"]
            else:
                ok = bool(status)
            rest = {k: v for k, v in result.items() if k != "status"}
            if ok:
                rest["ok"] = True
                return rest
            msg = str(result.get("error") or result.get("message") or "执行失败")
            return _error_payload("tool_failed", msg, tool=tool_name, scope=scope, data=rest)
        code_key = None
        for key in ["code", "errcode", "errno", "error_code"]:
            if key in result:
                code_key = key
                break
        if code_key:
            code_value = result.get(code_key)
            ok = False
            if isinstance(code_value, bool):
                ok = code_value
            elif isinstance(code_value, (int, float)):
                ok = code_value == 0
            elif isinstance(code_value, str):
                s = code_value.strip().lower()
                if s.isdigit():
                    ok = int(s) == 0
                else:
                    ok = s in ["ok", "success", "succeeded", "true"]
            if ok:
                rest = {k: v for k, v in result.items() if k != code_key}
                rest["ok"] = True
                return rest
            msg = str(result.get("error") or result.get("message") or "执行失败")
            return _error_payload("tool_failed", msg, tool=tool_name, scope=scope, data=result)
        if "error" in result:
            msg = str(result.get("error") or "执行失败")
            return _error_payload("tool_failed", msg, tool=tool_name, scope=scope, data=result)
        return _ok_payload("", tool=tool_name, scope=scope, result=result)
    if result is None:
        return _ok_payload("", tool=tool_name, scope=scope, result=None)
    if isinstance(result, str):
        return _ok_payload(result, tool=tool_name, scope=scope)
    return _ok_payload("", tool=tool_name, scope=scope, result=result)

class StandardizedTool(BaseTool):
    name: str
    description: str
    args_schema: Any = None
    return_direct: bool = False
    inner_tool: BaseTool
    scope: str
    skill_name: str = ""

    def _run(self, *args, **kwargs):
        import time
        payload = kwargs if kwargs else (args[0] if args else {})
        if not isinstance(payload, dict):
            payload = {"input": payload}
        
        start_time = time.time()
        audit_logger = None
        try:
            from app.integrations.audit_logger import get_audit_logger
            audit_logger = get_audit_logger()
        except Exception:
            pass
        
        try:
            result = self.inner_tool.invoke(payload)
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 记录成功日志
            if audit_logger:
                try:
                    audit_logger.log_tool_call(
                        tool_name=self.name,
                        request_data=payload,
                        response_data=result if isinstance(result, dict) else {"result": str(result)},
                        duration_ms=duration_ms
                    )
                except Exception:
                    pass  # 审计日志失败不影响主流程
            
        except SkillException as se:
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 记录失败日志
            if audit_logger:
                try:
                    audit_logger.log_tool_call(
                        tool_name=self.name,
                        request_data=payload,
                        error=se,
                        duration_ms=duration_ms
                    )
                except Exception:
                    pass

            _emit_event(self.name, "error", scope=self.scope, error=se.message, code=se.code)
            return _error_payload(se.code, se.message, tool=self.name, scope=self.scope, **se.details)

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 记录失败日志
            if audit_logger:
                try:
                    audit_logger.log_tool_call(
                        tool_name=self.name,
                        request_data=payload,
                        error=e,
                        duration_ms=duration_ms
                    )
                except Exception:
                    pass  # 审计日志失败不影响主流程
            
            _emit_event(self.name, "error", scope=self.scope, error=str(e))
            return _error_payload("tool_exception", str(e), tool=self.name, scope=self.scope)
        
        normalized = _normalize_result(result, self.name, self.scope)
        _emit_event(self.name, "invoke", scope=self.scope, ok=normalized.get("ok"))
        return normalized

    async def _arun(self, *args, **kwargs):
        import time
        payload = kwargs if kwargs else (args[0] if args else {})
        if not isinstance(payload, dict):
            payload = {"input": payload}
        
        start_time = time.time()
        audit_logger = None
        try:
            from app.integrations.audit_logger import get_audit_logger
            audit_logger = get_audit_logger()
        except Exception:
            pass
        
        try:
            result = await self.inner_tool.ainvoke(payload)
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 记录成功日志
            if audit_logger:
                try:
                    audit_logger.log_tool_call(
                        tool_name=self.name,
                        request_data=payload,
                        response_data=result if isinstance(result, dict) else {"result": str(result)},
                        duration_ms=duration_ms
                    )
                except Exception:
                    pass  # 审计日志失败不影响主流程
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 记录失败日志
            if audit_logger:
                try:
                    audit_logger.log_tool_call(
                        tool_name=self.name,
                        request_data=payload,
                        error=e,
                        duration_ms=duration_ms
                    )
                except Exception:
                    pass  # 审计日志失败不影响主流程
            
            _emit_event(self.name, "error", scope=self.scope, error=str(e))
            return _error_payload("tool_exception", str(e), tool=self.name, scope=self.scope)
        
        normalized = _normalize_result(result, self.name, self.scope)
        _emit_event(self.name, "invoke", scope=self.scope, ok=normalized.get("ok"))
        return normalized

def _wrap_auto_tool(tool: BaseTool, scope: str, skill_name: str = "") -> BaseTool:
    if isinstance(tool, StandardizedTool):
        # 如果已经有了skill_name，就不覆盖了；否则补充
        if skill_name and not getattr(tool, "skill_name", ""):
            tool.skill_name = skill_name
        return tool
    return StandardizedTool(
        name=getattr(tool, "name", ""),
        description=getattr(tool, "description", ""),
        args_schema=getattr(tool, "args_schema", None),
        return_direct=getattr(tool, "return_direct", False),
        inner_tool=tool,
        scope=scope,
        skill_name=skill_name,
    )

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
                if not entry:
                    return None
                if entry.startswith("##") or " " in entry:
                    return None
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_\\.]*$", entry):
                    return None
                return entry
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
    def _load_from_package(pkg_name: str, wrap_tools: bool = False) -> List[BaseTool]:
        tools = []
        if auto_package_name and pkg_name == auto_package_name:
            # 强制清理父包缓存，确保 pkgutil 能扫描到新目录
            if pkg_name in sys.modules:
                del sys.modules[pkg_name]
            importlib.invalidate_caches()
        try:
            package = importlib.import_module(pkg_name)
        except ImportError as e:
            print(f"Warning: Could not import package {pkg_name}: {e}")
            return []

        packages_to_scan = []
        if pkg_name.endswith(".scripts"):
            # 如果直接指定了 scripts 路径，尝试反推 skill_name
            # 例如 app.skills.board_skill.scripts -> board_skill
            skill_name = ""
            parts = pkg_name.split(".")
            if len(parts) >= 2 and parts[-1] == "scripts":
                skill_name = parts[-2]
            packages_to_scan = [(pkg_name, skill_name)]
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
                # skill_name 就是 module_name (目录名)
                if entry:
                    packages_to_scan.append((entry, module_name))
                else:
                    packages_to_scan.append((f"{pkg_name}.{module_name}.scripts", module_name))

        for scripts_package, skill_name in packages_to_scan:
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
                spec = importlib.util.find_spec(scripts_package)
                origin = spec.origin if spec else "not found"
                print(f"Registry Warning: Failed to import scripts package {scripts_package} (origin={origin}): {repr(e)}")
                continue
            
            if hasattr(scripts_module, "__path__"):
                for _, module_name, _ in pkgutil.iter_modules(scripts_module.__path__):
                    full_module_name = f"{scripts_package}.{module_name}"
                    try:
                        module = importlib.import_module(full_module_name)
                        found_tools = 0
                        for name, obj in inspect.getmembers(module):
                            if isinstance(obj, BaseTool):
                                tool = _wrap_auto_tool(obj, "skills", skill_name) if wrap_tools else obj
                                tools.append(tool)
                                found_tools += 1
                            elif inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                                try:
                                    instance = obj()
                                    tool = _wrap_auto_tool(instance, "skills", skill_name) if wrap_tools else instance
                                    tools.append(tool)
                                    found_tools += 1
                                except Exception:
                                    pass
                        if found_tools == 0:
                            # 忽略下划线开头的模块（通常是内部工具或辅助模块）
                            if not module_name.startswith("_"):
                                if os.getenv("SKILL_REGISTRY_VERBOSE", "").strip() == "1":
                                    print(f"Registry: No tools found in {full_module_name}")
                    except Exception as e:
                        print(f"Registry Warning: Failed to load module {full_module_name}: {e}")
            else:
                try:
                    module = importlib.import_module(scripts_package)
                    for name, obj in inspect.getmembers(module):
                        if isinstance(obj, BaseTool):
                            tool = _wrap_auto_tool(obj, "skills", skill_name) if wrap_tools else obj
                            tools.append(tool)
                        elif inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                            try:
                                instance = obj()
                                tool = _wrap_auto_tool(instance, "skills", skill_name) if wrap_tools else instance
                                tools.append(tool)
                            except Exception:
                                pass
                except Exception:
                    continue
        return tools

    tools = []
    # 包装普通 skills 中的工具
    tools.extend(_load_from_package(package_name, wrap_tools=True))
    if auto_package_name and auto_package_name != package_name:
        auto_tools = _load_from_package(auto_package_name, wrap_tools=True)
        tools.extend([_wrap_auto_tool(t, "auto_skills", getattr(t, "skill_name", "")) for t in auto_tools])

    # 去重 (根据 name)
    unique_tools = {t.name: t for t in tools}
    return list(unique_tools.values())
