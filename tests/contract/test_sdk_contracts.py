# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""SDK contract tests: build module requests against the real Tencent Cloud SDK.

Unit-test fakes (``tests/unit/plugins/modules/harness.py``) accept arbitrary
attribute assignment, so they cannot catch request fields the real API would
silently ignore. Two production bugs of that class have shipped already:
``models.Filter()`` rejecting constructor kwargs, and APIs requiring
``Limit``/``ProjectId`` as strings instead of ints.

These tests close the gap: every write module's request builders and every
``_info`` module's ``build_request`` are invoked with the *real* SDK
``models`` modules, and each resulting request object is audited:

1. the builder must not raise,
2. every attribute stored in the instance ``__dict__`` must correspond to a
   declared ``@property`` of its class (Tencent Cloud SDK models declare
   their fields as class-level properties backed by ``_<Name>`` attributes;
   an unknown attribute is a wrong field name that ``_serialize`` mangles
   and the API silently ignores),
3. when the property's docstring declares a simple ``:rtype:`` (``str``,
   ``int``, ``bool``, ``list of str``, ``list of int``) the assigned value
   must match it,
4. ``_serialize(allow_none=True)`` must round-trip without error and must
   only produce keys that are declared properties of the request class.

These tests are intentionally NOT part of ``ansible-test units``: the
ansible-test environments do not install the Tencent Cloud SDK. They run
in CI as a plain pytest step (see ``.github/workflows/ci.yml``) that first
installs ``requirements.txt``. When the SDK (or ansible-core) is not
importable, every test here skips.

