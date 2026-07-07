"""
pipeline/scene_validator.py
Layer 5: Post-run validation for object posture, overlapping detection,
          scale correctness, and confidence scoring.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List
import math

from .scene_positions import ScenePositions, PlacedObject
from .spatial_reasoner import SpatialReasoner, EXCLUSION_PAIRS, _SCALE_PRESETS
from .reference_loop import ReferenceLoop


@dataclass
class ValidationResult:
    """Single validation pass result."""
    type: str           # 'overlap', 'scale', 'posture', 'confidence'
    objects: List[str]  # affected objects
    fix_hint: str       # concise corrective instruction
    score: int          # 1-100 confidence score
    description: str    # human-readable issue description


class SceneValidator:
    """Compute spatial validity & confidence for a completed scene."""

    def __init__(self, client) -> None:
        self._client = client
        self._reasoner = SpatialReasoner()
        self._positions = ScenePositions(client)

    def validate(
        self,
        reasoner: SpatialReasoner | None = None,
        score_threshold: int = 70,
    ) -> List[ValidationResult]:
        """Run comprehensive validation. Returns list of issues."""
        issues: List[ValidationResult] = []

        for placed in sorted(self._positions._registry.values()):
            name = placed.name
            pos = placed.loc
            dim = placed.dim

            label = placed.name.lower()
            for other in self._positions._registry.values():
                if name == other.name:
                    continue
                other_key = other.name.lower()
                if frozenset({label, other_key}) in EXCLUSION_PAIRS:
                    min_sep = _SCALE_PRESETS.get("default", (0.75, 2.0))[0]
                    required = min_sep * 2 + 0.1
                    dx = pos[0] - other.loc[0]
                    dy = pos[1] - other.loc[1]
                    dist = math.hypot(dx, dy)
                    if dist < required:
                        fix = f"ensure minimum {required:.1f}m spacing between {name} and {other.name}"
                        issues.append(ValidationResult(
                            type="overlap",
                            objects=[name, other.name],
                            fix_hint=fix,
                            score=max(0, 100 - int(dist / required * 150)),
                            description=f"{name} overlaps with {other.name}"
                        ))

            label_lower = label.lower()
            expected_scale = _SCALE_PRESETS.get(
                reasoner.detect_scene_scale(name) if reasoner else "default"
            )[0] * 2
            max_dim = max(dim)
            if max_dim > expected_scale * 1.5:
                fix = f"reduce {name} dimensions (current: {max_dim:.1f}m) to fit {expected_scale:.1f}m scale"
                issues.append(ValidationResult(
                    type="scale",
                    objects=[name],
                    fix_hint=fix,
                    score=80 if max_dim < expected_scale * 2.5 else 30,
                    description=f"{name} exceeds expected scale"
                ))

            if "chair" in label_lower and dim[2] > 0.9:
                fix = f"check {name} upright posture (height > 0.9m typical)"
                issues.append(ValidationResult(
                    type="posture",
                    objects=[name],
                    fix_hint=fix,
                    score=90,
                    description=f"{name} posture requires correction"
                ))
            if "tower" in label_lower and dim[2] < 8:
                fix = f"increase {name} height (target ~5-8m)"
                issues.append(ValidationResult(
                    type="posture",
                    objects=[name],
                    fix_hint=fix,
                    score=70,
                    description=f"{name} posture is too short"
                ))

        try:
            score = self._run_confidence_check(reasoner, score_threshold)
            return [ValidationResult(
                type="confidence",
                objects=[],
                fix_hint=f"confidence score {score:.1f}/100",
                score=score,
                description=f"Overall spatial confidence is {'acceptable' if score >= score_threshold else 'insufficient'}"
            )]
        except Exception:
            pass

        return issues

    def _run_confidence_check(
        self,
        reasoner: SpatialReasoner | None,
        score_threshold: int,
    ) -> int:
        """Use VLM to score spatial validity internally.
        Returns 0-100 integer score."""
        prompt = (
            "You are a spatial validation auditor. "
            f"Score overall scene layout confidence from 0-100 based on:\n"
            "- Proper spacing between objects (no clashes)\n"
            "- Reasonable scale relative to real-world sizes\n"
            "- Correct posture (e.g., chairs upright, towers tall enough)\n"
            "If score < 70, add brief fix hint.\n"
            "Respond with ONLY: 'score=<X>\\n<short_description>'\n"
        )
        try:
            raw_response = self._client.exec_code(f"print('{prompt}')")
            if raw_response and "score=" in raw_response.output:
                parts = str(raw_response.output).split("\\n", 1)
                score = int(parts[0].replace("score=", "").strip())
                score = max(1, min(100, score))
                return score
        except Exception:
            pass
        return 70

    def get_overlapping_pairs(self) -> List[tuple[str, str]]:
        """Return raw overlapping object pairs (no scoring)."""
        overlaps = []
        placed_dict = {p.name: p for p in self._positions._registry.values()}
        for name, placed in placed_dict.items():
            for other_name, other_placed in placed_dict.items():
                if name >= other_name:
                    continue
                if self._positions.overlaps(placed.loc, placed.dim) and \
                   self._positions.overlaps(other_placed.loc, other_placed.dim):
                    min_sep = _SCALE_PRESETS.get("default", (0.75, 2.0))[0] * 2
                    dx = placed.loc[0] - other_placed.loc[0]
                    dy = placed.loc[1] - other_placed.loc[1]
                    dist = math.hypot(dx, dy)
                    if dist < min_sep:
                        overlaps.append((name, other_name))
        return overlaps