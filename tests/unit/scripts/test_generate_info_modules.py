from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import re
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


def test_zero_based_page_pagination_renders_offset_division(generator):
    # trtc/ccc/bsca number pages from 0; the 1-based offset // limit + 1
    # would skip the first page on these APIs.
    for module in ("trtc_call_info", "ccc_extension_info",
                   "bsca_kb_component_info"):
        spec = _spec(generator, module)
        assert spec.get("page_number_base") == 0
        rendered = generator.render_module(spec)
        assert "request.PageNumber = offset // limit" in rendered
        test_rendered = generator.render_test(spec)
        assert "assert request.PageNumber == 2" in test_rendered
        assert "[0, 1]" in test_rendered


def test_curated_param_no_log_renders_in_argument_spec(generator):
    spec = _spec(generator, "weilingwith_element_profile_page_info")
    rendered = generator.render_module(spec)
    assert ('"application_token": {"type": "str", "required": True, '
            '"no_log": True}' in rendered)


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


# ---------------------------------------------------------------------------
# Resource-skeleton emitter (roadmap #54)
# ---------------------------------------------------------------------------

def _resource_spec(overrides=None):
    spec = {
        "module": "example_thing",
        "version_added": "0.14.0",
        "short_description": "Manage example things",
        "label": "Example thing",
        "resource": "thing",
        "result_key": "thing",
        "service_package": "tencentcloud.example.v20180101",
        "client_module": "example_client",
        "client_class": "ExampleClient",
        "sdk_package": "tencentcloud-sdk-python-example",
        "endpoint": "example.tencentcloudapi.com",
        "identity": ["thing_id"],
        "no_log": [],
        "actions": {
            "create": {"action": "CreateThing", "request_class": "CreateThingRequest"},
            "update": {"action": "UpdateThing", "request_class": "UpdateThingRequest"},
            "delete": {"action": "DeleteThing", "request_class": "DeleteThingRequest"},
        },
        "identify": {"action": "GetThing", "request_class": "GetThingRequest"},
    }
    if overrides:
        spec.update(overrides)
    return spec


def _sdk_prop(rtype, doc):
    """Mimic an SDK request-model @property descriptor.

    Real models expose request fields as class-level properties whose
    ``fget.__doc__`` carries the Chinese description plus a ``:rtype:``
    hint; the generator reads exactly those two things.
    """
    def fget(self):
        return None
    fget.__doc__ = "%s\n:rtype: %s" % (doc, rtype)
    return property(fget)


def _make_request_class(models_mod, name, fields):
    props = {}
    for field, (rtype, doc) in fields.items():
        props[field] = _sdk_prop(rtype, doc)
    setattr(models_mod, name, type(name, (), props))


def _install_fake_sdk(monkeypatch, generator, with_secret=True):
    """Serve fake request models from the generator's import hook.

    Hermetic: no tencentcloud SDK is imported; importlib.import_module is
    patched so %s.models lookups for the fake service package resolve to
    locally built request classes carrying :rtype: hints.
    """
    import importlib as importlib_mod
    import types
    models = types.ModuleType("tencentcloud.example.v20180101.models")
    create_fields = {
        "ThingId": ("str", "ID of the thing"),
        "Name": ("str", "Display name"),
        "Count": ("int", "Number of replicas"),
        "Tags": ("list of str", "Tag keys"),
        "Config": (":class:`tencentcloud.example.v20180101.models.Config`", "Runtime config"),
    }
    if with_secret:
        create_fields["Secret"] = ("str", "Secret token")
    update_fields = dict(create_fields)
    _make_request_class(models, "CreateThingRequest", create_fields)
    _make_request_class(models, "UpdateThingRequest", update_fields)
    _make_request_class(models, "DeleteThingRequest", {"ThingId": ("str", "ID of the thing")})
    _make_request_class(models, "GetThingRequest", {"ThingId": ("str", "ID of the thing")})

    real_import = importlib_mod.import_module

    def _patched(name, *args, **kwargs):
        if name == "tencentcloud.example.v20180101.models":
            return models
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib_mod, "import_module", _patched)
    return models


def test_resource_camel_to_snake(generator):
    mapping = {
        "FunctionName": "function_name",
        "RoutingConfig": "routing_config",
        "FunctionVersion": "function_version",
        "Description": "description",
        "Namespace": "namespace",
        "Name": "name",
        "URL": "url",
        "DBInstanceId": "db_instance_id",
    }
    for camel, snake in mapping.items():
        assert generator._camel_to_snake(camel) == snake, camel


