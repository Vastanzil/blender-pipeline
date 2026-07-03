"""Tests for the EventBus pub/sub system."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_subscribe_and_emit():
    from realtime.event_bus import EventBus
    bus = EventBus()
    received = []
    bus.subscribe("test.event", lambda d: received.append(d))
    bus.emit("test.event", {"value": 42})
    assert received == [{"value": 42}]


def test_emit_no_data_sends_empty_dict():
    from realtime.event_bus import EventBus
    bus = EventBus()
    received = []
    bus.subscribe("ev", lambda d: received.append(d))
    bus.emit("ev")
    assert received == [{}]


def test_multiple_subscribers_all_called():
    from realtime.event_bus import EventBus
    bus = EventBus()
    a, b, c = [], [], []
    bus.subscribe("ev", lambda d: a.append(d))
    bus.subscribe("ev", lambda d: b.append(d))
    bus.subscribe("ev", lambda d: c.append(d))
    bus.emit("ev", {"x": 1})
    assert a == b == c == [{"x": 1}]


def test_unsubscribe_stops_delivery():
    from realtime.event_bus import EventBus
    bus = EventBus()
    received = []
    fn = lambda d: received.append(d)
    bus.subscribe("ev", fn)
    bus.unsubscribe("ev", fn)
    bus.emit("ev", {"x": 1})
    assert received == []


def test_unsubscribe_nonexistent_no_crash():
    from realtime.event_bus import EventBus
    bus = EventBus()
    bus.unsubscribe("ev", lambda d: None)   # must not raise


def test_once_fires_exactly_once():
    from realtime.event_bus import EventBus
    bus = EventBus()
    received = []
    bus.once("ev", lambda d: received.append(d))
    bus.emit("ev", {"n": 1})
    bus.emit("ev", {"n": 2})
    bus.emit("ev", {"n": 3})
    assert len(received) == 1
    assert received[0] == {"n": 1}


def test_emit_unknown_event_no_crash():
    from realtime.event_bus import EventBus
    bus = EventBus()
    bus.subscribe("real", lambda d: None)
    bus.emit("other", {"x": 1})   # must not raise


def test_handler_exception_does_not_crash_bus():
    from realtime.event_bus import EventBus
    bus = EventBus()
    good = []
    bus.subscribe("ev", lambda d: 1 / 0)         # raises
    bus.subscribe("ev", lambda d: good.append(1)) # should still fire
    bus.emit("ev", {})
    assert good == [1]   # second handler ran despite first throwing


def test_clear_specific_event():
    from realtime.event_bus import EventBus
    bus = EventBus()
    received = []
    bus.subscribe("a", lambda d: received.append("a"))
    bus.subscribe("b", lambda d: received.append("b"))
    bus.clear("a")
    bus.emit("a", {})
    bus.emit("b", {})
    assert received == ["b"]


def test_clear_all():
    from realtime.event_bus import EventBus
    bus = EventBus()
    received = []
    bus.subscribe("a", lambda d: received.append("a"))
    bus.subscribe("b", lambda d: received.append("b"))
    bus.clear()
    bus.emit("a", {})
    bus.emit("b", {})
    assert received == []


def test_threaded_emit():
    """EventBus must not deadlock when emitting from multiple threads."""
    import threading
    from realtime.event_bus import EventBus
    bus = EventBus()
    results = []
    bus.subscribe("tick", lambda d: results.append(d["i"]))

    def worker(i):
        bus.emit("tick", {"i": i})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(results) == 20
