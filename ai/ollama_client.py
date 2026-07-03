"""
ai/ollama_client.py — Ollama local inference client.
Auto-detects which models are installed and picks the best available one.
Falls back gracefully when the configured model is not found.
"""
import json
import re
import requests

# Preferred models in priority order (first match wins)
_PREFERRED_CODER = [
    "qwen2.5-coder:7b", "qwen2.5-coder:3b", "qwen2.5-coder:14b",
    "codellama:7b", "codellama:13b", "deepseek-coder:6.7b",
]
_PREFERRED_PLANNER = [
    "qwen3:8b", "qwen3:4b", "qwen2.5:7b", "llama3.2:3b",
    "llama3:8b", "mistral:7b",
]


def _pick_model(available: list[str], preferred: list[str]) -> str | None:
    """Return the first preferred model found in available list, or None."""
    avail_lower = {m.lower(): m for m in available}
    for pref in preferred:
        if pref.lower() in avail_lower:
            return avail_lower[pref.lower()]
    return None


class OllamaClient:
    def __init__(self, host="http://localhost:11434",
                 model="", planner_model="", timeout=120):
        self.host          = host.rstrip("/")
        self.timeout       = timeout
        self._cfg_model    = model          # user-configured (may be empty/missing)
        self._cfg_planner  = planner_model
        self._model        = None           # resolved at first use
        self._planner      = None

    # ------------------------------------------------------------------
    # Model resolution — called once, then cached
    # ------------------------------------------------------------------

    def _list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=5)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def _resolve_models(self):
        if self._model and self._planner:
            return
        available = self._list_models()
        if not available:
            # Ollama not reachable — use config values as-is
            self._model   = self._cfg_model   or "llama3:8b"
            self._planner = self._cfg_planner or self._model
            return

        # Try config value first, then preferred list, then just use first available
        def resolve(cfg, preferred):
            if cfg and any(cfg.lower() in m.lower() for m in available):
                # find the full model name matching config
                for m in available:
                    if cfg.lower() in m.lower():
                        return m
            best = _pick_model(available, preferred)
            return best if best else available[0]

        self._model   = resolve(self._cfg_model,   _PREFERRED_CODER)
        self._planner = resolve(self._cfg_planner, _PREFERRED_PLANNER)

    @property
    def model(self) -> str:
        self._resolve_models()
        return self._model

    @property
    def planner_model(self) -> str:
        self._resolve_models()
        return self._planner

    # ------------------------------------------------------------------
    # Core generate
    # ------------------------------------------------------------------

    def _generate(self, prompt: str, model: str) -> str:
        payload = {"model": model, "prompt": prompt, "stream": False}
        try:
            r = requests.post(f"{self.host}/api/generate",
                              json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json().get("response", "")
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                raise RuntimeError(
                    f"Ollama model '{model}' not found.\n"
                    f"Run:  ollama pull {model}\n"
                    f"Or change the model in Connection Setup → AI Backend."
                ) from e
            raise

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate_code(self, prompt: str) -> str:
        return self._generate(prompt, self.model)

    def plan(self, prompt: str) -> list:
        resp = self._generate(prompt, self.planner_model)
        # Try to extract a JSON array from the response
        m = re.search(r'\[.*?\]', resp, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        # Fallback: split by newlines and clean up
        lines = [l.strip().lstrip("-•*0123456789.) ").strip()
                 for l in resp.splitlines() if l.strip()]
        return [l for l in lines if l]

    def fix_error(self, code: str, error: str, context: str = "") -> str:
        prompt = (
            f"The following bpy Python code raised an error.\n"
            f"Fix it so it runs correctly in Blender.\n\n"
            f"CODE:\n```python\n{code}\n```\n\n"
            f"ERROR:\n{error}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"Return ONLY the corrected Python code, no explanation."
        )
        return self._generate(prompt, self.model)

    def available_models(self) -> list[str]:
        """Return list of all installed Ollama model names. Empty if unreachable."""
        return self._list_models()

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=5)
            return r.status_code == 200 and bool(r.json().get("models"))
        except Exception:
            return False
