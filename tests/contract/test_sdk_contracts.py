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
    reason="requires the Tencent Cloud SDK packages and ansible-core; run via the CI sanity job or any env with requirements.txt installed",
)


def _ensure_collection_importable():
    """Make ``ansible_collections.susunola.tencentcloud`` importable.

    The preferred layout is the standard ``.../ansible_collections/
    tencentcloud/cloud`` checkout (CI, synced test trees). When this file
    sits in a bare repository checkout, a temporary symlink tree provides
    the same layout so the collection namespace resolves.
    """
    cloud_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if (
        os.path.basename(cloud_dir) == "cloud"
        and os.path.basename(os.path.dirname(cloud_dir)) == "tencentcloud"
        and os.path.basename(os.path.dirname(os.path.dirname(cloud_dir))) == "ansible_collections"
    ):
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
    return importlib.import_module("ansible_collections.susunola.tencentcloud.plugins.modules." + name)


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
        self.params = {"region": "ap-guangzhou", "waiter_timeout": 10, "waiter_delay": 1}
        self.check_mode = False
        self.requests = []

    def sdk_call(self, operation, request):
        self.requests.append(request)
        return operation(request)


_RTYPE_RE = re.compile(r":rtype:\s*(?P<rtype>[^\n]+)")


def _declared_properties(obj):
    """Return the ``@property`` descriptors declared on the object's class."""
    return {name: attr for name, attr in vars(type(obj)).items() if isinstance(attr, property)}


def _check_rtype(location, prop, value):
    """Check a non-None value against the property's declared ``:rtype:``."""
    doc = prop.fget.__doc__ or ""
    match = _RTYPE_RE.search(doc)
    if not match:
        return []
    rtype = match.group("rtype").strip()

    def fail():
        return ["%s: SDK declares rtype %r but the module assigns %r (%s)" % (location, rtype, value, type(value).__name__)]

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
        ok = isinstance(value, list) and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
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
            errors.append("%s: attribute %r is not a declared property of %s; the API would silently ignore it" % (location, key, type(obj).__name__))
            continue
        prop = declared.get(key[1:])
        if prop is None:
            errors.append("%s: %r is not a declared property of %s; the API would silently ignore it" % (location, key[1:], type(obj).__name__))
            continue
        if value is None:
            continue
        errors.extend(_check_rtype(location, prop, value))
        children = value if isinstance(value, list) else [value]
        for index, child in enumerate(children):
            if isinstance(child, AbstractModel):
                child_where = "%s[%d]" % (location, index) if isinstance(value, list) else location
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
            errors.append("%s: serialized key %r is not a declared property of %s" % (where, key, type(request).__name__))
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
MODULE_UTILS_DIR = os.path.join(CLOUD_DIR, "plugins", "module_utils")

# Modules that genuinely have no API 3.0 request models to audit. Anything
# not listed here is auto-discovered and must be covered by the tests below.
NO_API3_CONTRACT = {
    "cos_bucket": "cos_bucket uses the qcloud_cos SDK (COS is not an API 3.0 service), which has no declarative request models to audit",
    "cos_bucket_info": "cos_bucket_info uses the qcloud_cos SDK (COS is not an API 3.0 service), which has no declarative request models to audit",
    "cos_bucket_policy": "cos_bucket_policy uses the qcloud_cos SDK (COS is not an API 3.0 service), which has no declarative request models to audit",
    "cos_bucket_replication": "cos_bucket_replication uses the qcloud_cos SDK (COS is not an API 3.0 service), which has no declarative request models to audit",
}

