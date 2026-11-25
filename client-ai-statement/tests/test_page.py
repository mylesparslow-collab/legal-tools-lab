"""One printed page: render with Chromium (if present) and count PDF pages."""
import json
import re
import shutil
import subprocess

import pytest
from conftest import AS_OF, ROOT

from statement import render
from statement.build import WORD_LIMIT, build_statement, statement_word_count

SCRIPT = ROOT / "scripts" / "render_page.js"


def page_count(pdf) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf.read_bytes()))


def render_pdf(html: str, tmp_path):
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    (tmp_path / "s.html").write_text(html, encoding="utf-8")
    r = subprocess.run(["node", str(SCRIPT), str(tmp_path / "s.html"), str(tmp_path / "s.png"), str(tmp_path / "s.pdf")],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        pytest.skip("Playwright with Chromium is not available: " + r.stderr[:200])
    return tmp_path / "s.pdf", json.loads(r.stdout)


def test_firm_statement_pdf_is_exactly_one_page(clean, inputs, tmp_path):
    pdf, info = render_pdf(render.statement_html(build_statement(clean, inputs, AS_OF)), tmp_path)
    assert page_count(pdf) == 1
    assert info["sheet_height_in"] <= 11.0
    assert (tmp_path / "s.png").stat().st_size > 10_000


def test_longest_sample_client_statement_pdf_is_one_page(clean, inputs, client_restricted, tmp_path):
    pdf, _ = render_pdf(render.statement_html(build_statement(clean, inputs, AS_OF, client_restricted)), tmp_path)
    assert page_count(pdf) == 1


def test_statement_padded_to_the_word_ceiling_still_fits_one_page(clean, inputs, client_restricted, tmp_path):
    """The ceiling is only useful if text at the ceiling fits. Pad a real statement up to it and print."""
    stmt = build_statement(clean, inputs, AS_OF, client_restricted)
    filler = ("Each tool approved for client confidential information is covered by a written agreement "
              "with its provider, recorded in our tool registry.").split()
    need = WORD_LIMIT - statement_word_count(stmt)
    words = (filler * 40)[:need]
    k = len(stmt["sections"])
    for i, sec in enumerate(stmt["sections"]):
        chunk = words[i * need // k:(i + 1) * need // k]
        if chunk:
            sec["sentences"].append({"text": " ".join(chunk)})
    assert statement_word_count(stmt) == WORD_LIMIT
    pdf, _ = render_pdf(render.statement_html(stmt), tmp_path)
    assert page_count(pdf) == 1


def test_committed_pdfs_are_one_page():
    pdfs = sorted((ROOT / "output").rglob("statement.pdf"))
    if not pdfs:
        pytest.skip("run python3 run_demo.py first")
    assert len(pdfs) == 5
    assert all(page_count(p) == 1 for p in pdfs)


def test_print_stylesheet_is_letter_and_self_contained(clean, inputs):
    html = render.statement_html(build_statement(clean, inputs, AS_OF))
    assert "@page{size:letter" in html and "@media print" in html
    assert not re.search(r"https?://|<link|<script|@import|url\(", html)
