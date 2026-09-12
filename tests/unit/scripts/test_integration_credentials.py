from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

import importlib.util
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENV = {
    "TENCENTCLOUD_SECRET_ID": "IKIDTESTSECRETID",
    "TENCENTCLOUD_SECRET_KEY": "s3cr3t-key-value",
    "TENCENTCLOUD_REGION": "ap-hongkong",
}


def test_values_from_env_reads_the_tencentcloud_prefix():
    module = load_script("integration_credentials")
    values = module.values_from_env(ENV)
    assert values["secret_id"] == "IKIDTESTSECRETID"
    assert values["secret_key"] == "s3cr3t-key-value"
    assert values["region"] == "ap-hongkong"
    assert values["token"] == ""


def test_values_from_env_falls_back_to_the_ci_default_region():
    module = load_script("integration_credentials")
    assert module.values_from_env({})["region"] == module.DEFAULT_REGION


def test_values_from_env_region_override_wins():
    module = load_script("integration_credentials")
    assert module.values_from_env(ENV, region="ap-singapore")["region"] == "ap-singapore"


def test_write_creates_a_private_profile_file(tmp_path):
    module = load_script("integration_credentials")
    path = module.write(module.values_from_env(ENV), tmp_path)
    assert path == tmp_path / ".tencentcloud" / "default.configure"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    text = path.read_text(encoding="utf-8")
    assert "[default]" in text
    assert "secret_id = IKIDTESTSECRETID" in text
    assert "region = ap-hongkong" in text
    # the optional token is omitted rather than written empty
    assert "token" not in text


def test_render_includes_the_token_when_present():
    module = load_script("integration_credentials")
    text = module.render({"secret_id": "a", "secret_key": "b", "token": "tok", "region": "r"})
    assert "token = tok" in text


def test_check_round_trips_a_written_profile(tmp_path):
    module = load_script("integration_credentials")
    module.write(module.values_from_env(ENV), tmp_path)
    ok, values = module.check(tmp_path)
    assert ok
    assert values["secret_id"] == "IKIDTESTSECRETID"
    assert values["region"] == "ap-hongkong"


def test_check_reports_missing_for_an_absent_file(tmp_path):
    module = load_script("integration_credentials")
    ok, values = module.check(tmp_path / "nowhere")
    assert ok is False
    assert values == {}


def test_write_refuses_to_materialise_without_a_key_pair(tmp_path):
    module = load_script("integration_credentials")
    try:
        module.write(module.values_from_env({"TENCENTCLOUD_SECRET_ID": "only-id"}), tmp_path)
    except module.MissingCredentials:
        pass
    else:  # pragma: no cover - the guard above is the contract
        raise AssertionError("MissingCredentials was not raised")
    assert not (tmp_path / ".tencentcloud" / "default.configure").exists()


def test_main_returns_two_without_credentials(tmp_path, capsys, monkeypatch):
    module = load_script("integration_credentials")
    for key in ("TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert module.main(["--home", str(tmp_path)]) == 2
    assert "TENCENTCLOUD_SECRET_ID" in capsys.readouterr().err


def test_main_writes_and_reports_the_region(tmp_path, capsys, monkeypatch):
    module = load_script("integration_credentials")
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    assert module.main(["--home", str(tmp_path)]) == 0
    assert "region=ap-hongkong" in capsys.readouterr().out
    assert module.check(tmp_path)[0]


def test_main_dry_run_writes_nothing_and_masks_secrets(tmp_path, capsys, monkeypatch):
    module = load_script("integration_credentials")
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    assert module.main(["--home", str(tmp_path), "--dry-run", "--region", "ap-guangzhou"]) == 0
    out = capsys.readouterr().out
    assert "s3cr3t-key-value" not in out
    assert "IKIDTESTSECRETID" not in out
    assert not (tmp_path / ".tencentcloud" / "default.configure").exists()


def test_main_check_reports_missing(tmp_path, capsys):
    module = load_script("integration_credentials")
    assert module.main(["--home", str(tmp_path / "nowhere"), "--check"]) == 1
    assert "missing" in capsys.readouterr().out