# Individual builders that exist but cannot be exercised by the contract
# tests, keyed by (module, function), with the reason.
UNEXERCISED_BUILDERS = {
    ("cam_policy_info", "run_module"): "run_module constructs a GetPolicyRequest inline and cannot be "
    "called without real AnsibleModule params; the request is trivial "
    "(PolicyId only) and the path is covered by unit tests",
    ("kms_key", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("monitor_alarm_policy", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("tcr_repository", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("tke_addon", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("private_dns_zone", "run_module"): "inline update and delete requests are covered by unit tests",
    ("private_dns_record", "run_module"): "inline delete requests are covered by unit tests",
    ("network_acl", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("api_gateway_api", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("as_scaling_policy", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("as_scheduled_action", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("cls_index", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("cls_machine_group", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("cmq_subscription", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("cmq_topic", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("dts_migration_job", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("scf_trigger", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("tcr_replication_rule", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("tdmq_subscription", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("cam_group", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("cdb_parameter_template", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("dnspod_domain", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("postgresql_parameter_template", "run_module"): "inline lifecycle requests are covered by unit tests",
    ("redis_parameter_template", "run_module"): "inline lifecycle requests are covered by unit tests",
}

# Write-module request builders exercised by the ``test_<module>`` functions
# at the bottom of this file. Info-module builders are registered in
# INFO_BUILDERS instead. Both sets are verified against the static scan.
WRITE_MODULE_BUILDERS = {
    "cdb_account": ["create", "describe"],
    "cdb_account_privilege": ["describe_request", "modify_request"],
    "cdb_audit_config": ["describe_request", "modify_request"],
    "cdb_database": ["create_request", "delete_request", "describe_request"],
    "organization_member": ["create", "delete", "describe", "move", "update"],
    "organization_member_identity": ["create_request", "delete_request", "describe_request"],
    "organization_member_policy": ["create_request", "delete_request", "describe_request", "update_request"],
    "mongodb_backup_config": ["describe_request", "set_request"],
    "mongodb_account": ["create_request", "delete_request", "describe_request", "password_request", "privilege_request"],
    "sqlserver_account": ["create_request", "delete_request", "describe_request", "password_request", "privilege_request", "remark_request"],
    "mariadb_account": ["create_request", "delete_request", "describe_request", "description_request", "password_request"],
    "mariadb_backup_config": ["describe_request", "modify_request"],
    "mariadb_account_privilege": ["describe_request", "grant_request"],
    "elasticsearch_index": ["create_request", "delete_request", "describe_request", "update_request"],
    "ckafka_user": ["create_request", "delete_request", "describe_request", "password_request"],
    "ckafka_route": ["create_request", "delete_request", "describe_request"],
    "ckafka_acl_rule": ["create_request", "delete_request", "describe_request", "update_request"],
    "tdmq_namespace": ["create_request", "delete_request", "describe_request", "update_request"],
    "tdmq_namespace_role": ["create_request", "delete_request", "describe_request", "update_request"],
    "tdmq_rabbitmq_vhost": ["create_request", "delete_request", "describe_request", "update_request"],
    "tdmq_rabbitmq_user": ["create_request", "delete_request", "describe_request", "update_request"],
    "tdmq_rabbitmq_permission": ["delete_request", "describe_request", "modify_request"],
    "tdmq_rabbitmq_binding": ["create_request", "delete_request", "describe_request"],
    "tdmq_rocketmq_namespace": ["create_request", "delete_request", "describe_request", "update_request"],
    "tdmq_rocketmq_topic": ["create_request", "delete_request", "describe_request", "update_request"],
    "tdmq_rocketmq_group": ["create_request", "delete_request", "describe_request", "update_request"],
    "tdmq_rocketmq_role": ["create_request", "delete_request", "describe_request", "update_request"],
    "tdmq_rocketmq_permission": ["create_request", "delete_request", "describe_request", "update_request"],
    "tdmq_rocketmq_cluster": ["create_request", "delete_request", "describe_request", "update_request"],
    "waf_protect_group": ["create_request", "delete_request", "describe_request", "update_request"],
    "cls_shipper": ["create_request", "delete_request", "describe_request", "update_request"],
    "tke_backup_storage_location": ["create_request", "delete_request", "describe_request"],
    "cam_saml_provider": ["create_request", "delete_request", "get_request", "update_request"],
    "cam_oidc_provider": ["create_request", "delete_request", "describe_request", "update_request"],
    "dnspod_custom_line": ["create_request", "delete_request", "describe_request", "update_request"],
    "dnspod_line_group": ["create_request", "delete_request", "describe_request", "update_request"],
    "ckafka_datahub_topic": ["create_request", "delete_request", "describe_request", "update_request"],
    "ckafka_datahub_connection": ["create_request", "delete_request", "describe_request", "list_request", "update_request"],
    "ckafka_datahub_task": ["create_request", "delete_request", "describe_request", "list_request", "pause_request", "resume_request", "update_request"],
    "sqlserver_backup_config": ["describe_request", "update_request"],
    "cynosdb_backup_config": ["describe_request", "update_request"],
    "api_gateway_service_release": ["build_describe", "build_release", "build_unrelease"],
    "api_gateway_api_key": ["build_create", "build_delete", "build_get", "build_list", "build_update"],
    "api_gateway_usage_plan": ["build_create", "build_delete", "build_get", "build_list", "build_update"],
    "api_gateway_usage_plan_binding": ["build_change", "build_describe"],
    "api_gateway_usage_plan_key_binding": ["build_bind", "build_describe", "build_unbind"],
    "cls_config": ["build_create", "build_delete", "build_describe", "build_update"],
    "cls_config_machine_group_binding": ["build_apply", "build_describe", "build_remove"],
    "tke_cluster_endpoint": ["build_create", "build_delete", "build_describe", "build_status"],
    "tke_cluster_authentication": ["build_describe", "build_modify"],
    "tke_cluster_audit": ["build_describe", "build_disable", "build_enable"],
    "waf_host": ["build_create", "build_delete", "build_get", "build_update"],
    "waf_custom_rule": ["build_create", "build_delete", "build_list", "build_update"],
    "monitor_prometheus_scrape_job": ["build_create", "build_delete", "build_describe", "build_update"],
    "monitor_prometheus_record_rule": ["build_create", "build_delete", "build_describe", "build_update"],
    "monitor_prometheus_alert_group": ["build_create", "build_delete", "build_describe", "build_update"],
    "monitor_prometheus_instance": ["build_create", "build_delete", "build_describe", "build_update"],
    "monitor_prometheus_cluster_agent": ["build_create", "build_delete", "build_describe"],
    "monitor_grafana_instance": ["build_create", "build_delete", "build_describe", "build_update"],
    "monitor_prometheus_grafana_binding": ["build_bind", "build_describe", "build_unbind"],
    "monitor_grafana_integration": ["build_create", "build_delete", "build_describe", "build_update"],
    "monitor_grafana_whitelist": ["build_describe", "build_update"],
    "monitor_grafana_internet": ["build_describe", "build_update"],
    "monitor_grafana_notification_channel": ["build_create", "build_delete", "build_describe", "build_update"],
    "monitor_prometheus_global_notification": ["build_describe", "build_update"],
    "monitor_prometheus_alertmanager_config": ["build_describe", "build_update"],
    "cdb_backup_config": ["build_describe", "build_update"],
    "redis_backup_config": ["build_describe", "build_update"],
    "redis_account": ["build_create", "build_delete", "build_describe", "build_update"],
    "postgresql_backup_plan": ["build_create", "build_delete", "build_describe", "build_update"],
    "cam_policy": [
        "_apply_tags",
        "_create",
        "_delete",
        "_update",
        "find_policy",
    ],
    "cam_role": [
        "_create",
        "_delete",
        "_tag_role",
        "_untag_role",
        "_update_description",
        "_update_policy_document",
        "find_role",
    ],
    "cam_user": [
        "_apply_tags",
        "_create",
        "_current_tags",
        "_delete",
        "_update",
        "find_user",
    ],
    "clb_load_balancer": [
        "_apply_tags",
        "_delete",
        "_update_attributes",
        "_wait_task",
        "build_create_request",
        "build_describe_request",
    ],
    "cfs_file_system": [
        "_create",
        "_delete",
        "_update_name",
        "_update_size_limit",
        "build_describe_request",
    ],
    "cdn_domain": [
        "_delete",
        "_start",
        "_stop",
        "build_add_request",
        "build_describe_request",
    ],
    "cvm_chc": [
        "_configure_vpc",
        "_remove_assist",
        "_remove_deploy",
        "_rename",
        "_set_network_mode",
        "build_describe_request",
    ],
    "cvm_image": [
        "_create",
        "_delete",
        "_update",
        "build_describe_request",
    ],
    "lighthouse_instance": [
        "_isolate",
        "_start",
        "_stop",
        "_update_name",
        "build_create_request",
        "build_describe_request",
    ],
    "mongodb_instance": [
        "_delete",
        "_rename",
        "build_create_request",
        "build_describe_request",
    ],
    "clb_listener": [
        "_delete",
        "_update",
        "_wait_task",
        "build_create_request",
        "build_describe_request",
    ],
    "clb_listener_target": [
        "_deregister",
        "_register",
        "_wait_task",
        "build_describe_request",
    ],
    "cvm_instance": [
        "_apply_tags",
        "_delete",
        "_reboot",
        "_reset_password",
        "_reset_type",
        "_start",
        "_stop",
        "_update_attributes",
        "build_describe_request",
        "build_run_request",
    ],
    "eip": [
        "_apply_tags",
        "_associate",
        "_create",
        "_delete",
        "_disassociate",
        "_update_bandwidth",
        "_update_charge_type",
        "_update_name",
        "build_describe_request",
    ],
    "gaap_proxy": [
        "_close",
        "_destroy",
        "_open",
        "_rename",
        "build_create_request",
        "build_describe_request",
    ],
    "key_pair": [
        "_create",
        "_delete",
        "_import",
        "build_describe_request",
    ],
    "route_table": [
        "_apply_routes",
        "_apply_tags",
        "_create",
        "_delete",
        "_update_name",
        "build_describe_request",
    ],
    "security_group": [
        "_apply_tags",
        "_create",
        "_delete",
        "_update_attributes",
        "build_describe_request",
    ],
    "security_group_rule": [
        "build_describe_request",
        "create_rules",
        "delete_rules",
    ],
    "subnet": [
        "_apply_tags",
        "_create",
        "_delete",
        "_update",
        "build_describe_request",
    ],
    "vpc": [
        "_apply_tags",
        "_create",
        "_delete",
        "_update_attributes",
        "build_describe_request",
    ],
    "cbs_disk": [
        "_attach",
        "_create",
        "_delete",
        "_detach",
        "_rename",
        "_resize",
        "build_describe_request",
    ],
    "cbs_snapshot": [
        "_create",
        "_delete",
        "build_describe_request",
    ],
    "cdb_instance": [
        "_create",
        "_delete",
        "_rename",
        "build_describe_request",
        "build_restart_request",
        "build_task_status_request",
        "build_upgrade_request",
    ],
    "ckafka_topic": [
        "_create",
        "_delete",
        "_scale_partitions",
        "_update",
        "find_topic",
    ],
    "clb_rule": [
        "_create",
        "_delete",
        "_update",
        "build_describe_request",
    ],
    "dnspod_record": [
        "_create",
        "_delete",
        "_update",
        "build_describe_request",
    ],
    "nat_gateway": [
        "_create",
        "_delete",
        "_set_deletion_protection",
        "_update",
        "build_describe_request",
    ],
    "nat_gateway_rule": [
        "_create_dnat",
        "_create_snat",
        "_delete_dnat",
        "_delete_snat",
        "build_dnat_describe_request",
        "build_snat_describe_request",
        "find_gateway",
    ],
    "peering_connection": [
        "_accept",
        "_create",
        "_delete",
        "_update",
        "build_describe_request",
    ],
    "private_dns_zone": ["build_create_request", "find_zone"],
    "private_dns_record": ["build_create_request", "build_update_request", "find_record"],
    "redis_instance": [
        "_create",
        "_destroy",
        "_rename",
        "build_describe_request",
    ],
    "scf_function": [
        "_create",
        "_delete",
        "_update_code",
        "_update_config",
        "find_function",
    ],
    "ssl_certificate": [
        "_delete",
        "_deploy",
        "_rename",
        "_upload",
        "build_describe_request",
    ],
    "ssm_parameter": [
        "_create",
        "_delete",
        "_update_value",
        "find_secret",
    ],
    "tag": [
        "_attach",
        "_detach",
        "_update_value",
        "build_describe_request",
    ],
    "tcr_instance": [
        "_delete",
        "_update",
        "build_create_request",
        "build_describe_request",
    ],
    "tcr_namespace": [
        "_delete",
        "_update",
        "build_create_request",
        "build_describe_request",
    ],
    "tcr_repository": ["build_create_request", "find_repository"],
    "cam_policy_attachment": ["build_list_request", "build_mutation_request"],
    "cam_group_membership": ["build_list_request", "build_mutation_request"],
    "kms_key": [
        "build_cancel_deletion_request",
        "build_create_request",
        "build_list_key_request",
        "build_rotation_request",
        "describe_key",
    ],
    "kms_key_rotation": ["build_describe_request", "build_status_request", "build_update_request"],
    "monitor_alarm_policy": [
        "build_condition_request",
        "build_create_request",
        "build_notice_request",
        "build_tasks_request",
        "find_policy",
    ],
    "tke_addon": ["build_install_request", "build_update_request", "describe_addon"],
    "tke_cluster": [
        "_create",
        "_delete",
        "_set_deletion_protection",
        "_update",
        "build_describe_request",
    ],
    "tke_node_pool": [
        "_delete",
        "_update",
        "build_create_request",
        "build_describe_request",
    ],
    "network_interface": [
        "_delete",
        "_update",
        "build_create_request",
        "build_describe_request",
    ],
    "scf_alias": [
        "_delete",
        "_update",
        "build_create_request",
        "build_get_request",
    ],
    "scf_version": [
        "_delete",
        "build_list_request",
        "build_publish_request",
    ],
    "elasticsearch_instance": [
        "_destroy",
        "_rename",
        "build_create_request",
        "build_describe_request",
    ],
    "vpn_gateway": [
        "_create",
        "_delete",
        "_update",
        "build_describe_request",
    ],
    "customer_gateway": [
        "build_create_request",
        "build_delete_request",
        "build_describe_request",
        "build_update_request",
    ],
    "vpn_connection": [
        "build_create_request",
        "build_delete_request",
        "build_describe_request",
        "build_update_request",
    ],
    "clb_target_group": [
        "build_create_request",
        "build_delete_request",
        "build_describe_request",
        "build_update_request",
        "find_instances",
    ],
    "network_acl": [
        "build_create_request",
        "build_describe_request",
        "build_entries_request",
    ],
    "vpc_flow_log": [
        "build_create_request",
        "build_delete_request",
        "build_describe_request",
        "build_toggle_request",
        "build_update_request",
    ],
    "ccn": [
        "build_create_request",
        "build_delete_request",
        "build_describe_request",
        "build_update_request",
    ],
    "ccn_attachment": ["build_describe_request"],
    "cls_logset": [
        "build_create_request",
        "build_delete_request",
        "build_describe_request",
        "build_update_request",
    ],
    "cls_topic": ["build_create_request", "build_delete_request", "build_describe_request", "build_update_request"],
    "privatelink_endpoint_service": ["build_create_request", "build_delete_request", "build_describe_request", "build_update_request"],
    "privatelink_endpoint": ["build_create_request", "build_delete_request", "build_describe_request", "build_update_request"],
    "postgresql_account": ["build_create_request", "build_delete_request", "build_describe_request", "build_password_request", "build_remark_request"],
    "cynosdb_account": ["build_create_request", "build_delete_request", "build_describe_request", "build_description_request", "build_password_request"],
    "api_gateway_service": ["build_create_request", "build_delete_request", "build_get_request", "build_list_request", "build_update_request"],
    "waf_ip_access_control": ["build_create_request", "build_delete_request", "build_describe_request", "build_update_request"],
    "tdmq_topic": ["build_create_request", "build_delete_request", "build_describe_request", "build_update_request"],
    "teo_dns_record": ["build_create_request", "build_delete_request", "build_describe_request", "build_update_request"],
    "cfw_address_template": ["build_create_request", "build_delete_request", "build_describe_request", "build_update_request"],
    "cloudaudit_track": ["build_create_request", "build_delete_request", "build_describe_request", "build_list_request", "build_update_request"],
    "config_rule": ["build_create_request", "build_delete_request", "build_describe_request", "build_list_request", "build_update_request"],
    "organization_node": ["build_create_request", "build_delete_request", "build_describe_request", "build_update_request"],
    "tat_command": ["build_create_request", "build_delete_request", "build_describe_request", "build_update_request"],
    "as_scaling_group": ["build_create_request", "build_delete_request", "build_describe_request", "build_update_request"],
    "dts_consumer_group": ["build_create_request", "build_delete_request", "build_describe_request", "build_update_request"],
    "dbbrain_sql_filter": ["build_create_request", "build_delete_request", "build_describe_request"],
    "cmq_queue": ["build_create_request", "build_delete_request", "build_describe_request", "build_update_request"],
    "tcr_replication_instance": ["build_create_request", "build_delete_request", "build_describe_request"],
    "api_gateway_api": ["build_get", "build_list"],
    "as_scaling_policy": ["find"],
    "as_scheduled_action": ["find"],
    "cls_index": ["find"],
    "cls_machine_group": ["find"],
    "cmq_subscription": ["find"],
    "cmq_topic": ["describe_request"],
    "dts_migration_job": ["describe_request"],
    "scf_trigger": ["create", "delete_request", "find"],
    "tcr_replication_rule": ["find"],
    "tdmq_subscription": ["delete_request", "describe_request"],
    "cam_group": ["find"],
    "cdb_parameter_template": ["find"],
    "ckafka_acl": ["find", "request_for"],
    "dnspod_domain": ["find"],
    "postgresql_parameter_template": ["find"],
    "redis_parameter_template": ["find"],
}


def discover_modules():
    """Return the names of every module in ``plugins/modules``."""
    return sorted(filename[: -len(".py")] for filename in os.listdir(MODULES_DIR) if filename.endswith(".py") and not filename.startswith("__"))


def _request_calls(node):
    """Return the set of ``models.*Request()`` names called inside *node*."""
    calls = set()
    for sub in ast.walk(node):
        func = getattr(sub, "func", None)
        if (
            isinstance(sub, ast.Call)
            and isinstance(func, ast.Attribute)
            and func.attr.endswith("Request")
            and isinstance(func.value, ast.Name)
            and func.value.id.endswith("models")
        ):
            calls.add(func.attr)
    return calls


def _module_utils_builders(tree):
    """Map a module's imported module_utils helpers to the SDK requests they build.

    The static scan cannot see functions relocated to ``plugins/module_utils``
    (e.g. ``monitor_alarm_policy``'s builders), so the module's own
    ``from ...module_utils.<name> import ...`` statements are followed one
    level and the imported helper bodies are scanned the same way. Only
    ``FunctionDef`` helpers that directly build requests are returned; helpers
    that merely delegate (e.g. waiters calling ``find_policy``) are ignored.
    """
    util_builders = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if not node.module or ".module_utils." not in node.module:
            continue
        util_name = node.module.rsplit(".", 1)[1]
        util_path = os.path.join(MODULE_UTILS_DIR, util_name + ".py")
        if not os.path.exists(util_path):
            continue
        with open(util_path, encoding="utf-8") as handle:
            util_tree = ast.parse(handle.read(), filename=util_path)
        helpers = {}
        for util_node in util_tree.body:
            if isinstance(util_node, ast.FunctionDef):
                requests = _request_calls(util_node)
                if requests:
                    helpers[util_node.name] = requests
        for alias in node.names:
            local = alias.asname or alias.name
            if local in helpers:
                util_builders[local] = helpers[local]
    return util_builders


def discover_request_builders(module_name):
    """Statically find a module's functions that build SDK request objects.

    A module-level function counts as a request builder when its body calls
    ``<something>models.<Name>Request()`` (matching both ``models`` and e.g.
    ``tag_models``). The scan is a pure AST walk, so it also runs in
    environments without the SDK.

    Builders relocated to ``plugins/module_utils`` are invisible to a scan of
    the module file alone. Registered builders (``WRITE_MODULE_BUILDERS``) are
    therefore also resolved through the module's own module_utils imports so
    the exercised/phantom audit keeps working after such refactors.
    """
    path = os.path.join(MODULES_DIR, module_name + ".py")
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    builders = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        requests = _request_calls(node)
        if requests:
            builders[node.name] = requests
    util_builders = _module_utils_builders(tree)
    for name in set(WRITE_MODULE_BUILDERS.get(module_name, ())):
        if name not in builders and name in util_builders:
            builders[name] = util_builders[name]
    return builders


def _exercised_builders(module_name):
    """Return the builders registered as contract-tested for *module_name*."""
    if module_name.endswith("_info"):
        return {builder for name, _service, builder, _calls in INFO_BUILDERS if name == module_name}
    return set(WRITE_MODULE_BUILDERS.get(module_name, ()))


# ---------------------------------------------------------------------------
# Info modules
# ---------------------------------------------------------------------------

# (module, SDK service, builder, [args tuples]) -- the real models module is
# passed as the first positional argument by the test. Only hand-written info
# modules are registered here; generated modules (those carrying the
# generator's MARKER) are covered automatically via _generated_info_builders.
INFO_BUILDERS_HANDWRITTEN = [
    (
        "vpc_info",
        "vpc.v20170312",
        "build_request",
        [
            (["vpc-xxxxxxxx"], None, 0, 100),
            (None, {"is-default": ["true"], "vpc-name": ["prod-vpc"]}, 0, 100),
        ],
    ),
    (
        "subnet_info",
        "vpc.v20170312",
        "build_request",
        [
            (["subnet-xxxxxxxx"], None, 0, 100),
            (None, {"vpc-id": ["vpc-xxxxxxxx"]}, 0, 100),
        ],
    ),
    (
        "route_table_info",
        "vpc.v20170312",
        "build_request",
        [
            (["rtb-xxxxxxxx"], None, 0, 100),
            (None, {"vpc-id": ["vpc-xxxxxxxx"]}, 0, 100),
        ],
    ),
    (
        "security_group_info",
        "vpc.v20170312",
        "build_request",
        [
            (["sg-xxxxxxxx"], None, 0, 100),
            (None, {"security-group-name": ["web-sg"]}, 0, 100),
        ],
    ),
    (
        "eip_info",
        "vpc.v20170312",
        "build_request",
        [
            (["eip-xxxxxxxx"], None, None, 0, 100),
            (None, ["1.2.3.4"], {"address-status": ["BIND"]}, 0, 100),
        ],
    ),
    (
        "key_pair_info",
        "cvm.v20170312",
        "build_request",
        [
            (["skey-xxxxxxxx"], None, 0, 100),
            (None, {"key-name": ["deploy-key"]}, 0, 100),
        ],
    ),
    (
        "cvm_instance_info",
        "cvm.v20170312",
        "build_request",
        [
            (["ins-xxxxxxxx"], None, 0, 100),
            (None, {"instance-name": ["web-01"]}, 0, 100),
        ],
    ),
    ("cam_user_info", "cam.v20190116", "build_request", [()]),
    ("cam_role_info", "cam.v20190116", "build_request", [(1, 100)]),
    (
        "cam_policy_info",
        "cam.v20190116",
        "build_request",
        [
            ("local", "app-read-only", 1, 100),
            ("all", None, 1, 100),
        ],
    ),
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
        selectors.append(
            (
                ["x-xxxxxxxx"] if spec["ids"] else None,
                {"name": ["value"]} if spec["filters"] else {},
            )
        )
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
    assert not overlap, "modules registered in both INFO_BUILDERS_HANDWRITTEN and the generator SPECS: %s" % ", ".join(overlap)


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


def _smoke_response(spec):
    """Spec-driven fake SDK response for a generated module's run_module.

    The paginator terminates after the first call either because the
    reported total (0) equals the collected items (0), or because a short
    page (0 < page_size) or a missing continuation token ends the loop.
    Dotted response paths (e.g. ``RecordCountInfo.TotalCount``) are
    materialised as nested namespaces so the generator's guarded accessor
    lambdas work.
    """
    resp = SimpleNamespace(RequestId="req-smoke")
    for path, value in (
        (spec["response_items"], []),
        (spec["response_total"], 0),
        # Generator defaults mirror _run_module_token_source: ListOver is
        # read by every token template even when the spec omits it.
        (spec.get("token_response_field", "NextToken"), None),
        (spec.get("list_over_field", "ListOver"), None),
        (spec.get("has_more_field"), None),
        # ids_action describe branches read their own response list field.
        (spec.get("ids_action", {}).get("response_items"), []),
    ):
        if not path:
            continue
        holder = resp
        parts = path.split(".")
        for part in parts[:-1]:
            nested = getattr(holder, part, None)
            if nested is None:
                nested = SimpleNamespace()
                setattr(holder, part, nested)
            holder = nested
        setattr(holder, parts[-1], value)
    return resp


class _SmokeModule(object):
    """Module stand-in that records the exit payload instead of exiting."""

    def __init__(self, params):
        self.params = params
        self.exit_payload = None

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs

    def fail_json(self, **kwargs):
        raise AssertionError("module failed during smoke run: %r" % (kwargs,))


def _smoke_params(spec):
    """Every param the generated ``run_module`` reads, with sample values.

    ``AnsibleModule`` is stubbed out (see ``_smoke_run_module``) so
    argument_spec validation and ``mutually_exclusive`` checks are bypassed;
    the module only ever reads ``module.params[...]`` for the names the
    generator emits, so every one of them must be present.
    """
    params = {"region": "ap-guangzhou"}
    for param in spec["extra_params"]:
        params[param["name"]] = _param_sample(param)
    if spec["ids"]:
        params[spec["ids"]["param"]] = ["x-xxxxxxxx"]
    if spec["filters"]:
        params["filters"] = {"name": ["value"]}
    params["page_size"] = 100
    return params


def _smoke_run_module(monkeypatch, spec, params):
    """Run a generated info module's ``run_module`` end to end (mocked SDK).

    Every network boundary is stubbed: the client class constructor is
    replaced with ``_StubClient``, ``sdk_call`` returns the spec-driven fake
    response, and ``AnsibleModule`` is replaced by ``_SmokeModule`` so the
    argument assembly, request construction and pagination logic run without
    exiting the process. ``serialize_sdk_object`` is neutralised because the
    fake response is not a real SDK model.
    """
    mod = _import_plugin(spec["module"])
    # Import the service package first: the client submodule below resolves
    # against it, and the import also registers the models the generated
    # module references at import time.
    importlib.import_module(spec["service_package"])
    client_module = importlib.import_module("%s.%s" % (spec["service_package"], spec["client_module"]))
    monkeypatch.setattr(client_module, spec["client_class"], lambda *args, **kwargs: _StubClient())
    fake = _SmokeModule(params)
    monkeypatch.setattr(mod, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(mod, "create_credential", lambda module: None)
    monkeypatch.setattr(mod, "create_client_profile", lambda module, endpoint: None)
    monkeypatch.setattr(mod, "sdk_call", lambda module, function, request: _smoke_response(spec))
    monkeypatch.setattr(mod, "serialize_sdk_object", lambda value: {})
    mod.run_module()
    return fake


SMOKE_SPECS = _load_generator_specs()


@pytest.mark.parametrize(
    "module_name",
    [spec["module"] for spec in SMOKE_SPECS],
    ids=[spec["module"] for spec in SMOKE_SPECS],
)
def test_info_module_run_module_smoke(monkeypatch, module_name):
    """Every generated info module's ``run_module`` runs to completion.

    The builder-only contract tests audit request construction; this smoke
    test additionally executes the whole ``run_module`` body against the
    real SDK packages (with the network stubbed) and catches wiring
    regressions a builder audit cannot see: renamed params, broken
    pagination lambdas, missing response-field reads, argument_spec typos.
    ``ids_action`` modules branch on the ids option, so both arms run.
    """
    spec = next(s for s in SMOKE_SPECS if s["module"] == module_name)
    params = _smoke_params(spec)
    param_sets = [params]
    if spec.get("ids_action"):
        # ids_action modules read module.params[ids] unconditionally and
        # branch on its truthiness; the list-all arm therefore passes an
        # empty list rather than omitting the key.
        no_ids = dict(params)
        no_ids[spec["ids"]["param"]] = []
        param_sets.append(no_ids)
    for params in param_sets:
        fake = _smoke_run_module(monkeypatch, spec, params)
        assert fake.exit_payload is not None, "run_module returned without exit_json"
        assert fake.exit_payload["changed"] is False
        assert fake.exit_payload["request_id"] == "req-smoke"


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
        assert not discovered, "%s is excepted via NO_API3_CONTRACT but now builds API 3.0 requests (%s); drop the exception and add contract coverage" % (
            module_name,
            ", ".join(sorted(discovered)),
        )
        pytest.skip(NO_API3_CONTRACT[module_name])

    exercised = _exercised_builders(module_name)
    if module_name.endswith("_info"):
        hint = "add an INFO_BUILDERS_HANDWRITTEN entry"
        marker = "# Generated by scripts/generate_info_modules.py"
        with open(os.path.join(MODULES_DIR, module_name + ".py"), encoding="utf-8") as handle:
            if marker in handle.read():
                hint = "the module is generated; add its SPECS entry to scripts/generate_info_modules.py"
    else:
        hint = "add a WRITE_MODULE_BUILDERS entry and a test_%s function exercising its builders" % module_name
    assert exercised or not discovered, "%s builds SDK requests (%s) but has no contract coverage; %s" % (module_name, ", ".join(sorted(discovered)), hint)

    excepted = {builder for (name, builder) in UNEXERCISED_BUILDERS if name == module_name}
    problems = []
    unexercised = sorted(set(discovered) - excepted - exercised)
    if unexercised:
        problems.append("builders not exercised by any contract test: %s" % ", ".join(unexercised))
    phantom = sorted(exercised - set(discovered))
    if phantom:
        problems.append("registered builders that build no requests (stale registration?): %s" % ", ".join(phantom))
    stale_exceptions = sorted(excepted - set(discovered))
    if stale_exceptions:
        problems.append("stale UNEXERCISED_BUILDERS entries: %s" % ", ".join(stale_exceptions))
    assert not problems, "%s: %s" % (module_name, "; ".join(problems))

    module = _import_plugin(module_name)
    for builder in sorted(exercised):
        assert callable(getattr(module, builder, None)), "%s.%s is registered as exercised but does not exist" % (module_name, builder)
    if not module_name.endswith("_info"):
        assert callable(globals().get("test_" + module_name)), "%s is registered in WRITE_MODULE_BUILDERS but test_%s is missing" % (module_name, module_name)


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
    errors.extend(audit_request(module.build_describe_request(models, "prod-vpc", None), "vpc describe by name"))
    errors.extend(audit_request(module.build_describe_request(models, None, "vpc-xxxxxxxx"), "vpc describe by id"))
    module._create(fake, client, models, "prod-vpc", "10.0.0.0/16", ["183.60.83.19"], "prod.internal", {"env": "prod"})
    module._update_attributes(fake, client, models, "vpc-xxxxxxxx", "prod-vpc", ["183.60.83.19"], "prod.internal")
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
    errors.extend(audit_request(module.build_describe_request(models, "subnet-xxxxxxxx", None, None), "subnet describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "vpc-xxxxxxxx", "web-subnet"), "subnet describe by filters"))
    module._create(fake, client, models, "vpc-xxxxxxxx", "web-subnet", "10.0.1.0/24", "ap-guangzhou-1", {"env": "prod"})
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
    errors.extend(audit_request(module.build_describe_request(models, "rtb-xxxxxxxx", None, None), "route_table describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "vpc-xxxxxxxx", "app-rtb"), "route_table describe by filters"))
    module._create(fake, client, models, "vpc-xxxxxxxx", "app-rtb", {"env": "prod"})
    module._update_name(fake, client, models, "rtb-xxxxxxxx", "app-rtb")
    module._delete(fake, client, models, "rtb-xxxxxxxx")
    to_add = [
        {
            "destination_cidr_block": "10.1.0.0/16",
            "gateway_type": "NAT",
            "gateway_id": "nat-xxxxxxxx",
            "description": "egress via NAT",
        }
    ]
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
    errors.extend(audit_request(module.build_describe_request(models, "web-sg", None), "security_group describe by name"))
    errors.extend(audit_request(module.build_describe_request(models, None, "sg-xxxxxxxx"), "security_group describe by id"))
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
    errors.extend(audit_request(module.build_describe_request(models, "sg-xxxxxxxx"), "security_group_rule describe"))
    rules = [
        module.normalize_desired_rule(
            {
                "protocol": "tcp",
                "port": "443",
                "cidr_block": "0.0.0.0/0",
                "action": "ACCEPT",
                "policy_description": "HTTPS",
                "direction": "ingress",
            }
        ),
        module.normalize_desired_rule(
            {
                "protocol": "UDP",
                "port": "53",
                "cidr_block": "10.0.1.0/24",
                "action": "DROP",
                "direction": "egress",
            }
        ),
    ]
    errors.extend(audit_request(module.build_policy_set(models, rules), "security_group_rule policy set"))
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
    errors.extend(audit_request(module.build_describe_request(models, "eip-xxxxxxxx", None, None), "eip describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "1.2.3.4", None), "eip describe by ip"))
    errors.extend(audit_request(module.build_describe_request(models, None, None, "web-eip"), "eip describe by name"))
    module._create(fake, client, models, "web-eip", "TRAFFIC_POSTPAID_BY_HOUR", 10, {"env": "prod"})
    module._associate(fake, client, models, "eip-xxxxxxxx", "ins-xxxxxxxx")
    module._disassociate(fake, client, models, "eip-xxxxxxxx")
    module._update_name(fake, client, models, "eip-xxxxxxxx", "web-eip")
    module._update_bandwidth(fake, client, models, "eip-xxxxxxxx", 20)
    module._update_charge_type(fake, client, models, "eip-xxxxxxxx", "BANDWIDTH_PREPAID_BY_MONTH", 20)
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
    errors.extend(audit_request(module.build_describe_request(models, "deploy-key", None), "key_pair describe by name"))
    errors.extend(audit_request(module.build_describe_request(models, None, "skey-xxxxxxxx"), "key_pair describe by id"))
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
    errors.extend(audit_request(module.build_describe_request(models, "ins-xxxxxxxx", None), "cvm describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "web-01"), "cvm describe by name"))
    errors.extend(audit_request(module.build_describe_request(models, None, None, {"role": "web"}), "cvm describe by count_tag"))
    errors.extend(audit_request(module.build_describe_request(models, None, None, {"role": "web", "tier": "api"}), "cvm describe by multi count_tag"))
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
    errors.extend(audit_request(module.build_run_request(models, params), "cvm run request (key pair)"))
    password_params = dict(params, key_ids=None, password="Sup3rSecret!", dry_run=False, vpc_id=None, subnet_id=None, tags={})
    errors.extend(audit_request(module.build_run_request(models, password_params), "cvm run request (password)"))
    bulk_params = dict(params, instance_count=3, dry_run=False)
    errors.extend(audit_request(module.build_run_request(models, bulk_params), "cvm run request (exact_count bulk)"))
    zone_params = dict(params, instance_count=3, dry_run=False, zone="ap-guangzhou-3", subnet_id="subnet-az3")
    errors.extend(audit_request(module.build_run_request(models, zone_params), "cvm run request (exact_count zone spread)"))
    module._create(fake, client, models, params)
    module._delete(fake, client, models, "ins-xxxxxxxx")
    module._start(fake, client, models, "ins-xxxxxxxx")
    module._stop(fake, client, models, "ins-xxxxxxxx")
    module._reboot(fake, client, models, "ins-xxxxxxxx")
    module._reset_password(fake, client, models, "ins-xxxxxxxx", "Sup3rSecret!")
    module._reset_type(fake, client, models, "ins-xxxxxxxx", "S5.LARGE4")
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
        "statement": [
            {
                "action": "name/sts:AssumeRole",
                "effect": "allow",
                "principal": {"service": ["cvm.qcloud.com"]},
            }
        ],
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
        "statement": [
            {
                "action": ["cvm:DescribeInstances"],
                "effect": "allow",
                "resource": "*",
            }
        ],
    }
    module.find_policy(fake, client, models, 1000001, None, "Local")
    module.find_policy(fake, client, models, None, "app-read-only", "Local")
    module._create(fake, client, models, "app-read-only", "Read-only", document, {"env": "prod"})
    module._update(fake, client, models, 1000001, "app-read-only", "Read-only", document, ["policy_name", "description", "policy_document"])
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
    errors.extend(audit_request(module.build_describe_request(models, "lb-xxxxxxxx", None, None), "clb describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "web-lb", "vpc-xxxxxxxx"), "clb describe by name"))
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
    errors.extend(audit_request(module.build_create_request(models, params), "clb create request"))
    module._delete(fake, client, models, "lb-xxxxxxxx")
    module._update_attributes(fake, client, models, "lb-xxxxxxxx", "web-lb", "TRAFFIC_POSTPAID_BY_HOUR", 10)
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
    errors.extend(audit_request(module.build_describe_request(models, "lb-xxxxxxxx", "lbl-xxxxxxxx", None, None), "listener describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, "lb-xxxxxxxx", None, 8080, "TCP"), "listener describe by port/protocol"))
    params = {
        "load_balancer_id": "lb-xxxxxxxx",
        "port": 8080,
        "protocol": "TCP",
        "name": "tcp-8080",
        "scheduler": "WRR",
        "session_expire_time": 0,
        "health_check": {
            "health_switch": True,
            "interval_time": 5,
            "health_num": 3,
            "un_health_num": 3,
            "time_out": 2,
            "check_type": "HTTP",
            "http_check_path": "/healthz",
            "http_check_domain": "example.com",
            "http_check_method": "HEAD",
            "http_code": 31,
            "http_version": "HTTP/1.1",
        },
        "certificate": None,
        "sni_switch": None,
        "keepalive_enable": None,
    }
    errors.extend(audit_request(module.build_create_request(models, params), "listener create request (TCP)"))
    https_params = dict(
        params,
        protocol="HTTPS",
        port=443,
        health_check=None,
        certificate={"ssl_mode": "UNIDIRECTIONAL", "cert_id": "abc", "cert_ca_id": None},
        sni_switch=False,
        keepalive_enable=True,
    )
    errors.extend(audit_request(module.build_create_request(models, https_params), "listener create request (HTTPS)"))
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
    errors.extend(audit_request(module.build_describe_request(models, "lb-xxxxxxxx", "lbl-xxxxxxxx"), "targets describe"))
    targets = [
        {"instance_id": "ins-aaaaaaaa", "eni_ip": None, "port": 8080, "weight": 20},
        {"instance_id": None, "eni_ip": "10.0.1.15", "port": 8081, "weight": 10},
    ]
    module._register(fake, client, models, "lb-xxxxxxxx", "lbl-xxxxxxxx", None, targets)
    module._deregister(fake, client, models, "lb-xxxxxxxx", "lbl-xxxxxxxx", "loc-xxxxxxxx", targets)
    module._wait_task(fake, client, models, "req-0001")
    errors.extend(audit_recorded(fake, "clb_listener_target"))
    assert errors == []


def test_cvm_image():
    module = _import_plugin("cvm_image")
    models = _models("cvm.v20170312")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "img-xxxxxxxx", None), "cvm_image describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "web-prod"), "cvm_image describe by name"))
    module._create(
        fake,
        client,
        models,
        {
            "instance_id": "ins-xxxxxxxx",
            "image_name": "web-prod",
            "image_description": "golden image",
            "force_poweroff": True,
            "sysprep": False,
        },
    )
    module._update(fake, client, models, "img-xxxxxxxx", "web-prod-v2", "renamed")
    module._delete(fake, client, models, "img-xxxxxxxx", True)
    errors.extend(audit_recorded(fake, "cvm_image"))
    assert errors == []


def test_cfs_file_system():
    module = _import_plugin("cfs_file_system")
    models = _models("cfs.v20190719")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "cfs-xxxxxxxx", None), "cfs describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "app-share"), "cfs describe by name"))
    module._create(
        fake,
        client,
        models,
        {
            "zone": "ap-guangzhou-3",
            "protocol": "NFS",
            "storage_type": "SD",
            "capacity": 100,
            "name": "app-share",
            "vpc_id": "vpc-xxxxxxxx",
            "subnet_id": "subnet-xxxxxxxx",
            "pgroup_id": "pgroup-xxxxxxxx",
        },
    )
    module._update_name(fake, client, models, "cfs-xxxxxxxx", "app-share-v2")
    module._update_size_limit(fake, client, models, "cfs-xxxxxxxx", 200)
    module._delete(fake, client, models, "cfs-xxxxxxxx")
    errors.extend(audit_recorded(fake, "cfs_file_system"))
    assert errors == []


def test_lighthouse_instance():
    module = _import_plugin("lighthouse_instance")
    models = _models("lighthouse.v20200324")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "lhins-xxxxxxxx", None), "lighthouse describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "blog-01"), "lighthouse describe by name"))
    errors.extend(
        audit_request(
            module.build_create_request(
                models,
                {
                    "bundle_id": "bundle_2022_std_1c1g",
                    "blueprint_id": "lhbp-xxxxxxxx",
                    "instance_count": 1,
                    "instance_name": "blog-01",
                    "zones": ["ap-guangzhou-3"],
                    "password": "secret",
                    "prepaid_period": 1,
                },
            ),
            "lighthouse create request",
        )
    )
    module._create(
        fake,
        client,
        models,
        {
            "bundle_id": "bundle_2022_std_1c1g",
            "blueprint_id": "lhbp-xxxxxxxx",
            "instance_count": 1,
            "instance_name": "blog-01",
            "zones": ["ap-guangzhou-3"],
            "password": "secret",
            "prepaid_period": 1,
        },
    )
    module._start(fake, client, models, "lhins-xxxxxxxx")
    module._stop(fake, client, models, "lhins-xxxxxxxx")
    module._isolate(fake, client, models, "lhins-xxxxxxxx")
    module._update_name(fake, client, models, "lhins-xxxxxxxx", "blog-01")
    errors.extend(audit_recorded(fake, "lighthouse_instance"))
    assert errors == []


def test_cbs_disk():
    module = _import_plugin("cbs_disk")
    models = _models("cbs.v20170312")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "disk-xxxxxxxx", None, None), "cbs describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "data-disk", None), "cbs describe by name"))
    errors.extend(audit_request(module.build_describe_request(models, None, None, "ap-guangzhou-3"), "cbs describe by zone"))
    params = {
        "charge_type": "POSTPAID_BY_HOUR",
        "disk_size": 100,
        "disk_type": "CLOUD_PREMIUM",
        "encrypt": False,
        "name": "data-disk",
        "prepaid_period_months": None,
        "snapshot_id": None,
        "tags": {"env": "prod"},
        "zone": "ap-guangzhou-3",
    }
    module._create(fake, client, models, params)
    module._rename(fake, client, models, "disk-xxxxxxxx", "data-disk-v2")
    module._resize(fake, client, models, "disk-xxxxxxxx", 200)
    module._attach(fake, client, models, "disk-xxxxxxxx", "ins-xxxxxxxx", True)
    module._detach(fake, client, models, "disk-xxxxxxxx", "ins-xxxxxxxx")
    module._delete(fake, client, models, "disk-xxxxxxxx", False)
    errors.extend(audit_recorded(fake, "cbs_disk"))
    assert errors == []


def test_cbs_snapshot():
    module = _import_plugin("cbs_snapshot")
    models = _models("cbs.v20170312")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, ["snap-xxxxxxxx"], None, None), "cbs_snapshot describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "disk-xxxxxxxx", "nightly"), "cbs_snapshot describe by disk and name"))
    module.find_snapshot(fake, client, models, None, "disk-xxxxxxxx", "nightly")
    module._create(fake, client, models, "disk-xxxxxxxx", "nightly")
    module._delete(fake, client, models, ["snap-xxxxxxxx"])
    errors.extend(audit_recorded(fake, "cbs_snapshot"))
    assert errors == []


def test_cdb_instance():
    module = _import_plugin("cdb_instance")
    models = _models("cdb.v20170320")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "cdb-xxxxxxxx", None), "cdb describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "order-db"), "cdb describe by name"))
    module._create(
        fake,
        client,
        models,
        {
            "zone": "ap-guangzhou-3",
            "engine_version": "8.0",
            "memory": 4000,
            "volume": 200,
            "name": "order-db",
            "password": "Sup3rSecret!",
            "vpc_id": "vpc-xxxxxxxx",
            "subnet_id": "subnet-xxxxxxxx",
            "project_id": 0,
            "period_months": None,
            "auto_renew": None,
            "security_group": ["sg-xxxxxxxx"],
            "tags": {"env": "prod"},
        },
    )
    module._rename(fake, client, models, "cdb-xxxxxxxx", "order-db-v2")
    module._delete(fake, client, models, "cdb-xxxxxxxx")
    errors.extend(audit_request(module.build_restart_request(models, "cdb-xxxxxxxx"), "cdb restart by id"))
    errors.extend(audit_request(module.build_task_status_request(models, "9ad9c2d5-88007b27-7d2c8b8c-f2598f12"), "cdb async task status"))
    errors.extend(audit_request(module.build_upgrade_request(models, "cdb-xxxxxxxx", 16000, 200), "cdb spec resize"))
    # Drive the full restart and spec-resize paths: the async task client
    # returns the doc-shaped RestartDBInstances/UpgradeDBInstance responses
    # (each carrying an AsyncRequestId) and the DescribeAsyncRequestInfo
    # responses so the polling loops terminate on SUCCESS.

    class _AsyncTaskClient(_StubClient):
        def RestartDBInstances(self, request):
            response = _StubResponse()
            response.AsyncRequestId = "9ad9c2d5-88007b27-7d2c8b8c-f2598f12"
            return response

        def UpgradeDBInstance(self, request):
            response = _StubResponse()
            response.AsyncRequestId = "a6040589-3b098df5-b551d9e5-81c6bfdc"
            return response

        def DescribeAsyncRequestInfo(self, request):
            response = _StubResponse()
            response.Status = "SUCCESS"
            response.Info = "task succeeded"
            return response

    module._restart(fake, _AsyncTaskClient(), models, "cdb-xxxxxxxx")
    module._upgrade(fake, _AsyncTaskClient(), models, "cdb-xxxxxxxx", 16000, 200)
    errors.extend(audit_recorded(fake, "cdb_instance"))
    assert errors == []


def test_ckafka_topic():
    module = _import_plugin("ckafka_topic")
    models = _models("ckafka.v20190819")
    fake = _RecordingModule()
    client = _StubClient()
    module.find_topic(fake, client, models, "ckafka-xxxxxxxx", "order-events")
    module._create(
        fake,
        client,
        models,
        {
            "instance_id": "ckafka-xxxxxxxx",
            "topic_name": "order-events",
            "partition_num": 3,
            "replica_num": 2,
            "retention_ms": 86400000,
            "retention_bytes": None,
            "clean_up_policy": "delete",
            "note": "Order event stream",
            "max_message_bytes": None,
            "min_insync_replicas": 1,
            "unclean_leader_election": False,
            "producer_quota_mb": None,
            "consumer_quota_mb": None,
            "message_timestamp_type": "CreateTime",
        },
    )
    module._update(
        fake,
        client,
        models,
        "ckafka-xxxxxxxx",
        "order-events",
        3,
        {
            "partition_num": 6,
            "replica_num": 2,
            "retention_ms": 86400000,
            "retention_bytes": None,
            "clean_up_policy": "delete",
            "note": "Order event stream (scaled)",
            "max_message_bytes": None,
            "min_insync_replicas": 1,
            "unclean_leader_election": False,
            "producer_quota_mb": 20,
            "consumer_quota_mb": 30,
            "message_timestamp_type": "LogAppendTime",
        },
    )
    module._scale_partitions(fake, client, models, "ckafka-xxxxxxxx", "order-events", 3, 6)
    module._delete(fake, client, models, "ckafka-xxxxxxxx", "order-events")
    assert audit_recorded(fake, "ckafka_topic") == []


def test_clb_rule():
    module = _import_plugin("clb_rule")
    models = _models("clb.v20180317")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "lb-xxxxxxxx", "lbl-xxxxxxxx"), "clb_rule describe by ids"))
    health_check = {
        "health_switch": True,
        "interval_time": 5,
        "health_num": 3,
        "un_health_num": 3,
        "time_out": 3,
        "check_type": "HTTP",
        "check_port": 80,
        "http_check_path": "/healthz",
        "http_check_domain": "example.com",
        "http_check_method": "GET",
        "http_code": 200,
        "http_version": "HTTP/1.0",
    }
    create_params = {
        "load_balancer_id": "lb-xxxxxxxx",
        "listener_id": "lbl-xxxxxxxx",
        "domain": "api.example.com",
        "url": "/v1/orders",
        "scheduler": "WRR",
        "session_expire_time": None,
        "forward_type": None,
        "cookie_name": None,
        "http2": False,
        "health_check": health_check,
    }
    location_id = module._create(fake, client, models, create_params)
    update_params = dict(create_params, health_check=dict(health_check, interval_time=10))
    module._update(fake, client, models, update_params, location_id or "loc-xxxxxxxx")
    module._delete(fake, client, models, create_params, location_id or "loc-xxxxxxxx")
    errors.extend(audit_recorded(fake, "clb_rule"))
    assert errors == []


def test_dnspod_record():
    module = _import_plugin("dnspod_record")
    models = _models("dnspod.v20210323")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "example.com", None, "www", "A", None), "dnspod describe by domain and subdomain"))
    errors.extend(audit_request(module.build_describe_request(models, None, 123456, "www", "A", "默认"), "dnspod describe by domain id"))
    params = {
        "domain": "example.com",
        "domain_id": None,
        "subdomain": "www",
        "record_type": "A",
        "record_line": "默认",
        "value": "1.2.3.4",
        "ttl": 600,
        "weight": None,
        "mx": None,
        "remark": "www frontend",
        "status": "ENABLE",
    }
    module._create(fake, client, models, params)
    module._update(fake, client, models, params, 123456789)
    module._delete(fake, client, models, params, 123456789)
    errors.extend(audit_recorded(fake, "dnspod_record"))
    assert errors == []


def test_dnspod_custom_line():
    module = _import_plugin("dnspod_custom_line"); models = _models("dnspod.v20210323")
    p = {"domain": "example.com", "domain_id": None, "name": "office", "area": "203.0.113.1-203.0.113.254"}
    requests = [module.describe_request(models, p), module.create_request(models, p), module.update_request(models, p), module.delete_request(models, p)]
    errors = []
    for request in requests: errors.extend(audit_request(request, "DNSPod custom line request"))
    assert errors == []


def test_dnspod_line_group():
    module = _import_plugin("dnspod_line_group"); models = _models("dnspod.v20210323")
    p = {"domain": "example.com", "domain_id": None, "line_group_id": 123, "name": "corporate", "lines": ["office", "vpn"]}
    requests = [module.describe_request(models, p), module.create_request(models, p), module.update_request(models, p, 123), module.delete_request(models, p, 123)]
    errors = []
    for request in requests: errors.extend(audit_request(request, "DNSPod line group request"))
    assert errors == []


def test_nat_gateway():
    module = _import_plugin("nat_gateway")
    models = _models("vpc.v20170312")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "nat-xxxxxxxx", None, None), "nat describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "egress-nat", None), "nat describe by name"))
    errors.extend(audit_request(module.build_describe_request(models, None, None, "vpc-xxxxxxxx"), "nat describe by vpc"))
    module._create(
        fake,
        client,
        models,
        {
            "vpc_id": "vpc-xxxxxxxx",
            "name": "egress-nat",
            "internet_max_bandwidth_out": 100,
            "max_concurrent_connection": None,
            "address_count": None,
            "public_ip_addresses": ["eip-xxxxxxxx"],
            "zone": "ap-guangzhou-3",
        },
    )
    module._set_deletion_protection(fake, client, models, "nat-xxxxxxxx", True)
    module._update(fake, client, models, "nat-xxxxxxxx", "egress-nat-v2", 200)
    module._delete(fake, client, models, "nat-xxxxxxxx", True)
    errors.extend(audit_recorded(fake, "nat_gateway"))
    assert errors == []


def test_nat_gateway_rule():
    module = _import_plugin("nat_gateway_rule")
    models = _models("vpc.v20170312")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_dnat_describe_request(models, "nat-xxxxxxxx"), "nat_gateway_rule dnat describe"))
    errors.extend(audit_request(module.build_snat_describe_request(models, "nat-xxxxxxxx"), "nat_gateway_rule snat describe"))
    dnat = module.normalize_dnat(
        {
            "ip_protocol": "tcp",
            "public_ip_address": "114.182.81.73",
            "public_port": 8989,
            "private_ip_address": "10.80.80.41",
            "private_port": 8989,
            "description": "web",
        }
    )
    snat = module.normalize_snat(
        {
            "resource_type": "cvm",
            "resource_id": "cvm-xxxxxxxx",
            "private_ip_address": "10.0.0.5",
            "public_ip_addresses": ["180.12.59.43"],
            "description": "prod",
        }
    )
    module.find_gateway(fake, client, models, "nat-xxxxxxxx")
    module.list_dnat_rules(fake, client, models, "nat-xxxxxxxx")
    module.list_snat_rules(fake, client, models, "nat-xxxxxxxx")
    module._create_dnat(fake, client, models, "nat-xxxxxxxx", [dnat])
    module._delete_dnat(fake, client, models, "nat-xxxxxxxx", [dnat])
    module._create_snat(fake, client, models, "nat-xxxxxxxx", [snat])
    module._delete_snat(fake, client, models, "nat-xxxxxxxx", ["snat-xxxxxxxx"])
    errors.extend(audit_recorded(fake, "nat_gateway_rule"))
    assert errors == []


def test_peering_connection():
    module = _import_plugin("peering_connection")
    models = _models("vpc.v20170312")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "pcx-xxxxxxxx", None, None), "peering describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "app-peer", None), "peering describe by name"))
    errors.extend(audit_request(module.build_describe_request(models, None, None, "vpc-xxxxxxxx"), "peering describe by source vpc"))
    module._create(
        fake,
        client,
        models,
        {
            "source_vpc_id": "vpc-xxxxxxxx",
            "destination_vpc_id": "vpc-yyyyyyyy",
            "name": "app-peer",
            "destination_region": "ap-shanghai",
            "destination_uin": "100000000001",
            "bandwidth": 100,
            "charge_type": "POSTPAID_BY_HOUR",
            "qos_level": "PT",
        },
    )
    module._accept(fake, client, models, "pcx-xxxxxxxx")
    module._update(fake, client, models, "pcx-xxxxxxxx", "app-peer-v2", 200, "POSTPAID_BY_HOUR")
    module._delete(fake, client, models, "pcx-xxxxxxxx")
    errors.extend(audit_recorded(fake, "peering_connection"))
    assert errors == []


def test_redis_instance():
    module = _import_plugin("redis_instance")
    models = _models("redis.v20180412")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "crs-xxxxxxxx", None), "redis describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "session-cache"), "redis describe by name"))
    module._create(
        fake,
        client,
        models,
        {
            "zone_name": "ap-guangzhou-3",
            "type_id": 2,
            "mem_size": 1024,
            "name": "session-cache",
            "redis_shard_num": 1,
            "redis_replicas_num": 1,
            "vpc_id": "vpc-xxxxxxxx",
            "subnet_id": "subnet-xxxxxxxx",
            "password": "Sup3rSecret!",
            "no_auth": False,
            "project_id": 0,
            "security_group_id_list": ["sg-xxxxxxxx"],
            "tags": {"env": "prod"},
        },
    )
    module._rename(fake, client, models, "crs-xxxxxxxx", "session-cache-v2")
    module._destroy(fake, client, models, "crs-xxxxxxxx", "POSTPAID")
    module._destroy(fake, client, models, "crs-xxxxxxxx", "PREPAID")
    errors.extend(audit_recorded(fake, "redis_instance"))
    assert errors == []


def test_scf_function():
    module = _import_plugin("scf_function")
    models = _models("scf.v20180416")
    fake = _RecordingModule()
    client = _StubClient()
    module.find_function(fake, client, models, "etl-job", "default")
    create_params = {
        "function_name": "etl-job",
        "namespace": "default",
        "handler": "index.handler",
        "runtime": "Python3.9",
        "description": "ETL job",
        "memory_size": 256,
        "execution_timeout": 30,
        "environment": {"LOG_LEVEL": "info"},
        "role": "cos-scf-role",
        "vpc_id": None,
        "subnet_id": None,
        "zip_file": None,
        "cos_bucket_name": "bucket-1250000000",
        "cos_bucket_region": "ap-guangzhou",
        "cos_object_name": "etl.zip",
        "region": "ap-guangzhou",
    }
    module._create(fake, client, models, create_params)
    module._update_code(
        fake,
        client,
        models,
        "etl-job",
        "default",
        {
            "handler": "index.handler",
            "zip_file": None,
            "cos_bucket_name": "bucket-1250000000",
            "cos_bucket_region": "ap-guangzhou",
            "cos_object_name": "etl-v2.zip",
            "region": "ap-guangzhou",
        },
    )
    module._update_config(
        fake,
        client,
        models,
        "etl-job",
        "default",
        {
            "description": "ETL job v2",
            "environment": {"LOG_LEVEL": "debug"},
            "execution_timeout": 60,
            "memory_size": 512,
            "role": "cos-scf-role",
            "vpc_id": None,
            "subnet_id": None,
        },
    )
    module._delete(fake, client, models, "etl-job", "default")
    assert audit_recorded(fake, "scf_function") == []


def test_ssl_certificate():
    module = _import_plugin("ssl_certificate")
    models = _models("ssl.v20191205")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "cert-xxxxxxxx", None), "ssl describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "api.example.com"), "ssl describe by alias"))
    cert_id = module._upload(
        fake,
        client,
        models,
        {
            "cert_content": "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE\n-----END PRIVATE KEY-----",
            "certificate_type": "SVR",
            "alias": "api.example.com",
            "project_id": 0,
            "tags": {"env": "prod"},
        },
    )
    module._rename(fake, client, models, cert_id or "cert-xxxxxxxx", "api-v2.example.com")
    module._deploy(fake, client, models, cert_id or "cert-xxxxxxxx", ["lbl-xxxxxxxx"], "clb")
    module._delete(fake, client, models, cert_id or "cert-xxxxxxxx")
    errors.extend(audit_recorded(fake, "ssl_certificate"))
    assert errors == []


def test_ssm_parameter():
    module = _import_plugin("ssm_parameter")
    models = _models("ssm.v20190923")
    fake = _RecordingModule()
    client = _StubClient()
    module.find_secret(fake, client, models, "db-password")
    module._create(
        fake,
        client,
        models,
        {
            "secret_name": "db-password",
            "secret_string": "Sup3rSecret!",
            "secret_binary": None,
            "description": "Database password",
            "secret_type": 1,
            "encrypt_type": 0,
            "kms_key_id": None,
        },
    )
    module._update_value(fake, client, models, "db-password", "NewSecret!", None)
    module._delete(fake, client, models, "db-password", False, 30)
    assert audit_recorded(fake, "ssm_parameter") == []


def test_tag():
    module = _import_plugin("tag")
    models = _models("tag.v20180813")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "env", None, "cvm", "instance", "ap-guangzhou"), "tag describe by key"))
    errors.extend(audit_request(module.build_describe_request(models, "env", "prod", "cvm", "instance", None), "tag describe by key and value"))
    module.find_resources(fake, client, models, "env", "prod", "cvm", "instance", "ap-guangzhou")
    module._attach(fake, client, models, "env", "prod", "cvm", "instance", "ap-guangzhou", ["ins-xxxxxxxx"])
    module._update_value(fake, client, models, "env", "prod", "cvm", "instance", "ap-guangzhou", ["ins-xxxxxxxx"])
    module._detach(fake, client, models, "env", "cvm", "instance", "ap-guangzhou", ["ins-xxxxxxxx"])
    errors.extend(audit_recorded(fake, "tag"))
    assert errors == []


def test_tke_cluster():
    module = _import_plugin("tke_cluster")
    models = _models("tke.v20180525")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "cls-xxxxxxxx", None), "tke describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "order-cluster"), "tke describe by name"))
    module._create(
        fake,
        client,
        models,
        {
            "cluster_type": "MANAGED_CLUSTER",
            "name": "order-cluster",
            "vpc_id": "vpc-xxxxxxxx",
            "subnet_id": "subnet-xxxxxxxx",
            "cluster_version": "1.30.3",
            "cluster_desc": "Order service cluster",
            "project_id": 0,
            "tags": {"env": "prod"},
            "cluster_cidr": "10.244.0.0/16",
            "service_cidr": "10.96.0.0/16",
            "max_node_pod_num": 64,
            "deletion_protection": True,
        },
    )
    module._update(fake, client, models, "cls-xxxxxxxx", "order-cluster-v2", "Order service cluster v2", 0)
    module._set_deletion_protection(fake, client, models, "cls-xxxxxxxx", False)
    module._delete(fake, client, models, "cls-xxxxxxxx", "terminate")
    errors.extend(audit_recorded(fake, "tke_cluster"))
    assert errors == []


def test_vpn_gateway():
    module = _import_plugin("vpn_gateway")
    models = _models("vpc.v20170312")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "vpngw-xxxxxxxx", None, None), "vpn describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "site-vpn", None), "vpn describe by name"))
    errors.extend(audit_request(module.build_describe_request(models, None, None, "vpc-xxxxxxxx"), "vpn describe by vpc"))
    module._create(
        fake,
        client,
        models,
        {
            "vpc_id": "vpc-xxxxxxxx",
            "name": "site-vpn",
            "instance_charge_type": "POSTPAID_BY_HOUR",
            "type": "IPSEC",
            "internet_max_bandwidth_out": 100,
            "max_connection": 100,
            "zone": "ap-guangzhou-3",
            "bgp_asn": 64512,
        },
    )
    module._update(fake, client, models, "vpngw-xxxxxxxx", "site-vpn-v2", 200, 64512)
    module._delete(fake, client, models, "vpngw-xxxxxxxx")
    errors.extend(audit_recorded(fake, "vpn_gateway"))
    assert errors == []


def test_customer_gateway():
    module = _import_plugin("customer_gateway")
    models = _models("vpc.v20170312")
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "cgw-xxxxxxxx"), "customer gateway describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, name="office-peer"), "customer gateway describe by name"))
    params = {
        "name": "office-peer",
        "ip_address": "203.0.113.10",
        "bgp_asn": 65001,
        "tags": {"env": "prod"},
    }
    errors.extend(audit_request(module.build_create_request(models, params), "customer gateway create"))
    errors.extend(audit_request(module.build_update_request(models, "cgw-xxxxxxxx", "office-v2", 65002), "customer gateway update"))
    errors.extend(audit_request(module.build_delete_request(models, "cgw-xxxxxxxx"), "customer gateway delete"))
    assert errors == []


def test_vpn_connection():
    module = _import_plugin("vpn_connection")
    models = _models("vpc.v20170312")
    params = {
        "name": "office",
        "vpn_gateway_id": "vpngw-xxxxxxxx",
        "customer_gateway_id": "cgw-xxxxxxxx",
        "vpc_id": "vpc-xxxxxxxx",
        "pre_shared_key": "secret",
        "rotate_pre_shared_key": True,
        "security_policy_databases": [{"local_cidr": "10.0.0.0/16", "remote_cidr": "192.168.0.0/16"}],
        "route_type": "Policy",
        "negotiation_type": "active",
        "dpd_enabled": True,
        "dpd_timeout": 30,
        "dpd_action": "restart",
        "tags": {"env": "prod"},
    }
    requests = [
        module.build_describe_request(models, "vpnx-xxxxxxxx"),
        module.build_describe_request(models, name="office", gateway_id="vpngw-xxxxxxxx"),
        module.build_create_request(models, params),
        module.build_update_request(models, "vpnx-xxxxxxxx", params),
        module.build_delete_request(models, "vpngw-xxxxxxxx", "vpnx-xxxxxxxx"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "vpn connection request %s" % index))
    assert errors == []


def test_clb_target_group():
    module = _import_plugin("clb_target_group")
    models = _models("clb.v20180317")
    params = {
        "name": "api",
        "vpc_id": "vpc-xxxxxxxx",
        "type": "v2",
        "protocol": "HTTP",
        "port": 8080,
        "schedule_algorithm": "WRR",
        "weight": 10,
        "tags": {"env": "prod"},
    }
    requests = [
        module.build_describe_request(models, "lbtg-xxxxxxxx"),
        module.build_describe_request(models, name="api", vpc_id="vpc-xxxxxxxx"),
        module.build_create_request(models, params),
        module.build_update_request(models, "lbtg-xxxxxxxx", params),
        module.build_delete_request(models, "lbtg-xxxxxxxx"),
        module.build_instances_request(models, "lbtg-xxxxxxxx", [{"ip": "10.0.0.1", "port": 8080, "weight": 10}], models.RegisterTargetGroupInstancesRequest),
        module.build_instances_request(models, "lbtg-xxxxxxxx", [{"ip": "10.0.0.1", "port": 8080, "weight": 10}], models.DeregisterTargetGroupInstancesRequest),
    ]
    fake = _RecordingModule()
    module.find_instances(fake, _StubClient(), models, "lbtg-xxxxxxxx")
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "target group request %s" % index))
    errors.extend(audit_recorded(fake, "target group instances"))
    assert errors == []


def test_network_acl():
    module = _import_plugin("network_acl")
    models = _models("vpc.v20170312")
    params = {"name": "app", "vpc_id": "vpc-xxxxxxxx", "acl_type": None, "tags": {"env": "prod"}}
    rules = [{"protocol": "TCP", "port": "443", "cidr": "10.0.0.0/8", "ipv6_cidr": None, "action": "ACCEPT", "description": "https", "priority": 1}]
    requests = [
        module.build_describe_request(models, "acl-xxxxxxxx"),
        module.build_describe_request(models, name="app", vpc_id="vpc-xxxxxxxx"),
        module.build_create_request(models, params),
        module.build_entries_request(models, "acl-xxxxxxxx", rules, []),
        module.build_subnets_request(models, models.AssociateNetworkAclSubnetsRequest, "acl-xxxxxxxx", ["subnet-xxxxxxxx"]),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "network ACL request %s" % index))
    assert errors == []


def test_vpc_flow_log():
    module = _import_plugin("vpc_flow_log")
    models = _models("vpc.v20170312")
    params = {
        "name": "eni-flow",
        "vpc_id": "vpc-xxxxxxxx",
        "resource_type": "NETWORKINTERFACE",
        "resource_id": "eni-xxxxxxxx",
        "traffic_type": "ALL",
        "cls_topic_id": "topic-xxxxxxxx",
        "description": "audit",
        "cls_region": "ap-guangzhou",
        "period": None,
        "tags": {"env": "prod"},
    }
    requests = [
        module.build_describe_request(models, params["vpc_id"], name=params["name"]),
        module.build_create_request(models, params),
        module.build_update_request(models, "fl-xxxxxxxx", params),
        module.build_toggle_request(models, True, "fl-xxxxxxxx"),
        module.build_toggle_request(models, False, "fl-xxxxxxxx"),
        module.build_delete_request(models, params["vpc_id"], "fl-xxxxxxxx"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "flow log request %s" % index))
    assert errors == []


def test_ccn():
    module = _import_plugin("ccn")
    models = _models("vpc.v20170312")
    params = {
        "name": "backbone",
        "description": "prod",
        "qos_level": "AU",
        "instance_charge_type": "POSTPAID",
        "bandwidth_limit_type": "OUTER_REGION_LIMIT",
        "route_ecmp": True,
        "route_overlap": False,
        "traffic_marking_policy": True,
        "tags": {"env": "prod"},
    }
    requests = [
        module.build_describe_request(models, "ccn-xxxxxxxx"),
        module.build_describe_request(models, name="backbone"),
        module.build_create_request(models, params),
        module.build_update_request(models, "ccn-xxxxxxxx", params),
        module.build_delete_request(models, "ccn-xxxxxxxx"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "CCN request %s" % index))
    assert errors == []


def test_ccn_attachment():
    module = _import_plugin("ccn_attachment")
    models = _models("vpc.v20170312")
    params = {
        "ccn_id": "ccn-xxxxxxxx",
        "instance_id": "vpc-xxxxxxxx",
        "instance_region": "ap-guangzhou",
        "instance_type": "VPC",
        "description": "prod",
        "route_table_id": None,
    }
    requests = [module.build_describe_request(models, params["ccn_id"])]
    for operation in (models.AttachCcnInstancesRequest, models.DetachCcnInstancesRequest, models.ModifyCcnAttachedInstancesAttributeRequest):
        requests.append(module.build_mutation_request(models, params, operation))
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "CCN attachment request %s" % index))
    assert errors == []


def test_cls_logset():
    module = _import_plugin("cls_logset")
    models = _models("cls.v20201016")
    requests = [
        module.build_describe_request(models, "logset-xxxxxxxx"),
        module.build_create_request(models, "prod", {"env": "prod"}),
        module.build_update_request(models, "logset-xxxxxxxx", "prod-v2", {"env": "prod"}),
        module.build_delete_request(models, "logset-xxxxxxxx"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "CLS logset request %s" % index))
    assert errors == []


def test_cls_topic():
    module = _import_plugin("cls_topic")
    models = _models("cls.v20201016")
    params = {
        "logset_id": "logset-x",
        "name": "network",
        "partition_count": 2,
        "period": 30,
        "hot_period": 7,
        "storage_type": "hot",
        "auto_split": True,
        "max_split_partitions": 50,
        "description": "flow",
        "tags": {"env": "prod"},
    }
    requests = [
        module.build_describe_request(models, logset_id=params["logset_id"], name=params["name"]),
        module.build_create_request(models, params),
        module.build_update_request(models, "topic-x", params),
        module.build_delete_request(models, "topic-x"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "CLS topic request %s" % index))
    assert errors == []


def test_privatelink_endpoint_service():
    module = _import_plugin("privatelink_endpoint_service")
    models = _models("vpc.v20170312")
    params = {
        "name": "api",
        "vpc_id": "vpc-x",
        "service_instance_id": "lb-x",
        "service_type": "CLB",
        "auto_accept": True,
        "ip_address_type": "IPv4",
        "tags": {"env": "prod"},
    }
    requests = [
        module.build_describe_request(models, "vpcsvc-x"),
        module.build_create_request(models, params),
        module.build_update_request(models, "vpcsvc-x", params),
        module.build_delete_request(models, "vpcsvc-x", "IPv4"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "PrivateLink service request %s" % index))
    assert errors == []


def test_privatelink_endpoint():
    module = _import_plugin("privatelink_endpoint")
    models = _models("vpc.v20170312")
    params = {
        "name": "api-client",
        "vpc_id": "vpc-x",
        "subnet_id": "subnet-x",
        "endpoint_service_id": "vpcsvc-x",
        "endpoint_vip": None,
        "security_group_ids": ["sg-x"],
        "ip_address_type": "IPv4",
        "tags": {"env": "prod"},
    }
    requests = [
        module.build_describe_request(models, "vpce-x"),
        module.build_create_request(models, params),
        module.build_update_request(models, "vpce-x", params),
        module.build_delete_request(models, "vpce-x", "IPv4"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "PrivateLink endpoint request %s" % index))
    assert errors == []


def test_postgresql_account():
    module = _import_plugin("postgresql_account")
    models = _models("postgres.v20170312")
    params = {"instance_id": "postgres-x", "username": "app", "password": "secret", "account_type": "normal", "remark": "application", "cam_auth": False}
    requests = [
        module.build_describe_request(models, params["instance_id"]),
        module.build_create_request(models, params),
        module.build_remark_request(models, params["instance_id"], params["username"], params["remark"]),
        module.build_password_request(models, params["instance_id"], params["username"], params["password"]),
        module.build_delete_request(models, params["instance_id"], params["username"]),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "PostgreSQL account request %s" % index))
    assert errors == []


def test_cynosdb_account():
    module = _import_plugin("cynosdb_account")
    models = _models("cynosdb.v20190107")
    params = {
        "cluster_id": "cynosdbmysql-x",
        "account_name": "app",
        "host": "%",
        "password": "secret",
        "description": "application",
        "max_user_connections": 100,
        "password_rotation": 90,
    }
    requests = [
        module.build_describe_request(models, params["cluster_id"], params["account_name"], params["host"]),
        module.build_create_request(models, params),
        module.build_description_request(models, params),
        module.build_password_request(models, params),
        module.build_delete_request(models, params),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "CynosDB account request %s" % index))
    assert errors == []


def test_cynosdb_backup_config():
    module = _import_plugin("cynosdb_backup_config"); models = _models("cynosdb.v20190107")
    p = {"cluster_id": "cynosdbmysql-x", "backup_start": 10800, "backup_end": 14400, "retention_seconds": 2592000}
    errors = audit_request(module.describe_request(models, p["cluster_id"]), "CynosDB backup describe")
    errors.extend(audit_request(module.update_request(models, p), "CynosDB backup update"))
    assert errors == []


def test_api_gateway_service():
    module = _import_plugin("api_gateway_service")
    models = _models("apigateway.v20180808")
    params = {
        "name": "orders",
        "description": "order APIs",
        "protocol": "http&https",
        "network_types": ["OUTER"],
        "ip_version": "IPv4",
        "vpc_id": None,
        "instance_id": None,
        "tags": {"env": "prod"},
    }
    requests = [
        module.build_list_request(models, params["name"]),
        module.build_get_request(models, "service-x"),
        module.build_create_request(models, params),
        module.build_update_request(models, "service-x", params),
        module.build_delete_request(models, "service-x"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "API Gateway service request %s" % index))
    assert errors == []


def _api_gateway_resource_family_requests():
    models = _models("apigateway.v20180808")
    release = _import_plugin("api_gateway_service_release")
    usage = _import_plugin("api_gateway_usage_plan")
    binding = _import_plugin("api_gateway_usage_plan_binding")
    release_params = {"service_id": "service-x", "environment": "release", "description": "production"}
    usage_params = {"name": "clients", "description": "production clients", "qps": 100, "max_request_num": 1000000}
    binding_params = {"usage_plan_id": "usagePlan-x", "service_id": "service-x", "environment": "release", "api_id": "api-x"}
    requests = [
        release.build_describe(models, "service-x"),
        release.build_release(models, release_params),
        release.build_unrelease(models, release_params),
        usage.build_get(models, "usagePlan-x"),
        usage.build_list(models, "clients"),
        usage.build_create(models, usage_params),
        usage.build_update(models, usage_params, "usagePlan-x"),
        usage.build_delete(models, "usagePlan-x"),
        binding.build_describe(models, "usagePlan-x"),
        binding.build_change(models, binding_params),
        binding.build_change(models, binding_params, unbind=True),
    ]
    return requests


def _audit_api_gateway_resource_family():
    errors = []
    requests = _api_gateway_resource_family_requests()
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "API Gateway resource-family request %s" % index))
    assert errors == []


