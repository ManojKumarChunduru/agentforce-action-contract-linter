"""Properties of the repository itself: the things a reviewer notices before reading any code."""

import re
import subprocess

import pytest

from tests.conftest import REPO_ROOT

README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
REPO_NAME = "agentforce-action-contract-linter"
EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)


def tracked_text_files():
    # tracked and untracked alike: a test file that only checks tracked files exempts itself
    # until its first commit, which is how this test passed once while containing a dash
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    for rel in out:
        p = REPO_ROOT / rel
        if p.suffix in (".png", ".gif", ".mp4", ".webm") or not p.is_file():
            continue
        yield p


@pytest.mark.skipif(not (REPO_ROOT / ".git").exists(), reason="needs the git checkout")
def test_no_em_or_en_dashes_anywhere_in_tracked_text():
    offenders = []
    for p in tracked_text_files():
        text = p.read_text(encoding="utf-8", errors="replace")
        if EM_DASH in text or EN_DASH in text:
            offenders.append(str(p.relative_to(REPO_ROOT)))
    assert offenders == []


def test_every_image_the_readme_embeds_exists_in_the_repository():
    for src in re.findall(r'<img src="([^"]+)"', README) + re.findall(
        r"!\[[^\]]*\]\(([^)]+)\)", README
    ):
        if src.startswith("http"):
            continue
        assert (REPO_ROOT / src).is_file(), src


def test_every_badge_url_names_the_repository_exactly_including_case():
    for url in re.findall(r"https://github\.com/[^)\s]+", README):
        assert f"/{REPO_NAME}" in url and f"/{REPO_NAME.title()}" not in url, url


def test_the_readme_links_every_adr():
    for adr in sorted((REPO_ROOT / "docs" / "adr").glob("ADR-*.md")):
        assert f"docs/adr/{adr.name}" in README, adr.name


def test_no_placeholder_handles_or_todo_markers_survive():
    for p in tracked_text_files():
        if p.name == "test_repo_hygiene.py":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for marker in ("YOUR_USERNAME", "USERNAME/", "TODO", "FIXME"):
            assert marker not in text, f"{p.relative_to(REPO_ROOT)} contains {marker}"


def test_the_banner_is_a_self_contained_animated_svg():
    svg = (REPO_ROOT / "docs" / "assets" / "banner.svg").read_text(encoding="utf-8")
    assert "<script" not in svg and "@import" not in svg and 'href="http' not in svg
    assert "@keyframes" in svg or "<animate" in svg
    assert "prefers-reduced-motion" in svg
    assert re.search(r'<svg[^>]*\swidth="\d+"', svg) and re.search(r'<svg[^>]*\sheight="\d+"', svg)


def test_the_architecture_svg_has_intrinsic_size_and_no_foreign_objects():
    svg = (REPO_ROOT / "docs" / "assets" / "architecture.svg").read_text(encoding="utf-8")
    assert "<foreignObject" not in svg
    assert re.search(r'<svg[^>]*\swidth="\d+"', svg) and re.search(r'<svg[^>]*\sheight="\d+"', svg)


def test_the_demo_gif_stays_under_five_megabytes():
    gif = REPO_ROOT / "docs" / "evidence" / "demo.gif"
    assert gif.stat().st_size < 5_000_000


def test_the_fixture_readme_and_ground_truth_agree_on_the_action_count():
    import json

    expected = json.loads((REPO_ROOT / "fixture" / "EXPECTED_DRIFTS.json").read_text())
    readme = (REPO_ROOT / "fixture" / "README.md").read_text()
    words = {16: "sixteen", 17: "seventeen", 18: "eighteen"}
    assert f"{words[expected['actions_total']]} actions" in readme


def test_the_license_names_the_author():
    assert "Manoj Kumar Chunduru" in (REPO_ROOT / "LICENSE").read_text()


def test_the_git_identity_carries_no_ai_attribution():
    if not (REPO_ROOT / ".git").exists():
        pytest.skip("needs the git checkout")
    log = subprocess.run(
        ["git", "log", "--format=%an <%ae>%n%(trailers)%n%b"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert "Co-Authored-By" not in log and "Co-authored-by" not in log
    assert "Generated with" not in log and "noreply@anthropic" not in log
