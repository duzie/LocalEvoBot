"""
{tool_name} - {功能描述}

示例工具，展示如何定义工具。
"""

from langchain_core.tools import tool
from app.skills.common import ok_payload, error_payload, SkillException


@tool
def {tool_name}(param1: str, param2: int = 10) -> dict:
    """
    {工具功能描述}
    
    Args:
        param1: {参数 1 描述}
        param2: {参数 2 描述}，默认值 10
    
    Returns:
        dict: 包含 ok 字段的字典
        - ok: True/False
        - message: 成功/失败消息
        - data: 返回数据（可选）
    
    Example:
        result = {tool_name}.invoke({"param1": "test", "param2": 20})
        if result.get("ok"):
            print(result.get("message"))
    """
    try:
        # 验证参数
        if not param1:
            raise SkillException("invalid_param", "param1 不能为空")
        
        # 实现逻辑
        result = f"处理了 {param1}，次数 {param2}"
        
        return ok_payload("操作成功", result=result)
        
    except SkillException:
        raise  # 重新抛出，让 StandardizedTool 处理
    
    except Exception as e:
        return error_payload("unexpected_error", f"意外错误：{e}")
