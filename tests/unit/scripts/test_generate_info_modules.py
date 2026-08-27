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
        if spec.get("pagination_type", "int") != "none":
            expected_options.add("page_size")
        assert set(doc["options"] or {}) == expected_options

        assert yaml.safe_load(blocks["EXAMPLES"])
        returned = yaml.safe_load(blocks["RETURN"])
        expected_return = {spec["result_key"]}
        if spec.get("pagination_type", "int") != "none":
            expected_return.add("total_count")
        assert set(returned) == expected_return


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


BATCH2_MODULES = (
    "nat_gateway_info", "vpn_gateway_info", "gaap_proxy_info",
    "cdn_domain_info", "cloudaudit_event_info", "cwp_machine_info",
    "waf_instance_info", "ssl_certificate_info", "organization_member_info",
    "monitor_alarm_policy_info", "cls_topic_info", "tat_command_info",
    "billing_balance_info",
)


def test_batch2_specs_pin_release_version_added(generator):
    for module in BATCH2_MODULES:
        rendered = generator.render_module(_spec(generator, module))
        assert 'version_added: "0.7.0"' in rendered


def test_page_pagination_renders_page_number(generator):
    rendered = generator.render_module(_spec(generator, "monitor_alarm_policy_info"))
    assert "request.PageNumber = offset // limit + 1" in rendered
    assert "request.PageSize = limit" in rendered
    assert '"module": {"type": "str", "default": "monitor"}' in rendered


def test_token_pagination_renders_next_token_loop(generator):
    rendered = generator.render_module(_spec(generator, "cloudaudit_event_info"))
    assert "request.MaxResults = max_results" in rendered
    assert "    if next_token:\n        request.NextToken = next_token" in rendered
    assert "if response.ListOver or not next_token:" in rendered
    assert '"page_size": {"type": "int", "default": 50}' in rendered
    # Token pagination does not use the offset/limit Paginator.
    assert "Paginator" not in rendered


def test_unpaginated_module_renders_single_call(generator):
    rendered = generator.render_module(_spec(generator, "billing_balance_info"))
    assert "Paginator" not in rendered
    assert 'balance.pop("RequestId", None)' in rendered
    assert "page_size" not in rendered
    assert "options: {}" in rendered


def test_filter_value_field_override(generator):
    rendered = generator.render_module(_spec(generator, "cdn_domain_info"))
    assert "api_filter = models.DomainFilter()" in rendered
    assert "api_filter.Value = values if isinstance(values, list) else [values]" in rendered
