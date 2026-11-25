"""Time model assumptions. These are inputs to set, not measurements."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class TimeModel:
    # Minutes to load the document, run the tool and read its output layout.
    setup_minutes: float = 5.0
    # Minutes for an attorney to check one finding against the document and the cited law.
    verify_minutes_per_finding: float = 4.0
    # Extra minutes when a quote cannot be found in the document and must be hunted down.
    unverified_quote_penalty_minutes: float = 6.0
    # Share of the unaided review time the attorney still spends reading the whole
    # document, however good the tool is.
    spot_check_fraction: float = 0.25
    # Weight of a high-severity defect relative to a medium one when estimating how
    # much review is left for the issues the tool missed.
    high_weight: float = 2.0
    medium_weight: float = 1.0
    # Pass marks used in the scorecard summary.
    pass_high_recall: float = 0.90
    pass_grounding: float = 0.98

    def to_dict(self) -> dict:
        return asdict(self)


def load_time_model(path: str | Path | None) -> TimeModel:
    if path is None:
        return TimeModel()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    unknown = set(data) - set(TimeModel.__dataclass_fields__)
    if unknown:
        raise ValueError(f"unknown time model settings: {sorted(unknown)}")
    return TimeModel(**data)
