from langchain_core.tools import tool
import datetime

@tool
def get_current_time():
    """获取当前系统时间。当用户询问现在几点，或者今天是几号时使用。"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