def test_api_gateway_service_release():
    _audit_api_gateway_resource_family()


def test_api_gateway_usage_plan():
    _audit_api_gateway_resource_family()


def test_api_gateway_usage_plan_binding():
    _audit_api_gateway_resource_family()


def test_cls_config():
    module = _import_plugin("cls_config")
    models = _models("cls.v20201016")
    params = {"name": "nginx", "topic_id": "topic-x", "path": "/var/log/nginx/access.log", "log_type": "minimalist_log", "extract_rule": None, "exclude_paths": [], "user_define_rule": None, "advanced_config": None, "input_type": None}
    requests = [module.build_describe(models, "nginx"), module.build_create(models, params), module.build_update(models, params, "config-x"), module.build_delete(models, "config-x")]
    errors = []
    for index, request in enumerate(requests): errors.extend(audit_request(request, "CLS config request %s" % index))
    assert errors == []


def test_cls_config_machine_group_binding():
    module = _import_plugin("cls_config_machine_group_binding")
    models = _models("cls.v20201016")
    requests = [module.build_describe(models, "group-x"), module.build_apply(models, "config-x", "group-x"), module.build_remove(models, "config-x", "group-x")]
    errors = []
    for index, request in enumerate(requests): errors.extend(audit_request(request, "CLS config binding request %s" % index))
    assert errors == []


