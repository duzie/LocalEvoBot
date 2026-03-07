import os
import time
import functools
import asyncio
from typing import Any, Callable, Optional, Dict
from langchain_core.tools import BaseTool
from pydantic import Field, PrivateAttr


class AgentTimeoutError(Exception):
    """Agent 执行超时错误"""
    pass


class AgentRetryError(Exception):
    """Agent 重试次数耗尽错误"""
    pass


def with_timeout_and_retry(
    timeout: float = 60.0,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    retry_on_timeout: bool = True,
    retry_on_error: bool = True,
    error_keywords: list = None
):
    """
    为函数添加超时和重试机制的装饰器
    
    Args:
        timeout: 单次执行超时时间（秒）
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
        retry_on_timeout: 超时是否重试
        retry_on_error: 错误是否重试
        error_keywords: 触发重试的错误关键词列表
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    # 使用线程池实现超时
                    import threading
                    result = [None]
                    error = [None]
                    
                    def target():
                        try:
                            result[0] = func(*args, **kwargs)
                        except Exception as e:
                            error[0] = e
                    
                    thread = threading.Thread(target=target)
                    thread.daemon = True
                    thread.start()
                    thread.join(timeout=timeout)
                    
                    if thread.is_alive():
                        # 超时
                        if retry_on_timeout and attempt < max_retries:
                            print(f"[超时重试] {func.__name__} 执行超时 ({timeout}s)，第 {attempt + 1}/{max_retries} 次重试...")
                            time.sleep(retry_delay * (attempt + 1))
                            continue
                        raise AgentTimeoutError(f"{func.__name__} 执行超时 ({timeout}s)")
                    
                    if error[0]:
                        raise error[0]
                    
                    return result[0]
                    
                except AgentTimeoutError:
                    raise
                except Exception as e:
                    last_error = e
                    
                    # 检查是否应该重试
                    should_retry = False
                    if retry_on_error and attempt < max_retries:
                        if error_keywords:
                            error_str = str(e).lower()
                            should_retry = any(kw.lower() in error_str for kw in error_keywords)
                        else:
                            should_retry = True
                    
                    if should_retry:
                        print(f"[错误重试] {func.__name__} 执行失败: {str(e)[:100]}，第 {attempt + 1}/{max_retries} 次重试...")
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    else:
                        raise
            
            if last_error:
                raise AgentRetryError(f"{func.__name__} 重试 {max_retries} 次后仍然失败: {last_error}")
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    # 使用 asyncio.wait_for 实现超时
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout
                    )
                    return result
                    
                except asyncio.TimeoutError:
                    if retry_on_timeout and attempt < max_retries:
                        print(f"[超时重试] {func.__name__} 执行超时 ({timeout}s)，第 {attempt + 1}/{max_retries} 次重试...")
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    raise AgentTimeoutError(f"{func.__name__} 执行超时 ({timeout}s)")
                    
                except Exception as e:
                    last_error = e
                    
                    # 检查是否应该重试
                    should_retry = False
                    if retry_on_error and attempt < max_retries:
                        if error_keywords:
                            error_str = str(e).lower()
                            should_retry = any(kw.lower() in error_str for kw in error_keywords)
                        else:
                            should_retry = True
                    
                    if should_retry:
                        print(f"[错误重试] {func.__name__} 执行失败: {str(e)[:100]}，第 {attempt + 1}/{max_retries} 次重试...")
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    else:
                        raise
            
            if last_error:
                raise AgentRetryError(f"{func.__name__} 重试 {max_retries} 次后仍然失败: {last_error}")
        
        # 返回对应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class TimeoutToolWrapper(BaseTool):
    """
    为工具添加超时和重试机制的包装器
    继承 BaseTool 以兼容 LangChain
    """
    name: str = Field(default="unknown_tool")
    description: str = Field(default="")
    
    # 使用 PrivateAttr 声明私有字段
    _tool: BaseTool = PrivateAttr()
    _timeout: float = PrivateAttr()
    _max_retries: int = PrivateAttr()
    _retry_delay: float = PrivateAttr()
    
    def __init__(
        self,
        tool: BaseTool,
        timeout: float = 30.0,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        **kwargs
    ):
        # 从原始工具获取属性
        tool_name = getattr(tool, "name", "unknown_tool")
        tool_description = getattr(tool, "description", "")
        
        # 初始化 BaseTool
        super().__init__(
            name=tool_name,
            description=tool_description,
            **kwargs
        )
        
        # 设置私有属性
        self._tool = tool
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay
    
    def _should_retry(self, error: Exception) -> bool:
        """判断是否应该重试"""
        error_str = str(error).lower()
        retry_keywords = [
            "timeout",
            "connection",
            "network",
            "rate limit",
            "429",
            "503",
            "502",
            "internal error"
        ]
        return any(kw in error_str for kw in retry_keywords)
    
    def _run(self, *args, **kwargs) -> Any:
        """同步调用（BaseTool 要求的方法）"""
        last_error = None
        
        for attempt in range(self._max_retries + 1):
            try:
                import threading
                result = [None]
                error = [None]
                
                def target():
                    try:
                        result[0] = self._tool._run(*args, **kwargs)
                    except Exception as e:
                        error[0] = e
                
                thread = threading.Thread(target=target)
                thread.daemon = True
                thread.start()
                thread.join(timeout=self._timeout)
                
                if thread.is_alive():
                    if attempt < self._max_retries:
                        print(f"[工具超时] {self.name} 执行超时 ({self._timeout}s)，重试中...")
                        time.sleep(self._retry_delay * (attempt + 1))
                        continue
                    raise AgentTimeoutError(f"工具 {self.name} 执行超时")
                
                if error[0]:
                    raise error[0]
                
                return result[0]
                
            except AgentTimeoutError:
                raise
            except Exception as e:
                last_error = e
                if self._should_retry(e) and attempt < self._max_retries:
                    print(f"[工具错误] {self.name} 执行失败: {str(e)[:100]}，重试中...")
                    time.sleep(self._retry_delay * (attempt + 1))
                    continue
                raise
        
        if last_error:
            raise last_error
    
    async def _arun(self, *args, **kwargs) -> Any:
        """异步调用（BaseTool 要求的方法）"""
        last_error = None
        
        for attempt in range(self._max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self._tool._arun(*args, **kwargs),
                    timeout=self._timeout
                )
                return result
                
            except asyncio.TimeoutError:
                if attempt < self._max_retries:
                    print(f"[工具超时] {self.name} 执行超时 ({self._timeout}s)，重试中...")
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    continue
                raise AgentTimeoutError(f"工具 {self.name} 执行超时")
                
            except Exception as e:
                last_error = e
                if self._should_retry(e) and attempt < self._max_retries:
                    print(f"[工具错误] {self.name} 执行失败: {str(e)[:100]}，重试中...")
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    continue
                raise
        
        if last_error:
            raise last_error


def wrap_tools_with_timeout(tools: list, timeout: float = 30.0, max_retries: int = 2) -> list:
    """
    为工具列表添加超时和重试机制
    
    Args:
        tools: 工具列表
        timeout: 单次工具调用超时时间（秒）
        max_retries: 最大重试次数
    
    Returns:
        包装后的工具列表
    """
    wrapped_tools = []
    for tool in tools:
        wrapped_tool = TimeoutToolWrapper(tool, timeout=timeout, max_retries=max_retries)
        wrapped_tools.append(wrapped_tool)
    return wrapped_tools


class HeartbeatMonitor:
    """
    心跳监控器，用于检测Agent是否卡住
    """
    def __init__(self, check_interval: float = 5.0, max_silence: float = 60.0):
        self._check_interval = check_interval
        self._max_silence = max_silence
        self._last_heartbeat = time.time()
        self._is_running = False
        self._monitor_task = None
    
    def heartbeat(self):
        """发送心跳"""
        self._last_heartbeat = time.time()
    
    async def _monitor_loop(self):
        """监控循环"""
        while self._is_running:
            await asyncio.sleep(self._check_interval)
            silence_duration = time.time() - self._last_heartbeat
            
            if silence_duration > self._max_silence:
                print(f"[心跳超时] Agent 已静默 {silence_duration:.1f}s，可能已卡住")
                # 可以在这里触发恢复机制
    
    def start(self):
        """启动监控"""
        if not self._is_running:
            self._is_running = True
            self._last_heartbeat = time.time()
            self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    def stop(self):
        """停止监控"""
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None


def get_timeout_config():
    """
    从环境变量获取超时配置
    
    Returns:
        dict: 超时配置字典
    """
    return {
        "llm_timeout": float(os.getenv("AGENT_LLM_TIMEOUT", "120")),
        "tool_timeout": float(os.getenv("AGENT_TOOL_TIMEOUT", "30")),
        "llm_max_retries": int(os.getenv("AGENT_LLM_MAX_RETRIES", "3")),
        "tool_max_retries": int(os.getenv("AGENT_TOOL_MAX_RETRIES", "2")),
        "retry_delay": float(os.getenv("AGENT_RETRY_DELAY", "2.0")),
        "heartbeat_interval": float(os.getenv("AGENT_HEARTBEAT_INTERVAL", "5.0")),
        "max_silence": float(os.getenv("AGENT_MAX_SILENCE", "120.0"))
    }
