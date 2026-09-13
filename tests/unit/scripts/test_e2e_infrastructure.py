from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

import importlib.util
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_reaper(monkeypatch):
    # resource_reaper imports e2e_manifest by name rather than by path, so
    # scripts/ has to be importable. Running it as `python scripts/...` puts
    # that directory on sys.path automatically; importing it as a module does
    # not.
    monkeypatch.syspath_prepend(ROOT / "scripts")
    return load_script("resource_reaper")


def manifest_entry(**overrides):
    entry = {
        "run_id": "1",
        "target": "cmq_queue",
        "resource_type": "cmq_queue",
        "resource_id": "q-1",
        "region": "ap-guangzhou",
    }
    entry.update(overrides)
    return entry


def add_via_cli(module, path, *extra):
    argv = [
        "--path",
        str(path),
        "add",
        "--run-id",
        "1",
        "--target",
        "cmq_queue",
        "--resource-type",
        "cmq_queue",
        "--resource-id",
        "q-1",
        "--region",
        "ap-guangzhou",
    ]
    return module.main(argv + list(extra))


def test_manifest_validate_and_load(tmp_path):
    module = load_script("e2e_manifest")
    entry = {
        "run_id": "1",
        "target": "cmq_queue",
        "resource_type": "cmq_queue",
        "resource_id": "q-1",
        "region": "ap-guangzhou",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    module.validate(entry)
    path = tmp_path / "manifest.jsonl"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    assert module.load(path)[0]["resource_id"] == "q-1"


def test_integration_impact_selection():
    module = load_script("integration_impact")
    coverage = {"targets": {"cmq_queue": {"cost": "low", "modules": ["cmq_queue"]}, "dbbrain_sql_filter": {"cost": "high", "modules": ["dbbrain_sql_filter"]}}}
    assert module.select({"plugins/modules/cmq_queue.py"}, coverage) == ["cmq_queue"]
    assert module.select({"plugins/module_utils/base.py"}, coverage) == ["cmq_queue"]


def test_integration_registry_validation(tmp_path, monkeypatch):
    module = load_script("integration_impact")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / "plugins/modules").mkdir(parents=True)
    (tmp_path / "plugins/modules/example.py").write_text("", encoding="utf-8")
    target = tmp_path / "tests/integration/targets/example/tasks"
    target.mkdir(parents=True)
    (target / "main.yml").write_text("---\n", encoding="utf-8")
    assert module.validate_registry({"targets": {"example": {"cost": "free", "modules": ["example"]}}}) == []
    problems = module.validate_registry({"targets": {"missing": {"cost": "expensive", "modules": ["gone"]}}})
    assert len(problems) == 3


def test_manifest_add_derives_the_expiry_from_the_ttl(tmp_path):
    """Targets run without gathered facts, so they pass a TTL, not a date."""
    module = load_script("e2e_manifest")
    path = tmp_path / "manifest.jsonl"
    before = datetime.now(timezone.utc)
    assert add_via_cli(module, path, "--ttl-seconds", "7200") == 0
    expiry = datetime.fromisoformat(module.load(path)[0]["expires_at"])
    assert before + timedelta(seconds=7000) <= expiry <= before + timedelta(seconds=7400)


def test_manifest_add_defaults_to_the_standard_ttl(tmp_path):
    module = load_script("e2e_manifest")
    path = tmp_path / "manifest.jsonl"
    before = datetime.now(timezone.utc)
    assert add_via_cli(module, path) == 0
    expiry = datetime.fromisoformat(module.load(path)[0]["expires_at"])
    assert before + timedelta(seconds=module.DEFAULT_TTL_SECONDS - 200) <= expiry
    assert expiry <= before + timedelta(seconds=module.DEFAULT_TTL_SECONDS + 200)


def test_manifest_add_prefers_an_explicit_expiry(tmp_path):
    module = load_script("e2e_manifest")
    path = tmp_path / "manifest.jsonl"
    fixed = "2030-01-01T00:00:00+00:00"
    assert add_via_cli(module, path, "--expires-at", fixed, "--ttl-seconds", "60") == 0
    assert module.load(path)[0]["expires_at"] == fixed


def test_manifest_add_still_requires_the_caller_supplied_fields(tmp_path):
    """Only the expiry became optional; the rest of the record is mandatory."""
    module = load_script("e2e_manifest")
    path = tmp_path / "manifest.jsonl"
    argv = [
        "--path",
        str(path),
        "add",
        "--run-id",
        "1",
        "--target",
        "cmq_queue",
        "--resource-type",
        "cmq_queue",
        "--resource-id",
        "q-1",
        # --region deliberately omitted
    ]
    with pytest.raises(SystemExit):
        module.main(argv)
    assert not path.exists()


def test_reaper_flags_an_expired_resource(tmp_path, monkeypatch):
    module = load_reaper(monkeypatch)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        json.dumps(manifest_entry(expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "plan.json"
    assert module.main(["--manifest", str(manifest), "--output", str(output), "--fail-on-expired"]) == 1
    assert json.loads(output.read_text(encoding="utf-8"))["expired"][0]["resource_id"] == "q-1"


def test_reaper_leaves_a_live_resource_alone(tmp_path, monkeypatch):
    module = load_reaper(monkeypatch)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        json.dumps(manifest_entry(expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "plan.json"
    assert module.main(["--manifest", str(manifest), "--output", str(output), "--fail-on-expired"]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["expired"] == []


def test_reaper_says_so_when_the_manifest_is_empty(tmp_path, monkeypatch, capsys):
    """0 expired on an empty manifest is absence of data, not a clean bill."""
    module = load_reaper(monkeypatch)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("", encoding="utf-8")
    output = tmp_path / "plan.json"
    assert module.main(["--manifest", str(manifest), "--output", str(output), "--warn-on-empty"]) == 0
    assert "manifest is empty" in capsys.readouterr().err


def test_reaper_stays_quiet_without_the_flag(tmp_path, monkeypatch, capsys):
    module = load_reaper(monkeypatch)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("", encoding="utf-8")
    output = tmp_path / "plan.json"
    assert module.main(["--manifest", str(manifest), "--output", str(output)]) == 0
    assert capsys.readouterr().err == ""


def test_integration_targets_do_not_depend_on_gathered_facts():
    """Facts are on by default, but not for every target.

    ansible-test sets gather_facts: true for ordinary targets and false for
    network and Windows ones and for anything carrying the `gather_facts/no/`
    alias. A target that templates ansible_date_time fails at task
    finalisation in those cases - and with `ignore_errors` on the manifest
    task that failure stays invisible while the reaper audits nothing.
    """
    offenders = sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "tests/integration/targets").glob("*/tasks/*.yml")
        if re.search(r"\{\{[^}]*ansible_date_time", path.read_text(encoding="utf-8"))
    )
    assert offenders == []
