"""Unit tests for scripts/release_check.py (the pre-release guard)."""

from __future__ import absolute_import, division, print_function

import importlib.util
import io
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "release_check.py"
GALAXY_PATH = REPO_ROOT / "galaxy.yml"


def _load_script():
    spec = importlib.util.spec_from_file_location("release_check", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return _load_script()


def make_state(guard, version="1.2.0", local=(), remote=(), tag=None):
    return {
        "namespace": "susunola",
        "name": "tencentcloud",
        "version": version,
        "tag": tag,
        "local_tags": set(local),
        "remote_tags": None if remote is None else set(remote),
    }


def test_version_tuple_rejects_non_semver(guard):
    assert guard.version_tuple("1.2.0") == (1, 2, 0)
    assert guard.version_tuple("1.2") is None
    assert guard.version_tuple("1.2.0rc1") is None
    assert guard.version_tuple("") is None


def test_version_format(guard):
    assert guard.check_version_format(make_state(guard))[0] == guard.PASS
    status, detail = guard.check_version_format(make_state(guard, version="1.2"))
    assert status == guard.FAIL
    assert "1.2" in detail


def test_version_bumped_first_release(guard):
    status, detail = guard.check_version_bumped(make_state(guard, local=()))
    assert status == guard.PASS


def test_version_bumped_ahead_of_latest_tag(guard):
    status, detail = guard.check_version_bumped(
        make_state(guard, version="1.2.0", local=("v1.0.0", "v1.1.0", "v0.9.0")))
    assert status == guard.PASS
    assert "v1.1.0" in detail


def test_version_bumped_fails_when_version_is_already_released(guard):
    status, detail = guard.check_version_bumped(
        make_state(guard, version="1.1.0", local=("v1.1.0",)))
    assert status == guard.FAIL
    assert "bump the version" in detail


def test_version_bumped_fails_when_behind(guard):
    status, detail = guard.check_version_bumped(
        make_state(guard, version="1.0.0", local=("v1.1.0",)))
    assert status == guard.FAIL


def test_version_bumped_skips_unparseable_version(guard):
    status, detail = guard.check_version_bumped(make_state(guard, version="nope"))
    assert status == guard.SKIP


def test_tag_free(guard):
    status, detail = guard.check_tag_free(
        make_state(guard, version="1.2.0", local=("v1.1.0",), remote=("v1.1.0",)))
    assert status == guard.PASS


def test_tag_free_fails_on_local_and_remote(guard):
    status, detail = guard.check_tag_free(
        make_state(guard, version="1.2.0", local=("v1.2.0",), remote=("v1.2.0",)))
    assert status == guard.FAIL
    assert "locally" in detail and "origin" in detail


def test_tag_free_skips_when_remote_unreachable(guard):
    status, detail = guard.check_tag_free(
        make_state(guard, version="1.2.0", local=(), remote=None))
    assert status == guard.SKIP
    assert "unreachable" in detail


def test_tag_matches(guard):
    assert guard.check_tag_matches(make_state(guard, tag=None))[0] == guard.SKIP
    assert guard.check_tag_matches(make_state(guard, tag="v1.2.0"))[0] == guard.PASS
    status, detail = guard.check_tag_matches(make_state(guard, tag="v9.9.9"))
    assert status == guard.FAIL
    assert "does not match" in detail


def test_fragments_fail_when_directory_is_empty(guard, tmp_path, monkeypatch):
    empty = tmp_path / "fragments"
    empty.mkdir()
    monkeypatch.setattr(guard, "FRAGMENTS_DIR", empty)
    status, detail = guard.check_fragments(make_state(guard))
    assert status == guard.FAIL
    assert "no changelog fragments" in detail


def test_fragments_pass_and_count(guard, tmp_path, monkeypatch):
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    for name in ("a.yml", "b.yaml", "README.md"):
        (fragments / name).write_text("bugfixes:\n  - x\n", encoding="utf-8")
    monkeypatch.setattr(guard, "FRAGMENTS_DIR", fragments)
    status, detail = guard.check_fragments(make_state(guard))
    assert status == guard.PASS
    # README.md is not a fragment and must not be counted.
    assert "2 changelog fragment(s)" in detail


def test_no_duplicate(guard, tmp_path, monkeypatch):
    changelog = tmp_path / "changelog.yaml"
    changelog.write_text(
        "releases:\n  1.1.0:\n    release_date: '2026-09-04'\n", encoding="utf-8")
    monkeypatch.setattr(guard, "CHANGELOG_PATH", changelog)

    status, detail = guard.check_no_duplicate(make_state(guard, version="1.1.0"))
    assert status == guard.FAIL
    assert "already holds a 1.1.0 entry" in detail

    status, detail = guard.check_no_duplicate(make_state(guard, version="1.2.0"))
    assert status == guard.PASS


def test_no_duplicate_skips_missing_changelog(guard, tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "CHANGELOG_PATH", tmp_path / "nope.yaml")
    assert guard.check_no_duplicate(make_state(guard))[0] == guard.SKIP


def test_clean_worktree(guard, monkeypatch):
    monkeypatch.setattr(guard, "run", lambda *a, **k: (0, "", ""))
    assert guard.check_clean_worktree(make_state(guard))[0] == guard.PASS

    dirty = " M galaxy.yml\n?? scripts/new.py\n"
    monkeypatch.setattr(guard, "run", lambda *a, **k: (0, dirty, ""))
    status, detail = guard.check_clean_worktree(make_state(guard))
    assert status == guard.FAIL
    assert "2 uncommitted change(s)" in detail


def test_clean_worktree_skips_without_git(guard, monkeypatch):
    monkeypatch.setattr(guard, "run", lambda *a, **k: (None, "", "git is not installed"))
    assert guard.check_clean_worktree(make_state(guard))[0] == guard.SKIP


def test_fragment_lint(guard, monkeypatch):
    monkeypatch.setattr(guard, "run", lambda *a, **k: (None, "", "not installed"))
    assert guard.check_fragment_lint(make_state(guard))[0] == guard.SKIP

    monkeypatch.setattr(guard, "run", lambda *a, **k: (0, "clean\n", ""))
    assert guard.check_fragment_lint(make_state(guard))[0] == guard.PASS

    monkeypatch.setattr(guard, "run", lambda *a, **k: (1, "", "fragment is broken\n"))
    status, detail = guard.check_fragment_lint(make_state(guard))
    assert status == guard.FAIL
    assert "fragment is broken" in detail


def test_optional_check_is_skipped_unless_lint_requested(guard, monkeypatch):
    monkeypatch.setattr(guard, "run", lambda *a, **k: (0, "clean\n", ""))
    state = make_state(guard)
    skipped = guard.run_checks(state, set())
    name, status, detail = next(r for r in skipped if r[0] == "fragment-lint")
    assert status == guard.SKIP
    assert "--lint" in detail

    run = guard.run_checks(state, set(), lint=True)
    name, status, detail = next(r for r in run if r[0] == "fragment-lint")
    assert status == guard.PASS


def test_ignore_marks_check_skipped(guard):
    results = guard.run_checks(make_state(guard), {"clean-worktree"})
    name, status, detail = next(r for r in results if r[0] == "clean-worktree")
    assert status == guard.SKIP
    assert "ignored via --ignore" in detail


def test_coveragerc_is_not_confused_with_coverage_data(guard):
    """.coveragerc is a committed config file; .coverage is generated data.

    A prefix test on ".coverage" matches both, which would fail every dry
    run on a tree that legitimately ships .coveragerc.
    """
    assert guard.forbidden_in([".coveragerc", "plugins/modules/cvm_instance.py"]) == []
    assert guard.forbidden_in([".coverage"]) == [".coverage"]
    assert guard.forbidden_in([".coverage.atom.1234.5678"]) == [".coverage."]


def test_forbidden_in_finds_packaged_junk(guard):
    names = ["MANIFEST.json", "plugins/", "docs/docsite/build/html/index.html",
             ".pytest_cache/v/cache/nodeids", ".github/workflows/ci.yml",
             "tests/unit/foo.py", "coverage.xml"]
    assert guard.forbidden_in(names) == [
        ".github/", ".pytest_cache/", "coverage.xml", "docs/docsite/build/", "tests/",
    ]


def test_plan_lines_up(guard, monkeypatch):
    """The five release steps align regardless of version width."""
    monkeypatch.setattr(guard, "FRAGMENTS_DIR", REPO_ROOT / "changelogs" / "fragments")
    for version in ("1.2.0", "10.20.30"):
        out = io.StringIO()
        guard.plan(make_state(guard, version=version), out)
        arrows = {line.index("->") for line in out.getvalue().splitlines() if "->" in line}
        assert len(arrows) == 1, out.getvalue()
        assert "push tag v%s" % version in out.getvalue()


def test_unknown_ignore_name_is_rejected(guard):
    err = io.StringIO()
    assert guard.main(["--ignore", "no-such-check"], out=io.StringIO(), err=err) == 2
    assert "unknown check name" in err.getvalue()


def test_every_check_has_a_name_and_a_function(guard):
    assert [name for func, name in guard.CHECKS] == guard.CHECK_NAMES


def test_real_galaxy_yml_is_a_release_version(guard):
    """The committed galaxy.yml parses and carries an X.Y.Z version."""
    import yaml
    galaxy = yaml.safe_load(GALAXY_PATH.read_text(encoding="utf-8"))
    assert guard.version_tuple(str(galaxy["version"])) is not None


def test_json_output_reports_readiness(guard, monkeypatch):
    """--json emits one object per check plus a readiness flag."""
    monkeypatch.setattr(
        guard, "build_state",
        lambda tag=None: make_state(guard, version="1.2.0",
                                    local=("v1.1.0",), remote=("v1.1.0",)))
    monkeypatch.setattr(guard, "FRAGMENTS_DIR", REPO_ROOT / "changelogs" / "fragments")
    monkeypatch.setattr(guard, "run", lambda *a, **k: (0, "", ""))
    out = io.StringIO()
    assert guard.main(["--json"], out=out, err=io.StringIO()) == 0
    payload = json.loads(out.getvalue())
    assert payload["ready"] is True
    assert payload["version"] == "1.2.0"
    assert {item["check"] for item in payload["results"]} == set(guard.CHECK_NAMES)
