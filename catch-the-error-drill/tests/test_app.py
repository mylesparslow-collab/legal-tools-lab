"""Static checks on the shipped files, and the browser smoke test."""
import re
import shutil
import subprocess

import pytest

from conftest import ROOT

APP_FILES = ["index.html", "facilitator.html", "app/app.js", "app/facilitator.js", "app/scoring.js", "app/styles.css"]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_app_makes_no_network_calls_and_loads_nothing_remote():
    for name in APP_FILES + ["app/data.js"]:
        text = read(name)
        assert not re.search(r"https?://|//cdn|fetch\(|XMLHttpRequest|sendBeacon|WebSocket|@import", text), name


def test_pages_load_only_sibling_files():
    for page in ("index.html", "facilitator.html"):
        refs = re.findall(r'(?:src|href)="([^"]+)"', read(page))
        assert refs and all((ROOT / r).exists() for r in refs), refs


def test_storage_is_only_touched_inside_try_blocks():
    for name in ("app/app.js", "app/facilitator.js", "app/scoring.js"):
        for line in read(name).splitlines():
            if "localStorage" in line:
                assert "try {" in line, line
        assert "sessionStorage" not in read(name) and "document.cookie" not in read(name)


def test_styles_cover_dark_mode_focus_and_print():
    css = read("app/styles.css")
    assert "prefers-color-scheme: dark" in css and ":focus-visible" in css and "@media print" in css
    assert re.search(r"\.doc \{[^}]*font-size: 1\.125rem", css, re.S)  # 18px reading size


def test_result_files_carry_no_name_and_pages_have_no_ranking():
    assert not re.search(r"participant|leaderboard|trainee name|your name", read("app/app.js"), re.I)
    fac = read("app/facilitator.js")
    assert "leaderboard" not in fac and fac.count("ranking") == 1  # only the notice that there is none


def test_readme_says_what_this_is_near_the_top():
    head = "\n".join(read("README.md").splitlines()[:12]).lower()
    for phrase in ("personal portfolio demo", "fictional", "not legal advice", "not reviewed by an attorney"):
        assert phrase in head


def test_gitignore_lists_the_usual_caches():
    lines = read(".gitignore").split()
    assert {"__pycache__/", ".pytest_cache/", "node_modules/"} <= set(lines)


def test_browser_smoke_test_passes():
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    out = subprocess.run(["node", "tests/smoke.js"], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "12 checks passed" in out.stdout
