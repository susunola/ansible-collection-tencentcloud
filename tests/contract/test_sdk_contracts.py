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

Not covered, by design:

- ``cos_bucket`` / ``cos_bucket_info``: COS is not an API 3.0 service; the
  ``qcloud_cos`` SDK has no declarative request models to audit.
- Response handling: only request construction is under contract here.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib
import importlib.util
import os
import re
import sys
import tempfile

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
# Info modules
# ---------------------------------------------------------------------------

# (module, SDK service, builder, [args tuples]) -- the real models module is
# passed as the first positional argument by the test.
INFO_BUILDERS = [
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
    ("cbs_disk_info", "cbs.v20170312", "build_request", [
        (["disk-xxxxxxxx"], None, 0, 100),
        (None, {"zone": ["ap-guangzhou-1"]}, 0, 100),
    ]),
    ("cdb_instance_info", "cdb.v20170320", "build_request", [
        (["cdb-xxxxxxxx"], 0, 100),
        (None, 0, 100),
    ]),
    ("clb_load_balancer_info", "clb.v20180317", "build_request", [
        (["lb-xxxxxxxx"], None, 0, 100),
        (None, {"loadbalancer-name": ["web-lb"]}, 0, 100),
    ]),
    ("dnspod_record_info", "dnspod.v20210323", "build_request", [
        ("example.com", 0, 100),
    ]),
    ("kms_key_info", "kms.v20190118", "build_list_request", [(0, 100)]),
    ("kms_key_info", "kms.v20190118", "build_describe_request", [
        (["xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"],),
    ]),
    ("mongodb_instance_info", "mongodb.v20190725", "build_request", [
        (["cmgo-xxxxxxxx"], 0, 100),
        (None, 0, 100),
    ]),
    ("redis_instance_info", "redis.v20180412", "build_request", [
        (["crs-xxxxxxxx"], 0, 100),
        (None, 0, 100),
    ]),
    ("tke_cluster_info", "tke.v20180525", "build_request", [
        (["cls-xxxxxxxx"], None, 0, 100),
        (None, {"ClusterName": ["prod"]}, 0, 100),
    ]),
]


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


def test_cos_modules_have_no_api3_contract():
    """COS is not an API 3.0 service; nothing to audit here."""
    pytest.skip(
        "cos_bucket and cos_bucket_info use the qcloud_cos SDK, which has "
        "no declarative request models to audit"
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
