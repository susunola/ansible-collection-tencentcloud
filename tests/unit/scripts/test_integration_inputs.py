"""Unit tests for scripts/integration_inputs.py."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "integration_inputs.py"


def load():
    spec = importlib.util.spec_from_file_location("integration_inputs", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Collect() reads the real environment; start from a known-empty one."""
    import os

    for key in list(os.environ):
        if key.startswith("TENCENTCLOUD_") or key == "GITHUB_RUN_ID":
            monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def mod():
    return load()


def test_collect_picks_up_prefixed_variables(mod, monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_REGION", "ap-hongkong")
    monkeypatch.setenv("TENCENTCLOUD_RUN_BILLED_TARGETS", "1")
    monkeypatch.setenv("UNRELATED_VARIABLE", "keep-out")
    assert mod.collect() == {
        "TENCENTCLOUD_REGION": "ap-hongkong",
        "TENCENTCLOUD_RUN_BILLED_TARGETS": "1",
    }


def test_collect_includes_github_run_id(mod, monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "123456")
    assert mod.collect() == {"GITHUB_RUN_ID": "123456"}


def test_collect_never_carries_credentials(mod, monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_SECRET_ID", "IKIDsecret")
    monkeypatch.setenv("TENCENTCLOUD_SECRET_KEY", "topsecret")
    monkeypatch.setenv("TENCENTCLOUD_TOKEN", "ststoken")
    monkeypatch.setenv("TENCENTCLOUD_REGION", "ap-guangzhou")
    assert mod.collect() == {"TENCENTCLOUD_REGION": "ap-guangzhou"}


def test_collect_skips_empty_values(mod, monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_TKE_CLUSTER_ID", "")
    assert mod.collect() == {}


def test_collect_is_sorted(mod, monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_ZONE", "ap-guangzhou-1")
    monkeypatch.setenv("TENCENTCLOUD_CDB_ZONE", "ap-guangzhou-3")
    assert list(mod.collect()) == ["TENCENTCLOUD_CDB_ZONE", "TENCENTCLOUD_ZONE"]


def test_path_is_under_home(mod, tmp_path):
    assert mod.inputs_path(str(tmp_path)) == tmp_path / ".tencentcloud" / "e2e_inputs.yml"


def test_write_creates_a_private_file_with_the_values(mod, tmp_path, monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_REGION", "ap-hongkong")
    monkeypatch.setenv("TENCENTCLOUD_RUN_BILLED_TARGETS", "1")
    path = mod.write(mod.collect(), str(tmp_path))
    assert path.exists()
    assert oct(path.stat().st_mode)[-3:] == "600"
    body = path.read_text(encoding="utf-8")
    assert "TENCENTCLOUD_RUN_BILLED_TARGETS: '1'" in body
    assert "TENCENTCLOUD_REGION: ap-hongkong" in body


def test_write_renders_an_empty_mapping_rather_than_null(mod, tmp_path):
    path = mod.write({}, str(tmp_path))
    assert mod.read(str(tmp_path)) == {}
    assert "{}" in path.read_text(encoding="utf-8")


def test_read_round_trips(mod, tmp_path, monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_ZONE", "ap-guangzhou-3")
    mod.write(mod.collect(), str(tmp_path))
    assert mod.read(str(tmp_path)) == {"TENCENTCLOUD_ZONE": "ap-guangzhou-3"}


def test_read_returns_empty_for_a_missing_file(mod, tmp_path):
    assert mod.read(str(tmp_path)) == {}


def test_check_reports_a_missing_file(mod, tmp_path):
    ok, path, values = mod.check(str(tmp_path))
    assert ok is False
    assert values == {}
    assert path == tmp_path / ".tencentcloud" / "e2e_inputs.yml"


def test_check_round_trips(mod, tmp_path, monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_REGION", "ap-hongkong")
    mod.write(mod.collect(), str(tmp_path))
    ok, path, values = mod.check(str(tmp_path))
    assert ok is True
    assert values == {"TENCENTCLOUD_REGION": "ap-hongkong"}


def test_masked_hides_secret_looking_values(mod):
    values = {
        "TENCENTCLOUD_DBBRAIN_SESSION_TOKEN": "abcdefghijkl",
        "TENCENTCLOUD_REGION": "ap-guangzhou",
    }
    assert mod.masked(values) == {
        "TENCENTCLOUD_DBBRAIN_SESSION_TOKEN": "abcd…(12 chars)",
        "TENCENTCLOUD_REGION": "ap-guangzhou",
    }


def test_main_writes_by_default(mod, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TENCENTCLOUD_REGION", "ap-guangzhou")
    assert mod.main(["--home", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "wrote" in out
    assert "1 key(s)" in out
    assert mod.read(str(tmp_path))["TENCENTCLOUD_REGION"] == "ap-guangzhou"


def test_main_region_overrides_the_environment(mod, tmp_path, monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_REGION", "ap-guangzhou")
    assert mod.main(["--home", str(tmp_path), "--region", "ap-hongkong"]) == 0
    assert mod.read(str(tmp_path))["TENCENTCLOUD_REGION"] == "ap-hongkong"


def test_main_dry_run_writes_nothing_and_masks(mod, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TENCENTCLOUD_DBBRAIN_SESSION_TOKEN", "abcdefghijkl")
    monkeypatch.setenv("TENCENTCLOUD_REGION", "ap-guangzhou")
    assert mod.main(["--home", str(tmp_path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert not (tmp_path / ".tencentcloud" / "e2e_inputs.yml").exists()
    assert "abcdefghijkl" not in out
    assert "(12 chars)" in out


def test_main_check_exits_one_when_absent(mod, tmp_path, capsys):
    assert mod.main(["--home", str(tmp_path), "--check"]) == 1
    assert "missing" in capsys.readouterr().out


def test_main_check_exits_zero_when_present(mod, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TENCENTCLOUD_REGION", "ap-guangzhou")
    mod.main(["--home", str(tmp_path)])
    capsys.readouterr()
    assert mod.main(["--home", str(tmp_path), "--check"]) == 0
    assert "ok:" in capsys.readouterr().out