def test_api_gateway_api_key():
    module = _import_plugin("api_gateway_api_key"); models = _models("apigateway.v20180808")
    params = {"name": "client", "key_type": "manual", "access_key_id": "AKIDexample", "access_key_secret": "secret_example"}
    requests = [module.build_get(models, "AKIDexample"), module.build_list(models, "client"), module.build_create(models, params), module.build_update(models, "AKIDexample", "secret_example"), module.build_delete(models, "AKIDexample")]
    errors = []
    for index, request in enumerate(requests): errors.extend(audit_request(request, "API Gateway API key request %s" % index))
    assert errors == []


def test_api_gateway_usage_plan_key_binding():
    module = _import_plugin("api_gateway_usage_plan_key_binding"); models = _models("apigateway.v20180808")
    requests = [module.build_describe(models, "usagePlan-x"), module.build_bind(models, "usagePlan-x", "AKIDexample"), module.build_unbind(models, "usagePlan-x", "AKIDexample")]
    errors = []
    for index, request in enumerate(requests): errors.extend(audit_request(request, "API Gateway key binding request %s" % index))
    assert errors == []


def test_tke_cluster_endpoint():
    module = _import_plugin("tke_cluster_endpoint"); models = _models("tke.v20180525")
    params = {"cluster_id": "cls-x", "access": "public", "subnet_id": None, "domain": None, "security_group_id": "sg-x", "load_balancer_id": None, "extensive_parameters": {"InternetAccessible": {"InternetChargeType": "TRAFFIC_POSTPAID_BY_HOUR", "InternetMaxBandwidthOut": 10}}}
    requests = [module.build_describe(models, "cls-x"), module.build_status(models, "cls-x", True), module.build_create(models, params), module.build_delete(models, params)]
    errors = []
    for index, request in enumerate(requests): errors.extend(audit_request(request, "TKE endpoint request %s" % index))
    assert errors == []


