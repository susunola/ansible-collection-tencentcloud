# -*- coding: utf-8 -*-
"""Hermetic tests for the module-test skeleton generator (P0-01 / roadmap #57).

The generator (``scripts/generate_module_test_skeleton.py``) statically reads a
write module's source -- it never imports the module, the SDK or ansible -- so
these tests run in a plain environment: the generator is loaded with
``importlib`` and fixture modules are written to ``tmp_path`` and analyzed by
pointing the generator's ``MODULES_DIR``/``TESTS_DIR`` at the fixture dir.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import ast
import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_module_test_skeleton.py"

# A small write module exercising every shape the generator must recognize:
# two lazy loaders, unconditional + conditional request-builder fields,
# params-ref and arg-ref assignments, a find helper, a waiter, an absent
# branch, a check_mode switch and a wrapped SDK error.
FIXTURE_MODULE = """\
def _load_a():
    return None, None


def _load_b():
    return None, None


def build_get(models, key_id):
    request = models.DescribeThingRequest()
    request.ThingId = key_id
    return request


def build_create(models, p):
    request = models.CreateThingRequest()
    request.Name = p["name"]
    request.Kind = "fixed-kind"
    if p["extra"]:
        request.Extra = p["extra"]
    return request


def find(module, client, models, key_id, name):
    return None


def wait_ready(module, client, key_id):
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "key_id": {"required": True, "type": "str"},
            "name": {"type": "str"},
            "kind": {"choices": ["alpha", "fixed-kind"], "default": "alpha"},
            "tags": {"type": "list"},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, sdk_a = _load_a()
    models2, cm = _load_b()
    client = module.create_client(sdk_a.ThingClient, "thing.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["key_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False)
            if not module.check_mode:
                module.sdk_call(client.DeleteThing, build_get(models, p["key_id"]))
            module.exit_json(changed=True)
        if current is None:
            if not module.check_mode:
                module.sdk_call(client.CreateThing, build_create(models, p))
            module.exit_json(changed=True)
        wait_ready(module, client, p["key_id"])
        module.exit_json(changed=False)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))
"""

# A run_module that reads check_mode off a NON-module object: the generator
# must not emit a check_mode stub for it (regression for the name guard).
GUARD_MODULE = """\
def _load():
    return None, None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {}}, supports_check_mode=True)
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.XClient, "x.tencentcloudapi.com")
    cfg = {"check_mode": False}
    if cfg["check_mode"]:
        module.exit_json(changed=True)
    module.exit_json(changed=False)
