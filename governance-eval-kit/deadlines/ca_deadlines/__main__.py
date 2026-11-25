"""Command line: python3 -m ca_deadlines <command> ...

  motion   --hearing YYYY-MM-DD [--service METHOD]
  msj      --hearing YYYY-MM-DD [--service METHOD] [--trial YYYY-MM-DD]
  respond  --served YYYY-MM-DD --rule RULE_OR_DAYS [--service METHOD]
  holidays --year YYYY

Add --json for machine-readable output.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from . import compute
from .holidays import holiday_source, judicial_holidays
from .rules import RESPONSE_RULES

DISCLAIMER = ("Demonstration only, not legal advice. Court orders, local rules and other statutes "
              "can change these dates. Check every date before relying on it.")


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _print(results: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps({k: v.as_dict() for k, v in results.items()} | {"disclaimer": DISCLAIMER}, indent=2))
        return
    for r in results.values():
        line = f"{r.label}: {r.date.strftime('%A %Y-%m-%d')}"
        if r.safe_date:
            line += f"  (safe date {r.safe_date.strftime('%A %Y-%m-%d')})"
        print(line)
        print(f"  Authority: {r.authority}")
        for s in r.steps:
            print(f"  - {s}")
        for w in r.warnings:
            print(f"  ! {w}")
    print(DISCLAIMER)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ca_deadlines", description="California civil deadline arithmetic (demo).")
    sub = p.add_subparsers(dest="cmd", required=True)
    methods = sorted(compute.SERVICE_METHODS)
    m = sub.add_parser("motion", help="notice periods for a regularly noticed motion (CCP 1005(b))")
    m.add_argument("--hearing", required=True, type=_d)
    m.add_argument("--service", default="personal", choices=methods)
    s = sub.add_parser("msj", help="summary judgment schedule (CCP 437c)")
    s.add_argument("--hearing", required=True, type=_d)
    s.add_argument("--service", default="personal", choices=methods)
    s.add_argument("--trial", type=_d)
    r = sub.add_parser("respond", help="last day to respond after service")
    r.add_argument("--served", required=True, type=_d)
    r.add_argument("--rule", required=True, help="one of: " + ", ".join(sorted(RESPONSE_RULES)) + ", or a number of days")
    r.add_argument("--service", default="personal", choices=methods)
    h = sub.add_parser("holidays", help="list judicial holidays for a year")
    h.add_argument("--year", required=True, type=int)
    for sp in (m, s, r, h):
        sp.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        if a.cmd == "motion":
            _print(compute.motion_schedule(a.hearing, a.service), a.json)
        elif a.cmd == "msj":
            _print(compute.msj_schedule(a.hearing, a.service, a.trial), a.json)
        elif a.cmd == "respond":
            rule = int(a.rule) if a.rule.isdigit() else a.rule
            _print({"deadline": compute.response_deadline(a.served, rule, a.service)}, a.json)
        else:
            hol = judicial_holidays(a.year)
            if a.json:
                print(json.dumps({"year": a.year, "source": holiday_source(a.year),
                                  "holidays": {d.isoformat(): n for d, n in sorted(hol.items())}}, indent=2))
            else:
                print(f"Judicial holidays {a.year} ({holiday_source(a.year)}), plus every Saturday and Sunday:")
                for d, n in sorted(hol.items()):
                    print(f"  {d.strftime('%a %Y-%m-%d')}  {n}")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