def test_tke_cluster_authentication():
    module = _import_plugin("tke_cluster_authentication"); models = _models("tke.v20180525")
    params = {"cluster_id": "cls-x", "service_accounts": {"UseTKEDefault": True, "AutoCreateDiscoveryAnonymousAuth": True}, "oidc": {"AutoCreateOIDCConfig": True, "AutoCreateClientId": ["kubernetes"], "AutoInstallPodIdentityWebhookAddon": True}}
    requests = [module.build_describe(models, "cls-x"), module.build_modify(models, params)]
    errors = []
    for index, request in enumerate(requests): errors.extend(audit_request(request, "TKE authentication request %s" % index))
    assert errors == []


def test_tke_cluster_audit():
    module = _import_plugin("tke_cluster_audit"); models = _models("tke.v20180525")
    params = {"cluster_id": "cls-x", "logset_id": "logset-x", "topic_id": "topic-x", "topic_region": "ap-guangzhou", "delete_logset_and_topic": False}
    requests = [module.build_describe(models, "cls-x"), module.build_enable(models, params), module.build_disable(models, params)]
    errors = []
    for index, request in enumerate(requests): errors.extend(audit_request(request, "TKE audit request %s" % index))
    assert errors == []


def test_waf_host():
    module = _import_plugin("waf_host"); models = _models("waf.v20180125")
    params = {"instance_id": "waf-x", "domain": "api.example.com", "domain_id": "domain-x", "host": {"Domain": "api.example.com", "Edition": "clb-waf", "Region": "ap-guangzhou", "LoadBalancerSet": [], "FlowMode": 1}, "tags": {"env": "prod"}}
    requests = [module.build_get(models, params), module.build_create(models, params), module.build_update(models, params), module.build_delete(models, params)]
    errors = []
    for index, request in enumerate(requests): errors.extend(audit_request(request, "WAF host request %s" % index))
    assert errors == []


def test_waf_custom_rule():
    module = _import_plugin("waf_custom_rule"); models = _models("waf.v20180125")
    params = {"domain": "api.example.com", "name": "block-admin", "edition": "sparta-waf", "priority": 10, "action": "1", "strategies": [{"Field": "URI", "CompareFunc": "contains", "Content": "/admin", "CaseNotSensitive": 1}], "logical_operator": "and", "redirect": "", "expire_time": 0, "action_ratio": 100}
    requests = [module.build_list(models, params), module.build_create(models, params), module.build_update(models, params, 123), module.build_delete(models, params, 123)]
    errors = []
    for index, request in enumerate(requests): errors.extend(audit_request(request, "WAF custom rule request %s" % index))
    assert errors == []


def test_monitor_prometheus_scrape_job():
    module = _import_plugin("monitor_prometheus_scrape_job"); models = _models("monitor.v20180724")
    params = {"instance_id": "prom-x", "agent_id": "agent-x", "job_id": "job-x", "name": "application", "config": "job_name: application"}
    requests = [module.build_describe(models, params), module.build_create(models, params), module.build_update(models, params, "job-x"), module.build_delete(models, params, "job-x")]
    errors = []
    for index, request in enumerate(requests): errors.extend(audit_request(request, "Prometheus scrape-job request %s" % index))
    assert errors == []


def test_monitor_prometheus_record_rule():
    module = _import_plugin("monitor_prometheus_record_rule"); models = _models("monitor.v20180724")
    params = {"instance_id": "prom-x", "name": "rollups", "content": "groups: []"}
    requests = [module.build_describe(models, "prom-x", "rollups"), module.build_create(models, params), module.build_update(models, params), module.build_delete(models, params)]
    errors = []
    for index, request in enumerate(requests): errors.extend(audit_request(request, "Prometheus record-rule request %s" % index))
    assert errors == []


def test_monitor_prometheus_alert_group():
    module = _import_plugin("monitor_prometheus_alert_group"); models = _models("monitor.v20180724")
    params = {"instance_id": "prom-x", "group_id": "alert-x", "name": "application", "enabled": True, "receivers": ["notice-x"], "custom_receiver": None, "repeat_interval": "1h", "rules": [{"RuleName": "high-errors", "Expr": "rate(errors_total[5m]) > 1", "Duration": "5m", "State": 2}]}
    requests = [module.build_describe(models, params), module.build_create(models, params), module.build_update(models, params, "alert-x"), module.build_delete(models, "prom-x", "alert-x")]
    errors = []
    for index, request in enumerate(requests): errors.extend(audit_request(request, "Prometheus alert-group request %s" % index))
    assert errors == []


def _monitor_platform_requests(name):
    models = _models("monitor.v20180724"); module = _import_plugin(name)
    if name == "monitor_prometheus_instance":
        p={"name":"prod","vpc_id":"vpc-x","subnet_id":"subnet-x","zone":"ap-guangzhou-3","retention_days":30,"grafana_instance_id":None,"tags":{"env":"prod"},"instance_attributes":{}}
        return [module.build_describe(models,"prom-x","prod"),module.build_create(models,p),module.build_update(models,p,"prom-x"),module.build_delete(models,"prom-x")]
    if name == "monitor_prometheus_cluster_agent":
        p={"instance_id":"prom-x","cluster_id":"cls-x","cluster_type":"tke","region":"ap-guangzhou","agent":{}}
        return [module.build_describe(models,p),module.build_create(models,p),module.build_delete(models,p)]
    if name == "monitor_grafana_instance":
        p={"name":"grafana","vpc_id":"vpc-x","subnet_ids":["subnet-x"],"enable_internet":False,"initial_password":None,"tags":{"env":"prod"}}
        return [module.build_describe(models,"grafana-x","grafana"),module.build_create(models,p),module.build_update(models,"grafana-x","grafana"),module.build_delete(models,"grafana-x")]
    if name == "monitor_prometheus_grafana_binding":
        return [module.build_describe(models,"prom-x"),module.build_bind(models,"prom-x","grafana-x"),module.build_unbind(models,"prom-x","grafana-x")]
    p={"instance_id":"grafana-x","integration_id":"integration-x","kind":"tencent-cloud-prometheus","content":"{}"}
    return [module.build_describe(models,p),module.build_create(models,p),module.build_update(models,p,"integration-x"),module.build_delete(models,p,"integration-x")]


def _audit_monitor_platform(name):
    errors=[]
    for index,request in enumerate(_monitor_platform_requests(name)): errors.extend(audit_request(request,"%s request %s"%(name,index)))
    assert errors==[]


def test_monitor_prometheus_instance(): _audit_monitor_platform("monitor_prometheus_instance")
def test_monitor_prometheus_cluster_agent(): _audit_monitor_platform("monitor_prometheus_cluster_agent")
def test_monitor_grafana_instance(): _audit_monitor_platform("monitor_grafana_instance")
def test_monitor_prometheus_grafana_binding(): _audit_monitor_platform("monitor_prometheus_grafana_binding")
def test_monitor_grafana_integration(): _audit_monitor_platform("monitor_grafana_integration")


def test_monitor_grafana_whitelist():
    module=_import_plugin("monitor_grafana_whitelist"); models=_models("monitor.v20180724")
    errors=[]
    for index,request in enumerate([module.build_describe(models,"grafana-x"),module.build_update(models,"grafana-x",["203.0.113.10/32"])]): errors.extend(audit_request(request,"Grafana whitelist request %s"%index))
    assert errors==[]


def test_monitor_grafana_internet():
    module=_import_plugin("monitor_grafana_internet"); models=_models("monitor.v20180724")
    errors=[]
    for index,request in enumerate([module.build_describe(models,"grafana-x"),module.build_update(models,"grafana-x",True)]): errors.extend(audit_request(request,"Grafana internet request %s"%index))
    assert errors==[]


def test_monitor_notification_controls():
    models=_models("monitor.v20180724"); requests=[]
    channel=_import_plugin("monitor_grafana_notification_channel"); p={"instance_id":"grafana-x","channel_id":"nchannel-x","name":"ops","receivers":["notice-x"],"organization_ids":["1"]}
    requests += [channel.build_describe(models,p),channel.build_create(models,p),channel.build_update(models,p,"nchannel-x"),channel.build_delete(models,p,"nchannel-x")]
    notification=_import_plugin("monitor_prometheus_global_notification"); value={"Enabled":True,"Type":"amp","RepeatInterval":"1h","ReceiverGroups":["notice-x"]}
    requests += [notification.build_describe(models,"prom-x"),notification.build_update(models,"prom-x",value)]
    alertmanager=_import_plugin("monitor_prometheus_alertmanager_config"); config={"InhibitRules":[]}
    requests += [alertmanager.build_describe(models,"prom-x"),alertmanager.build_update(models,"prom-x",config)]
    errors=[]
    for index,request in enumerate(requests): errors.extend(audit_request(request,"Monitor notification request %s"%index))
    assert errors==[]


def test_monitor_grafana_notification_channel(): test_monitor_notification_controls()
def test_monitor_prometheus_global_notification(): test_monitor_notification_controls()
def test_monitor_prometheus_alertmanager_config(): test_monitor_notification_controls()


def test_cdb_backup_config():
    module=_import_plugin("cdb_backup_config"); models=_models("cdb.v20170320"); p={"instance_id":"cdb-x","expire_days":30,"start_time":"03:00","backup_method":"physical","binlog_expire_days":7,"backup_time_window":"03:00-04:00"}
    errors=[]
    for i,r in enumerate([module.build_describe(models,"cdb-x"),module.build_update(models,p)]): errors.extend(audit_request(r,"CDB backup request %s"%i))
    assert errors==[]


def test_redis_backup_config():
    module=_import_plugin("redis_backup_config"); models=_models("redis.v20180412"); p={"instance_id":"crs-x","week_days":["Monday"],"time_period":"03:00-04:00","backup_type":0,"storage_days":30}
    errors=[]
    for i,r in enumerate([module.build_describe(models,"crs-x"),module.build_update(models,p)]): errors.extend(audit_request(r,"Redis backup request %s"%i))
    assert errors==[]


def test_redis_account():
    module=_import_plugin("redis_account"); models=_models("redis.v20180412"); p={"instance_id":"crs-x","name":"app","password":"Password_123","privilege":"rw","readonly_policy":["master"],"remark":"app","encrypt_password":False}
    requests=[module.build_describe(models,"crs-x"),module.build_create(models,p),module.build_update(models,p,True),module.build_delete(models,p)]
    errors=[]
    for i,r in enumerate(requests): errors.extend(audit_request(r,"Redis account request %s"%i))
    assert errors==[]


def test_postgresql_backup_plan():
    module=_import_plugin("postgresql_backup_plan"); models=_models("postgres.v20170312"); p={"instance_id":"postgres-x","name":"prod","period_type":"week","periods":["monday"],"min_start_time":"03:00:00","max_start_time":"04:00:00","retention_days":30,"log_retention_days":7}
    requests=[module.build_describe(models,"postgres-x"),module.build_create(models,p),module.build_update(models,p,"plan-x"),module.build_delete(models,"postgres-x","plan-x")]
    errors=[]
    for i,r in enumerate(requests): errors.extend(audit_request(r,"PostgreSQL backup-plan request %s"%i))
    assert errors==[]


def test_waf_ip_access_control():
    module = _import_plugin("waf_ip_access_control")
    models = _models("waf.v20180125")
    params = {
        "rule_id": 123,
        "domain": "api.example.com",
        "action": "block",
        "ip_list": ["203.0.113.0/24"],
        "note": "abuse",
        "valid_until": 0,
        "instance_id": "waf-x",
        "edition": "sparta-waf",
    }
    requests = [
        module.build_describe_request(models, params),
        module.build_create_request(models, params),
        module.build_update_request(models, params),
        module.build_delete_request(models, params),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "WAF IP rule request %s" % index))
    assert errors == []


def test_waf_protect_group():
    module = _import_plugin("waf_protect_group")
    models = _models("waf.v20180125")
    p = {"group_id": 123, "name": "production-apps", "domains": ["api.example.com"], "remark": "apps"}
    requests = [module.describe_request(models, p), module.create_request(models, p), module.update_request(models, p, 123), module.delete_request(models, 123)]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "WAF protect group request %s" % index))
    assert errors == []


def test_cls_shipper():
    module = _import_plugin("cls_shipper")
    models = _models("cls.v20201016")
    p = {"shipper_id": "shipper-x", "topic_id": "topic-x", "name": "archive", "bucket": "logs-1250000000", "prefix": "cls/", "enabled": True, "interval": 300, "max_size": 256, "partition": "%Y/%m/%d/%H", "compress": {"Format": "gzip"}, "content": {"Format": "json"}, "filter_rules": [], "filename_mode": 0, "storage_type": "STANDARD", "role_arn": None, "external_id": None, "time_zone": "UTC+08:00", "dsl_filter": ""}
    requests = [module.describe_request(models, p), module.create_request(models, p), module.update_request(models, p, p["shipper_id"]), module.delete_request(models, p["shipper_id"])]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "CLS shipper request %s" % index))
    assert errors == []


def test_tke_backup_storage_location():
    module = _import_plugin("tke_backup_storage_location")
    models = _models("tke.v20180525")
    p = {"name": "production-backups", "storage_region": "ap-guangzhou", "bucket": "tke-backup-1250000000", "provider": "tencentcloud", "path": "production/"}
    requests = [module.describe_request(models, p["name"]), module.create_request(models, p), module.delete_request(models, p["name"])]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "TKE backup storage location request %s" % index))
    assert errors == []


def test_tdmq_topic():
    module = _import_plugin("tdmq_topic")
    models = _models("tdmq.v20200217")
    params = {
        "cluster_id": "pulsar-x",
        "environment_id": "prod",
        "name": "orders",
        "partitions": 4,
        "topic_type": 3,
        "remark": "orders",
        "message_ttl": 86400,
        "isolate_consumer": True,
        "ack_timeout": 120,
        "delay_message_policy": "defaultPolicy",
    }
    requests = [
        module.build_describe_request(models, "pulsar-x", "prod", "orders"),
        module.build_create_request(models, params),
        module.build_update_request(models, params),
        module.build_delete_request(models, "pulsar-x", "prod", "orders", True),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "TDMQ topic request %s" % index))
    assert errors == []


def test_teo_dns_record():
    module = _import_plugin("teo_dns_record")
    models = _models("teo.v20220901")
    params = {
        "zone_id": "zone-x",
        "name": "api.example.com",
        "record_type": "A",
        "content": "203.0.113.10",
        "location": "Default",
        "ttl": 300,
        "weight": -1,
        "priority": 0,
    }
    requests = [
        module.build_describe_request(models, "zone-x", name="api.example.com"),
        module.build_create_request(models, params),
        module.build_update_request(models, "record-x", params),
        module.build_delete_request(models, "zone-x", "record-x"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "TEO DNS record request %s" % index))
    assert errors == []


