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
        assert doc["extends_documentation_fragment"] == "susunola.tencentcloud.tencentcloud"

        expected_options = {param["name"] for param in spec["extra_params"]}
        if spec["ids"]:
            expected_options.add(spec["ids"]["param"])
        if spec["filters"]:
            expected_options.add("filters")
        if generator._page_size_field(spec) is not None:
            expected_options.add("page_size")
        assert set(doc["options"] or {}) == expected_options

        assert yaml.safe_load(blocks["EXAMPLES"])
        returned = yaml.safe_load(blocks["RETURN"])
        expected_return = {spec["result_key"], "request_id"}
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


def test_auto_specs_are_appended_and_pin_release_version(generator):
    auto_path = GENERATOR_PATH.with_name("info_specs_auto.py")
    assert auto_path.exists(), "run scripts/discover_info_specs.py"
    spec = importlib.util.spec_from_file_location("info_specs_auto", auto_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.SPECS_AUTO, "info_specs_auto.py must not be empty"
    by_name = {entry["module"] for entry in generator.SPECS}
    for entry in module.SPECS_AUTO:
        assert entry["module"] in by_name
        # 0.8.0 specs are reused verbatim by discovery; new batches pin the
        # release they were nominated in.
        assert entry["version_added"] in ("0.8.0", "0.9.0")
        rendered = generator.render_module(entry)
        assert 'version_added: "%s"' % entry["version_added"] in rendered


def test_token_module_renders_custom_token_fields(generator):
    rendered = generator.render_module(_spec(generator, "ams_task_info"))
    assert "request.Limit = max_results" in rendered
    assert "request.PageToken = next_token" in rendered
    assert "next_token = response.PageToken" in rendered


def test_token_module_without_page_size_field(generator):
    rendered = generator.render_module(_spec(generator, "chdfs_file_system_info"))
    assert "page_size" not in rendered
    assert "response.IsOver or not next_token" in rendered


def test_list_module_renders_single_call(generator):
    rendered = generator.render_module(_spec(generator, "advisor_strategy_info"))
    assert "Paginator" not in rendered
    assert "items = response.Strategies or []" in rendered
    assert "total_count=len(strategies)" in rendered


def test_simple_spec_tests_are_generated(generator):
    for spec in generator.SPECS:
        if not generator.is_simple_spec(spec):
            continue
        path = generator.test_path(spec)
        assert path.exists(), "run scripts/generate_info_modules.py"
        content = path.read_text()
        if generator.MARKER in content:
            assert content == generator.render_test(spec)


def test_hand_written_tests_survive_regeneration(generator):
    """Hand-finished test files (no MARKER) are never rewritten or checked.

    The generator skips any test file that does not carry the generation
    MARKER (see ``main()``), so hand-written coverage is preserved even for
    specs that now qualify for the generated test template (e.g. curated
    specs whose extra parameters are simple scalars).
    """
    for name in ("kms_key_info", "dnspod_record_info", "cfs_file_system_info",
                 "cloudaudit_event_info", "monitor_alarm_policy_info",
                 "billing_balance_info"):
        spec = _spec(generator, name)
        content = generator.test_path(spec).read_text()
        assert generator.MARKER not in content


def _top_level_arg_count(region):
    """Count comma-separated args in *region*, ignoring commas inside braces.

    Dict parameters (e.g. essbasic's Agent) nest braces in the call, so a
    naive ``str.count(",")`` would over-count; only depth-0 commas separate
    positional arguments.
    """
    depth = 0
    count = 1
    for char in region:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "," and depth == 0:
            count += 1
    return count


def test_curated_extra_params_tests_match_module_signature(generator):
    """Generated unit tests for curated specs exercise the required params.

    Curated modules (REQUIRED_PARAM_OVERRIDES) carry extra parameters, so
    their generated tests must call ``build_request`` with the same
    positional signature and pass every parameter through ``run_module``.
    """
    for module_name in ("tbaas_block_info", "essbasic_template_info",
                        "emr_node_data_disk_info"):
        spec = _spec(generator, module_name)
        assert generator.is_simple_spec(spec)
        rendered = generator.render_test(spec)
        # The generated file is in sync with the module signature (the repo's
        # own generated test file is checked against render_test output).
        path = generator.test_path(spec)
        content = path.read_text()
        assert generator.MARKER in content
        assert content == rendered
        # build_request is called with every extra param sample populated:
        # the test's positional args match the module signature exactly.
        build_line = [line for line in rendered.splitlines()
                      if "build_request(FakeModels" in line][0]
        call_args = build_line.split("(", 1)[1].rsplit(")", 1)[0]
        module_src = generator.render_module(spec)
        def_line = [line for line in module_src.splitlines()
                    if line.startswith("def build_request(")][0]
        def_args = def_line.split("(", 1)[1].rsplit(")", 1)[0]
        assert _top_level_arg_count(call_args) == _top_level_arg_count(def_args)
        # run_module is driven with the same parameters (keyword args on the
        # _run(...) call inside the pagination test).
        pagination_section = rendered.split("def test_run_module_paginates", 1)[1]
        for param in spec["extra_params"]:
            assert "%s=" % param["name"] in pagination_section


# ---------------------------------------------------------------------------
# validate_specs (generator tightening)
# ---------------------------------------------------------------------------

def _valid_spec(overrides=None):
    spec = {
        "module": "example_thing_info",
        "version_added": "0.12.0",
        "service_package": "tencentcloud.example.v20180101",
        "client_module": "example_client",
        "client_class": "ExampleClient",
        "sdk_package": "tencentcloud-sdk-python-example",
        "endpoint": "example.tencentcloudapi.com",
        "action": "DescribeThings",
        "request_class": "DescribeThingsRequest",
        "ids": None,
        "filters": None,
        "extra_params": [],
        "response_items": "ThingSet",
        "response_total": "TotalCount",
        "result_key": "things",
        "pagination_type": "int",
    }
    if overrides:
        spec.update(overrides)
    return spec


def test_valid_spec_passes_validation(generator):
    assert generator.validate_specs([_valid_spec()]) == []


def test_validate_missing_module_key(generator):
    problems = generator.validate_specs([_valid_spec({"module": None})])
    assert any("missing string 'module'" in problem for problem in problems)


def test_validate_non_info_module_name(generator):
    problems = generator.validate_specs([_valid_spec({"module": "example_thing"})])
    assert any("must end with _info" in problem for problem in problems)


def test_validate_duplicate_module_names(generator):
    problems = generator.validate_specs([_valid_spec(), _valid_spec()])
    assert any("duplicate module name" in problem for problem in problems)


def test_validate_missing_required_key(generator):
    problems = generator.validate_specs([_valid_spec({"request_class": None})])
    assert any("missing required key 'request_class'" in problem for problem in problems)


def test_validate_unknown_pagination_type(generator):
    problems = generator.validate_specs([_valid_spec({"pagination_type": "cursor"})])
    assert any("unknown pagination_type" in problem for problem in problems)


def test_validate_paginated_spec_requires_response_items(generator):
    problems = generator.validate_specs([_valid_spec({"response_items": None})])
    assert any("requires a response_items field" in problem for problem in problems)


def test_validate_none_spec_must_not_declare_response_items(generator):
    problems = generator.validate_specs([
        _valid_spec({"pagination_type": "none", "response_items": "ThingSet",
                     "response_total": None})
    ])
    assert any("must not declare response_items" in problem for problem in problems)


def test_validate_deep_dotted_response_path(generator):
    problems = generator.validate_specs([_valid_spec({"response_items": "A.B.C"})])
    assert any("more than one dot" in problem for problem in problems)


def test_validate_bad_ids_shape(generator):
    problems = generator.validate_specs([_valid_spec({"ids": {"param": "x"}})])
    assert any("ids must be None or a dict with param/field/doc" in problem
               for problem in problems)


def test_validate_bad_filters_shape(generator):
    problems = generator.validate_specs([_valid_spec({"filters": {}})])
    assert any("filters must be None or a dict with a doc" in problem
               for problem in problems)


def test_validate_extra_param_missing_field(generator):
    spec = _valid_spec({"extra_params": [
        {"name": "zone_id", "type": "str", "doc": "Zone ID."}
    ]})
    problems = generator.validate_specs([spec])
    assert any("extra_param 'zone_id' missing 'field'" in problem for problem in problems)


def test_validate_extra_param_non_bool_required(generator):
    spec = _valid_spec({"extra_params": [
        {"name": "zone_id", "field": "ZoneId", "type": "str", "doc": "Zone ID.",
         "required": "yes"}
    ]})
    problems = generator.validate_specs([spec])
    assert any("'required' must be a bool" in problem for problem in problems)


def test_validate_extra_param_duplicate_and_region_collision(generator):
    spec = _valid_spec({"extra_params": [
        {"name": "region", "field": "Region", "type": "str", "doc": "collides"},
        {"name": "zone_id", "field": "ZoneId", "type": "str", "doc": "Zone ID."},
        {"name": "zone_id", "field": "ZoneId2", "type": "str", "doc": "dup"},
    ]})
    problems = generator.validate_specs([spec])
    assert any("collides with the shared region parameter" in problem
               for problem in problems)
    assert any("duplicate extra_param 'zone_id'" in problem for problem in problems)


def test_validate_real_combined_specs_pass(generator):
    # The full curated + auto SPECS list must validate cleanly; CI runs
    # generate_info_modules.py --check which rejects any violation.
    assert generator.validate_specs(generator.SPECS) == []
