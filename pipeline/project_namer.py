"""
pipeline/project_namer.py
Derives a filesystem-safe project name from scene understanding rather than
from raw user input.
"""
from __future__ import annotations
import re
from datetime import datetime


class ProjectNamer:
    STOPWORDS = {
        "a", "an", "the", "with", "and", "of", "on", "in", "at", "to",
        "for", "from", "by", "is", "are", "be", "into", "onto", "over",
        "around", "near", "some", "this", "that", "it", "its", "make",
        "create", "add", "put", "generate", "build", "place", "scene",
        "blender", "model", "render", "image", "object", "mesh",
    }

    def name_from_understanding(self, scene_summary: str,
                                detected_labels: list[str]) -> str:
        """Return a slug like 'cottage_pond_bridge_20260706_1423'."""
        tokens = self._extract_nouns(scene_summary, detected_labels)
        slug   = "_".join(tokens[:3]) if tokens else "scene"
        stamp  = datetime.now().strftime("%Y%m%d_%H%M")
        return f"{slug}_{stamp}"

    # ------------------------------------------------------------------

    def _extract_nouns(self, summary: str, labels: list[str]) -> list[str]:
        # Prefer explicit detected labels over free-text parsing
        cleaned = [self._clean(l) for l in labels if self._clean(l)]
        if cleaned:
            return self._dedupe(cleaned)

        # Fall back: tokenise the summary
        words = re.findall(r"[a-zA-Z]+", summary.lower())
        nouns = [w for w in words if w not in self.STOPWORDS and len(w) > 2]
        return self._dedupe(nouns)

    @staticmethod
    def _clean(label: str) -> str:
        return re.sub(r"[^a-z0-9]", "", label.lower().replace(" ", "_").replace("-", "_"))

    @staticmethod
    def _dedupe(tokens: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out