def test_resource_option_shape_mapping(generator):
    # (rtype hint) -> (option type, elements); elements only for lists.
    assert generator._option_shape("str") == ("str", None)
    assert generator._option_shape("int") == ("int", None)
    assert generator._option_shape("float") == ("float", None)
    assert generator._option_shape("bool") == ("bool", None)
    assert generator._option_shape("boolean") == ("bool", None)
    assert generator._option_shape("dict") == ("dict", None)
    assert generator._option_shape(
        ":class:`tencentcloud.scf.v20180416.models.RoutingConfig`") == ("dict", None)
    # list of scalar -> type list, scalar elements
    assert generator._option_shape("list of str") == ("list", "str")
    assert generator._option_shape("list of int") == ("list", "int")
    # list of nested model -> type list, dict elements
    assert generator._option_shape(
        "list of :class:`tencentcloud.cam.v20190116.models.SubUser`") == ("list", "dict")
    # unrecognised and missing hints fall back to str
    assert generator._option_shape("") == ("str", None)
    assert generator._option_shape("mystery-type") == ("str", None)


def test_validate_resource_spec_ok(generator):
    assert generator.validate_resource_specs([_resource_spec()]) == []
    # the curated reference entry validates too
    assert generator.validate_resource_specs(generator.RESOURCE_SPECS) == []


def test_validate_resource_spec_missing_module(generator):
    problems = generator.validate_resource_specs([_resource_spec({"module": None})])
    assert any("missing string 'module'" in problem for problem in problems)


def test_validate_resource_spec_info_suffix_rejected(generator):
    problems = generator.validate_resource_specs([_resource_spec({"module": "example_thing_info"})])
    assert any("do not end in _info" in problem for problem in problems)


def test_validate_resource_spec_duplicate(generator):
    problems = generator.validate_resource_specs([_resource_spec(), _resource_spec()])
    assert any("duplicate resource spec" in problem for problem in problems)


def test_validate_resource_spec_collides_with_info_module(generator, monkeypatch):
    # An info module named example_thing would shadow the write module.
    monkeypatch.setattr(generator, "SPECS", [{"module": "example_thing"}])
    problems = generator.validate_resource_specs([_resource_spec()])
    assert any("collides with an existing _info module" in problem for problem in problems)


def test_validate_resource_spec_missing_keys(generator):
    spec = _resource_spec({"identity": None, "endpoint": None})
    problems = generator.validate_resource_specs([spec])
    assert any("missing required key 'identity'" in problem for problem in problems)
    assert any("missing required key 'endpoint'" in problem for problem in problems)


def test_validate_resource_spec_action_shapes(generator):
    spec = _resource_spec()
    spec["actions"]["create"] = {}
    problems = generator.validate_resource_specs([spec])
    assert any("actions.create needs action and request_class" in problem
               for problem in problems)
    # update is optional but must be complete when present
    spec = _resource_spec()
    spec["actions"]["update"] = {"action": "UpdateThing"}
    problems = generator.validate_resource_specs([spec])
    assert any("actions.update needs action and request_class" in problem
               for problem in problems)
    # delete is mandatory
    spec = _resource_spec()
    del spec["actions"]["delete"]
    problems = generator.validate_resource_specs([spec])
    assert any("actions.delete needs action and request_class" in problem
               for problem in problems)
    # identify is mandatory
    spec = _resource_spec({"identify": {}})
    problems = generator.validate_resource_specs([spec])
    assert any("identify needs action and request_class" in problem
               for problem in problems)


def test_validate_resource_spec_identity_rules(generator):
    # identity must be a non-empty list and not collide with shared args
    spec = _resource_spec({"identity": []})
    problems = generator.validate_resource_specs([spec])
    assert any("identity must be a non-empty list" in problem for problem in problems)

    spec = _resource_spec({"identity": ["region"]})
    problems = generator.validate_resource_specs([spec])
    assert any("collides with the shared argument spec" in problem
               for problem in problems)

    # result_key must be snake_case
    spec = _resource_spec({"result_key": "ThingResult"})
    problems = generator.validate_resource_specs([spec])
    assert any("result_key must be a snake_case identifier" in problem
               for problem in problems)


def test_validate_resource_spec_no_log_shape(generator):
    spec = _resource_spec({"no_log": "secret"})
    problems = generator.validate_resource_specs([spec])
    assert any("no_log must be a list" in problem for problem in problems)


def test_resource_collect_fields_metadata(generator, monkeypatch):
    _install_fake_sdk(monkeypatch, generator)
    collected = generator.collect_resource_fields(_resource_spec())
    assert sorted(collected) == ["create", "delete", "identify", "update"]
    names = [field["name"] for field in collected["create"]]
    assert names == ["thing_id", "name", "count", "tags", "config", "secret"]
    # type mapping: list of str -> type list/elements str; nested -> dict
    by_name = {field["name"]: field for field in collected["create"]}
    assert by_name["thing_id"]["type"] == "str"
    assert by_name["count"]["type"] == "int"
    assert by_name["tags"]["type"] == "list" and by_name["tags"]["elements"] == "str"
    assert by_name["config"]["type"] == "dict"
    assert by_name["secret"]["doc"] == "Secret token"
    # identify request only carries the identity field
    assert [field["name"] for field in collected["identify"]] == ["thing_id"]


