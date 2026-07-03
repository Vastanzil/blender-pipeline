"""
realtime/data_bridge.py
Background daemon thread that polls Blender scene info every N seconds.
Uses MD5 hashing to emit 'scene.updated' only when content actually changes.
"""
import hashlib
import json
import threading
import time
from utils.logger import get_logger

log = get_logger("data_bridge")


class DataBridge:
    def __init__(self, client, bus, interval=2.0):
        self._client   = client
        self._bus      = bus
        self._interval = interval
        self._last_md5 = ""
        self._running  = False
        self._thread   = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True, name="DataBridge")
        self._thread.start()
        log.info(f"DataBridge started (interval={self._interval}s)")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("DataBridge stopped")

    def _loop(self):
        while self._running:
            try:
                self._poll()
            except Exception as e:
                log.debug(f"DataBridge poll error: {e}")
            time.sleep(self._interval)

    def _poll(self):
        result = self._client.get_scene_info()
        if not result.success:
            return
        raw  = result.output
        text = raw if isinstance(raw, str) else json.dumps(raw, sort_keys=True)
        md5  = hashlib.md5(text.encode()).hexdigest()
        if md5 != self._last_md5:
            self._last_md5 = md5
            self._bus.emit("scene.updated", {"scene": raw, "md5": md5})
