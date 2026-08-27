from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_info_modules.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_info_modules", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator():
    return _load_generator()


def _spec(generator, module_name):
    for spec in generator.SPECS:
        if spec["module"] == module_name:
            return spec
    raise AssertionError("no spec for %s" % module_name)


def _doc_blocks(rendered):
    blocks = {}
    for name in ("DOCUMENTATION", "EXAMPLES", "RETURN"):
        marker = "%s = r'''" % name
        start = rendered.index(marker) + len(marker)
        end = rendered.index("'''", start)
        blocks[name] = rendered[start:end]
    return blocks


def test_generator_path_exists():
    assert GENERATOR_PATH.exists()


def test_every_spec_renders_valid_documentation_yaml(generator):
    for spec in generator.SPECS:
        rendered = generator.render_module(spec)
        blocks = _doc_blocks(rendered)
        doc = yaml.safe_load(blocks["DOCUMENTATION"])
        assert doc["module"] == spec["module"]
        assert doc["version_added"] == spec.get("version_added", generator.VERSION_ADDED)
        assert doc["extends_documentation_fragment"] == "tencentcloud.cloud.tencentcloud"

        expected_options = {param["name"] for param in spec["extra_params"]}
        if spec["ids"]:
            expected_options.add(spec["ids"]["param"])
        if spec["filters"]:
            expected_options.add("filters")
        expected_options.add("page_size")
        assert set(doc["options"]) == expected_options

        assert yaml.safe_load(blocks["EXAMPLES"])
        returned = yaml.safe_load(blocks["RETURN"])
        assert set(returned) == {spec["result_key"], "total_count"}


def test_generated_files_are_up_to_date(generator):
    for spec in generator.SPECS:
        path = generator.module_path(spec)
        assert path.exists(), "run scripts/generate_info_modules.py"
        content = path.read_text()
        assert content.startswith("#!/usr/bin/python")
        assert generator.MARKER in content
        assert content == generator.render_module(spec)


def test_version_added_default_is_current(generator):
    assert generator.VERSION_ADDED == "0.6.0"
    for module in ("as_scaling_group_info", "scf_function_info",
                   "cfs_file_system_info", "lighthouse_instance_info",
                   "cynosdb_cluster_info", "postgres_instance_info",
                   "sqlserver_instance_info", "mariadb_instance_info",
                   "es_cluster_info", "ckafka_instance_info",
                   "tcr_instance_info", "apigateway_service_info"):
        rendered = generator.render_module(_spec(generator, module))
        assert 'version_added: "0.6.0"' in rendered


def test_legacy_specs_keep_original_version_added(generator):
    for module in ("clb_load_balancer_info", "cdb_instance_info", "tke_cluster_info",
                   "cbs_disk_info", "redis_instance_info", "mongodb_instance_info",
                   "kms_key_info", "dnspod_record_info"):
        rendered = generator.render_module(_spec(generator, module))
        assert 'version_added: "0.4.0"' in rendered


def test_nested_response_fields_render_none_guards(generator):
    rendered = generator.render_module(_spec(generator, "ckafka_instance_info"))
    assert "response.Result.InstanceList if response.Result is not None else None" in rendered
    assert "response.Result.TotalCount if response.Result is not None else None" in rendered


def test_query_filter_model_override(generator):
    rendered = generator.render_module(_spec(generator, "cynosdb_cluster_info"))
    assert "api_filter = models.QueryFilter()" in rendered
    assert "api_filter.Names = [name]" in rendered


def test_optional_extra_param_renders_none_guard(generator):
    rendered = generator.render_module(_spec(generator, "cfs_file_system_info"))
    assert "    if file_system_id is not None:\n        request.FileSystemId = file_system_id" in rendered