def test_resource_collect_missing_request_class(generator, monkeypatch):
    _install_fake_sdk(monkeypatch, generator)
    spec = _resource_spec()
    spec["actions"]["create"]["request_class"] = "CreateMissingRequest"
    with pytest.raises(ValueError) as exc:
        generator.collect_resource_fields(spec)
    assert "has no request class CreateMissingRequest" in str(exc.value)


def test_resource_collect_identity_not_declared(generator, monkeypatch):
    _install_fake_sdk(monkeypatch, generator)
    spec = _resource_spec({"identity": ["missing_id"]})
    with pytest.raises(ValueError) as exc:
        generator.collect_resource_fields(spec)
    assert "identity option 'missing_id'" in str(exc.value)


def test_resource_collect_missing_sdk_package(generator):
    # A service package that is not installed (and not faked) surfaces the
    # install hint instead of crashing.
    spec = _resource_spec()
    spec["service_package"] = "tencentcloud.no_such_service.v99999999"
    with pytest.raises(ValueError) as exc:
        generator.collect_resource_fields(spec)
    assert "install tencentcloud-sdk-python-example and retry" in str(exc.value)


def _resource_doc_blocks(rendered):
    blocks = {}
    for name in ("DOCUMENTATION", "EXAMPLES", "RETURN"):
        marker = "%s = r'''" % name
        start = rendered.index(marker) + len(marker)
        end = rendered.index("'''", start)
        blocks[name] = rendered[start:end]
    return blocks


def _resource_arg_keys(rendered):
    region = rendered.split("argument_spec={", 1)[1].split("supports_check_mode", 1)[0]
    return set(re.findall(r'^\s{12}"([a-z_]+)":', region, re.M))


def _resource_builder_params(rendered):
    """All params["x"] reads inside the build_*_request helpers only."""
    region = rendered.split("def build_create_request", 1)[1]
    region = region.split("def run_module", 1)[0]
    return set(re.findall(r'params\["([a-z_]+)"\]', region))


def test_resource_skeleton_renders_consistent_module(generator, monkeypatch):
    """The skeleton is internally consistent: DOCUMENTATION options,
    argument_spec keys and builder params all agree, and identity options
    are required + written unconditionally while the rest are guarded."""
    _install_fake_sdk(monkeypatch, generator)
    spec = _resource_spec({"no_log": ["secret"]})
    collected = generator.collect_resource_fields(spec)
    rendered = generator.render_resource_skeleton(spec, collected)

    blocks = _resource_doc_blocks(rendered)
    doc = yaml.safe_load(blocks["DOCUMENTATION"])
    assert yaml.safe_load(blocks["EXAMPLES"])
    returned = yaml.safe_load(blocks["RETURN"])
    assert "thing" in returned

    local_options = {"state", "thing_id", "name", "count", "tags", "config", "secret"}
    # shared params from base_argument_spec() are documented (validate-modules)
    documented = set(doc["options"])
    assert documented == local_options | {"retries", "waiter_delay", "waiter_timeout", "user_agent"}
    assert _resource_arg_keys(rendered) == local_options
    # builders read exactly the resource options (state is a run_module concern)
    assert _resource_builder_params(rendered) == local_options - {"state"}

    # identity: required in docs + argspec, written unconditionally in builders
    assert doc["options"]["thing_id"]["required"] is True
    assert '"thing_id": {"type": "str", "required": True}' in rendered
    assert '    request.ThingId = params["thing_id"]' in rendered
    assert 'if params["thing_id"] is not None' not in rendered
    # optional fields are guarded in builders
    assert '    if params["name"] is not None:\n        request.Name = params["name"]' in rendered
    # nested dict option carries the modelling comment, list carries elements
    assert "# config maps to a nested API object" in rendered
    assert '"config": {"type": "dict"}' in rendered
    assert '"tags": {"type": "list", "elements": "str"}' in rendered
    assert "    elements: str" in blocks["DOCUMENTATION"]
    # no_log option is marked in both places
    assert '"secret": {"type": "str", "no_log": True}' in rendered
    assert "    no_log: true" in blocks["DOCUMENTATION"]
    # shared-parameter defaults match module_utils/base.py
    assert doc["options"]["retries"]["default"] == 5
    assert doc["options"]["user_agent"]["default"] == "ansible-collection.susunola.tencentcloud"

    # wiring: lazy loader, action wrappers, identify/find, run_module paths
    for needle in (
        "def _load_example():", "def build_create_request(models, params):",
        "def build_update_request(models, params):", "def build_delete_request(models, params):",
        "def build_identify_request(models, params):", "def find_thing(module, client, models, params):",
        "def _create(module, client, models, params):", "def _update(module, client, models, params):",
        "def _delete(module, client, models, params):", "module.sdk_call(client.CreateThing, request)",
        "module.sdk_call(client.GetThing, request)",
        'client = module.create_client(example_client.ExampleClient, "example.tencentcloudapi.com")',
        "supports_check_mode=True", "# TODO(resource)",
    ):
        assert needle in rendered, needle
    # state absent/present branches + check mode
    assert 'module.exit_json(changed=False, msg="Example thing already absent")' in rendered
    assert "Would delete Example thing" in rendered
    assert "Would create Example thing" in rendered
    assert 'module.exit_json(changed=False, thing=current, msg="Example thing is up to date")' in rendered
    # valid python
    compile(rendered, "example_thing.py", "exec")


