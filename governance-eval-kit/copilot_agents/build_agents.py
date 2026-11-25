#!/usr/bin/env python3
"""Build Microsoft 365 Copilot declarative agent packages from checklists/*.json.

For each checklist this writes agents/<id>/ with:
  declarativeAgent.json  declarative agent manifest, schema v1.9
  manifest.json          Microsoft 365 app manifest that references it
  instructions.txt       the instruction text, for review in plain text
  color.png, outline.png placeholder icons
and, with --zip, dist/<id>.zip ready to upload.

The checklists are the source of truth. Edit a checklist, then rebuild. The
packages have not been loaded into any Microsoft 365 tenant.
"""
from __future__ import annotations

import argparse
import json
import struct
import uuid
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKLISTS = HERE / "checklists"
AGENTS = HERE / "agents"
DIST = HERE / "dist"

PACK_VERSION = "1.0.0"
VERIFIED_ON = "2026-11-25"
INSTRUCTION_LIMIT = 8000
DISCLAIMER = ("Checklist aid only. Not legal advice. An attorney must verify every item and "
              "citation against the current text before relying on it.")
DEVELOPER = {
    "name": "Myles Parslow (personal portfolio demo)",
    "websiteUrl": "https://mylesparslow-collab.github.io/",
    "privacyUrl": "https://mylesparslow-collab.github.io/",
    "termsOfUseUrl": "https://mylesparslow-collab.github.io/",
}
NAMESPACE = uuid.UUID("6f1d1f0e-5c1b-4a55-9b62-3d1f7a2c9e10")

TEMPLATE = """You are {name}, a checklist assistant for {scope}.

HOW TO WORK
1. Ask for what you need if it is missing: {input}.
2. Use only the material the user gives you. Never invent a fact, date, name or quote. If the material does not say, answer "Not stated".
3. Go through every checklist item in order. For each give: the item number; a status of Met, Not met, Not stated or Needs attorney judgment; a quote copied word for word from the user's material, in quotation marks, with its section or page; and the authority listed for that item.
4. If you cannot find words to quote, say "No supporting text found". Do not paraphrase inside quotation marks.
5. Cite only the authorities in this checklist. Do not cite cases, secondary sources or other sections. Do not say a law is current; the checklist was checked against the official text on {verified_on}, and the user must confirm the current text.
6. Do not calculate deadlines or count days. State the rule and the dates the user gave, and tell the user to compute the date with a deadline calculator and have an attorney confirm it.
7. Do not give an opinion on what the user should do, on likely outcomes, or on whether a document is valid. Report the checklist result only.
8. Do not ask for confidential client information or personal data beyond what the checklist needs. Remind the user to follow their organization's policy on what may be entered into an AI tool.
9. Finish with a short table of the items marked Not met or Not stated, then this sentence exactly: "{disclaimer}"

CHECKLIST
{items}"""


def render_instructions(c: dict) -> str:
    items = "\n".join(
        f"{i}. {it['check']} [{'; '.join(it['authority'])}]" for i, it in enumerate(c["items"], 1)
    )
    return TEMPLATE.format(name=c["name"], scope=c["scope"], input=c["input"],
                           verified_on=VERIFIED_ON, disclaimer=DISCLAIMER, items=items)


def declarative_agent(c: dict) -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/copilot/declarative-agent/v1.9/schema.json",
        "version": "v1.9",
        "name": c["name"],
        "description": c["description"],
        "instructions": render_instructions(c),
        "conversation_starters": c["starters"],
    }


def app_manifest(c: dict) -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.22/MicrosoftTeams.schema.json",
        "manifestVersion": "1.22",
        "version": PACK_VERSION,
        "id": str(uuid.uuid5(NAMESPACE, c["id"])),
        "developer": DEVELOPER,
        "name": {"short": c["name"], "full": f"{c['name']} (demo checklist agent)"},
        "description": {"short": c["description"][:80].rsplit(" ", 1)[0], "full": c["description"]},
        "icons": {"color": "color.png", "outline": "outline.png"},
        "accentColor": "#2F4858",
        "copilotAgents": {"declarativeAgents": [{"id": c["id"], "file": "declarativeAgent.json"}]},
    }


def _png(size: int, rgba: tuple[int, int, int, int]) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    row = b"\x00" + bytes(rgba) * size
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * size, 9)) + chunk(b"IEND", b""))


def load_checklists() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CHECKLISTS.glob("*.json"))]


def build(make_zip: bool = False) -> list[Path]:
    written = []
    for c in load_checklists():
        out = AGENTS / c["id"]
        out.mkdir(parents=True, exist_ok=True)
        instructions = render_instructions(c)
        if len(instructions) > INSTRUCTION_LIMIT:
            raise SystemExit(f"{c['id']}: instructions are {len(instructions)} characters; limit is {INSTRUCTION_LIMIT}")
        files = {
            "declarativeAgent.json": json.dumps(declarative_agent(c), indent=2, ensure_ascii=False) + "\n",
            "manifest.json": json.dumps(app_manifest(c), indent=2, ensure_ascii=False) + "\n",
            "instructions.txt": instructions + "\n",
        }
        for name, text in files.items():
            (out / name).write_text(text, encoding="utf-8")
        (out / "color.png").write_bytes(_png(192, (47, 72, 88, 255)))
        (out / "outline.png").write_bytes(_png(32, (255, 255, 255, 255)))
        written.append(out)
        if make_zip:
            DIST.mkdir(exist_ok=True)
            with zipfile.ZipFile(DIST / f"{c['id']}.zip", "w", zipfile.ZIP_DEFLATED) as z:
                for name in ("manifest.json", "declarativeAgent.json", "color.png", "outline.png"):
                    z.write(out / name, name)
        print(f"{c['id']}: {len(c['items'])} items, instructions {len(instructions)} of {INSTRUCTION_LIMIT} characters")
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zip", action="store_true", help="also write dist/<id>.zip upload packages")
    build(ap.parse_args().zip)
