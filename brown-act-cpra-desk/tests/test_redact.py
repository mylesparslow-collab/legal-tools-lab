import pytest

pytest.importorskip("pypdfium2")
rl = pytest.importorskip("reportlab.pdfgen.canvas")

from desk import redact  # noqa: E402

SECRET, PHONE = "1187 Fennimore Court", "(559) 555-0142"


def make(path, lines):
    c = rl.Canvas(str(path))
    c.setFont("Helvetica", 11)
    for i, line in enumerate(lines):
        c.drawString(72, 720 - 16 * i, line)
    c.save()
    return path


def test_redaction_removes_text_and_keeps_the_rest(tmp_path):
    src = make(tmp_path / "a.pdf", [f"Home address: {SECRET}, Quillhaven", f"Call {PHONE} after noon.", "Untouched line."])
    assert redact.verify_no_leak(src, [SECRET])  # the unredacted file does leak
    res = redact.redact_pdf(src, tmp_path / "b.pdf", [SECRET, PHONE])
    assert res["hits"] == {SECRET: 1, PHONE: 1}
    text = redact.extract_text(tmp_path / "b.pdf")
    assert SECRET not in text and PHONE not in text
    assert "Home address:" in text and "after noon." in text and "Untouched line." in text
    assert redact.verify_no_leak(tmp_path / "b.pdf", [SECRET, PHONE]) == []


def test_case_insensitive_and_repeated_matches(tmp_path):
    src = make(tmp_path / "a.pdf", ["Password: Tulip99 and again TULIP99.", "tulip99"])
    res = redact.redact_pdf(src, tmp_path / "b.pdf", ["tulip99"])
    assert res["hits"]["tulip99"] == 3
    assert redact.verify_no_leak(tmp_path / "b.pdf", ["Tulip99"]) == []


def test_a_box_drawn_over_live_text_is_caught(tmp_path):
    """The failure this tool exists to prevent: a black rectangle with the text still underneath."""
    c = rl.Canvas(str(tmp_path / "fake.pdf"))
    c.setFont("Helvetica", 11)
    c.drawString(72, 720, f"Home address: {SECRET}")
    c.rect(150, 716, 140, 14, fill=1)
    c.save()
    assert redact.verify_no_leak(tmp_path / "fake.pdf", [SECRET]) == [{"term": SECRET, "where": "text layer"}]


def test_propagate_across_near_duplicates(tmp_path):
    base = ["From: A", "To: B", "Subject: site walk on Thursday morning at the yard", f"His home address: {SECRET}", "Bring the gate key and the survey sheets please."]
    srcs = {"E1": make(tmp_path / "e1.pdf", base), "E2": make(tmp_path / "e2.pdf", ["Confirmed."] + ["> " + x for x in base]),
            "E3": make(tmp_path / "e3.pdf", ["Agenda for an unrelated finance committee meeting next month."])}
    rep = redact.propagate([SECRET], srcs, tmp_path / "out")
    assert rep["E1"]["hits"] == {SECRET: 1} and rep["E2"]["hits"] == {SECRET: 1} and rep["E3"]["hits"] == {}
    assert all(r["leaks"] == [] for r in rep.values())
    texts = {k: redact.extract_text(v) for k, v in srcs.items()}
    assert redact.near_duplicates(texts) == [["E1", "E2"]]


def test_propagate_refuses_to_leave_a_leaking_file(tmp_path, monkeypatch):
    src = make(tmp_path / "a.pdf", [f"Address {SECRET}"])
    monkeypatch.setattr(redact, "redact_pdf", lambda s, d, t: (__import__("shutil").copy(s, d), {"hits": {}, "pages": 1})[1])
    with pytest.raises(redact.RedactionError):
        redact.propagate([SECRET], {"A": src}, tmp_path / "out")
    assert not (tmp_path / "out" / "A_redacted.pdf").exists()


def test_demo_runs_end_to_end(tmp_path):
    from desk.__main__ import main
    assert main(["demo", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "report.html").exists() and len(list((tmp_path / "production").glob("*.pdf"))) == 4
    assert "EM-004" not in " ".join(p.name for p in (tmp_path / "production").iterdir())  # withheld in full
