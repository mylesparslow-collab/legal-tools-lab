"""Rule table. Every entry cites the section read on leginfo on 2026-11-25."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseRule:
    key: str
    label: str
    days: int
    authority: str
    service_extension: bool  # whether §§ 1013 / 1010.6 extend the period
    note: str = ""


RESPONSE_RULES: dict[str, ResponseRule] = {r.key: r for r in [
    ResponseRule(
        "demurrer", "Demurrer to a complaint or cross-complaint", 30,
        "Code Civ. Proc. § 430.40(a)", True,
        "Counted from service of the complaint. How the complaint was served can "
        "change when service is complete; that is outside this helper.",
    ),
    ResponseRule(
        "interrogatories", "Response to interrogatories", 30,
        "Code Civ. Proc. § 2030.260(a); § 2016.050", True,
        "Unlawful detainer cases have a five-day period (§ 2030.260(b)), not handled here.",
    ),
    ResponseRule(
        "compel_further_interrogatories", "Notice of motion to compel further interrogatory responses", 45,
        "Code Civ. Proc. § 2030.300(c); § 2016.050", True,
        "Counted from service of the verified response or supplemental verified response.",
    ),
    ResponseRule(
        "new_trial_notice", "Notice of intention to move for new trial", 15,
        "Code Civ. Proc. § 659(a)(2)", False,
        "Counted from service of notice of entry of judgment; outer limit of 180 days "
        "after entry of judgment. Not extended by the method of service "
        "(§ 1013(a), (c), (e); § 1010.6(a)(3)(B)).",
    ),
]}