def test_resource_skeleton_without_update_action(generator, monkeypatch):
    """Optional update is absent from a spec -> no update builder/wrapper."""
    _install_fake_sdk(monkeypatch, generator)
    spec = _resource_spec()
    del spec["actions"]["update"]
    assert generator.validate_resource_specs([spec]) == []
    collected = generator.collect_resource_fields(spec)
    assert collected["update"] == []
    rendered = generator.render_resource_skeleton(spec, collected)
    assert "build_update_request" not in rendered
    assert "def _update(" not in rendered
    assert "UpdateThing" not in rendered
    assert "def build_create_request" in rendered
    assert "def build_delete_request" in rendered
    assert "def find_thing" in rendered
    compile(rendered, "no_update.py", "exec")


@pytest.fixture
def scratch_dir():
    """Writable temp dir for write-once tests.

    pytest's tmp_path/tmpdir fixtures create their base dir through the
    host file broker which is unavailable in some sandboxes; a plain
    tempfile.mkdtemp works everywhere (contract tests use the same trick).
    """
    import shutil
    import tempfile
    path = Path(tempfile.mkdtemp(prefix="gen-skel-"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_resource_main_write_once_and_check(monkeypatch, generator, scratch_dir):
    """_resource_main scaffolds a missing module, never overwrites an
    existing file and verifies existing files against the SDK in --check."""
    import io
    _install_fake_sdk(monkeypatch, generator)
    monkeypatch.setattr(generator, "MODULES_DIR", scratch_dir)
    # replace, not prepend: the real scf_alias entry must not be verified
    # against the (uninstalled) real SDK inside these hermetic tests
    monkeypatch.setattr(generator, "RESOURCE_SPECS", [_resource_spec()])

    class Args:
        def __init__(self, resource, do_print=False, do_check=False):
            self.resource = resource
            self.print = do_print
            self.check = do_check

    out, err = io.StringIO(), io.StringIO()
    assert generator._resource_main(Args("example_thing"), out, err) == 0
    target = scratch_dir / "example_thing.py"
    assert target.exists()
    assert "wrote skeleton:" in out.getvalue()
    first = target.read_text()

    # write-once: a second run leaves the finished file untouched
    out, err = io.StringIO(), io.StringIO()
    assert generator._resource_main(Args("example_thing"), out, err) == 0
    assert "exists:" in out.getvalue()
    assert target.read_text() == first

    # --check passes for an existing verified spec
    out, err = io.StringIO(), io.StringIO()
    assert generator._resource_main(Args("example_thing", do_check=True), out, err) == 0
    # unknown module name is reported on stderr with exit code 1
    out, err = io.StringIO(), io.StringIO()
    assert generator._resource_main(Args("no_such_module"), out, err) == 1
    assert "no RESOURCE_SPECS entry" in err.getvalue()


def test_resource_main_print_renders_without_writing(monkeypatch, generator, scratch_dir):
    import io
    _install_fake_sdk(monkeypatch, generator)
    monkeypatch.setattr(generator, "MODULES_DIR", scratch_dir)
    monkeypatch.setattr(generator, "RESOURCE_SPECS", [_resource_spec()])
    out, err = io.StringIO(), io.StringIO()
    args = type("Args", (), {"resource": "example_thing", "print": True, "check": False})()
    assert generator._resource_main(args, out, err) == 0
    assert "def run_module():" in out.getvalue()
    assert not (scratch_dir / "example_thing.py").exists()


def test_resource_main_check_flags_missing_scaffold(monkeypatch, generator, scratch_dir):
    import io
    _install_fake_sdk(monkeypatch, generator)
    monkeypatch.setattr(generator, "MODULES_DIR", scratch_dir)
    monkeypatch.setattr(generator, "RESOURCE_SPECS", [_resource_spec()])
    out, err = io.StringIO(), io.StringIO()
    args = type("Args", (), {"resource": None, "print": False, "check": True})()
    assert generator._resource_main(args, out, err) == 1
    assert "missing scaffolds: example_thing.py" in err.getvalue()
