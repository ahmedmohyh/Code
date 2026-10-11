"""Rule-based post-match tilt / break recommendation generator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from flow_lol.inference.pipeline import Prediction


class BreakRecommendation(Enum):
    """Simple recommendation categories after a match."""

    CONTINUE = "continue"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"
    WARM_UP = "warm_up"


@dataclass
class MatchSummary:
    n_predictions: int
    n_flow: int
    flow_pct: float
    early_flow_pct: float
    late_flow_pct: float
    deaths_near_no_flow: int
    recommendation: BreakRecommendation

    def to_text(self) -> str:
        rec_text = {
            BreakRecommendation.CONTINUE: "Flow state looks stable — you can keep playing.",
            BreakRecommendation.SHORT_BREAK: "Signs of fatigue/tilt — take a 5–10 minute break.",
            BreakRecommendation.LONG_BREAK: "Strong tilt signal — step away for 20+ minutes.",
            BreakRecommendation.WARM_UP: "Warm up first — flow was low throughout the match.",
        }[self.recommendation]
        return (
            f"Flow: {self.flow_pct:.0f}% ({self.n_flow}/{self.n_predictions} windows). "
            f"Early: {self.early_flow_pct:.0f}%, late: {self.late_flow_pct:.0f}%. "
            f"Deaths near no-flow: {self.deaths_near_no_flow}. {rec_text}"
        )


def summarize_match(
    predictions: List[Prediction],
    game_events: Optional[List[Dict[str, Any]]] = None,
) -> MatchSummary:
    """Generate a simple recommendation from predictions and game events.

    Heuristics:
      - If flow % is high (≥ 55%) and stable → CONTINUE.
      - If late-game flow drops > 15 percentage points below early game → SHORT_BREAK.
      - If flow % is very low (≤ 25%) → WARM_UP.
      - If multiple deaths occurred within 10 s of a no-flow window → tilt signal.
    """
    game_events = game_events or []
    n_preds = len(predictions)
    if n_preds == 0:
        return MatchSummary(
            n_predictions=0,
            n_flow=0,
            flow_pct=0.0,
            early_flow_pct=0.0,
            late_flow_pct=0.0,
            deaths_near_no_flow=0,
            recommendation=BreakRecommendation.WARM_UP,
        )

    labels = [p.ensemble_label for p in predictions]
    n_flow = sum(labels)
    flow_pct = n_flow / n_preds * 100

    # Split predictions into early and late halves by timestamp.
    timestamps = [p.end_timestamp for p in predictions]
    t_min, t_max = min(timestamps), max(timestamps)
    mid = (t_min + t_max) / 2
    early = [p for p in predictions if p.end_timestamp <= mid]
    late = [p for p in predictions if p.end_timestamp > mid]
    early_flow_pct = _flow_pct(early)
    late_flow_pct = _flow_pct(late)

    deaths_near_no_flow = _count_deaths_near_no_flow(predictions, game_events)

    recommendation = BreakRecommendation.CONTINUE
    if flow_pct <= 25:
        recommendation = BreakRecommendation.WARM_UP
    elif early_flow_pct - late_flow_pct > 15 or flow_pct < 40:
        recommendation = BreakRecommendation.SHORT_BREAK
    if deaths_near_no_flow >= 2 or (flow_pct < 30 and late_flow_pct < early_flow_pct):
        recommendation = BreakRecommendation.LONG_BREAK

    return MatchSummary(
        n_predictions=n_preds,
        n_flow=n_flow,
        flow_pct=flow_pct,
        early_flow_pct=early_flow_pct,
        late_flow_pct=late_flow_pct,
        deaths_near_no_flow=deaths_near_no_flow,
        recommendation=recommendation,
    )


def _flow_pct(predictions: List[Prediction]) -> float:
    if not predictions:
        return 0.0
    return sum(1 for p in predictions if p.ensemble_label == 1) / len(predictions) * 100


def _count_deaths_near_no_flow(
    predictions: List[Prediction],
    game_events: List[Dict[str, Any]],
    window_seconds: float = 10.0,
) -> int:
    """Count deaths that occur shortly after a no-flow prediction window."""
    count = 0
    for event in game_events:
        if event.get("event_type") != "death":
            continue
        death_time = event.get("timestamp")
        if death_time is None:
            continue
        # Check if any no-flow prediction window ended within ``window_seconds`` before the death.
        for pred in predictions:
            if pred.ensemble_label == 0 and 0 <= death_time - pred.end_timestamp <= window_seconds:
                count += 1
                break
    return count