"""


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_module_test_skeleton", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator():
    return _load_generator()


@pytest.fixture
def fixture_dir(tmp_path, generator):
    """Point the generator at a temp dir holding ``fixture_thing.py``.

    The module-level MODULES_DIR/TESTS_DIR are restored afterwards so tests
    that analyze real repo modules are not affected by ordering.
    """
    (tmp_path / "fixture_thing.py").write_text(FIXTURE_MODULE)
    (tmp_path / "guard_thing.py").write_text(GUARD_MODULE)
    old_modules, old_tests = generator.MODULES_DIR, generator.TESTS_DIR
    generator.MODULES_DIR = tmp_path
    generator.TESTS_DIR = tmp_path
    yield tmp_path
    generator.MODULES_DIR = old_modules
    generator.TESTS_DIR = old_tests


# --------------------------------------------------------------------------- #
# analysis
# --------------------------------------------------------------------------- #


def test_generator_path_exists():
    assert GENERATOR_PATH.exists()


def test_analyze_fixture_payload(generator, fixture_dir):
    info = generator.analyze("fixture_thing")
    assert info["loaders"] == ["_load_a", "_load_b"]
    assert info["client_class"] == "ThingClient"
    assert sorted(info["ops"]) == ["CreateThing", "DeleteThing"]
    assert info["has_absent"] is True
    assert info["has_check_mode"] is True
    assert info["has_wrapped_sdk_error"] is True
    assert info["required_test"] is True  # key_id required=True
    helper_names = [h["name"] for h in info["helpers"]]
    assert helper_names == ["build_get", "build_create", "find", "wait_ready"]
    by_name = {h["name"]: h for h in info["helpers"]}
    # unconditional fields only: the `if p["extra"]` assignment is excluded.
    # lineno is asserted against the source in test_skeleton_line_numbers_*.
    assert [(f[0], f[1]) for f in by_name["build_get"]["fields"]] == [("ThingId", "key_id")]
    assert [(f[0], f[1]) for f in by_name["build_create"]["fields"]] == [("Kind", "'fixed-kind'")]
    assert by_name["find"]["is_find"] is True
    assert by_name["wait_ready"]["is_waiter"] is True


def test_analyze_spec_parses_inline_and_missing_defaults(generator, fixture_dir):
    spec = generator.analyze("fixture_thing")["spec"]
    assert set(spec) == {"state", "key_id", "name", "kind", "tags"}
    assert spec["key_id"]["required"] is True
    assert generator._param_value("key_id", spec["key_id"]) == "key-xxxx"
    assert generator._param_value("name", spec["name"]) is None  # no default
    assert generator._param_value("tags", spec["tags"]) == []
    assert generator._param_value("state", spec["state"]) == "present"


def test_analyze_check_mode_guard_ignores_non_module_objects(generator, fixture_dir):
    info = generator.analyze("guard_thing")
    assert info["has_check_mode"] is False
    assert info["has_absent"] is False


def test_analyze_missing_module_raises(generator, fixture_dir):
    with pytest.raises(generator.AnalysisError):
        generator.analyze("ghost")


def test_analyze_no_run_module_raises(generator, fixture_dir):
    (fixture_dir / "info_thing.py").write_text("def main():\n    pass\n")
    with pytest.raises(generator.AnalysisError):
        generator.analyze("info_thing")


def test_analyze_no_load_helper_raises(generator, fixture_dir):
    (fixture_dir / "direct_thing.py").write_text(
        "def run_module():\n    module = TencentCloudModule(argument_spec={})\n"
        "    module.exit_json(changed=False)\n"
    )
    with pytest.raises(generator.AnalysisError):
        generator.analyze("direct_thing")


def test_real_module_ops_exclude_client_class(generator):
    """Regression: create_client(cm.ApigatewayClient, ...) must not become an op."""
    info = generator.analyze("api_gateway_api_key")
    assert info["client_class"] == "ApigatewayClient"
    assert "ApigatewayClient" not in info["ops"]
    assert set(info["ops"]) == {
        "CreateApiKey",
        "DeleteApiKey",
        "DescribeApiKey",
        "DescribeApiKeysStatus",
        "UpdateApiKey",
    }


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #


def test_render_is_valid_python_and_marked(generator, fixture_dir):
    info = generator.analyze("fixture_thing")
    rendered = generator.render(info)
    compile(rendered, "<skeleton>", "exec")
    assert rendered.startswith(generator.MARKER)


def _fixture_lineno(predicate):
    """Line number (1-based) of the first matching node in FIXTURE_MODULE."""
    tree = ast.parse(FIXTURE_MODULE)
    for node in ast.walk(tree):
        if predicate(node):
            return node.lineno
    raise AssertionError("no matching node in FIXTURE_MODULE")


def test_render_fixture_structure(generator, fixture_dir):
    info = generator.analyze("fixture_thing")
    rendered = generator.render(info)
    # loaders: fixture patches each _load_*; sdk-error test iterates a real tuple
    assert "def client(monkeypatch):" in rendered
    assert "monkeypatch.setattr(\n        mod,\n        '_load_a'," in rendered
    assert "monkeypatch.setattr(\n        mod,\n        '_load_b'," in rendered
    assert "for loader in ('_load_a', '_load_b'):" in rendered
    # _params() carries every spec key, None for no-default scalars
    assert "'key_id': 'key-xxxx'" in rendered
    assert "'name': None" in rendered
    assert "'tags': []" in rendered
    assert "'state': 'present'" in rendered
    # builders: unconditional field assertions; conditional ones absent
    thing_id_line = _fixture_lineno(
        lambda n: isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Attribute)
        and n.targets[0].attr == "ThingId"
    )
    kind_line = _fixture_lineno(
        lambda n: isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Attribute)
        and n.targets[0].attr == "Kind"
    )
    assert "assert request.ThingId == 'key-xxxx'  # module line %d" % thing_id_line in rendered
    assert "assert request.Kind == 'fixed-kind'  # module line %d" % kind_line in rendered
    assert "request.Extra" not in rendered
    # non-builder helpers are non-executing xfail stubs
    assert "def test_find_helper(client):" in rendered
    assert "def test_wait_ready_waiter(client):" in rendered
    assert rendered.count("pytest.fail(\"unfinished skeleton\")") >= 5
    # run_module main-path tests
    assert "def test_required_arguments_enforced(monkeypatch):" in rendered
    assert "def test_sdk_error_is_reported(monkeypatch):" in rendered
    assert "class _BoomClient(object):" in rendered
    assert "def test_run_module_present_reconcile(client):" in rendered
    assert "def test_run_module_absent_remove(client):" in rendered
    assert "def test_run_module_check_mode_dry_run(client):" in rendered


def test_render_sdk_satisfiers_fill_early_gates(generator, fixture_dir):
    info = generator.analyze("fixture_thing")
    rendered = generator.render(info)
    # name has no default; the sdk-error test overrides it with a placeholder so
    # find(...) is reached before the (booming) SDK call. key_id is already in
    # _params() (required), tags is a list and must NOT be placeholder-filled.
    assert "_run_args(name='name-xxxx')" in rendered
    assert "access_key" not in rendered  # fixture has no such option


def test_render_check_mode_guard_module_has_no_dry_run_stub(generator, fixture_dir):
    info = generator.analyze("guard_thing")
    rendered = generator.render(info)
    assert "test_run_module_check_mode_dry_run" not in rendered


def test_render_real_module_has_correct_satisfiers(generator):
    """api_gateway: name placeholder must clear the body pre-check so the
    wrapped-SDK-error path (not the early fail_json) is what gets exercised."""
    info = generator.analyze("api_gateway_api_key")
    rendered = generator.render(info)
    assert "_run_args(access_key_id='access-key-xxxx', access_key_secret='access-key-secret-xxxx', name='name-xxxx')" in rendered
    assert "for loader in ('_load',):" in rendered


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_print_writes_nothing(generator, fixture_dir, capsys):
    assert generator.main(["--module-test", "fixture_thing", "--print"]) == 0
    out = capsys.readouterr().out
    assert generator.MARKER in out
    assert not (fixture_dir / "test_fixture_thing.py").exists()


def test_cli_write_then_check_then_idempotent(generator, fixture_dir, capsys):
    assert generator.main(["--module-test", "fixture_thing"]) == 0
    target = fixture_dir / "test_fixture_thing.py"
    assert target.exists()
    first = target.read_text()
    assert generator.MARKER in first
    assert generator.main(["--module-test", "fixture_thing"]) == 0  # up to date
    assert generator.main(["--module-test", "fixture_thing", "--check"]) == 0
    assert target.read_text() == first


def test_cli_check_fails_when_skeleton_drifts(generator, fixture_dir):
    assert generator.main(["--module-test", "fixture_thing"]) == 0
    target = fixture_dir / "test_fixture_thing.py"
    target.write_text(target.read_text() + "\n# drift\n")
    assert generator.main(["--module-test", "fixture_thing", "--check"]) == 1


def test_cli_never_rewrites_hand_finished_file(generator, fixture_dir):
    assert generator.main(["--module-test", "fixture_thing"]) == 0
    target = fixture_dir / "test_fixture_thing.py"
    hand_finished = target.read_text().replace(generator.MARKER + "\n", "", 1)
    hand_finished += "\n\ndef test_human_added():\n    pass\n"
    target.write_text(hand_finished)
    assert generator.main(["--module-test", "fixture_thing"]) == 0
    assert target.read_text() == hand_finished  # never rewritten


def test_cli_unknown_module_exits_1(generator, fixture_dir, capsys):
    assert generator.main(["--module-test", "ghost", "--print"]) == 1
    assert "cannot analyze" in capsys.readouterr().err


def test_skeleton_line_numbers_point_at_fixture_source(generator, fixture_dir):
    """The '# module line N' annotations must match the analyzed module."""
    info = generator.analyze("fixture_thing")
    rendered = generator.render(info)
    thing_id_line = _fixture_lineno(
        lambda n: isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Attribute)
        and n.targets[0].attr == "ThingId"
    )
    assert "assert request.ThingId == 'key-xxxx'  # module line %d" % thing_id_line in rendered
    wait_line = _fixture_lineno(lambda n: isinstance(n, ast.FunctionDef) and n.name == "wait_ready")
    assert "plugins/modules/fixture_thing.py:%d-%d" % (wait_line, wait_line + 1) in rendered
    run_line = _fixture_lineno(lambda n: isinstance(n, ast.FunctionDef) and n.name == "run_module")
    assert "module lines %d-" % run_line in rendered
