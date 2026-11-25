"""Deterministic California civil deadline arithmetic (demo; not legal advice)."""
from .compute import (  # noqa: F401
    Result, add_calendar_days, add_court_days, back_calendar_days, back_court_days,
    motion_schedule, msj_schedule, response_deadline, SERVICE_METHODS,
)
from .holidays import is_court_day, judicial_holidays, holiday_source  # noqa: F401
from .rules import RESPONSE_RULES  # noqa: F401

__version__ = "0.1.0"