def test_cfw_address_template():
    module = _import_plugin("cfw_address_template")
    models = _models("cfw.v20190904")
    params = {"name": "trusted", "description": "internal", "addresses": ["10.0.0.0/8"], "template_type": "ip", "ip_version": 0}
    requests = [
        module.build_describe_request(models, name="trusted"),
        module.build_create_request(models, params),
        module.build_update_request(models, "uuid-x", params),
        module.build_delete_request(models, "uuid-x"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "CFW address template request %s" % index))
    assert errors == []


def test_cloudaudit_track():
    module = _import_plugin("cloudaudit_track")
    models = _models("cloudaudit.v20190319")
    params = {
        "name": "events",
        "enabled": True,
        "action_type": "*",
        "resource_type": "*",
        "event_names": ["*"],
        "track_all_members": False,
        "storage_type": "cls",
        "storage_region": "ap-guangzhou",
        "storage_name": "topic-x",
        "storage_prefix": "",
        "storage_account_id": None,
        "storage_app_id": None,
        "compress": True,
    }
    requests = [
        module.build_list_request(models),
        module.build_describe_request(models, 12),
        module.build_create_request(models, params),
        module.build_update_request(models, 12, params),
        module.build_delete_request(models, 12),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "CloudAudit track request %s" % index))
    assert errors == []


def test_config_rule():
    module = _import_plugin("config_rule")
    models = _models("config.v20220802")
    params = {
        "name": "encrypted-disks",
        "identifier": "CBS_DISK_ENCRYPTED",
        "identifier_type": "SYSTEM",
        "resource_types": ["QCS::CBS::Disk"],
        "triggers": [{"message_type": "ConfigurationItemChangeNotification", "maximum_execution_frequency": None}],
        "risk_level": 1,
        "input_parameters": {"required": "true"},
        "description": "Encrypted disks",
        "regions": ["ap-guangzhou"],
        "tags": {"env": "prod"},
        "excluded_resource_ids": [],
    }
    requests = [
        module.build_list_request(models, params["name"]),
        module.build_describe_request(models, "rule-x"),
        module.build_create_request(models, params),
        module.build_update_request(models, "rule-x", params),
        module.build_delete_request(models, "rule-x"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "Config rule request %s" % index))
    assert errors == []


def test_organization_node():
    module = _import_plugin("organization_node")
    models = _models("organization.v20210331")
    params = {"parent_node_id": 1001, "name": "Production", "remark": "Production units", "tags": {"env": "prod"}}
    requests = [
        module.build_describe_request(models),
        module.build_create_request(models, params),
        module.build_update_request(models, 1002, params),
        module.build_delete_request(models, 1002),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "Organization node request %s" % index))
    assert errors == []


def test_tat_command():
    module = _import_plugin("tat_command")
    models = _models("tat.v20201028")
    params = {
        "name": "hello",
        "content": "#!/bin/bash\necho {{word}}",
        "description": "hello",
        "command_type": "SHELL",
        "working_directory": "/root",
        "timeout": 60,
        "enable_parameters": True,
        "default_parameters": {"word": "hello"},
        "username": "root",
        "output_cos_bucket_url": None,
        "output_cos_key_prefix": None,
        "tags": {"env": "prod"},
    }
    requests = [
        module.build_describe_request(models, name="hello"),
        module.build_create_request(models, params),
        module.build_update_request(models, "cmd-x", params),
        module.build_delete_request(models, "cmd-x"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "TAT command request %s" % index))
    assert errors == []


def test_as_scaling_group():
    module = _import_plugin("as_scaling_group")
    models = _models("autoscaling.v20180419")
    params = {
        "name": "web",
        "launch_configuration_id": "asc-x",
        "vpc_id": "vpc-x",
        "subnet_ids": ["subnet-a"],
        "min_size": 0,
        "max_size": 10,
        "desired_capacity": 0,
        "default_cooldown": 300,
        "termination_policy": "OLDEST_INSTANCE",
        "retry_policy": "IMMEDIATE_RETRY",
        "subnet_policy": "PRIORITY",
        "health_check_type": "CVM",
        "capacity_rebalance": False,
        "project_id": 0,
    }
    requests = [
        module.build_describe_request(models, name="web"),
        module.build_create_request(models, params),
        module.build_update_request(models, "asg-x", params),
        module.build_delete_request(models, "asg-x"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "Auto Scaling group request %s" % index))
    assert errors == []


def test_dts_consumer_group():
    module = _import_plugin("dts_consumer_group")
    models = _models("dts.v20211206")
    params = {"subscribe_id": "subs-x", "consumer_group_name": "analytics", "account_name": "reader", "password": "secret", "description": "analytics"}
    requests = [
        module.build_describe_request(models, "subs-x"),
        module.build_create_request(models, params),
        module.build_update_request(models, "subs-x", "consumer-full", "account-full", "new"),
        module.build_delete_request(models, "subs-x", "consumer-full", "account-full"),
    ]
    errors = []
    for index, request in enumerate(requests):
        errors.extend(audit_request(request, "DTS consumer group request %s" % index))
    assert errors == []


def test_dbbrain_sql_filter():
    module = _import_plugin("dbbrain_sql_filter")
    models = _models("dbbrain.v20210527")
    params = {
        "instance_id": "cdb-x",
        "sql_type": "SELECT",
        "filter_key": "select,user",
        "max_concurrency": 2,
        "duration": -1,
        "session_token": "token",
        "product": "mysql",
    }
    requests = [module.build_describe_request(models, params), module.build_create_request(models, params), module.build_delete_request(models, params, [1])]
    assert [error for index, request in enumerate(requests) for error in audit_request(request, "DBbrain SQL filter request %s" % index)] == []


def test_cmq_queue():
    module = _import_plugin("cmq_queue")
    models = _models("tdmq.v20200217")
    params = {
        "queue_name": "jobs",
        "max_msg_heap_num": 10000000,
        "polling_wait_seconds": 10,
        "visibility_timeout": 30,
        "max_msg_size": 1048576,
        "msg_retention_seconds": 3600,
        "rewind_seconds": 0,
    }
    requests = [
        module.build_describe_request(models, "jobs"),
        module.build_create_request(models, params),
        module.build_update_request(models, params),
        module.build_delete_request(models, "jobs"),
    ]
    assert [error for index, request in enumerate(requests) for error in audit_request(request, "CMQ queue request %s" % index)] == []


def test_tcr_replication_instance():
    module = _import_plugin("tcr_replication_instance")
    models = _models("tcr.v20190924")
    params = {"registry_id": "tcr-x", "replication_region_id": 1, "replication_region_name": "ap-shanghai", "sync_tag": False}
    requests = [
        module.build_describe_request(models, "tcr-x"),
        module.build_create_request(models, params),
        module.build_delete_request(models, "tcr-x", "tcr-y", 1),
    ]
    assert [error for index, request in enumerate(requests) for error in audit_request(request, "TCR replication request %s" % index)] == []


def test_cvm_chc():
    module = _import_plugin("cvm_chc")
    models = _models("cvm.v20170312")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "chc-xxxxxxxx", None), "chc describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "chc-prod-01"), "chc describe by name"))
    module._configure_vpc(
        fake,
        client,
        models,
        "chc-xxxxxxxx",
        {
            "bmc_vpc_id": "vpc-aaaaaaaa",
            "bmc_subnet_id": "subnet-aaaaaaaa",
            "bmc_security_group_ids": ["sg-xxxxxxxx"],
            "deploy_vpc_id": "vpc-bbbbbbbb",
            "deploy_subnet_id": "subnet-bbbbbbbb",
            "deploy_security_group_ids": ["sg-yyyyyyyy"],
        },
    )
    module._rename(fake, client, models, "chc-xxxxxxxx", "chc-prod-01")
    module._remove_assist(fake, client, models, "chc-xxxxxxxx")
    module._remove_deploy(fake, client, models, "chc-xxxxxxxx")
    module._set_network_mode(fake, client, models, "chc-xxxxxxxx", "BUSINESS")
    errors.extend(audit_recorded(fake, "cvm_chc"))
    assert errors == []


def test_mongodb_instance():
    module = _import_plugin("mongodb_instance")
    models = _models("mongodb.v20190725")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "cmgo-xxxxxxxx", None), "mongodb describe by id"))
    errors.extend(audit_request(module.build_describe_request(models, None, "prod-mongo"), "mongodb describe by name"))
    errors.extend(
        audit_request(
            module.build_create_request(
                models,
                {
                    "name": "prod-mongo",
                    "memory": 8,
                    "volume": 100,
                    "mongo_version": "5.0",
                    "zone": "ap-guangzhou-3",
                    "cluster_type": "REPLSET",
                    "node_num": 3,
                    "replicate_set_num": None,
                    "password": "secret",
                    "vpc_id": "vpc-xxxxxxxx",
                    "subnet_id": "subnet-xxxxxxxx",
                    "project_id": None,
                    "period_months": 1,
                    "auto_renew": None,
                    "security_group": None,
                    "tags": {"env": "prod"},
                },
            ),
            "mongodb create request",
        )
    )
    module._create(
        fake,
        client,
        models,
        {
            "name": "prod-mongo",
            "memory": 8,
            "volume": 100,
            "mongo_version": "5.0",
            "zone": "ap-guangzhou-3",
            "cluster_type": "REPLSET",
            "node_num": 3,
            "replicate_set_num": None,
            "password": "secret",
            "vpc_id": "vpc-xxxxxxxx",
            "subnet_id": "subnet-xxxxxxxx",
            "project_id": None,
            "period_months": 1,
            "auto_renew": None,
            "security_group": None,
            "tags": {"env": "prod"},
        },
    )
    module._rename(fake, client, models, "cmgo-xxxxxxxx", "prod-mongo-v2")
    module._delete(fake, client, models, "cmgo-xxxxxxxx")
    errors.extend(audit_recorded(fake, "mongodb_instance"))
    assert errors == []


def test_gaap_proxy():
    module = _import_plugin("gaap_proxy")
    models = _models("gaap.v20180529")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "proxy-xxxxxxxx", None), "gaap describe by id"))
    errors.extend(
        audit_request(
            module.build_create_request(
                models,
                {
                    "name": "prod-gaap",
                    "access_region": "ap-guangzhou",
                    "real_server_region": "ap-hongkong",
                    "bandwidth": 20,
                    "concurrent": 2,
                    "project_id": None,
                    "billing_type": 0,
                    "network_type": "normal",
                    "ip_address_version": "IPv4",
                    "group_id": None,
                },
            ),
            "gaap create request",
        )
    )
    module._create(
        fake,
        client,
        models,
        {
            "name": "prod-gaap",
            "access_region": "ap-guangzhou",
            "real_server_region": "ap-hongkong",
            "bandwidth": 20,
            "concurrent": 2,
            "project_id": None,
            "billing_type": 0,
            "network_type": "normal",
            "ip_address_version": "IPv4",
            "group_id": None,
        },
    )
    module._rename(fake, client, models, "proxy-xxxxxxxx", "prod-gaap-v2")
    module._open(fake, client, models, "proxy-xxxxxxxx")
    module._close(fake, client, models, "proxy-xxxxxxxx")
    module._destroy(fake, client, models, "proxy-xxxxxxxx")
    errors.extend(audit_recorded(fake, "gaap_proxy"))
    assert errors == []


def test_cdn_domain():
    module = _import_plugin("cdn_domain")
    models = _models("cdn.v20180606")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "cdn.example.com"), "cdn describe by domain"))
    errors.extend(
        audit_request(
            module.build_add_request(
                models,
                {
                    "domain": "cdn.example.com",
                    "service_type": "web",
                    "origins": ["origin.example.com"],
                    "origin_type": "domain",
                    "origin_protocol": "http",
                    "backup_origins": None,
                    "project_id": None,
                    "area": None,
                },
            ),
            "cdn add request",
        )
    )
    module._add(
        fake,
        client,
        models,
        {
            "domain": "cdn.example.com",
            "service_type": "web",
            "origins": ["origin.example.com"],
            "origin_type": "domain",
            "origin_protocol": "http",
            "backup_origins": None,
            "project_id": None,
            "area": None,
        },
    )
    module._start(fake, client, models, "cdn.example.com")
    module._stop(fake, client, models, "cdn.example.com")
    module._delete(fake, client, models, "cdn.example.com")
    errors.extend(audit_recorded(fake, "cdn_domain"))
    assert errors == []


def test_tcr_instance():
    module = _import_plugin("tcr_instance")
    models = _models("tcr.v20190924")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "tcr-xxxxxxxx", None), "tcr describe by id"))
    errors.extend(
        audit_request(
            module.build_create_request(
                models,
                {
                    "name": "prod-registry",
                    "registry_type": "basic",
                    "deletion_protection": True,
                    "period_months": 12,
                    "auto_renew": 1,
                    "sync_tag": None,
                    "enable_cos_maz": None,
                    "tags": {"env": "prod"},
                },
            ),
            "tcr create request",
        )
    )
    module._create(
        fake,
        client,
        models,
        {
            "name": "prod-registry",
            "registry_type": "basic",
            "deletion_protection": True,
            "period_months": 12,
            "auto_renew": 1,
            "sync_tag": None,
            "enable_cos_maz": None,
            "tags": {"env": "prod"},
        },
    )
    module._update(fake, client, models, "tcr-xxxxxxxx", False)
    module._delete(fake, client, models, "tcr-xxxxxxxx", True)
    errors.extend(audit_recorded(fake, "tcr_instance"))
    assert errors == []


def test_tcr_namespace():
    module = _import_plugin("tcr_namespace")
    models = _models("tcr.v20190924")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "tcr-xxxxxxxx", "team-a"), "tcr namespace describe request"))
    params = {
        "registry_id": "tcr-xxxxxxxx",
        "name": "team-a",
        "is_public": False,
        "is_auto_scan": True,
        "is_prevent_vul": True,
        "severity": "high",
    }
    errors.extend(audit_request(module.build_create_request(models, params), "tcr namespace create request"))
    module._update(fake, client, models, params)
    module._delete(fake, client, models, "tcr-xxxxxxxx", "team-a")
    errors.extend(audit_recorded(fake, "tcr_namespace"))
    assert errors == []


def _audit_p1_resource_request_builders():
    cases = [
        (
            "tcr_repository",
            "tcr.v20190924",
            "build_create_request",
            {
                "registry_id": "tcr-xxxxxxxx",
                "namespace": "prod",
                "name": "api",
                "brief_description": "API",
                "description": "Production API",
            },
        ),
        (
            "kms_key",
            "kms.v20190118",
            "build_create_request",
            {
                "alias": "production",
                "description": "Production key",
                "key_usage": "ENCRYPT_DECRYPT",
                "key_type": 1,
            },
        ),
        (
            "monitor_alarm_policy",
            "monitor.v20180724",
            "build_create_request",
            {
                "module": "monitor",
                "name": "cpu-high",
                "monitor_type": "MT_QCE",
                "namespace": "QCE/CVM",
                "remark": "",
                "enabled": True,
                "condition": None,
                "event_condition": None,
                "notice_ids": [],
            },
        ),
        (
            "tke_addon",
            "tke.v20180525",
            "build_install_request",
            {
                "cluster_id": "cls-xxxxxxxx",
                "name": "cbs",
                "version": "1.4.0",
                "values": {},
            },
        ),
    ]
    errors = []
    for module_name, service, builder_name, params in cases:
        module = _import_plugin(module_name)
        models = _models(service)
        errors.extend(
            audit_request(
                getattr(module, builder_name)(models, params),
                "%s request" % module_name,
            )
        )

    fake = _RecordingModule()
    client = _StubClient()
    _import_plugin("tcr_repository").find_repository(fake, client, _models("tcr.v20190924"), "tcr-xxxxxxxx", "prod", "api")
    _import_plugin("kms_key").describe_key(fake, client, _models("kms.v20190118"), "key-xxxxxxxx")
    kms = _import_plugin("kms_key")
    kms_models = _models("kms.v20190118")
    for request in (
        kms.build_list_key_request(kms_models, "production"),
        kms.build_rotation_request(kms_models, "key-xxxxxxxx", None, None),
        kms.build_rotation_request(kms_models, "key-xxxxxxxx", True, 90),
        kms.build_rotation_request(kms_models, "key-xxxxxxxx", False, None),
        kms.build_cancel_deletion_request(kms_models, "key-xxxxxxxx"),
    ):
        errors.extend(audit_request(request, "kms lifecycle request"))
    tke = _import_plugin("tke_addon")
    tke_models = _models("tke.v20180525")
    errors.extend(
        audit_request(
            tke.build_update_request(
                tke_models,
                {
                    "cluster_id": "cls-xxxxxxxx",
                    "name": "cbs",
                    "version": "1.5.0",
                    "values": {"replicaCount": 2},
                    "update_strategy": "replace",
                },
                {"AddonVersion": "1.4.0"},
            ),
            "tke addon update request",
        )
    )
    monitor = _import_plugin("monitor_alarm_policy")
    monitor_models = _models("monitor.v20180724")
    errors.extend(
        audit_request(
            monitor.build_condition_request(
                monitor_models,
                {
                    "module": "monitor",
                    "name": "cpu-high",
                    "condition": {"IsUnionRule": 0},
                    "event_condition": None,
                    "notice_ids": ["notice-1"],
                },
                "policy-xxxxxxxx",
            ),
            "monitor condition update request",
        )
    )
    monitor_params = {
        "module": "monitor",
        "notice_ids": ["notice-1"],
        "hierarchical_notices": [{"NoticeId": "notice-1", "Classification": ["warning"]}],
        "notice_content_template_bindings": [{"NoticeID": "notice-1", "ContentTmplID": "tmpl-1"}],
        "trigger_tasks": [{"Type": "AS", "TaskConfig": "{}"}],
    }
    errors.extend(
        audit_request(
            monitor.build_notice_request(monitor_models, monitor_params, "policy-xxxxxxxx"),
            "monitor notice update request",
        )
    )
    errors.extend(
        audit_request(
            monitor.build_tasks_request(monitor_models, monitor_params, "policy-xxxxxxxx"),
            "monitor tasks update request",
        )
    )
    _import_plugin("monitor_alarm_policy").find_policy(fake, client, _models("monitor.v20180724"), "policy-xxxxxxxx", None, "monitor")
    _import_plugin("tke_addon").describe_addon(fake, client, _models("tke.v20180525"), "cls-xxxxxxxx", "cbs")
    errors.extend(audit_recorded(fake, "P1 describe requests"))

    cam = _import_plugin("cam_policy_attachment")
    cam_models = _models("cam.v20190116")
    for target_type, target_id, target_name in (
        ("user", 1000000001, None),
        ("role", "1", "deploy"),
        ("group", 2, None),
    ):
        params = {
            "target_type": target_type,
            "target_id": target_id,
            "target_name": target_name,
            "policy_id": 123,
        }
        errors.extend(
            audit_request(
                cam.build_list_request(cam_models, params),
                "cam %s list request" % target_type,
            )
        )
        errors.extend(
            audit_request(
                cam.build_mutation_request(cam_models, params, True),
                "cam %s attach request" % target_type,
            )
        )
        errors.extend(
            audit_request(
                cam.build_mutation_request(cam_models, params, False),
                "cam %s detach request" % target_type,
            )
        )
    assert errors == []


def test_tcr_repository():
    _audit_p1_resource_request_builders()


