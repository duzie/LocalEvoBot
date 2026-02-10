import threading
import time
from typing import Callable, Optional, Dict, Any


class HeartbeatManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        self._thread = t

    def stop(self):
        self._running = False

    def register(self, name: str, fn: Callable[[], None], interval: Any, enabled: Optional[Callable[[], bool]] = None, on_error: Optional[Callable[[Exception], None]] = None):
        if not name or not fn:
            return
        with self._lock:
            self._tasks[name] = {
                "fn": fn,
                "interval": interval,
                "interval_override": None,
                "enabled": enabled,
                "on_error": on_error,
                "next_at": 0.0,
                "paused": False,
            }
        self.start()

    def unregister(self, name: str):
        with self._lock:
            if name in self._tasks:
                del self._tasks[name]

    def list_tasks(self):
        with self._lock:
            items = list(self._tasks.items())
        result = []
        for name, task in items:
            interval_base = task.get("interval")
            interval_override = task.get("interval_override")
            interval_val = self._resolve_interval(interval_override if interval_override is not None else interval_base)
            result.append({
                "name": name,
                "interval": interval_val,
                "paused": bool(task.get("paused")),
                "override": interval_override is not None,
                "has_enabled": task.get("enabled") is not None,
            })
        return result

    def update_task(self, name: str, interval: Optional[float] = None, paused: Optional[bool] = None):
        with self._lock:
            if name not in self._tasks:
                return False
            task = self._tasks[name]
            if interval is None:
                task["interval_override"] = None
            else:
                try:
                    task["interval_override"] = float(interval)
                except Exception:
                    return False
            if paused is not None:
                task["paused"] = bool(paused)
                if not paused:
                    task["next_at"] = 0.0
            return True

    def _resolve_interval(self, value: Any) -> float:
        try:
            if callable(value):
                return float(value())
            return float(value)
        except Exception:
            return 1.0

    def _loop(self):
        while self._running:
            now = time.monotonic()
            with self._lock:
                task_items = list(self._tasks.items())
            next_sleep = 1.0
            for name, task in task_items:
                interval_base = task.get("interval")
                interval_override = task.get("interval_override")
                interval_val = max(0.2, self._resolve_interval(interval_override if interval_override is not None else interval_base))
                if task.get("paused"):
                    with self._lock:
                        if name in self._tasks:
                            self._tasks[name]["next_at"] = now + min(2.0, interval_val)
                    next_sleep = min(next_sleep, min(2.0, interval_val))
                    continue
                enabled_fn = task.get("enabled")
                if enabled_fn and not enabled_fn():
                    with self._lock:
                        if name in self._tasks:
                            self._tasks[name]["next_at"] = now + min(2.0, interval_val)
                    next_sleep = min(next_sleep, min(2.0, interval_val))
                    continue
                next_at = float(task.get("next_at") or 0.0)
                if now >= next_at:
                    try:
                        task["fn"]()
                    except Exception as e:
                        handler = task.get("on_error")
                        if handler:
                            try:
                                handler(e)
                            except Exception:
                                pass
                    with self._lock:
                        if name in self._tasks:
                            self._tasks[name]["next_at"] = now + interval_val
                    next_at = now + interval_val
                next_sleep = min(next_sleep, max(0.1, next_at - now))
            time.sleep(max(0.1, next_sleep))


_manager = HeartbeatManager()


def start():
    _manager.start()


def stop():
    _manager.stop()


def register_task(name: str, fn: Callable[[], None], interval: Any, enabled: Optional[Callable[[], bool]] = None, on_error: Optional[Callable[[Exception], None]] = None):
    _manager.register(name, fn, interval, enabled, on_error)


def unregister_task(name: str):
    _manager.unregister(name)


def list_tasks():
    return _manager.list_tasks()


def update_task(name: str, interval: Optional[float] = None, paused: Optional[bool] = None):
    return _manager.update_task(name, interval, paused)
