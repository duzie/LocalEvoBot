from langchain_core.tools import tool

@tool
def calculator(expression: str):
    """计算数学表达式的值。支持加减乘除。例如: '2 + 2' 或 '3 * 5'。"""
    try:
        allowed = set("0123456789+-*/. ()")
        if not all(c in allowed for c in expression):
            return "错误: 表达式包含非法字符，只允许数字和基本运算。"
        return str(eval(expression))
    except Exception as e:
        return f"计算出错: {e}"
