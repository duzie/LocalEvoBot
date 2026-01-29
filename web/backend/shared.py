import queue
import asyncio
from typing import Callable, Optional

class SharedState:
    def __init__(self):
        self.input_queue = queue.Queue()
        self.broadcast_func: Optional[Callable[[str], None]] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def put_input(self, text: str):
        self.input_queue.put(text)
    
    def get_input(self, block=True, timeout=None):
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

# Global instance
shared = SharedState()
