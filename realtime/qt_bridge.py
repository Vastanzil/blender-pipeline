"""
realtime/qt_bridge.py
=====================
Thread-safe bridge between the EventBus (called from any thread) and
PyQt6 widgets (must only be touched from the GUI thread).

Usage
-----
Instead of subscribing a widget method directly to the bus:

    # UNSAFE — widget._update() called from DataBridge thread → crash
    bus.subscribe("scene.updated", widget._update)

Use QtBridge:

    from realtime.qt_bridge import QtBridge
    QtBridge.subscribe(bus, "scene.updated", widget._update)

QtBridge marshals every emit() through Qt's signal/slot queued connection
mechanism, which automatically delivers the call on the GUI thread regardless
of which thread emitted it.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal, Qt


class _Relay(QObject):
    """One relay object per (bus, event, handler) triple."""
    fired = pyqtSignal(object)          # carries the data dict

    def __init__(self, handler):
        super().__init__()
        # Qt.ConnectionType.QueuedConnection ensures the slot runs on the
        # thread that owns this QObject (the GUI thread, since it is
        # created there).
        self.fired.connect(handler,
                           Qt.ConnectionType.QueuedConnection)

    def emit_safe(self, data):
        """Called from any thread — queues delivery to the GUI thread."""
        self.fired.emit(data)


class QtBridge:
    """
    Static helper — subscribe an EventBus event to a widget slot safely.

    Returns the _Relay object; keep a reference to it (e.g. store on the
    widget or in a list) so it is not garbage-collected.
    """

    @staticmethod
    def subscribe(bus, event: str, handler) -> _Relay:
        relay = _Relay(handler)
        bus.subscribe(event, relay.emit_safe)
        return relay
