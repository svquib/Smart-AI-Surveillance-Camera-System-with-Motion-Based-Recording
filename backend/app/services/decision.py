"""Suspicious-activity decision engine.

This is the "is this worth an alert?" brain. It's rule-based on purpose —
explainable, easy to tweak, and good enough to drive the SOS system in
Phase 10. Each rule looks at what was detected (objects), what they were
doing (activity), and when, then returns zero or more alerts.

Alert types:
    emergency   - someone fell / collapsed -> needs immediate attention
    suspicious  - person/vehicle around at an odd hour
    info        - logged, but nothing urgent
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class DecisionConfig:
    # "Unusual hours" window. Default: 10pm -> 6am.
    night_start_hour: int = 22
    night_end_hour: int = 6
    # Activities that always count as an emergency.
    emergency_activities: tuple = ("falling", "abnormal")


@dataclass
class AlertDraft:
    type: str          # emergency | suspicious | info
    message: str


@dataclass
class DecisionContext:
    """Everything the engine needs to make a call about one event."""

    object_counts: Dict[str, int] = field(default_factory=dict)
    activity: str = "no_person"
    when: datetime = field(default_factory=datetime.now)
    camera_name: str = "camera"


class DecisionEngine:
    def __init__(self, config: DecisionConfig | None = None):
        self.config = config or DecisionConfig()

    def _is_night(self, when: datetime) -> bool:
        h = when.hour
        s, e = self.config.night_start_hour, self.config.night_end_hour
        # window wraps past midnight, so handle both cases
        return h >= s or h < e if s > e else s <= h < e

    def evaluate(self, ctx: DecisionContext) -> List[AlertDraft]:
        alerts: List[AlertDraft] = []
        objs = ctx.object_counts or {}
        has_person = objs.get("person", 0) > 0
        has_vehicle = objs.get("vehicle", 0) > 0
        when_str = ctx.when.strftime("%Y-%m-%d %H:%M:%S")

        # 1) Falls / collapses -> emergency, no matter the time.
        if ctx.activity in self.config.emergency_activities:
            alerts.append(AlertDraft(
                "emergency",
                f"Possible fall detected on {ctx.camera_name} at {when_str}. "
                f"Activity: {ctx.activity}.",
            ))

        # 2) People or vehicles at an unusual hour -> suspicious.
        if self._is_night(ctx.when) and (has_person or has_vehicle):
            who = "person" if has_person else "vehicle"
            alerts.append(AlertDraft(
                "suspicious",
                f"{who.capitalize()} detected on {ctx.camera_name} during "
                f"unusual hours ({when_str}).",
            ))

        # 3) Nothing urgent but a person showed up -> info (handy for the feed).
        if not alerts and has_person:
            alerts.append(AlertDraft(
                "info",
                f"Person seen on {ctx.camera_name} at {when_str}.",
            ))

        return alerts
