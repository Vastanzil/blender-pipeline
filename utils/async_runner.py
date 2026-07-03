"""
utils/async_runner.py
AsyncWorker: QThread subclass that runs any callable off the GUI thread.
run_in_thread(): convenience wrapper — keeps the worker alive until it
finishes so the QThread is never GC'd while still running.
"""
from PyQt6.QtCore import QThread, pyqtSignal

# Module-level set that keeps every in-flight worker alive.
# Workers remove themselves via their finished signal.
_live: set = set()


class AsyncWorker(QThread):
    result_ready = pyqtSignal(object)
    error_raised  = pyqtSignal(str)
    progress      = pyqtSignal(int, str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn     = fn
        self._args   = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.result_ready.emit(result)
        except Exception as e:
            self.error_raised.emit(str(e))


def run_in_thread(fn, on_result=None, on_error=None, on_progress=None):
    worker = AsyncWorker(fn)
    if on_result:
        worker.result_ready.connect(on_result)
    if on_error:
        worker.error_raised.connect(on_error)
    if on_progress:
        worker.progress.connect(on_progress)

    # Keep the worker alive until Qt signals 'finished', then release it.
    _live.add(worker)
    worker.finished.connect(lambda: _live.discard(worker))

    worker.start()
    return worker
