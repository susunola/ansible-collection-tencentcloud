# -*- coding: utf-8 -*-
"""Audit read-side coverage of write modules.

Every hand-written (core) write module should have a readable query surface:
a generated ``<module>_info`` counterpart, or a curated mapping to another
``_info`` module whose response actually contains the resource. This script
reports the coverage table and, with ``--check``, exits 1 when a write
module is covered by neither — so a new write module cannot land without a
deliberate coverage decision, mirroring ``check_module_tiers.py``.

Verdicts:

* **covered** -- ``plugins/modules/<name>_info.py`` exists.
* **mapped** -- ``KNOWN_COVERAGE`` below points the write module at one or
  more existing ``_info`` modules that genuinely return the resource
  (verified against the covering module's API response shape).
* **gap** -- ``KNOWN_GAPS`` records why there is no read surface yet; gaps
  are reported but do not fail ``--check`` (they are the curated backlog).
  Reasons: ``backlog`` (a scoped list API exists; nobody wired it up yet) or
  ``no-list-api`` (the service offers no list/describe API for the resource).

Anything else fails ``--check``.

Run from the repository root:

    python3 scripts/audit_info_coverage.py            # report
    python3 scripts/audit_info_coverage.py --check    # CI gate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = REPO_ROOT / "plugins" / "modules"

# Write module -> (covering _info modules, why the mapping is valid).
# Only list a mapping after verifying the covering module's response really
# contains the resource; a wrong mapping is worse than an honest gap.
KNOWN_COVERAGE = {
    "clb_rule": (
        ["clb_listener_info"],
        "DescribeListeners returns L7 listeners with their Rules inline",
    ),
    "nat_gateway_rule": (
        ["nat_gateway_dnat_rule_info", "nat_gateway_snat_rule_info"],
        "the write module reconciles the DNAT and SNAT rule sets; the two "
        "generated modules read them via DescribeNatGateway*NatRules",
    ),
    "havip_association": (
        ["havip_info"],
        "DescribeHaVips returns the HaVipAssociationSet with bound CVM/ENI per HAVIP",
    ),
    "cos_object_sync": (
        ["cos_object_info"],
        "cos_object_info lists and filters the objects of a bucket, which is "
        "the read side a sync reconciles against",
    ),
    "cvm_instance_security_group": (
        ["cvm_instance_info"],
        "DescribeInstances returns SecurityGroupIds per instance",
    ),
    "tke_cluster_upgrade": (
        ["tke_cluster_info"],
        "DescribeClusters returns the current ClusterVersion per cluster",
    ),
}

# Write modules that are themselves the read surface, or whose resource has
# no list API at all; keyed by module name with the reason as value.
KNOWN_NO_LIST_API = {
    "tke_cluster_kubeconfig": (
        "kubeconfig is a per-cluster credential fetch (DescribeClusterKubeconfig "
        "requires a ClusterId); the module itself is the read surface"
    ),
}

# Coverage backlog: write modules whose read surface is not wired up yet.
# Each name here is a known gap, reported by the audit and accepted by
# --check; close a gap by adding a SPECS entry (preferred) or a curated
# KNOWN_COVERAGE mapping, and remove the name from this set.
KNOWN_GAPS = {
    "api_gateway_api",
    "api_gateway_api_key",
    "api_gateway_service",
    "api_gateway_service_release",
    "api_gateway_usage_plan",
    "api_gateway_usage_plan_binding",
    "api_gateway_usage_plan_key_binding",
    "as_scaling_policy",
    "as_scheduled_action",
    "cam_group",
    "cam_group_membership",
    "cam_oidc_provider",
    "cam_saml_provider",
    "cbs_disk_backup",
    "cbs_snapshot_share",
    "ccn_attachment",
    "cdb_account_privilege",
    "cdb_audit_config",
    "cdb_parameter_template",
    "cdn_cls_log_topic",
    "cdwch_instance",
    "cdwdoris_instance",
    "cdwpg_instance",
    "cfs_auto_snapshot_policy",
    "cfw_address_template",
    "cfw_internet_acl_rule",
    "cfw_nat_acl_rule",
    "cfw_nat_dnat_rule",
    "cfw_vpc_acl_rule",
    "chdfs_access_group",
    "chdfs_access_rules",
    "chdfs_mount_access_groups",
    "chdfs_mount_point",
    "ckafka_acl",
    "ckafka_acl_rule",
    "ckafka_datahub_connection",
    "ckafka_datahub_task",
    "ckafka_datahub_topic",
    "ckafka_route",
    "cloudaudit_audit",
    "cloudaudit_track",
    "cls_config_machine_group_binding",
    "cmq_subscription",
    "cmq_topic",
    "config_aggregate_delivery",
    "config_aggregator",
    "config_alarm_policy",
    "config_compliance_pack",
    "config_delivery",
    "config_recorder",
    "config_remediation",
    "config_rule",
    "cos_bucket_domain",
    "cos_bucket_domain_certificate",
    "cos_bucket_encryption",
    "cos_bucket_intelligent_tiering",
    "cos_bucket_inventory",
    "cos_bucket_logging",
    "cos_bucket_object_lock",
    "cos_bucket_origin",
    "cos_bucket_policy",
    "cos_bucket_referer",
    "cos_bucket_replication",
    "cos_bucket_response_control",
    "cos_bucket_website",
    "cvm_chc",
    "cvm_disaster_recover_group",
    "cvm_disaster_recover_group_binding",
    "cvm_hpc_cluster",
    "cvm_image",
    "cvm_instance_action_timer",
    "cvm_launch_template",
    "cvm_launch_template_version",
    "cynosdb_account_privilege",
    "cynosdb_backup_config",
    "dbbrain_sql_filter",
    "dnspod_custom_line",
    "dnspod_domain",
    "dnspod_line_group",
    "dts_consumer_group",
    "dts_migration_job",
    "eb_connection",
    "eb_rule",
    "eb_target",
    "elasticsearch_index",
    "elasticsearch_instance",
    "elasticsearch_snapshot",
    "emr_cluster",
    "goosefs_fileset",
    "gwlb_load_balancer",
    "gwlb_target_group",
    "gwlb_target_group_association",
    "gwlb_target_group_instances",
    "lighthouse_disk",
    "lighthouse_firewall_rules",
    "lighthouse_key_pair",
    "lighthouse_snapshot",
    "mariadb_account_privilege",
    "mariadb_backup_config",
    "mongodb_backup_config",
    "monitor_alarm_policy_notice",
    "monitor_grafana_integration",
    "monitor_grafana_internet",
    "monitor_grafana_notification_channel",
    "monitor_grafana_whitelist",
    "monitor_prometheus_alert_group",
    "monitor_prometheus_alertmanager_config",
    "monitor_prometheus_cluster_agent",
    "monitor_prometheus_global_notification",
    "monitor_prometheus_grafana_binding",
    "monitor_prometheus_record_rule",
    "monitor_prometheus_scrape_job",
    "mqtt_authorization_policy",
    "mqtt_instance",
    "mqtt_topic",
    "mqtt_user",
    "oceanus_job",
    "oceanus_workspace",
    "organization_member_identity",
    "organization_member_policy",
    "organization_node",
    "postgresql_backup_plan",
    "postgresql_instance",
    "postgresql_parameter_template",
    "private_dns_record",
    "private_dns_zone",
    "privatelink_endpoint",
    "privatelink_endpoint_service",
    "redis_backup_config",
    "redis_parameter_template",
    "sqlserver_backup_config",
    "ssm_parameter",
    "ssm_rotation",
    "ssm_secret_version",
    "tat_invoker",
    "tcb_environment",
    "tcb_http_service_route",
    "tcm_mesh_clusters",
    "tcr_namespace",
    "tcr_replication_instance",
    "tcr_replication_rule",
    "tcr_repository",
    "tdcpg_cluster",
    "tdmq_namespace",
    "tdmq_namespace_role",
    "tdmq_rabbitmq_binding",
    "tdmq_rabbitmq_instance",
    "tdmq_rabbitmq_permission",
    "tdmq_rabbitmq_user",
    "tdmq_rabbitmq_vhost",
    "tdmq_rocketmq_cluster",
    "tdmq_rocketmq_group",
    "tdmq_rocketmq_namespace",
    "tdmq_rocketmq_permission",
    "tdmq_rocketmq_role",
    "tdmq_rocketmq_topic",
    "tdmq_subscription",
    "tdmq_topic",
    "tem_application_deployment",
    "tem_application_service",
    "tem_environment",
    "teo_acceleration_domain",
    "teo_dns_record",
    "teo_origin_group",
    "teo_security_bot_lite",
    "teo_security_custom_rules",
    "teo_security_exception_rules",
    "teo_security_ip_group",
    "teo_security_managed_rules",
    "teo_security_rate_limiting_rules",
    "teo_security_template_binding",
    "teo_web_security_template",
    "teo_zone",
    "tke_addon",
    "tke_backup_storage_location",
    "tke_cluster_audit",
    "tke_cluster_authentication",
    "tke_cluster_endpoint",
    "trabbit_serverless_binding",
    "trabbit_serverless_exchange",
    "trabbit_serverless_permission",
    "trabbit_serverless_queue",
    "trabbit_serverless_user",
    "trabbit_serverless_vhost",
    "vpc_flow_log",
    "waf_anti_info_leak_rule",
    "waf_anti_tamper_rule",
    "waf_area_ban_rule",
    "waf_attack_white_rule",
    "waf_auto_deny",
    "waf_cc_rule",
    "waf_custom_rule",
    "waf_custom_white_rule",
    "waf_host",
    "waf_ip_access_control",
    "waf_owasp_white_rule",
    "waf_protect_group",
    "waf_threat_intelligence",
}


def discover_modules():
    modules = sorted(
        path.stem
        for path in MODULES_DIR.glob("*.py")
        if not path.name.startswith("__")
    )
    infos = {name for name in modules if name.endswith("_info")}
    writes = [name for name in modules if not name.endswith("_info")]
    return writes, infos


def audit():
    """Return (rows, uncovered) where rows are (module, verdict, detail)."""
    writes, infos = discover_modules()
    rows = []
    uncovered = []
    for name in writes:
        direct = name + "_info"
        if direct in infos:
            rows.append((name, "covered", direct))
            continue
        if name in KNOWN_COVERAGE:
            covering, note = KNOWN_COVERAGE[name]
            missing = [info for info in covering if info not in infos]
            if missing:
                rows.append((name, "uncovered",
                             "KNOWN_COVERAGE references missing modules: %s" % ", ".join(missing)))
                uncovered.append(name)
                continue
            rows.append((name, "mapped", "%s (%s)" % (" + ".join(covering), note)))
            continue
        if name in KNOWN_NO_LIST_API:
            rows.append((name, "gap", "no-list-api: " + KNOWN_NO_LIST_API[name]))
            continue
        if name in KNOWN_GAPS:
            rows.append((name, "gap", "backlog: read surface not wired up yet"))
            continue
        rows.append((name, "uncovered", "no <name>_info module and no KNOWN_COVERAGE/KNOWN_GAPS entry"))
        uncovered.append(name)
    return rows, uncovered


def main(argv=None, out=None, err=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="exit 1 when a write module has no coverage verdict",
    )
    args = parser.parse_args(argv)
    out = out or sys.stdout
    err = err or sys.stderr

    rows, uncovered = audit()
    counts = {}
    for _name, verdict, _detail in rows:
        counts[verdict] = counts.get(verdict, 0) + 1
    print("write modules audited: %d" % len(rows), file=out)
    for verdict in ("covered", "mapped", "gap", "uncovered"):
        if counts.get(verdict):
            print("  %-10s %d" % (verdict, counts[verdict]), file=out)
    print(file=out)
    for name, verdict, detail in rows:
        if verdict in ("mapped", "gap"):
            print("  %-10s %-44s %s" % (verdict, name, detail), file=out)
    if uncovered:
        print(file=out)
        for name, _verdict, detail in rows:
            if _verdict == "uncovered":
                print("  uncovered  %-42s %s" % (name, detail), file=out)

    # Stale table entries are as broken as missing coverage.
    writes, infos = discover_modules()
    stale_coverage = sorted(set(KNOWN_COVERAGE) - set(writes))
    gap_tables = set(KNOWN_GAPS) | set(KNOWN_NO_LIST_API)
    stale_gaps = sorted(gap_tables - set(writes))
    stale_gap_now_covered = sorted(
        name for name in gap_tables if name + "_info" in infos
    )
    overlaps = sorted(
        (set(KNOWN_GAPS) | set(KNOWN_NO_LIST_API)) & set(KNOWN_COVERAGE)
    )
    for name in stale_coverage:
        print("  stale KNOWN_COVERAGE entry (module gone): %s" % name, file=err)
    for name in stale_gaps:
        print("  stale KNOWN_GAPS entry (module gone): %s" % name, file=err)
    for name in stale_gap_now_covered:
        print("  stale KNOWN_GAPS entry (%s_info now exists): %s" % (name, name), file=err)
    for name in overlaps:
        print("  %s is in both KNOWN_COVERAGE and a gap table" % name, file=err)
    stale = stale_coverage + stale_gaps + stale_gap_now_covered + overlaps

    if args.check and (uncovered or stale):
        print("fix: add a SPECS entry to scripts/generate_info_modules.py, "
              "or curate KNOWN_COVERAGE/KNOWN_GAPS here", file=err)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
