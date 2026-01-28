from langchain_core.tools import tool
import os
import json
from datetime import datetime

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
    plan = {
        "created_at": datetime.now().isoformat(),
        "status": "in_progress",
        "steps": [{"id": i+1, "desc": step, "status": "pending"} for i, step in enumerate(steps)]
    }
    path = _get_task_plan_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    return f"任务计划已创建，共 {len(steps)} 个步骤。请调用 read_task_plan 获取第一步。"

@tool
def read_task_plan():
    """
    读取当前任务计划与进度。返回待处理的步骤。
    """
    path = _get_task_plan_path()
    if not os.path.exists(path):
        return "当前没有正在进行的任务计划。"
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            plan = json.load(f)
    except Exception as e:
        return f"读取计划失败: {e}"
        
    total = len(plan["steps"])
    pending = [s for s in plan["steps"] if s["status"] == "pending"]
    completed = [s for s in plan["steps"] if s["status"] == "completed"]
    
    if not pending:
        return f"所有任务步骤已完成 ({len(completed)}/{total})。请检查结果或输出最终结论。"
        
    next_step = pending[0]
    return json.dumps({
        "progress": f"{len(completed)}/{total}",
        "current_step": next_step,
        "remaining_count": len(pending)
    }, ensure_ascii=False, indent=2)

@tool
def mark_task_completed(step_id: int, result_summary: str = ""):
    """
    标记指定步骤已完成。
    
    Args:
        step_id: 步骤ID
        result_summary: 执行结果简述
    """
    path = _get_task_plan_path()
    if not os.path.exists(path):
        return "找不到任务计划文件。"
        
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
        return f"未找到 ID 为 {step_id} 的步骤。"
        
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
        
    return f"步骤 {step_id} 已标记完成。请调用 read_task_plan 获取下一步。"

@tool
def append_task_step(step_desc: str):
    """
    追加新的任务步骤到计划末尾（用于动态调整计划）。
    """
    path = _get_task_plan_path()
    if not os.path.exists(path):
        return "请先调用 create_task_plan 初始化计划。"
        
    with open(path, "r", encoding="utf-8") as f:
        plan = json.load(f)
        
    new_id = max([s["id"] for s in plan["steps"]]) + 1 if plan["steps"] else 1
    new_step = {"id": new_id, "desc": step_desc, "status": "pending"}
    plan["steps"].append(new_step)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
        
    return f"已追加步骤 {new_id}: {step_desc}"