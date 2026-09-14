"""Unit tests for scripts/check_doc_figures.py.

The guard exists because two headline figures on the benchmark page had
already drifted — the unit-test file count was quoted after two new files
had landed, and plugin_utils was called 6 when it has 5 — and nothing
re-measured them. So the anchor test here is the real repo: measure it and
assert every figure is still stated. The rest exercise `validate` against
synthetic figures so the failures do not depend on the repo's shape.
"""

from __future__ import absolute_import, division, print_function

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_doc_figures.py"
PANORAMA = REPO_ROOT / "docs" / "panorama.html"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "check_doc_figures", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return _load_script()


@pytest.fixture(scope="module")
def figures(guard):
    return guard.measure(REPO_ROOT)


def test_the_guard_measures_the_real_repo(guard, figures):
    """A wrong root would leave `figures` empty and every check below vacuous."""
    assert figures["modules"] > 0
    assert figures["write modules"] > 0
    assert figures["info modules"] > 0
    assert figures["unit test files"] >= figures["module-level unit files"]


def test_measured_figures_are_internally_consistent(figures):
    assert figures["modules"] == (
        figures["write modules"] + figures["info modules"])
    assert figures["read-side gap"] <= figures["write modules"]
    assert figures["products with write"] <= figures["products"]
    assert figures["sanity ignores"] <= figures["sanity ignore budget"]


def test_real_panorama_states_every_figure(guard, figures):
    """The regression this guard was written for: rot on the benchmark page."""
    problems = guard.validate(figures, PANORAMA.read_text(encoding="utf-8"))
    assert problems == [], "\n".join(problems)


def _with(figures, **overrides):
    """`validate` walks every claim, so tests must hand it a complete map."""
    merged = dict(figures)
    merged.update(overrides)
    return merged


def _doc_plus(line):
    """The real page plus one synthetic line, so only one claim is at stake."""
    return PANORAMA.read_text(encoding="utf-8") + "\n模块 %s 个\n" % line


def test_validate_accepts_the_comma_form(guard, figures):
    assert guard.validate(_with(figures, modules=1234),
                          _doc_plus("1,234")) == []


def test_validate_accepts_the_plain_form(guard, figures):
    assert guard.validate(_with(figures, modules=1234),
                          _doc_plus("1234")) == []


def test_validate_flags_a_stale_value(guard, figures):
    problems = guard.validate(_with(figures, modules=891),
                              "a line with 890 模块\n")
    stale = [p for p in problems if p.startswith("modules:")]
    assert len(stale) == 1
    assert "891" in stale[0]


def test_validate_flags_a_figure_the_doc_dropped(guard, figures):
    problems = guard.validate(_with(figures, modules=891),
                              "nothing but prose\n")
    assert any(p.startswith("modules:") for p in problems)


def test_validate_flags_only_the_figure_that_moved(guard, figures):
    """One wrong figure must not make the whole report unreadable."""
    doc = PANORAMA.read_text(encoding="utf-8").replace("1,017 个", "1,999 个")
    problems = guard.validate(figures, doc)
    assert len(problems) == 1 and problems[0].startswith("unit test files:")


def test_validate_ignores_the_keyword_on_other_lines(guard, figures):
    """The keyword must share a line with the value, not merely coexist."""
    problems = guard.validate(_with(figures, modules=891), "模块\n891\n")
    assert any(p.startswith("modules:") for p in problems)


def test_validate_flags_an_unmeasured_figure(guard):
    assert guard.validate({}, "any 模块 1 line\n")


def test_validate_reports_every_claim(guard):
    """Every claim is checked; a truncated CLAIMS list would skip figures."""
    assert len(guard.validate({}, "")) == len(guard.CLAIMS)


def _fake_root(tmp_path):
    """A root that reuses the real tree but owns its own panorama."""
    for name in ("plugins", "roles", "tests", "scripts", ".github"):
        (tmp_path / name).symlink_to(REPO_ROOT / name)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "panorama.html").write_text(
        PANORAMA.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_main_is_green_on_the_current_docs(guard, tmp_path, capsys):
    root = _fake_root(tmp_path)
    assert guard.main(["--root", str(root), "--check"]) == 0
    assert "all %d figures" % len(guard.CLAIMS) in capsys.readouterr().out


def test_main_fails_when_a_figure_is_stale(guard, tmp_path, capsys):
    root = _fake_root(tmp_path)
    panorama = root / "docs" / "panorama.html"
    text = panorama.read_text(encoding="utf-8")
    assert "1,017 个" in text, "the anchor string changed; retarget the test"
    panorama.write_text(text.replace("1,017 个", "1,014 个"), encoding="utf-8")
    assert guard.main(["--root", str(root), "--check"]) == 1
    assert "unit test files" in capsys.readouterr().out


def test_main_report_mode_does_not_fail(guard, tmp_path):
    root = _fake_root(tmp_path)
    panorama = root / "docs" / "panorama.html"
    panorama.write_text("nothing but prose\n", encoding="utf-8")
    assert guard.main(["--root", str(root)]) == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
