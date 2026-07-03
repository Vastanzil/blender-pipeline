"""
realtime/event_bus.py
Thread-safe publish/subscribe event bus.
All GUI and background threads communicate through this.
"""
import threading
from collections import defaultdict
from utils.logger import get_logger

log = get_logger("event_bus")


class EventBus:
    def __init__(self):
        self._subs: dict = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event: str, handler):
        with self._lock:
            self._subs[event].append(handler)

    def unsubscribe(self, event: str, handler):
        with self._lock:
            try:
                self._subs[event].remove(handler)
            except ValueError:
                pass

    def once(self, event: str, handler):
        def wrapper(data):
            self.unsubscribe(event, wrapper)
            handler(data)
        self.subscribe(event, wrapper)

    def emit(self, event: str, data: dict = None):
        if data is None:
            data = {}
        with self._lock:
            handlers = list(self._subs.get(event, []))
        for h in handlers:
            try:
                h(data)
            except Exception as e:
                log.warning(f"EventBus handler error [{event}]: {e}")

    def clear(self, event: str = None):
        with self._lock:
            if event:
                self._subs.pop(event, None)
            else:
                self._subs.clear()
