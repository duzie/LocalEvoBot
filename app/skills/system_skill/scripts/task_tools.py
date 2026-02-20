from langchain_core.tools import tool
import os
import json
from datetime import datetime
from typing import Any, Dict
from web.backend.shared import shared

def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _emit_event(tool_name: str, event: str, **fields):
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))

def _get_task_plan_path():
    # Use a fixed file for current task state
    return os.path.join(os.path.dirname(__file__), "current_task_plan.json")

@tool
def create_task_plan(steps: list):
    """
    创建或重置当前任务计划。将复杂任务拆解为多个步骤并保存。
    
    Args:
        steps: 步骤列表，每个步骤是一个字符串描述
    """
    tool_name = "create_task_plan"
    if not isinstance(steps, list) or not steps:
        return _error_payload("invalid_args", "steps 必须为非空列表", tool=tool_name)
    plan = {
        "created_at": datetime.now().isoformat(),
        "status": "in_progress",
        "steps": [{"id": i+1, "desc": step, "status": "pending"} for i, step in enumerate(steps)]
    }
    path = _get_task_plan_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    _emit_event(tool_name, "create", steps=len(steps))
    return _ok_payload("任务计划已创建", total=len(steps), path=path)

@tool
def read_task_plan():
    """
    读取当前任务计划与进度。返回待处理的步骤。
    """
    tool_name = "read_task_plan"
    path = _get_task_plan_path()
    if not os.path.exists(path):
        return _error_payload("plan_not_found", "当前没有正在进行的任务计划", tool=tool_name)
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            plan = json.load(f)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("read_failed", str(e), tool=tool_name)
        
    total = len(plan["steps"])
    pending = [s for s in plan["steps"] if s["status"] == "pending"]
    completed = [s for s in plan["steps"] if s["status"] == "completed"]
    
    if not pending:
        _emit_event(tool_name, "completed", total=total)
        return _ok_payload("所有任务步骤已完成", progress=f"{len(completed)}/{total}", completed=len(completed), total=total)
        
    next_step = pending[0]
    _emit_event(tool_name, "read", remaining=len(pending))
    return _ok_payload(
        "已读取任务计划",
        progress=f"{len(completed)}/{total}",
        current_step=next_step,
        remaining_count=len(pending),
    )

@tool
def mark_task_completed(step_id: int, result_summary: str = ""):
    """
    标记指定步骤已完成。
    
    Args:
        step_id: 步骤ID
        result_summary: 执行结果简述
    """
    tool_name = "mark_task_completed"
    path = _get_task_plan_path()
    if not os.path.exists(path):
        return _error_payload("plan_not_found", "找不到任务计划文件", tool=tool_name)
        
    with open(path, "r", encoding="utf-8") as f:
        plan = json.load(f)
        
    found = False
    for step in plan["steps"]:
        if step["id"] == step_id:
            step["status"] = "completed"
            step["result"] = result_summary
            step["completed_at"] = datetime.now().isoformat()
            found = True
            break
            
    if not found:
        return _error_payload("step_not_found", f"未找到 ID 为 {step_id} 的步骤", tool=tool_name, step_id=step_id)
        
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    _emit_event(tool_name, "complete", step_id=step_id)
    return _ok_payload("步骤已标记完成", step_id=step_id)

@tool
def append_task_step(step_desc: str):
    """
    追加新的任务步骤到计划末尾（用于动态调整计划）。
    """
    tool_name = "append_task_step"
    path = _get_task_plan_path()
    if not os.path.exists(path):
        return _error_payload("plan_not_found", "请先调用 create_task_plan 初始化计划", tool=tool_name)
    if not str(step_desc or "").strip():
        return _error_payload("invalid_args", "step_desc 不能为空", tool=tool_name)
        
    with open(path, "r", encoding="utf-8") as f:
        plan = json.load(f)
        
    new_id = max([s["id"] for s in plan["steps"]]) + 1 if plan["steps"] else 1
    new_step = {"id": new_id, "desc": step_desc, "status": "pending"}
    plan["steps"].append(new_step)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    _emit_event(tool_name, "append", step_id=new_id)
    return _ok_payload("已追加步骤", step_id=new_id, desc=step_desc)
