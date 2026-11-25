"""Document hashing.

Two hashes are used:

* file_sha256: SHA-256 of the file bytes. The verification record is tied to this.
  Any change to the file after sign-off changes it.
* verifier_text_hash: the hash the existing citation checker puts in its report as
  doc_sha256. It is SHA-256 of the document text after that tool's normalization
  (quote marks and dashes folded, whitespace collapsed). Reproduced here so the kit
  can confirm a report belongs to a document without importing that tool.
"""
from __future__ import annotations

import hashlib
import re
import zipfile
import xml.etree.ElementTree as ET

_QCHARS = str.maketrans({"“": "'", "”": "'", "„": "'", "‘": "'", "’": "'", '"': "'",
                         "–": "-", "—": "-", " ": " "})
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocumentError(ValueError):
    pass


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize(text: str) -> str:
    text = (text or "").translate(_QCHARS)
    return re.sub(r"\s+", " ", text).strip()


def verifier_text_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def _run_text(run) -> str:
    out = []
    for el in run:
        if el.tag == _W + "t":
            out.append(el.text or "")
        elif el.tag == _W + "tab":
            out.append("\t")
        elif el.tag in (_W + "br", _W + "cr"):
            out.append("\n")
        elif el.tag == _W + "noBreakHyphen":
            out.append("-")
    return "".join(out)


def _docx_text(path: str) -> str:
    """Text of the top-level body paragraphs of a .docx, joined by newlines.

    Mirrors what the citation checker reads (body paragraphs only: no tables,
    headers, footers or footnotes).
    """
    try:
        with zipfile.ZipFile(path) as z:
            data = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise DocumentError(f"not a readable .docx file: {path}") from e
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise DocumentError("document XML declares a DTD or entities; refused")
    body = ET.fromstring(data).find(_W + "body")
    paras = []
    for p in ([] if body is None else body.findall(_W + "p")):
        parts = []
        for child in p:
            if child.tag == _W + "r":
                parts.append(_run_text(child))
            elif child.tag == _W + "hyperlink":
                parts.extend(_run_text(r) for r in child.findall(_W + "r"))
        paras.append("".join(parts))
    return "\n".join(paras)


def extract_text(path: str) -> str:
    if path.lower().endswith(".docx"):
        return _docx_text(path)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError as e:
        raise DocumentError(f"document is not UTF-8 text or .docx: {path}") from e


def document_hashes(path: str) -> dict:
    text = extract_text(path)
    return {"sha256": file_sha256(path), "verifier_text_sha256": verifier_text_hash(text)}