Coverage is auto-discovered: ``test_module_request_builders_are_exercised``
scans every ``plugins/modules/*.py`` for functions that construct SDK
``*Request`` objects and fails loudly when such a builder is exercised by
no contract test. New modules therefore need no registration to be caught;
genuine exceptions (the ``cos_*`` modules use the ``qcloud_cos`` SDK, and
``cam_policy_info.run_module`` builds one request inline) live in the
reasoned ``NO_API3_CONTRACT`` / ``UNEXERCISED_BUILDERS`` tables below.

Not covered, by design:

- ``cos_bucket`` / ``cos_bucket_info``: COS is not an API 3.0 service; the
  ``qcloud_cos`` SDK has no declarative request models to audit.
- Response handling: only request construction is under contract here.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import ast
import importlib
import importlib.util
import os
import re
import sys
import tempfile
from types import SimpleNamespace

import pytest


def _spec_available(name):
    try:
        return importlib.util.find_spec(name) is not None
    except ImportError:
        return False


SDK_AVAILABLE = _spec_available("tencentcloud.common.abstract_model")
ANSIBLE_AVAILABLE = _spec_available("ansible.module_utils.basic")

pytestmark = pytest.mark.skipif(
    not (SDK_AVAILABLE and ANSIBLE_AVAILABLE),
    reason="requires the Tencent Cloud SDK packages and ansible-core; "
           "run via the CI sanity job or any env with requirements.txt installed",
)


def _ensure_collection_importable():
    """Make ``ansible_collections.tencentcloud.cloud`` importable.

    The preferred layout is the standard ``.../ansible_collections/
    tencentcloud/cloud`` checkout (CI, synced test trees). When this file
    sits in a bare repository checkout, a temporary symlink tree provides
    the same layout so the collection namespace resolves.
    """
    cloud_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if (os.path.basename(cloud_dir) == "cloud"
            and os.path.basename(os.path.dirname(cloud_dir)) == "tencentcloud"
            and os.path.basename(os.path.dirname(os.path.dirname(cloud_dir))) == "ansible_collections"):
        root = os.path.dirname(os.path.dirname(os.path.dirname(cloud_dir)))
    else:
        root = tempfile.mkdtemp(prefix="tc-contract-layout-")
        target_dir = os.path.join(root, "ansible_collections", "tencentcloud")
        os.makedirs(target_dir)
        os.symlink(cloud_dir, os.path.join(target_dir, "cloud"))
    if root not in sys.path:
        sys.path.insert(0, root)


_ensure_collection_importable()


def _models(service):
    """Import a real SDK ``models`` module, e.g. ``vpc.v20170312``."""
    return importlib.import_module("tencentcloud.%s.models" % service)


def _import_plugin(name):
    return importlib.import_module(
        "ansible_collections.tencentcloud.cloud.plugins.modules." + name
    )


class _StubResponse(object):
    """Permissive stand-in for SDK *responses* and values inside them.

    Responses are out of contract scope; this stub only keeps the module
    code paths that touch response objects alive.
    """

    def __getattr__(self, name):
        return _StubResponse()

    def __bool__(self):
        return False

    def __iter__(self):
        return iter(())

    def _serialize(self, allow_none=True):
        return {}


class _StubClient(object):
    """SDK client stand-in: any API operation returns a stub response."""

    def __getattr__(self, name):
        def _operation(request):
            return _StubResponse()
        return _operation


class _RecordingModule(object):
    """Module stand-in that captures every request passed to ``sdk_call``."""

    def __init__(self):
        self.params = {"region": "ap-guangzhou"}
        self.requests = []

    def sdk_call(self, operation, request):
        self.requests.append(request)
        return operation(request)


_RTYPE_RE = re.compile(r":rtype:\s*(?P<rtype>[^\n]+)")


def _declared_properties(obj):
    """Return the ``@property`` descriptors declared on the object's class."""
    return {
        name: attr
        for name, attr in vars(type(obj)).items()
        if isinstance(attr, property)
    }


def _check_rtype(location, prop, value):
    """Check a non-None value against the property's declared ``:rtype:``."""
    doc = prop.fget.__doc__ or ""
    match = _RTYPE_RE.search(doc)
    if not match:
        return []
    rtype = match.group("rtype").strip()

    def fail():
        return [
            "%s: SDK declares rtype %r but the module assigns %r (%s)"
            % (location, rtype, value, type(value).__name__)
        ]

    if rtype == "str":
        return [] if isinstance(value, str) else fail()
    if rtype == "int":
        return [] if isinstance(value, int) and not isinstance(value, bool) else fail()
    if rtype == "bool":
        return [] if isinstance(value, bool) else fail()
    if rtype.startswith("list of str"):
        ok = isinstance(value, list) and all(isinstance(item, str) for item in value)
        return [] if ok else fail()
    if rtype.startswith("list of int"):
        ok = isinstance(value, list) and all(
            isinstance(item, int) and not isinstance(item, bool) for item in value
        )
        return [] if ok else fail()
    # Nested model references and exotic rtypes are audited structurally.
    return []


def _audit_model(obj, where, errors):
    """Recursively audit an SDK model object against its class contract."""
    from tencentcloud.common.abstract_model import AbstractModel

    declared = _declared_properties(obj)
    for key, value in vars(obj).items():
        if key == "_headers":
            continue
        location = "%s.%s" % (where, key)
        if not key.startswith("_"):
            errors.append(
                "%s: attribute %r is not a declared property of %s; "
                "the API would silently ignore it"
                % (location, key, type(obj).__name__)
            )
            continue
        prop = declared.get(key[1:])
        if prop is None:
            errors.append(
                "%s: %r is not a declared property of %s; "
                "the API would silently ignore it"
                % (location, key[1:], type(obj).__name__)
            )
            continue
        if value is None:
            continue
        errors.extend(_check_rtype(location, prop, value))
        children = value if isinstance(value, list) else [value]
        for index, child in enumerate(children):
            if isinstance(child, AbstractModel):
                child_where = (
                    "%s[%d]" % (location, index) if isinstance(value, list) else location
                )
                _audit_model(child, child_where, errors)


def audit_request(request, where):
    """Assert a built request object honors the real SDK contract.

    Returns a list of human-readable contract violations; empty means pass.
    """
    errors = []
    _audit_model(request, where, errors)
    try:
        serialized = request._serialize(allow_none=True)
    except Exception as exc:
        errors.append("%s: _serialize(allow_none=True) raised %r" % (where, exc))
        return errors
    if not isinstance(serialized, dict):
        errors.append("%s: _serialize(allow_none=True) did not return a dict" % where)
        return errors
    declared = set(_declared_properties(request))
    for key in serialized:
        if key not in declared:
            errors.append(
                "%s: serialized key %r is not a declared property of %s"
                % (where, key, type(request).__name__)
            )
    return errors


def audit_recorded(module, where):
    """Audit every request captured by a :class:`_RecordingModule`."""
    errors = []
    for index, request in enumerate(module.requests):
        errors.extend(audit_request(request, "%s request %d" % (where, index)))
    return errors


# ---------------------------------------------------------------------------
# Auto-discovery and coverage audit
# ---------------------------------------------------------------------------

CLOUD_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULES_DIR = os.path.join(CLOUD_DIR, "plugins", "modules")

# Modules that genuinely have no API 3.0 request models to audit. Anything
# not listed here is auto-discovered and must be covered by the tests below.
NO_API3_CONTRACT = {
    "cos_bucket": "cos_bucket uses the qcloud_cos SDK (COS is not an API 3.0 "
                  "service), which has no declarative request models to audit",
    "cos_bucket_info": "cos_bucket_info uses the qcloud_cos SDK (COS is not "
                       "an API 3.0 service), which has no declarative request "
                       "models to audit",
}

# Individual builders that exist but cannot be exercised by the contract
# tests, keyed by (module, function), with the reason.
UNEXERCISED_BUILDERS = {
    ("cam_policy_info", "run_module"):
        "run_module constructs a GetPolicyRequest inline and cannot be "
        "called without real AnsibleModule params; the request is trivial "
        "(PolicyId only) and the path is covered by unit tests",
}

# Write-module request builders exercised by the ``test_<module>`` functions
# at the bottom of this file. Info-module builders are registered in
# INFO_BUILDERS instead. Both sets are verified against the static scan.
WRITE_MODULE_BUILDERS = {
    "cam_policy": [
        "_apply_tags", "_create", "_delete", "_update", "find_policy",
    ],
    "cam_role": [
        "_create", "_delete", "_tag_role", "_untag_role",
        "_update_description", "_update_policy_document", "find_role",
    ],
    "cam_user": [
        "_apply_tags", "_create", "_current_tags", "_delete", "_update",
        "find_user",
    ],
    "clb_load_balancer": [
        "_apply_tags", "_delete", "_update_attributes", "_wait_task",
        "build_create_request", "build_describe_request",
    ],
    "clb_listener": [
        "_delete", "_update", "_wait_task",
        "build_create_request", "build_describe_request",
    ],
    "clb_listener_target": [
        "_deregister", "_register", "_wait_task",
        "build_describe_request",
    ],
    "cvm_instance": [
        "_apply_tags", "_delete", "_start", "_stop", "_update_attributes",
        "build_describe_request", "build_run_request",
    ],
    "eip": [
        "_apply_tags", "_associate", "_create", "_delete", "_disassociate",
        "_update_name", "build_describe_request",
    ],
    "key_pair": [
        "_create", "_delete", "_import", "build_describe_request",
    ],
    "route_table": [
        "_apply_routes", "_apply_tags", "_create", "_delete", "_update_name",
        "build_describe_request",
    ],
    "security_group": [
        "_apply_tags", "_create", "_delete", "_update_attributes",
        "build_describe_request",
    ],
    "security_group_rule": [
        "build_describe_request", "create_rules", "delete_rules",
    ],
    "subnet": [
        "_apply_tags", "_create", "_delete", "_update",
        "build_describe_request",
    ],
    "vpc": [
        "_apply_tags", "_create", "_delete", "_update_attributes",
        "build_describe_request",
    ],
}


def discover_modules():
    """Return the names of every module in ``plugins/modules``."""
    return sorted(
        filename[:-len(".py")]
        for filename in os.listdir(MODULES_DIR)
        if filename.endswith(".py") and not filename.startswith("__")
    )


def discover_request_builders(module_name):
    """Statically find a module's functions that build SDK request objects.

    A module-level function counts as a request builder when its body calls
    ``<something>models.<Name>Request()`` (matching both ``models`` and e.g.
    ``tag_models``). The scan is a pure AST walk, so it also runs in
    environments without the SDK.
    """
    path = os.path.join(MODULES_DIR, module_name + ".py")
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    builders = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for sub in ast.walk(node):
            func = getattr(sub, "func", None)
            if (isinstance(sub, ast.Call)
                    and isinstance(func, ast.Attribute)
                    and func.attr.endswith("Request")
                    and isinstance(func.value, ast.Name)
                    and func.value.id.endswith("models")):
                builders.setdefault(node.name, set()).add(func.attr)
    return builders


def _exercised_builders(module_name):
    """Return the builders registered as contract-tested for *module_name*."""
    if module_name.endswith("_info"):
        return {
            builder
            for name, _service, builder, _calls in INFO_BUILDERS
            if name == module_name
        }
    return set(WRITE_MODULE_BUILDERS.get(module_name, ()))


# ---------------------------------------------------------------------------
# Info modules
# ---------------------------------------------------------------------------

# (module, SDK service, builder, [args tuples]) -- the real models module is
# passed as the first positional argument by the test. Only hand-written info
# modules are registered here; generated modules (those carrying the
# generator's MARKER) are covered automatically via _generated_info_builders.
INFO_BUILDERS_HANDWRITTEN = [
    ("vpc_info", "vpc.v20170312", "build_request", [
        (["vpc-xxxxxxxx"], None, 0, 100),
        (None, {"is-default": ["true"], "vpc-name": ["prod-vpc"]}, 0, 100),
    ]),
    ("subnet_info", "vpc.v20170312", "build_request", [
        (["subnet-xxxxxxxx"], None, 0, 100),
        (None, {"vpc-id": ["vpc-xxxxxxxx"]}, 0, 100),
    ]),
    ("route_table_info", "vpc.v20170312", "build_request", [
        (["rtb-xxxxxxxx"], None, 0, 100),
        (None, {"vpc-id": ["vpc-xxxxxxxx"]}, 0, 100),
    ]),
    ("security_group_info", "vpc.v20170312", "build_request", [
        (["sg-xxxxxxxx"], None, 0, 100),
        (None, {"security-group-name": ["web-sg"]}, 0, 100),
    ]),
    ("eip_info", "vpc.v20170312", "build_request", [
        (["eip-xxxxxxxx"], None, None, 0, 100),
        (None, ["1.2.3.4"], {"address-status": ["BIND"]}, 0, 100),
    ]),
    ("key_pair_info", "cvm.v20170312", "build_request", [
        (["skey-xxxxxxxx"], None, 0, 100),
        (None, {"key-name": ["deploy-key"]}, 0, 100),
    ]),
    ("cvm_instance_info", "cvm.v20170312", "build_request", [
        (["ins-xxxxxxxx"], None, 0, 100),
        (None, {"instance-name": ["web-01"]}, 0, 100),
    ]),
    ("cam_user_info", "cam.v20190116", "build_request", [()]),
    ("cam_role_info", "cam.v20190116", "build_request", [(1, 100)]),
    ("cam_policy_info", "cam.v20190116", "build_request", [
        ("local", "app-read-only", 1, 100),
        ("all", None, 1, 100),
    ]),
]

GENERATOR_PATH = os.path.join(CLOUD_DIR, "scripts", "generate_info_modules.py")

_SAMPLE_VALUES = {
    "str": "sample",
    "int": 1,
    "bool": True,
    "list": ["sample"],
    "dict": {"key": "value"},
}


def _load_generator_specs():
    """Load SPECS from scripts/generate_info_modules.py without running it."""
    spec = importlib.util.spec_from_file_location("generate_info_modules", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SPECS


def _param_sample(param):
    """Sample value used to exercise *param* against the real SDK models.

    Dict (struct) parameters include every declared sub-key so the SDK audit
    verifies each sub-field mapping (e.g. essbasic Agent.AppId,
    Agent.ProxyOperator.OpenId) rather than silently passing Nones.
    """
    if param.get("struct"):
        return {sub["key"]: "sample" for sub in param["struct"]}
    return _SAMPLE_VALUES[param["type"]]


def _generated_builder_calls(spec):
    """Contract invocations for a generated info module, derived from its spec.

    The generated builder signatures are fixed by the generator template:
    ``build_list_request``/``build_describe_request`` for ids_action specs,
    otherwise ``build_request(models, *extra_params, ids?, filters?, offset,
    limit)``. Each builder is called once with no selectors and once with
    every selector populated, so both branches are audited.
    """
    if spec.get("ids_action"):
        return [
            ("build_list_request", [(0, 100)]),
            ("build_describe_request", [(["x-xxxxxxxx"],)]),
        ]
    extras = [_param_sample(param) for param in spec["extra_params"]]
    calls = []
    selectors = [(None, {})]
    if spec["ids"] or spec["filters"]:
        selectors.append((
            ["x-xxxxxxxx"] if spec["ids"] else None,
            {"name": ["value"]} if spec["filters"] else {},
        ))
    for ids_value, filters_value in selectors:
        args = list(extras)
        if spec["ids"]:
            args.append(ids_value)
        if spec["filters"]:
            args.append(filters_value)
        args += [0, 100]
        calls.append(tuple(args))
    return [("build_request", calls)]


def _generated_info_builders():
    """Derive INFO_BUILDERS-style entries for every generated info module."""
    entries = []
    for spec in _load_generator_specs():
        service = spec["service_package"].split(".", 1)[1]
        for builder, calls in _generated_builder_calls(spec):
            entries.append((spec["module"], service, builder, calls))
    return entries


INFO_BUILDERS = INFO_BUILDERS_HANDWRITTEN + _generated_info_builders()


def test_info_builder_registrations_do_not_overlap():
    """A module must be registered either by hand or via the generator."""
    hand = {entry[0] for entry in INFO_BUILDERS_HANDWRITTEN}
    generated = {spec["module"] for spec in _load_generator_specs()}
    overlap = sorted(hand & generated)
    assert not overlap, (
        "modules registered in both INFO_BUILDERS_HANDWRITTEN and the "
        "generator SPECS: %s" % ", ".join(overlap)
    )


@pytest.mark.parametrize(
    "module_name, service, builder, calls",
    INFO_BUILDERS,
    ids=["%s.%s" % (entry[0], entry[2]) for entry in INFO_BUILDERS],
)
def test_info_module_request_contract(module_name, service, builder, calls):
    module = _import_plugin(module_name)
    models = _models(service)
    errors = []
    for call in calls:
        request = getattr(module, builder)(models, *call)
        errors.extend(audit_request(request, "%s.%s%r" % (module_name, builder, call)))
    assert errors == []


@pytest.mark.parametrize("module_name", discover_modules())
def test_module_request_builders_are_exercised(module_name):
    """Audit: every discovered module's request builders are contract-tested.

    This is what makes newly added modules fail loudly instead of silently
    shipping without real-SDK coverage: a module whose builders appear in no
    ``INFO_BUILDERS`` entry and no ``WRITE_MODULE_BUILDERS`` registration
    fails here until coverage (or a reasoned exception above) is added.
    """
    discovered = discover_request_builders(module_name)
    if module_name in NO_API3_CONTRACT:
        assert not discovered, (
            "%s is excepted via NO_API3_CONTRACT but now builds API 3.0 "
            "requests (%s); drop the exception and add contract coverage"
            % (module_name, ", ".join(sorted(discovered)))
        )
        pytest.skip(NO_API3_CONTRACT[module_name])

    exercised = _exercised_builders(module_name)
    if module_name.endswith("_info"):
        hint = "add an INFO_BUILDERS_HANDWRITTEN entry"
        marker = "# Generated by scripts/generate_info_modules.py"
        with open(os.path.join(MODULES_DIR, module_name + ".py"), encoding="utf-8") as handle:
            if marker in handle.read():
                hint = ("the module is generated; add its SPECS entry to "
                        "scripts/generate_info_modules.py")
    else:
        hint = ("add a WRITE_MODULE_BUILDERS entry and a test_%s function "
                "exercising its builders" % module_name)
    assert exercised or not discovered, (
        "%s builds SDK requests (%s) but has no contract coverage; %s"
        % (module_name, ", ".join(sorted(discovered)), hint)
    )

    excepted = {
        builder
        for (name, builder) in UNEXERCISED_BUILDERS
        if name == module_name
    }
    problems = []
    unexercised = sorted(set(discovered) - excepted - exercised)
    if unexercised:
        problems.append("builders not exercised by any contract test: %s"
                        % ", ".join(unexercised))
    phantom = sorted(exercised - set(discovered))
    if phantom:
        problems.append("registered builders that build no requests "
                        "(stale registration?): %s" % ", ".join(phantom))
    stale_exceptions = sorted(excepted - set(discovered))
    if stale_exceptions:
        problems.append("stale UNEXERCISED_BUILDERS entries: %s"
                        % ", ".join(stale_exceptions))
    assert not problems, "%s: %s" % (module_name, "; ".join(problems))

    module = _import_plugin(module_name)
    for builder in sorted(exercised):
        assert callable(getattr(module, builder, None)), (
            "%s.%s is registered as exercised but does not exist"
            % (module_name, builder)
        )
    if not module_name.endswith("_info"):
        assert callable(globals().get("test_" + module_name)), (
            "%s is registered in WRITE_MODULE_BUILDERS but test_%s is missing"
            % (module_name, module_name)
        )


# ---------------------------------------------------------------------------
# Write modules
# ---------------------------------------------------------------------------

def test_vpc():
    module = _import_plugin("vpc")
    models = _models("vpc.v20170312")
    tag_models = _models("tag.v20180813")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(
        module.build_describe_request(models, "prod-vpc", None), "vpc describe by name"))
    errors.extend(audit_request(
        module.build_describe_request(models, None, "vpc-xxxxxxxx"), "vpc describe by id"))
    module._create(fake, client, models, "prod-vpc", "10.0.0.0/16",
                   ["183.60.83.19"], "prod.internal", {"env": "prod"})
    module._update_attributes(fake, client, models, "vpc-xxxxxxxx", "prod-vpc",
                              ["183.60.83.19"], "prod.internal")
    module._delete(fake, client, models, "vpc-xxxxxxxx")
    module._apply_tags(fake, client, tag_models, "vpc-xxxxxxxx", {"env": "prod"}, ["legacy"])
    errors.extend(audit_recorded(fake, "vpc"))
    assert errors == []


def test_subnet():
    module = _import_plugin("subnet")
    models = _models("vpc.v20170312")
    tag_models = _models("tag.v20180813")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(
        module.build_describe_request(models, "subnet-xxxxxxxx", None, None),
        "subnet describe by id"))
    errors.extend(audit_request(
        module.build_describe_request(models, None, "vpc-xxxxxxxx", "web-subnet"),
        "subnet describe by filters"))
    module._create(fake, client, models, "vpc-xxxxxxxx", "web-subnet",
                   "10.0.1.0/24", "ap-guangzhou-1", {"env": "prod"})
    module._update(fake, client, models, "subnet-xxxxxxxx", "web-subnet", True)
    module._delete(fake, client, models, "subnet-xxxxxxxx")
    module._apply_tags(fake, client, tag_models, "subnet-xxxxxxxx", {"env": "prod"}, ["legacy"])
    errors.extend(audit_recorded(fake, "subnet"))
    assert errors == []


def test_route_table():
    module = _import_plugin("route_table")
    models = _models("vpc.v20170312")
    tag_models = _models("tag.v20180813")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(
        module.build_describe_request(models, "rtb-xxxxxxxx", None, None),
        "route_table describe by id"))
    errors.extend(audit_request(
        module.build_describe_request(models, None, "vpc-xxxxxxxx", "app-rtb"),
        "route_table describe by filters"))
    module._create(fake, client, models, "vpc-xxxxxxxx", "app-rtb", {"env": "prod"})
    module._update_name(fake, client, models, "rtb-xxxxxxxx", "app-rtb")
    module._delete(fake, client, models, "rtb-xxxxxxxx")
    to_add = [{
        "destination_cidr_block": "10.1.0.0/16",
        "gateway_type": "NAT",
        "gateway_id": "nat-xxxxxxxx",
        "description": "egress via NAT",
    }]
    to_delete = [{"RouteId": 42, "RouteItemId": "rti-xxxxxxxx"}]
    module._apply_routes(fake, client, models, "rtb-xxxxxxxx", to_add, to_delete)
    module._apply_tags(fake, client, tag_models, "rtb-xxxxxxxx", {"env": "prod"}, ["legacy"])
    errors.extend(audit_recorded(fake, "route_table"))
    assert errors == []


def test_security_group():
    module = _import_plugin("security_group")
    models = _models("vpc.v20170312")
    tag_models = _models("tag.v20180813")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(
        module.build_describe_request(models, "web-sg", None), "security_group describe by name"))
    errors.extend(audit_request(
        module.build_describe_request(models, None, "sg-xxxxxxxx"), "security_group describe by id"))
    module._create(fake, client, models, "web-sg", "Web tier", 0, {"env": "prod"})
    module._update_attributes(fake, client, models, "sg-xxxxxxxx", "web-sg", "Web tier")
    module._delete(fake, client, models, "sg-xxxxxxxx")
    module._apply_tags(fake, client, tag_models, "sg-xxxxxxxx", {"env": "prod"}, ["legacy"])
    errors.extend(audit_recorded(fake, "security_group"))
    assert errors == []


def test_security_group_rule():
    module = _import_plugin("security_group_rule")
    models = _models("vpc.v20170312")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(
        module.build_describe_request(models, "sg-xxxxxxxx"), "security_group_rule describe"))
    rules = [
        module.normalize_desired_rule({
            "protocol": "tcp", "port": "443", "cidr_block": "0.0.0.0/0",
            "action": "ACCEPT", "policy_description": "HTTPS", "direction": "ingress",
        }),
        module.normalize_desired_rule({
            "protocol": "UDP", "port": "53", "cidr_block": "10.0.1.0/24",
            "action": "DROP", "direction": "egress",
        }),
    ]
    errors.extend(audit_request(
        module.build_policy_set(models, rules), "security_group_rule policy set"))
    module.create_rules(fake, client, models, "sg-xxxxxxxx", rules)
    module.delete_rules(fake, client, models, "sg-xxxxxxxx", rules)
    errors.extend(audit_recorded(fake, "security_group_rule"))
    assert errors == []


def test_eip():
    module = _import_plugin("eip")
    models = _models("vpc.v20170312")
    tag_models = _models("tag.v20180813")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(
        module.build_describe_request(models, "eip-xxxxxxxx", None, None), "eip describe by id"))
    errors.extend(audit_request(
        module.build_describe_request(models, None, "1.2.3.4", None), "eip describe by ip"))
    errors.extend(audit_request(
        module.build_describe_request(models, None, None, "web-eip"), "eip describe by name"))
    module._create(fake, client, models, "web-eip", "TRAFFIC_POSTPAID_BY_HOUR", 10, {"env": "prod"})
    module._associate(fake, client, models, "eip-xxxxxxxx", "ins-xxxxxxxx")
    module._disassociate(fake, client, models, "eip-xxxxxxxx")
    module._update_name(fake, client, models, "eip-xxxxxxxx", "web-eip")
    module._delete(fake, client, models, "eip-xxxxxxxx", True)
    module._apply_tags(fake, client, tag_models, "eip-xxxxxxxx", {"env": "prod"}, ["legacy"])
    errors.extend(audit_recorded(fake, "eip"))
    assert errors == []


def test_key_pair():
    module = _import_plugin("key_pair")
    models = _models("cvm.v20170312")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(
        module.build_describe_request(models, "deploy-key", None), "key_pair describe by name"))
    errors.extend(audit_request(
        module.build_describe_request(models, None, "skey-xxxxxxxx"), "key_pair describe by id"))
    module._create(fake, client, models, "deploy-key", 0)
    module._import(fake, client, models, "deploy-key", 0, "ssh-rsa AAAA...")
    module._delete(fake, client, models, "skey-xxxxxxxx")
    errors.extend(audit_recorded(fake, "key_pair"))
    assert errors == []


def test_cvm_instance():
    module = _import_plugin("cvm_instance")
    models = _models("cvm.v20170312")
    tag_models = _models("tag.v20180813")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(
        module.build_describe_request(models, "ins-xxxxxxxx", None), "cvm describe by id"))
    errors.extend(audit_request(
        module.build_describe_request(models, None, "web-01"), "cvm describe by name"))
    params = {
        "image_id": "img-xxxxxxxx",
        "instance_type": "S5.MEDIUM2",
        "instance_charge_type": "POSTPAID_BY_HOUR",
        "instance_name": "web-01",
        "hostname": "web-01",
        "security_group_ids": ["sg-xxxxxxxx"],
        "vpc_id": "vpc-xxxxxxxx",
        "subnet_id": "subnet-xxxxxxxx",
        "internet_charge_type": "TRAFFIC_POSTPAID_BY_HOUR",
        "internet_max_bandwidth_out": 10,
        "public_ip_assigned": True,
        "password": None,
        "key_ids": ["skey-xxxxxxxx"],
        "tags": {"env": "prod"},
        "dry_run": True,
    }
    errors.extend(audit_request(
        module.build_run_request(models, params), "cvm run request (key pair)"))
    password_params = dict(params, key_ids=None, password="Sup3rSecret!", dry_run=False,
                           vpc_id=None, subnet_id=None, tags={})
    errors.extend(audit_request(
        module.build_run_request(models, password_params), "cvm run request (password)"))
    module._create(fake, client, models, params)
    module._delete(fake, client, models, "ins-xxxxxxxx")
    module._start(fake, client, models, "ins-xxxxxxxx")
    module._stop(fake, client, models, "ins-xxxxxxxx")
    module._update_attributes(fake, client, models, "ins-xxxxxxxx", "web-01", ["sg-xxxxxxxx"])
    module._apply_tags(fake, client, tag_models, "ins-xxxxxxxx", {"env": "prod"}, ["legacy"])
    errors.extend(audit_recorded(fake, "cvm_instance"))
    assert errors == []


def test_cam_user():
    module = _import_plugin("cam_user")
    models = _models("cam.v20190116")
    tag_models = _models("tag.v20180813")
    fake = _RecordingModule()
    client = _StubClient()
    module.find_user(fake, client, models, "deploy")
    module._create(fake, client, models, "deploy", "CI user", True, "Sup3rSecret!")
    module._update(fake, client, models, "deploy", "CI user", False)
    module._delete(fake, client, models, "deploy")
    module._current_tags(fake, client, tag_models, "100000000001", "uin")
    module._apply_tags(fake, client, tag_models, "100000000001", "uin", {"env": "prod"}, ["legacy"])
    assert audit_recorded(fake, "cam_user") == []


def test_cam_role():
    module = _import_plugin("cam_role")
    models = _models("cam.v20190116")
    fake = _RecordingModule()
    client = _StubClient()
    document = {
        "version": "2.0",
        "statement": [{
            "action": "name/sts:AssumeRole",
            "effect": "allow",
            "principal": {"service": ["cvm.qcloud.com"]},
        }],
    }
    module.find_role(fake, client, models, "APPID-xxxxxxxx", None)
    module.find_role(fake, client, models, None, "app-role")
    module._create(fake, client, models, "app-role", "App role", document, {"env": "prod"})
    module._update_description(fake, client, models, "APPID-xxxxxxxx", "App role")
    module._update_policy_document(fake, client, models, "APPID-xxxxxxxx", document)
    module._delete(fake, client, models, "APPID-xxxxxxxx", None)
    module._delete(fake, client, models, None, "app-role")
    module._tag_role(fake, client, models, "APPID-xxxxxxxx", {"env": "prod"})
    module._untag_role(fake, client, models, "APPID-xxxxxxxx", ["legacy"])
    assert audit_recorded(fake, "cam_role") == []


def test_cam_policy():
    module = _import_plugin("cam_policy")
    models = _models("cam.v20190116")
    tag_models = _models("tag.v20180813")
    fake = _RecordingModule()
    client = _StubClient()
    document = {
        "version": "2.0",
        "statement": [{
            "action": ["cvm:DescribeInstances"],
            "effect": "allow",
            "resource": "*",
        }],
    }
    module.find_policy(fake, client, models, 1000001, None, "Local")
    module.find_policy(fake, client, models, None, "app-read-only", "Local")
    module._create(fake, client, models, "app-read-only", "Read-only", document, {"env": "prod"})
    module._update(fake, client, models, 1000001, "app-read-only", "Read-only",
                   document, ["policy_name", "description", "policy_document"])
    module._delete(fake, client, models, 1000001)
    module._apply_tags(fake, client, tag_models, "1000001", {"env": "prod"}, ["legacy"])
    assert audit_recorded(fake, "cam_policy") == []


class _ClbTaskModule(_RecordingModule):
    """Recording module carrying the waiter parameters the CLB helpers read."""

    def __init__(self):
        super(_ClbTaskModule, self).__init__()
        self.params.update({"waiter_timeout": 5, "waiter_delay": 1})
        self.check_mode = False


class _ClbStubClient(_StubClient):
    """CLB stub whose asynchronous tasks always succeed immediately."""

    def DescribeTaskStatus(self, request):
        return SimpleNamespace(Status=0, Message=None, LoadBalancerIds=["lb-xxxxxxxx"])


def test_clb_load_balancer():
    module = _import_plugin("clb_load_balancer")
    models = _models("clb.v20180317")
    tag_models = _models("tag.v20180813")
    fake = _ClbTaskModule()
    client = _ClbStubClient()
    errors = []
    errors.extend(audit_request(
        module.build_describe_request(models, "lb-xxxxxxxx", None, None),
        "clb describe by id"))
    errors.extend(audit_request(
        module.build_describe_request(models, None, "web-lb", "vpc-xxxxxxxx"),
        "clb describe by name"))
    params = {
        "name": "web-lb",
        "load_balancer_type": "OPEN",
        "vpc_id": "vpc-xxxxxxxx",
        "subnet_id": None,
        "project_id": 0,
        "internet_charge_type": "TRAFFIC_POSTPAID_BY_HOUR",
        "internet_max_bandwidth_out": 10,
        "client_token": "ansible-0001",
        "tags": {"env": "prod"},
    }
    errors.extend(audit_request(
        module.build_create_request(models, params), "clb create request"))
    module._delete(fake, client, models, "lb-xxxxxxxx")
    module._update_attributes(fake, client, models, "lb-xxxxxxxx", "web-lb",
                              "TRAFFIC_POSTPAID_BY_HOUR", 10)
    module._apply_tags(fake, client, tag_models, "lb-xxxxxxxx", {"env": "prod"}, ["legacy"])
    module._wait_task(fake, client, models, "req-0001")
    errors.extend(audit_recorded(fake, "clb_load_balancer"))
    assert errors == []


def test_clb_listener():
    module = _import_plugin("clb_listener")
    models = _models("clb.v20180317")
    fake = _ClbTaskModule()
    client = _ClbStubClient()
    errors = []
    errors.extend(audit_request(
        module.build_describe_request(models, "lb-xxxxxxxx", "lbl-xxxxxxxx", None, None),
        "listener describe by id"))
    errors.extend(audit_request(
        module.build_describe_request(models, "lb-xxxxxxxx", None, 8080, "TCP"),
        "listener describe by port/protocol"))
    params = {
        "load_balancer_id": "lb-xxxxxxxx",
        "port": 8080,
        "protocol": "TCP",
        "name": "tcp-8080",
        "scheduler": "WRR",
        "session_expire_time": 0,
        "health_check": {
            "health_switch": True, "interval_time": 5, "health_num": 3,
            "un_health_num": 3, "time_out": 2, "check_type": "HTTP",
            "http_check_path": "/healthz", "http_check_domain": "example.com",
            "http_check_method": "HEAD", "http_code": 31,
            "http_version": "HTTP/1.1",
        },
        "certificate": None,
        "sni_switch": None,
        "keepalive_enable": None,
    }
    errors.extend(audit_request(
        module.build_create_request(models, params), "listener create request (TCP)"))
    https_params = dict(
        params, protocol="HTTPS", port=443, health_check=None,
        certificate={"ssl_mode": "UNIDIRECTIONAL", "cert_id": "abc", "cert_ca_id": None},
        sni_switch=False, keepalive_enable=True,
    )
    errors.extend(audit_request(
        module.build_create_request(models, https_params),
        "listener create request (HTTPS)"))
    module._delete(fake, client, models, "lb-xxxxxxxx", "lbl-xxxxxxxx")
    changes = ["name", "scheduler", "session_expire_time", "health_check", "certificate"]
    module._update(fake, client, models, "lb-xxxxxxxx", "lbl-xxxxxxxx", https_params, changes)
    module._wait_task(fake, client, models, "req-0001")
    errors.extend(audit_recorded(fake, "clb_listener"))
    assert errors == []


def test_clb_listener_target():
    module = _import_plugin("clb_listener_target")
    models = _models("clb.v20180317")
    fake = _ClbTaskModule()
    client = _ClbStubClient()
    errors = []
    errors.extend(audit_request(
        module.build_describe_request(models, "lb-xxxxxxxx", "lbl-xxxxxxxx"),
        "targets describe"))
    targets = [
        {"instance_id": "ins-aaaaaaaa", "eni_ip": None, "port": 8080, "weight": 20},
        {"instance_id": None, "eni_ip": "10.0.1.15", "port": 8081, "weight": 10},
    ]
    module._register(fake, client, models, "lb-xxxxxxxx", "lbl-xxxxxxxx", None, targets)
    module._deregister(
        fake, client, models, "lb-xxxxxxxx", "lbl-xxxxxxxx", "loc-xxxxxxxx", targets)
    module._wait_task(fake, client, models, "req-0001")
    errors.extend(audit_recorded(fake, "clb_listener_target"))
    assert errors == []
