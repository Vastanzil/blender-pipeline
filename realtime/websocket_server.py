"""
realtime/websocket_server.py
Async WebSocket server on port 8765.
Broadcasts scene.updated and pipeline.step.done to all connected clients.
Runs in a background thread with its own asyncio event loop.
"""
import asyncio
import json
import threading
from utils.logger import get_logger

log = get_logger("ws_server")

try:
    import websockets
    HAS_WS = True
except ImportError:
    HAS_WS = False


class WebSocketServer:
    PORT = 8765

    def __init__(self, bus, port=8765):
        self._bus     = bus
        self._port    = port
        self._clients = set()
        self._loop    = None
        self._thread  = None

    def start(self):
        if not HAS_WS:
            log.warning("websockets package not installed — WebSocket server disabled")
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="WSServer")
        self._thread.start()
        self._bus.subscribe("scene.updated",      self._on_scene)
        self._bus.subscribe("pipeline.step.done", self._on_step)
        log.info(f"WebSocket server starting on ws://localhost:{self._port}")

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self):
        async with websockets.serve(self._handler, "localhost", self._port):
            await asyncio.Future()  # run forever

    async def _handler(self, ws):
        self._clients.add(ws)
        log.info(f"WS client connected: {ws.remote_address}")
        try:
            async for _ in ws:
                pass
        finally:
            self._clients.discard(ws)
            log.info(f"WS client disconnected: {ws.remote_address}")

    def _broadcast(self, data: dict):
        if not self._loop or not self._clients:
            return
        msg = json.dumps(data)
        asyncio.run_coroutine_threadsafe(self._async_broadcast(msg), self._loop)

    async def _async_broadcast(self, msg: str):
        dead = set()
        for ws in list(self._clients):
            try:
                await ws.send(msg)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    def _on_scene(self, data):
        self._broadcast({"event": "scene.updated", "data": data})

    def _on_step(self, data):
        self._broadcast({"event": "pipeline.step.done", "data": data})
