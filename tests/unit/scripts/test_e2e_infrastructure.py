import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_validate_and_load(tmp_path):
    module = load_script("e2e_manifest")
    entry = {"run_id": "1", "target": "cmq_queue", "resource_type": "cmq_queue", "resource_id": "q-1", "region": "ap-guangzhou", "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
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