def test_cam_policy_attachment():
    _audit_p1_resource_request_builders()


def test_cam_saml_provider():
    module = _import_plugin("cam_saml_provider"); models = _models("cam.v20190116")
    p = {"name": "corporate-idp", "description": "Corporate", "metadata_document": "PHhtbD48L3htbD4="}
    requests = [module.get_request(models, p["name"]), module.create_request(models, p), module.update_request(models, p), module.delete_request(models, p["name"])]
    errors = []
    for request in requests: errors.extend(audit_request(request, "CAM SAML provider request"))
    assert errors == []


def test_cam_oidc_provider():
    module = _import_plugin("cam_oidc_provider"); models = _models("cam.v20190116")
    p = {"name": "ci-workloads", "identity_url": "https://issuer.example.com", "client_ids": ["sts.tencentcloudapi.com"], "identity_key": "cHVibGljLWtleQ==", "description": "CI"}
    requests = [module.describe_request(models, p["name"]), module.create_request(models, p), module.update_request(models, p), module.delete_request(models, p["name"])]
    errors = []
    for request in requests: errors.extend(audit_request(request, "CAM OIDC provider request"))
    assert errors == []


def test_cam_group_membership():
    module = _import_plugin("cam_group_membership")
    models = _models("cam.v20190116")
    params = {"group_id": 7, "sub_uin": 1000000001, "uid": None}
    errors = []
    for request in (
        module.build_list_request(models, params),
        module.build_mutation_request(models, params, True),
        module.build_mutation_request(models, params, False),
    ):
        errors.extend(audit_request(request, "cam group membership request"))
    assert errors == []


def test_kms_key():
    _audit_p1_resource_request_builders()


def test_kms_key_rotation():
    module = _import_plugin("kms_key_rotation")
    models = _models("kms.v20190118")
    errors = []
    for request in (
        module.build_describe_request(models, "key-xxxxxxxx"),
        module.build_status_request(models, "key-xxxxxxxx"),
        module.build_update_request(models, "key-xxxxxxxx", True, 90),
        module.build_update_request(models, "key-xxxxxxxx", False, 90),
    ):
        errors.extend(audit_request(request, "kms rotation request"))
    assert errors == []


def test_monitor_alarm_policy():
    _audit_p1_resource_request_builders()


def test_monitor_alarm_policy_notice():
    module = _import_plugin("monitor_alarm_policy_notice")
    models = _models("monitor.v20180724")
    request = module.build_notice_request(
        models,
        {
            "module": "monitor",
            "notice_ids": ["notice-1"],
            "hierarchical_notices": [],
            "notice_content_template_bindings": [],
        },
        "policy-xxxxxxxx",
    )
    assert audit_request(request, "monitor notice request") == []


def test_private_dns_zone():
    module = _import_plugin("private_dns_zone")
    models = _models("privatedns.v20201028")
    params = {
        "domain": "internal.example.com",
        "remark": "internal",
        "vpcs": [{"region": "ap-guangzhou", "vpc_id": "vpc-xxxxxxxx"}],
        "tags": {"environment": "test"},
    }
    errors = audit_request(module.build_create_request(models, params), "private DNS zone create")
    for item in module.build_vpcs(models, params["vpcs"]):
        errors.extend(audit_request(item, "private DNS VPC"))
    fake = _RecordingModule()
    response = SimpleNamespace(PrivateZoneSet=[], TotalCount=0)
    client = SimpleNamespace(DescribePrivateZoneList=lambda request: response)
    module.find_zone(fake, client, models, None, params["domain"])
    errors.extend(audit_recorded(fake, "private DNS zone describe"))
    assert errors == []


def test_private_dns_record():
    module = _import_plugin("private_dns_record")
    models = _models("privatedns.v20201028")
    params = {
        "zone_id": "zone-xxxxxxxx",
        "subdomain": "api",
        "record_type": "A",
        "value": "10.0.0.8",
        "ttl": 300,
        "mx": None,
        "weight": 10,
        "remark": "API",
    }
    errors = []
    errors.extend(audit_request(module.build_create_request(models, params), "private DNS record create"))
    errors.extend(audit_request(module.build_update_request(models, params, "record-xxxxxxxx"), "private DNS record update"))
    fake = _RecordingModule()
    response = SimpleNamespace(RecordSet=[], TotalCount=0)
    client = SimpleNamespace(DescribePrivateZoneRecordList=lambda request: response)
    module.find_record(fake, client, models, params["zone_id"], None, "api", "A")
    errors.extend(audit_recorded(fake, "private DNS record describe"))
    assert errors == []


def test_tke_addon():
    _audit_p1_resource_request_builders()


def test_tke_node_pool():
    module = _import_plugin("tke_node_pool")
    models = _models("tke.v20180525")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "cls-xxxxxxxx"), "tke node pool describe request"))
    params = {
        "cluster_id": "cls-xxxxxxxx",
        "name": "workers",
        "launch_configuration_json": '{"InstanceTypes":["S5.LARGE8"]}',
        "autoscaling_group_json": "",
        "enable_autoscale": True,
        "max_nodes_num": 10,
        "min_nodes_num": 2,
        "labels": {"app": "workers"},
        "taints": [{"key": "dedicated", "value": "true", "effect": "NoSchedule"}],
        "node_pool_os": "tlinux2.4x86_64",
        "deletion_protection": True,
        "tags": {"env": "prod"},
    }
    errors.extend(audit_request(module.build_create_request(models, params), "tke node pool create request"))
    module._update(fake, client, models, params, "np-xxxxxxxx")
    module._delete(fake, client, models, "cls-xxxxxxxx", "np-xxxxxxxx", False)
    errors.extend(audit_recorded(fake, "tke_node_pool"))
    assert errors == []


def test_network_interface():
    module = _import_plugin("network_interface")
    models = _models("vpc.v20170312")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "eni-xxxxxxxx", None, None), "eni describe request"))
    params = {
        "vpc_id": "vpc-xxxxxxxx",
        "name": "web-eni",
        "subnet_id": "subnet-xxxxxxxx",
        "description": "Web tier interface",
        "security_group_ids": ["sg-xxxxxxxx"],
        "secondary_private_ip_count": 2,
        "tags": {"env": "prod"},
    }
    errors.extend(audit_request(module.build_create_request(models, params), "eni create request"))
    module._update(fake, client, models, params, "eni-xxxxxxxx")
    module._delete(fake, client, models, "eni-xxxxxxxx")
    errors.extend(audit_recorded(fake, "network_interface"))
    assert errors == []


def test_scf_alias():
    module = _import_plugin("scf_alias")
    models = _models("scf.v20180416")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    params = {
        "function_name": "my-func",
        "name": "prod",
        "function_version": "2",
        "namespace": "default",
        "description": "Production traffic",
    }
    errors.extend(audit_request(module.build_get_request(models, params), "scf alias get request"))
    errors.extend(audit_request(module.build_create_request(models, params), "scf alias create request"))
    module._update(fake, client, models, params)
    module._delete(fake, client, models, params)
    errors.extend(audit_recorded(fake, "scf_alias"))
    assert errors == []


def test_scf_version():
    module = _import_plugin("scf_version")
    models = _models("scf.v20180416")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    params = {
        "function_name": "my-func",
        "version": "2",
        "namespace": "default",
        "description": "Deployed by ansible",
        "force_delete": False,
    }
    errors.extend(audit_request(module.build_list_request(models, params), "scf version list request"))
    errors.extend(audit_request(module.build_publish_request(models, params), "scf version publish request"))
    module._delete(fake, client, models, params)
    errors.extend(audit_recorded(fake, "scf_version"))
    assert errors == []


def test_elasticsearch_instance():
    module = _import_plugin("elasticsearch_instance")
    models = _models("es.v20180416")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_describe_request(models, "es-xxxxxxxx", None), "es describe request"))
    params = {
        "zone": "ap-guangzhou-3",
        "es_version": "7.10.1",
        "vpc_id": "vpc-xxxxxxxx",
        "subnet_id": "subnet-xxxxxxxx",
        "password": "secret-pass-1",
        "name": "logs-es",
        "node_type": "ES.S1.MEDIUM8",
        "node_num": 3,
        "disk_type": "CLOUD_SSD",
        "disk_size": 200,
        "license_type": "basic",
    }
    errors.extend(audit_request(module.build_create_request(models, params), "es create request"))
    module._rename(fake, client, models, "es-xxxxxxxx", "logs-es-v2")
    module._destroy(fake, client, models, "es-xxxxxxxx")
    errors.extend(audit_recorded(fake, "elasticsearch_instance"))
    assert errors == []


def test_api_gateway_api():
    module = _import_plugin("api_gateway_api")
    models = _models("apigateway.v20180808")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.build_list(models, "service-xxxxxxxx", "orders", 0), "api gateway api list"))
    errors.extend(audit_request(module.build_list(models, "service-xxxxxxxx", None, 0), "api gateway api list all"))
    errors.extend(audit_request(module.build_get(models, "service-xxxxxxxx", "api-xxxxxxxx"), "api gateway api get"))
    p = {"api_id": "api-xxxxxxxx", "service_id": "service-xxxxxxxx", "name": "orders"}
    module.find(fake, client, models, p)
    errors.extend(audit_recorded(fake, "api_gateway_api"))
    assert errors == []


def test_as_scaling_policy():
    module = _import_plugin("as_scaling_policy")
    models = _models("autoscaling.v20180419")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    p = {"policy_id": "asap-xxxxxxxx", "scaling_group_id": "asg-xxxxxxxx", "name": "add-two"}
    module.find(fake, client, models, p)
    p2 = {"policy_id": None, "scaling_group_id": "asg-xxxxxxxx", "name": "add-two"}
    module.find(fake, client, models, p2)
    errors.extend(audit_recorded(fake, "as_scaling_policy"))
    assert errors == []


def test_as_scheduled_action():
    module = _import_plugin("as_scheduled_action")
    models = _models("autoscaling.v20180419")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    p = {"action_id": "asac-xxxxxxxx", "scaling_group_id": "asg-xxxxxxxx", "name": "scale-up"}
    module.find(fake, client, models, p)
    errors.extend(audit_recorded(fake, "as_scheduled_action"))
    assert errors == []


def test_cls_index():
    module = _import_plugin("cls_index")
    models = _models("cls.v20201016")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    module.find(fake, client, models, "topic-xxxxxxxx")
    errors.extend(audit_recorded(fake, "cls_index"))
    assert errors == []


def test_cls_machine_group():
    module = _import_plugin("cls_machine_group")
    models = _models("cls.v20201016")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    p = {"group_id": None, "name": "prod-group"}
    module.find(fake, client, models, p)
    p2 = {"group_id": "mg-xxxxxxxx", "name": None}
    module.find(fake, client, models, p2)
    errors.extend(audit_recorded(fake, "cls_machine_group"))
    assert errors == []


def test_cmq_subscription():
    module = _import_plugin("cmq_subscription")
    models = _models("tdmq.v20200217")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    module.find(fake, client, models, "order-events", "order-webhook")
    errors.extend(audit_recorded(fake, "cmq_subscription"))
    assert errors == []


def test_cmq_topic():
    module = _import_plugin("cmq_topic")
    models = _models("tdmq.v20200217")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.describe_request(models, "order-events"), "cmq topic describe"))
    module.find(fake, client, models, "order-events")
    errors.extend(audit_recorded(fake, "cmq_topic"))
    assert errors == []


def test_dts_migration_job():
    module = _import_plugin("dts_migration_job")
    models = _models("dts.v20211206")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    errors.extend(audit_request(module.describe_request(models, "dts-xxxxxxxx", None, 0), "dts describe by id"))
    errors.extend(audit_request(module.describe_request(models, None, "prod-migration", 0), "dts describe by name"))
    module.find(fake, client, models, "dts-xxxxxxxx", None)
    errors.extend(audit_recorded(fake, "dts_migration_job"))
    assert errors == []


def test_scf_trigger():
    module = _import_plugin("scf_trigger")
    models = _models("scf.v20180416")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    p = {
        "function_name": "orders-processor",
        "namespace": "default",
        "qualifier": "$LATEST",
        "name": "cron-trigger",
        "trigger_type": "timer",
        "trigger_desc": "0 */5 * * * * *",
        "enabled": True,
        "custom_argument": "env=prod",
        "description": "Five-minute cron",
    }
    module.find(fake, client, models, p)
    errors.extend(audit_request(module.delete_request(models, p), "scf trigger delete"))
    module.create(fake, client, models, p)
    errors.extend(audit_recorded(fake, "scf_trigger"))
    assert errors == []


def test_tcr_replication_rule():
    module = _import_plugin("tcr_replication_rule")
    models = _models("tcr.v20190924")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    module.find(fake, client, models, "tcr-xxxxxxxx", "production-images")
    errors.extend(audit_recorded(fake, "tcr_replication_rule"))
    assert errors == []


def test_tdmq_subscription():
    module = _import_plugin("tdmq_subscription")
    models = _models("tdmq.v20200217")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    p = {
        "cluster_id": "pulsar-xxxxxxxx",
        "environment_id": "production",
        "topic_name": "orders",
        "name": "order-workers",
        "force": False,
    }
    errors.extend(audit_request(module.describe_request(models, p, 0), "tdmq subscription describe"))
    errors.extend(audit_request(module.delete_request(models, p), "tdmq subscription delete"))
    module.find(fake, client, models, p)
    errors.extend(audit_recorded(fake, "tdmq_subscription"))
    assert errors == []


def test_cam_group():
    module = _import_plugin("cam_group")
    models = _models("cam.v20190116")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    module.find(fake, client, models, 1, "operators")
    module.find(fake, client, models, None, "operators")
    errors.extend(audit_recorded(fake, "cam_group"))
    assert errors == []


def test_cdb_parameter_template():
    module = _import_plugin("cdb_parameter_template")
    models = _models("cdb.v20170320")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    module.find(fake, client, models, 12345, None)
    errors.extend(audit_recorded(fake, "cdb_parameter_template"))
    assert errors == []


def test_cdb_account():
    module = _import_plugin("cdb_account")
    models = _models("cdb.v20170320")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    p = {"instance_id": "cdb-xxxxxxxx", "username": "app", "host": "%", "password": "secret", "description": "app", "max_user_connections": 100}
    errors.extend(audit_request(module.describe(models, p), "cdb account describe"))
    errors.extend(audit_request(module.create(models, p), "cdb account create"))
    for kind in ("DeleteAccounts", "ModifyAccountDescription", "ModifyAccountMaxUserConnections", "ModifyAccountPassword"):
        errors.extend(audit_request(module.simple(models, kind, p), "cdb account " + kind))
    module.find(fake, client, models, p)
    errors.extend(audit_recorded(fake, "cdb_account"))
    assert errors == []


def test_cdb_account_privilege():
    module = _import_plugin("cdb_account_privilege")
    models = _models("cdb.v20170320")
    errors = []
    p = {"instance_id": "cdb-xxxxxxxx", "username": "app", "host": "%"}
    wanted = {"GlobalPrivileges": ["SELECT"], "DatabasePrivileges": [{"database": "orders", "privileges": ["SELECT", "INSERT"]}], "TablePrivileges": [{"database": "orders", "table": "events", "privileges": ["SELECT"]}], "ColumnPrivileges": [{"database": "orders", "table": "events", "column": "id", "privileges": ["SELECT"]}]}
    errors.extend(audit_request(module.describe_request(models, p), "cdb account privilege describe"))
    errors.extend(audit_request(module.modify_request(models, p, wanted), "cdb account privilege modify"))
    assert errors == []


def test_cdb_database():
    module = _import_plugin("cdb_database")
    models = _models("cdb.v20170320")
    errors = []
    p = {"instance_id": "cdb-xxxxxxxx", "name": "orders", "character_set": "utf8mb4"}
    errors.extend(audit_request(module.describe_request(models, p["instance_id"]), "cdb database describe"))
    errors.extend(audit_request(module.create_request(models, p), "cdb database create"))
    errors.extend(audit_request(module.delete_request(models, p), "cdb database delete"))
    assert errors == []


def test_cdb_audit_config():
    module = _import_plugin("cdb_audit_config")
    models = _models("cdb.v20170320")
    errors = []
    p = {"instance_id": "cdb-xxxxxxxx", "enabled": True, "retention_days": 180}
    errors.extend(audit_request(module.describe_request(models, p["instance_id"]), "cdb audit config describe"))
    errors.extend(audit_request(module.modify_request(models, p), "cdb audit config modify"))
    errors.extend(audit_request(module.modify_request(models, dict(p, enabled=False)), "cdb audit config close"))
    assert errors == []


def test_organization_member():
    module = _import_plugin("organization_member")
    models = _models("organization.v20210331")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    p = {"member_uin": 100000000001, "name": "production", "account_name": "production", "node_id": 1001, "remark": "prod", "permission_ids": [1, 2], "identity_role_ids": [1], "allow_quit": "Denied"}
    errors.extend(audit_request(module.describe(models), "organization member describe"))
    errors.extend(audit_request(module.create(models, p), "organization member create"))
    errors.extend(audit_request(module.update(models, p, p["member_uin"]), "organization member update"))
    errors.extend(audit_request(module.move(models, p["node_id"], p["member_uin"]), "organization member move"))
    errors.extend(audit_request(module.delete(models, p["member_uin"]), "organization member delete"))
    module.find(fake, client, models, p)
    errors.extend(audit_recorded(fake, "organization_member"))
    assert errors == []


def test_organization_member_identity():
    module = _import_plugin("organization_member_identity")
    models = _models("organization.v20210331")
    errors = []
    errors.extend(audit_request(module.describe_request(models, 100000000001), "organization member identity describe"))
    errors.extend(audit_request(module.create_request(models, 100000000001, [1, 12]), "organization member identity create"))
    errors.extend(audit_request(module.delete_request(models, 100000000001, 12), "organization member identity delete"))
    assert errors == []


def test_organization_member_policy():
    module = _import_plugin("organization_member_policy")
    models = _models("organization.v20210331")
    errors = []
    p = {"member_uin": 100000000001, "name": "operations", "identity_id": 12, "description": "Operations access"}
    errors.extend(audit_request(module.describe_request(models, p["member_uin"]), "organization member policy describe"))
    errors.extend(audit_request(module.create_request(models, p), "organization member policy create"))
    errors.extend(audit_request(module.update_request(models, p, 101), "organization member policy update"))
    errors.extend(audit_request(module.delete_request(models, 101), "organization member policy delete"))
    assert errors == []


def test_mongodb_backup_config():
    module = _import_plugin("mongodb_backup_config")
    models = _models("mongodb.v20190725")
    errors = []
    p = {"instance_id": "cmgo-xxxxxxxx", "backup_method": 1, "backup_hour": 3, "frequency_hours": 24, "active_weekdays": [1, 3, 5], "retention_days": 30, "oplog_retention_days": 14, "backup_version": 1, "alert_threshold": 100}
    errors.extend(audit_request(module.describe_request(models, p["instance_id"]), "mongodb backup config describe"))
    errors.extend(audit_request(module.set_request(models, p), "mongodb backup config set"))
    assert errors == []


