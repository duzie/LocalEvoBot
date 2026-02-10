import queue
import asyncio
from datetime import datetime, timezone
from typing import Callable, Optional, Dict, Any

class SharedState:
    def __init__(self):
        self.input_queue = queue.Queue()
        self._pushback = queue.LifoQueue()
        self.broadcast_func: Optional[Callable[[str], None]] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.stop_requested: bool = False
        self.execution_status: str = "idle"
        self.status_message: str = ""
        self.current_task: str = ""
        self.last_summary: str = ""
        self.last_summary_at: str = ""
        self.last_task_done_at: str = ""
        self.last_error: str = ""
        self.last_error_at: str = ""

    def put_input(self, text: str):
        self.input_queue.put(text)

    def put_back(self, text: str):
        self._pushback.put(text)
    
    def get_input(self, block=True, timeout=None):
        try:
            return self._pushback.get_nowait()
        except queue.Empty:
            pass
        return self.input_queue.get(block=block, timeout=timeout)

    def set_loop(self, loop):
        self.loop = loop

    def broadcast_threadsafe(self, message: str):
        """Call this from non-async threads (like main agent loop)"""
        if self.loop and self.broadcast_func:
            try:
                if self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.broadcast_func(message), self.loop)
            except Exception as e:
                print(f"Broadcast error: {e}")
    
    def request_stop(self):
        self.stop_requested = True
    
    def clear_stop(self):
        self.stop_requested = False

    def set_status(self, status: str, message: Optional[str] = None, task: Optional[str] = None, error: Optional[str] = None):
        prev = self.execution_status
        self.execution_status = status
        if message is not None:
            self.status_message = str(message)
        if task is not None:
            self.current_task = str(task)
        if error:
            self.last_error = str(error)
            self.last_error_at = datetime.now(timezone.utc).isoformat()
        if prev == "running" and status == "idle":
            self.last_task_done_at = datetime.now(timezone.utc).isoformat()

    def set_summary(self, summary_text: str):
        self.last_summary = str(summary_text or "")
        self.last_summary_at = datetime.now(timezone.utc).isoformat()

    def set_error(self, error: str):
        if error:
            self.last_error = str(error)
            self.last_error_at = datetime.now(timezone.utc).isoformat()

    def get_status(self) -> Dict[str, Any]:
        return {
            "execution_status": self.execution_status,
            "status_message": self.status_message,
            "current_task": self.current_task,
            "last_summary": self.last_summary,
            "last_summary_at": self.last_summary_at,
            "last_task_done_at": self.last_task_done_at,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at
        }

# Global instance
shared = SharedState()
