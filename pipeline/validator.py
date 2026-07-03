"""
pipeline/validator.py
Pings Blender with a simple print to confirm it is still responsive
between pipeline steps.
"""


class Validator:
    PROBE = "print('VALIDATE_OK')"

    def __init__(self, client):
        self._client = client

    def is_alive(self) -> bool:
        try:
            result = self._client.exec_code(self.PROBE)
            return "VALIDATE_OK" in str(result.output or "")
        except Exception:
            return False