def test_mongodb_account():
    module = _import_plugin("mongodb_account")
    models = _models("mongodb.v20190725")
    errors = []
    p = {"instance_id": "cmgo-xxxxxxxx", "username": "app", "password": "Password_123", "mongo_user_password": "Admin_123", "description": "app", "roles": [{"namespace": "orders", "access": "read_write"}]}
    errors.extend(audit_request(module.describe_request(models, p["instance_id"]), "mongodb account describe"))
    errors.extend(audit_request(module.create_request(models, p), "mongodb account create"))
    errors.extend(audit_request(module.privilege_request(models, p), "mongodb account privilege"))
    errors.extend(audit_request(module.password_request(models, p), "mongodb account password"))
    errors.extend(audit_request(module.delete_request(models, p), "mongodb account delete"))
    assert errors == []


def test_sqlserver_account():
    module = _import_plugin("sqlserver_account")
    models = _models("sqlserver.v20180328")
    errors = []
    p = {"instance_id": "mssql-xxxxxxxx", "username": "app", "password": "Password_123", "remark": "app", "account_type": "L3", "database_privileges": [{"database": "orders", "privilege": "ReadWrite"}]}
    errors.extend(audit_request(module.describe_request(models, p), "sqlserver account describe"))
    errors.extend(audit_request(module.create_request(models, p), "sqlserver account create"))
    errors.extend(audit_request(module.privilege_request(models, p, p["database_privileges"]), "sqlserver account privilege"))
    errors.extend(audit_request(module.remark_request(models, p), "sqlserver account remark"))
    errors.extend(audit_request(module.password_request(models, p), "sqlserver account password"))
    errors.extend(audit_request(module.delete_request(models, p), "sqlserver account delete"))
    assert errors == []


def test_sqlserver_backup_config():
    module = _import_plugin("sqlserver_backup_config"); models = _models("sqlserver.v20180328")
    p = {"instance_id": "mssql-xxxxxxxx", "backup_type": "weekly", "backup_hour": 3, "backup_cycle": [1, 3, 5], "backup_model": "master_pkg", "retention_days": 30}
    errors = audit_request(module.describe_request(models, p["instance_id"]), "SQL Server backup describe")
    errors.extend(audit_request(module.update_request(models, p), "SQL Server backup update"))
    assert errors == []


def test_mariadb_account():
    module = _import_plugin("mariadb_account")
    models = _models("mariadb.v20170312")
    errors = []
    p = {"instance_id": "tdsql-xxxxxxxx", "username": "app", "host": "%", "password": "Password_123", "description": "app", "read_only": 0, "delay_threshold": 10, "sticky_replica": False, "max_user_connections": 0}
    errors.extend(audit_request(module.describe_request(models, p["instance_id"]), "mariadb account describe"))
    errors.extend(audit_request(module.create_request(models, p), "mariadb account create"))
    errors.extend(audit_request(module.description_request(models, p), "mariadb account description"))
    errors.extend(audit_request(module.password_request(models, p), "mariadb account password"))
    errors.extend(audit_request(module.delete_request(models, p), "mariadb account delete"))
    assert errors == []


def test_mariadb_backup_config():
    module = _import_plugin("mariadb_backup_config")
    models = _models("mariadb.v20170312")
    errors = []
    p = {"instance_id": "tdsql-xxxxxxxx", "retention_days": 30, "start_time": "02:00", "end_time": "03:00", "weekdays": ["Monday", "Wednesday", "Friday"], "archive_after_days": -1}
    errors.extend(audit_request(module.describe_request(models, p["instance_id"]), "mariadb backup config describe"))
    errors.extend(audit_request(module.modify_request(models, p), "mariadb backup config modify"))
    assert errors == []


def test_mariadb_account_privilege():
    module = _import_plugin("mariadb_account_privilege")
    models = _models("mariadb.v20170312")
    errors = []
    p = {"instance_id": "tdsql-xxxxxxxx", "username": "app", "host": "%", "database": "orders", "object_type": "table", "object_name": "events", "column": "*"}
    errors.extend(audit_request(module.describe_request(models, p), "mariadb account privilege describe"))
    errors.extend(audit_request(module.grant_request(models, p, ["SELECT", "INSERT"]), "mariadb account privilege grant"))
    errors.extend(audit_request(module.grant_request(models, p, []), "mariadb account privilege clear"))
    assert errors == []


def test_elasticsearch_index():
    module = _import_plugin("elasticsearch_index")
    models = _models("es.v20180416")
    errors = []
    p = {"instance_id": "es-xxxxxxxx", "name": "orders", "index_type": "normal", "metadata": {"settings": {"number_of_shards": 3}, "mappings": {"properties": {"order_id": {"type": "keyword"}}}}, "username": "elastic", "password": "Password_123"}
    errors.extend(audit_request(module.describe_request(models, p), "elasticsearch index describe"))
    errors.extend(audit_request(module.create_request(models, p), "elasticsearch index create"))
    errors.extend(audit_request(module.update_request(models, p), "elasticsearch index update"))
    errors.extend(audit_request(module.delete_request(models, p), "elasticsearch index delete"))
    assert errors == []


def test_ckafka_user():
    module = _import_plugin("ckafka_user")
    models = _models("ckafka.v20190819")
    errors = []
    p = {"instance_id": "ckafka-xxxxxxxx", "name": "producer", "password": "Password_123", "current_password": "OldPassword_123"}
    errors.extend(audit_request(module.describe_request(models, p), "ckafka user describe"))
    errors.extend(audit_request(module.create_request(models, p), "ckafka user create"))
    errors.extend(audit_request(module.password_request(models, p), "ckafka user password"))
    errors.extend(audit_request(module.delete_request(models, p), "ckafka user delete"))
    assert errors == []


def test_ckafka_route():
    module = _import_plugin("ckafka_route")
    models = _models("ckafka.v20190819")
    errors = []
    p = {"instance_id": "ckafka-xxxxxxxx", "network_type": 3, "access_type": 3, "vpc_id": "vpc-xxxxxxxx", "subnet_id": "subnet-xxxxxxxx", "public_bandwidth": None, "note": "private", "security_group_ids": ["sg-xxxxxxxx"], "ip_whitelist": []}
    errors.extend(audit_request(module.describe_request(models, p["instance_id"]), "ckafka route describe"))
    errors.extend(audit_request(module.create_request(models, p), "ckafka route create"))
    errors.extend(audit_request(module.delete_request(models, p["instance_id"], 123), "ckafka route delete"))
    assert errors == []


def test_ckafka_acl_rule():
    module = _import_plugin("ckafka_acl_rule")
    models = _models("ckafka.v20190819")
    errors = []
    p = {"instance_id": "ckafka-xxxxxxxx", "name": "orders-producers", "pattern_type": "PREFIXED", "pattern": "orders-", "apply_to_new_topics": False, "comment": "producer access", "rules": [{"operation": "Write", "permission": "Allow", "host": "*", "principal": "User:producer"}]}
    errors.extend(audit_request(module.describe_request(models, p), "ckafka acl rule describe"))
    errors.extend(audit_request(module.create_request(models, p), "ckafka acl rule create"))
    errors.extend(audit_request(module.update_request(models, p), "ckafka acl rule update"))
    errors.extend(audit_request(module.delete_request(models, p), "ckafka acl rule delete"))
    assert errors == []


def test_ckafka_datahub_topic():
    module = _import_plugin("ckafka_datahub_topic"); models = _models("ckafka.v20190819")
    p = {"name": "1250000000-orders", "partition_num": 6, "retention_ms": 86400000, "note": "orders"}
    requests = [module.describe_request(models, p["name"]), module.create_request(models, p), module.update_request(models, p), module.delete_request(models, p["name"])]
    errors = []
    for request in requests: errors.extend(audit_request(request, "CKafka Datahub topic request"))
    assert errors == []


def test_ckafka_datahub_connection():
    module = _import_plugin("ckafka_datahub_connection"); models = _models("ckafka.v20190819")
    p = {"resource_id": "resource-x", "name": "analytics-kafka", "connection_type": "KAFKA", "description": "analytics", "config": {"Resource": "ckafka-x", "SelfBuilt": False}}
    requests = [module.describe_request(models, p["resource_id"]), module.list_request(models, p), module.create_request(models, p), module.update_request(models, p, p["resource_id"]), module.delete_request(models, p["resource_id"])]
    errors = []
    for request in requests: errors.extend(audit_request(request, "CKafka Datahub connection request"))
    assert errors == []


def test_ckafka_datahub_task():
    module = _import_plugin("ckafka_datahub_task"); models = _models("ckafka.v20190819")
    p = {"task_id": "task-x", "name": "mysql-orders", "task_type": "SOURCE", "source_resource": {"Type": "MYSQL", "MySQLParam": {"Resource": "resource-x", "Database": "orders", "Table": "*"}}, "target_resource": {"Type": "TOPIC", "TopicParam": {"Resource": "1250000000-orders"}}, "transform": None, "transforms": None, "schema_id": None, "description": "orders", "desired_status": "running", "tasks_max": 2, "sync_throttle_limit": 20, "auto_expand": True}
    requests = [module.describe_request(models, p["task_id"]), module.list_request(models, p), module.create_request(models, p), module.update_request(models, p, p["task_id"]), module.pause_request(models, p["task_id"]), module.resume_request(models, p["task_id"]), module.delete_request(models, p["task_id"])]
    errors = []
    for request in requests: errors.extend(audit_request(request, "CKafka Datahub task request"))
    assert errors == []


def test_tdmq_namespace():
    module = _import_plugin("tdmq_namespace")
    models = _models("tdmq.v20200217")
    errors = []
    p = {"cluster_id": "pulsar-xxxxxxxx", "name": "production", "message_ttl": 604800, "remark": "prod", "retention_minutes": 1440, "retention_size_mb": 10240, "auto_subscription_creation": False, "subscription_expiration_enabled": True, "subscription_expiration_time": 2592000}
    errors.extend(audit_request(module.describe_request(models, p), "tdmq namespace describe"))
    errors.extend(audit_request(module.create_request(models, p), "tdmq namespace create"))
    errors.extend(audit_request(module.update_request(models, p), "tdmq namespace update"))
    errors.extend(audit_request(module.delete_request(models, p), "tdmq namespace delete"))
    assert errors == []


def test_tdmq_namespace_role():
    module = _import_plugin("tdmq_namespace_role")
    models = _models("tdmq.v20200217")
    errors = []
    p = {"cluster_id": "pulsar-xxxxxxxx", "namespace": "production", "role_name": "application", "permissions": ["produce", "consume"]}
    errors.extend(audit_request(module.describe_request(models, p), "tdmq namespace role describe"))
    errors.extend(audit_request(module.create_request(models, p), "tdmq namespace role create"))
    errors.extend(audit_request(module.update_request(models, p), "tdmq namespace role update"))
    errors.extend(audit_request(module.delete_request(models, p), "tdmq namespace role delete"))
    assert errors == []


def test_tdmq_rabbitmq_vhost():
    module = _import_plugin("tdmq_rabbitmq_vhost")
    models = _models("tdmq.v20200217")
    errors = []
    p = {"instance_id": "amqp-xxxxxxxx", "name": "production", "description": "prod", "trace_enabled": True, "mirror_queue_policy": True}
    errors.extend(audit_request(module.describe_request(models, p), "tdmq rabbitmq vhost describe"))
    errors.extend(audit_request(module.create_request(models, p), "tdmq rabbitmq vhost create"))
    errors.extend(audit_request(module.update_request(models, p), "tdmq rabbitmq vhost update"))
    errors.extend(audit_request(module.delete_request(models, p), "tdmq rabbitmq vhost delete"))
    assert errors == []


def test_tdmq_rabbitmq_user():
    module = _import_plugin("tdmq_rabbitmq_user")
    models = _models("tdmq.v20200217")
    errors = []
    p = {"instance_id": "amqp-xxxxxxxx", "name": "application", "password": "Password_123", "rotate_password": True, "description": "app", "tags": ["management"], "max_connections": 100, "max_channels": 200, "cam_auth_enabled": False}
    errors.extend(audit_request(module.describe_request(models, p), "tdmq rabbitmq user describe"))
    errors.extend(audit_request(module.create_request(models, p), "tdmq rabbitmq user create"))
    errors.extend(audit_request(module.update_request(models, p), "tdmq rabbitmq user update"))
    errors.extend(audit_request(module.delete_request(models, p), "tdmq rabbitmq user delete"))
    assert errors == []


def test_tdmq_rabbitmq_permission():
    module = _import_plugin("tdmq_rabbitmq_permission")
    models = _models("tdmq.v20200217")
    errors = []
    p = {"instance_id": "amqp-xxxxxxxx", "user": "application", "virtual_host": "production", "configure_regex": "^orders\\.", "write_regex": "^orders\\.", "read_regex": "^orders\\."}
    errors.extend(audit_request(module.describe_request(models, p), "tdmq rabbitmq permission describe"))
    errors.extend(audit_request(module.modify_request(models, p), "tdmq rabbitmq permission modify"))
    errors.extend(audit_request(module.delete_request(models, p), "tdmq rabbitmq permission delete"))
    assert errors == []


def test_tdmq_rabbitmq_binding():
    module = _import_plugin("tdmq_rabbitmq_binding")
    models = _models("tdmq.v20200217")
    errors = []
    p = {"instance_id": "amqp-xxxxxxxx", "virtual_host": "production", "source_exchange": "orders", "destination_type": "queue", "destination": "order-workers", "routing_key": "orders.created"}
    errors.extend(audit_request(module.describe_request(models, p), "tdmq rabbitmq binding describe"))
    errors.extend(audit_request(module.create_request(models, p), "tdmq rabbitmq binding create"))
    errors.extend(audit_request(module.delete_request(models, p, 123), "tdmq rabbitmq binding delete"))
    assert errors == []


def test_tdmq_rocketmq_namespace():
    module = _import_plugin("tdmq_rocketmq_namespace")
    models = _models("tdmq.v20200217")
    errors = []
    p = {"cluster_id": "rocketmq-xxxxxxxx", "name": "production", "remark": "prod"}
    errors.extend(audit_request(module.describe_request(models, p), "tdmq rocketmq namespace describe"))
    errors.extend(audit_request(module.create_request(models, p), "tdmq rocketmq namespace create"))
    errors.extend(audit_request(module.update_request(models, p), "tdmq rocketmq namespace update"))
    errors.extend(audit_request(module.delete_request(models, p), "tdmq rocketmq namespace delete"))
    assert errors == []


def test_tdmq_rocketmq_topic():
    module = _import_plugin("tdmq_rocketmq_topic")
    models = _models("tdmq.v20200217")
    errors = []
    p = {"cluster_id": "rocketmq-xxxxxxxx", "namespace": "production", "name": "orders", "topic_type": "PartitionedOrder", "partition_num": 6, "remark": "orders"}
    errors.extend(audit_request(module.describe_request(models, p), "tdmq rocketmq topic describe"))
    errors.extend(audit_request(module.create_request(models, p), "tdmq rocketmq topic create"))
    errors.extend(audit_request(module.update_request(models, p), "tdmq rocketmq topic update"))
    errors.extend(audit_request(module.delete_request(models, p), "tdmq rocketmq topic delete"))
    assert errors == []


def test_tdmq_rocketmq_group():
    module = _import_plugin("tdmq_rocketmq_group")
    models = _models("tdmq.v20200217")
    errors = []
    p = {"cluster_id": "rocketmq-xxxxxxxx", "namespace": "production", "name": "order-workers", "group_type": "TCP", "read_enabled": True, "broadcast_enabled": False, "retry_max_times": 12, "remark": "workers"}
    errors.extend(audit_request(module.describe_request(models, p), "tdmq rocketmq group describe"))
    errors.extend(audit_request(module.create_request(models, p), "tdmq rocketmq group create"))
    errors.extend(audit_request(module.update_request(models, p), "tdmq rocketmq group update"))
    errors.extend(audit_request(module.delete_request(models, p), "tdmq rocketmq group delete"))
    assert errors == []


def test_tdmq_rocketmq_role():
    module = _import_plugin("tdmq_rocketmq_role")
    models = _models("tdmq.v20200217")
    errors = []
    p = {"cluster_id": "rocketmq-xxxxxxxx", "name": "order-service", "permission_type": "TopicAndGroup", "remark": "orders"}
    errors.extend(audit_request(module.describe_request(models, p), "tdmq rocketmq role describe"))
    errors.extend(audit_request(module.create_request(models, p), "tdmq rocketmq role create"))
    errors.extend(audit_request(module.update_request(models, p), "tdmq rocketmq role update"))
    errors.extend(audit_request(module.delete_request(models, p), "tdmq rocketmq role delete"))
    assert errors == []


def test_tdmq_rocketmq_permission():
    module = _import_plugin("tdmq_rocketmq_permission")
    models = _models("tdmq.v20200217")
    errors = []
    p = {"cluster_id": "rocketmq-xxxxxxxx", "namespace": "production", "role_name": "order-service", "permissions": ["produce", "consume"]}
    errors.extend(audit_request(module.describe_request(models, p), "tdmq rocketmq permission describe"))
    errors.extend(audit_request(module.create_request(models, p), "tdmq rocketmq permission create"))
    errors.extend(audit_request(module.update_request(models, p), "tdmq rocketmq permission update"))
    errors.extend(audit_request(module.delete_request(models, p), "tdmq rocketmq permission delete"))
    assert errors == []


def test_tdmq_rocketmq_cluster():
    module = _import_plugin("tdmq_rocketmq_cluster")
    models = _models("tdmq.v20200217")
    errors = []
    p = {"cluster_id": "rocketmq-xxxxxxxx", "name": "application-messaging", "remark": "shared"}
    errors.extend(audit_request(module.describe_request(models, p), "tdmq rocketmq cluster describe"))
    errors.extend(audit_request(module.create_request(models, p), "tdmq rocketmq cluster create"))
    errors.extend(audit_request(module.update_request(models, p, p["cluster_id"]), "tdmq rocketmq cluster update"))
    errors.extend(audit_request(module.delete_request(models, p["cluster_id"]), "tdmq rocketmq cluster delete"))
    assert errors == []


def test_ckafka_acl():
    module = _import_plugin("ckafka_acl")
    models = _models("ckafka.v20190819")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    p = {
        "instance_id": "ckafka-xxxxxxxx",
        "resource_type": "TOPIC",
        "resource_name": "orders",
        "operation": "ALL",
        "permission": "ALLOW",
        "host": "*",
        "principal": "User:consumer-app",
    }
    module.find(fake, client, models, p)
    errors.extend(audit_request(module.request_for(models, p), "ckafka acl create"))
    errors.extend(audit_request(module.request_for(models, p, deleting=True), "ckafka acl delete"))
    errors.extend(audit_recorded(fake, "ckafka_acl"))
    assert errors == []


def test_dnspod_domain():
    module = _import_plugin("dnspod_domain")
    models = _models("dnspod.v20210323")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    module.find(fake, client, models, 1234567, None)
    module.find(fake, client, models, None, "example.com")
    errors.extend(audit_recorded(fake, "dnspod_domain"))
    assert errors == []


def test_postgresql_parameter_template():
    module = _import_plugin("postgresql_parameter_template")
    models = _models("postgres.v20170312")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    module.find(fake, client, models, "tpl-xxxxxxxx", None)
    errors.extend(audit_recorded(fake, "postgresql_parameter_template"))
    assert errors == []


def test_redis_parameter_template():
    module = _import_plugin("redis_parameter_template")
    models = _models("redis.v20180412")
    fake = _RecordingModule()
    client = _StubClient()
    errors = []
    module.find(fake, client, models, "tpl-xxxxxxxx", None)
    errors.extend(audit_recorded(fake, "redis_parameter_template"))
    assert errors == []
