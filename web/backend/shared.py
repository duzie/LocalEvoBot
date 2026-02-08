import queue
import asyncio
from typing import Callable, Optional

class SharedState:
    def __init__(self):
        self.input_queue = queue.Queue()
        self._pushback = queue.LifoQueue()
        self.broadcast_func: Optional[Callable[[str], None]] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.stop_requested: bool = False

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

# Global instance
shared = SharedState()
