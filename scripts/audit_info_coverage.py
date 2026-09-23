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
* **gap** -- curated tables record why there is no read surface yet; gaps
  are reported but do not fail ``--check``. Reasons: ``backlog`` (not wired
  up yet) or ``no-list-api`` (no list/describe API; the detail API may also
  be retiring).

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
    "clb_snat_ip": (
        ['clb_load_balancer_info'],
        "DescribeLoadBalancers returns LoadBalancer.SnatIps, the SNAT IP set the "
        "write module adds and removes",
    ),
    "cos_object_sync": (
        ["cos_object_info"],
        "cos_object_info lists and filters the objects of a bucket, "
        "which is the read side a sync reconciles against",
    ),
    "cvm_disaster_recover_group_binding": (
        ["cvm_disaster_recover_group_info"],
        "DescribeDisasterRecoverGroups returns the InstanceIds bound "
        "to each placement group, the exact set the write module "
        "reconciles",
    ),
    "cvm_instance_security_group": (
        ["cvm_instance_info"],
        "DescribeInstances returns SecurityGroupIds per instance",
    ),
    "dlc_data_engine_config": (
        ["dlc_user_data_engine_config_info"],
        "DescribeUserDataEngineConfig returns "
        "the DataEngineConfigInstanceInfos the write module reconciles",
    ),
    "dlc_engine_resource_group": (
        ["dlc_standard_engine_resource_group_info"],
        "DescribeStandardEngineResourceGroups returns the "
        "standard-engine resource groups the write module manages",
    ),
    "dlc_spark_job": (
        ["dlc_spark_app_job_info"],
        "DescribeSparkAppJobs lists the SparkAppJob definitions the "
        "write module creates and updates",
    ),
    "dlc_user_policy": (
        ["dlc_user_info"],
        "DescribeUsers returns each user with its attached "
        "PolicySet inline, the exact set dlc_user_policy reconciles",
    ),
    "dlc_work_group_membership": (
        ["dlc_work_group_info"],
        "DescribeWorkGroups returns each group with its bound "
        "users(WorkGroupInfo.UserSet) inline",
    ),
    "dlc_work_group_policy": (
        ["dlc_work_group_info"],
        "DescribeWorkGroups returns each group with its attached PolicySet "
        "(WorkGroupInfo.PolicySet) inline",
    ),
    "dts_migration_action": (
        ['dts_migration_job_info'],
        "DescribeMigrationJobs returns JobItem.Status, the run state the write "
        "module starts and stops",
    ),
    "dts_migration_job_config": (
        ['dts_migration_job_info'],
        "DescribeMigrationJobs returns JobItem with SrcInfo, DstInfo, JobName, "
        "RunMode and AutoRetryTimeRangeMinutes, the configuration the write module "
        "modifies",
    ),
    "gwlb_target_group_association": (
        ['gwlb_gateway_load_balancer_info'],
        "DescribeGatewayLoadBalancers returns GatewayLoadBalancer.TargetGroupId, "
        "the association the write module manages",
    ),
    "havip_association": (
        ["havip_info"],
        "DescribeHaVips returns the HaVipAssociationSet with bound CVM/ENI "
        "per HAVIP",
    ),
    "monitor_alarm_policy_notice": (
        ["monitor_alarm_policy_info"],
        "DescribeAlarmPolicies returns each policy with its "
        "NoticeIds, HierarchicalNotices and "
        "NoticeContentTmplBindInfos inline, the exact bindings "
        "monitor_alarm_policy_notice reconciles",
    ),
    "monitor_grafana_internet": (
        ["monitor_grafana_instance_info"],
        "DescribeGrafanaInstances returns InternetUrl per instance, "
        "the exact state monitor_grafana_internet toggles",
    ),
    "nat_gateway_rule": (
        ["nat_gateway_dnat_rule_info", "nat_gateway_snat_rule_info"],
        "the write module reconciles the DNAT and SNAT rule sets; the "
        "two generated modules read them via DescribeNatGateway*NatRules",
    ),
    "postgresql_instance": (
        ["postgres_instance_info"],
        "postgres_instance_info (generated) reads TencentDB for PostgreSQL "
        "instances via DescribeDBInstances, the same list surface the "
        "write module reconciles against",
    ),
    "sqlserver_backup_config": (
        ['sqlserver_instance_info'],
        "DescribeDBInstances returns DBInstance BackupModel, BackupCycle, "
        "BackupCycleType, BackupSaveDays and BackupTime, the backup strategy the "
        "write module modifies",
    ),
    "ssm_parameter": (
        ['ssm_secret_info'],
        "an SSM parameter is a secret; DescribeSecret returns the named secret and "
        "ListSecrets lists every secret type (SecretType, ProductName)",
    ),
    "ssm_product_secret": (
        ['ssm_secret_info'],
        "a managed-product secret is a secret with ProductName set; ListSecrets "
        "filters on ProductName and DescribeSecret returns the named secret",
    ),
    "ssm_ssh_key_pair_secret": (
        ['ssm_secret_info'],
        "an SSH key-pair secret is a secret of that type; DescribeSecret returns "
        "the named secret and GetSSHKeyPairValue its key material",
    ),
    "tcm_mesh_clusters": (
        ['tcm_mesh_info'],
        "DescribeMeshList returns Mesh.ClusterList for every mesh, the exact "
        "cluster links the write module reconciles",
    ),
    "tcm_prometheus": (
        ['tcm_mesh_info'],
        "DescribeMeshList returns Mesh.Config.Prometheus for every mesh, the "
        "Prometheus integration the write module manages",
    ),
    "tcm_tracing": (
        ['tcm_mesh_info'],
        "DescribeMeshList returns Mesh.Config.Tracing for every mesh, the tracing "
        "config the write module manages",
    ),
    "tdmq_namespace": (
        ["tdmq_environment_info"],
        "DescribeEnvironments lists TDMQ namespaces (the API calls "
        "a namespace an environment)",
    ),
    "tdmq_namespace_role": (
        ["tdmq_environment_role_info"],
        "DescribeEnvironmentRoles lists TDMQ namespace-role "
        "bindings(EnvironmentRoleSets)",
    ),
    "tdmq_rabbitmq_binding": (
        ["tdmq_rabbit_mq_binding_info"],
        "DescribeRabbitMQBindings lists the RabbitMQ bindings the "
        "write module reconciles",
    ),
    "tdmq_rabbitmq_instance": (
        ["tdmq_rabbit_mq_vip_instance_info"],
        "DescribeRabbitMQVipInstances lists the RabbitMQ instances "
        "the write module manages",
    ),
    "tdmq_rabbitmq_permission": (
        ["tdmq_rabbit_mq_permission_info"],
        "DescribeRabbitMQPermission lists the RabbitMQ "
        "virtual-host permissions the write module manages",
    ),
    "tdmq_rabbitmq_user": (
        ["tdmq_rabbit_mq_user_info"],
        "DescribeRabbitMQUser lists the RabbitMQ users the write "
        "module manages",
    ),
    "tdmq_rabbitmq_vhost": (
        ["tdmq_rabbit_mq_virtual_host_info"],
        "DescribeRabbitMQVirtualHost lists the RabbitMQ virtual hosts "
        "the write module manages",
    ),
    "tdmq_rocketmq_cluster": (
        ["tdmq_rocket_mq_cluster_info"],
        "DescribeRocketMQClusters lists the RocketMQ clusters the "
        "write module manages",
    ),
    "tdmq_rocketmq_group": (
        ["tdmq_rocket_mq_group_info"],
        "DescribeRocketMQGroups lists the RocketMQ groups the write module "
        "manages",
    ),
    "tdmq_rocketmq_namespace": (
        ["tdmq_rocket_mq_namespace_info"],
        "DescribeRocketMQNamespaces lists the RocketMQ namespaces "
        "the write module manages",
    ),
    "tdmq_rocketmq_permission": (
        ["tdmq_rocket_mq_environment_role_info"],
        "DescribeRocketMQEnvironmentRoles lists the "
        "RocketMQ namespace-role (permission) bindings the write module "
        "reconciles",
    ),
    "tdmq_rocketmq_role": (
        ["tdmq_rocket_mq_role_info"],
        "DescribeRocketMQRoles lists the RocketMQ roles the write "
        "module manages",
    ),
    "tdmq_rocketmq_topic": (
        ["tdmq_rocket_mq_topic_info"],
        "DescribeRocketMQTopics lists the RocketMQ topics the write module "
        "manages",
    ),
    "tione_model_service_auth_token": (
        ['tione_model_service_traffic_info'],
        "DescribeModelServiceGroups returns every ServiceGroup with AuthTokens "
        "inline, the tokens the write module creates and deletes",
    ),
    "tke_cluster_deletion_protection": (
        ['tke_cluster_info'],
        "DescribeClusters returns Cluster.DeletionProtection, the flag the write "
        "module enables and disables",
    ),
    "tke_cluster_upgrade": (
        ["tke_cluster_info"],
        "DescribeClusters returns the current ClusterVersion per cluster",
    ),
    "tse_cloud_native_gateway": (
        ["tse_cloud_native_api_gateway_info"],
        "DescribeCloudNativeAPIGateways returns the cloud-native "
        "API gateways the write module manages",
    ),
    "tse_gateway_autoscaler_binding": (
        ["tse_auto_scaler_resource_strategy_binding_group_info"],
        "DescribeAutoScalerResourceStrategyBindingGroups returns "
        "the strategy-to-group bindings the write module reconciles",
    ),
    "tse_gateway_canary_rule": (
        ["tse_cloud_native_api_gateway_canary_rule_info"],
        "DescribeCloudNativeAPIGatewayCanaryRules returns the canary rules "
        "of a gateway",
    ),
    "tse_gateway_certificate": (
        ["tse_cloud_native_api_gateway_certificate_info"],
        "DescribeCloudNativeAPIGatewayCertificates returns the "
        "gateway certificates the write module manages",
    ),
    "tse_gateway_consumer": (
        ["tse_cloud_native_api_gateway_consumer_info"],
        "DescribeCloudNativeAPIGatewayConsumerList returns the "
        "gateway consumers the write module manages",
    ),
    "tse_gateway_consumer_group": (
        ["tse_cloud_native_api_gateway_consumer_group_info"],
        "DescribeCloudNativeAPIGatewayConsumerGroupList returns "
        "the gateway consumer groups the write module manages",
    ),
    "tse_gateway_model_api": (
        ["tse_cloud_native_api_gateway_llm_model_api_info"],
        "DescribeCloudNativeAPIGatewayLLMModelAPIs returns the Model "
        "API bindings the write module manages",
    ),
    "tse_gateway_model_service": (
        ["tse_cloud_native_api_gateway_llm_model_service_info"],
        "DescribeCloudNativeAPIGatewayLLMModelServices returns the "
        "Model services the write module manages",
    ),
    "tse_gateway_route": (
        ["tse_cloud_native_api_gateway_route_info"],
        "DescribeCloudNativeAPIGatewayRoutes returns the gateway "
        "routes the write module manages",
    ),
    "tse_gateway_secret_key": (
        ["tse_cloud_native_api_gateway_secret_key_info"],
        "DescribeCloudNativeAPIGatewaySecretKeyList returns the "
        "gateway secret keys the write module manages",
    ),
    "tse_gateway_server_group": (
        ["tse_native_gateway_server_group_info"],
        "DescribeNativeGatewayServerGroups returns the server groups of "
        "a gateway",
    ),
    "tse_gateway_service": (
        ["tse_cloud_native_api_gateway_service_info"],
        "DescribeCloudNativeAPIGatewayServices returns the "
        "gateway services the write module manages",
    ),
    "tse_gateway_service_source": (
        ["tse_native_gateway_service_source_info"],
        "DescribeNativeGatewayServiceSources returns the service "
        "sources the write module manages",
    ),
    "tse_governance_host_retirement": (
        ["tse_governance_instance_info"],
        "DescribeGovernanceInstances returns every governance "
        "instance with its Host and isolate state; host retirement "
        "reconciles the instances of one host",
    ),
}

# Write modules that are themselves the read surface, or whose resource has
# no list API at all; keyed by module name with the reason as value.
KNOWN_NO_LIST_API = {
    "dlc_udf_policy":
        "UDF access policy is read back through DescribeUDFPolicy with a "
        "required UDF identity; no list API enumerates UDF policies",
    "dlc_user_vpc_connection":
        "DescribeUserVpcConnection is an engine-network-scoped detail "
        "call returning an unpaginated connection list; no free-standing "
        "list API exists",
    "monitor_prometheus_global_notification":
        "DescribePrometheusGlobalNotification is a per-instance singleton "
        "read (requires InstanceId); no list API exists. The Describe/Modify "
        "APIs were marked for retirement on 2026-05-25; use alert groups "
        "and receivers for new configurations",
    "oceanus_folder":
        "folders form an organizational tree read through "
        "DescribeTreeJobs/DescribeTreeResources scoped to a WorkSpaceId; "
        "no flat list API exists",
    "oceanus_meta_table":
        "GetMetaTable returns one meta table by composite identity; no "
        "list API enumerates meta tables",
    "teo_security_bot_lite":
        "DescribeSecurityPolicy returns the per-zone security policy with "
        "the bot-lite settings inline; no list API enumerates them alone",
    "teo_security_custom_rules":
        "DescribeSecurityPolicy returns the per-zone security policy with "
        "the custom-rule set inline; no list API enumerates custom rules "
        "alone",
    "teo_security_exception_rules":
        "DescribeSecurityPolicy returns the per-zone security policy with "
        "the exception-rule set inline; no list API enumerates exception "
        "rules alone",
    "teo_security_managed_rules":
        "DescribeSecurityPolicy returns the per-zone security policy with "
        "the managed-rule set inline; no list API enumerates managed rules "
        "alone",
    "teo_security_rate_limiting_rules":
        "DescribeSecurityPolicy returns the per-zone security policy with "
        "the rate-limiting rule set inline; no list API enumerates "
        "rate-limiting rules alone",
    "teo_security_template_binding":
        "DescribeSecurityTemplateBindings returns the template-to-entity "
        "bindings keyed by a template; no list API exists",
    "teo_web_security_template":
        "DescribeWebSecurityTemplates is a template-detail call keyed by "
        "TemplateId; no list API enumerates templates",
    "tke_cluster_kubeconfig":
        "kubeconfig is a per-cluster credential "
        "fetch(DescribeClusterKubeconfig requires a ClusterId); the "
        "module itself is the read surface",
    "tke_addon":
        "DescribeAddon is a per-cluster/per-addon detail call (requires "
        "ClusterId and Name); no list API enumerates addons",
    "tke_backup_storage_location":
        "DescribeBackupStorageLocations returns the cluster's configured "
        "backup-storage locations (unpaginated detail); no list API "
        "exists",
    "tke_cluster_audit":
        "audit log switches are per-cluster state read via "
        "DescribeLogSwitches (requires ClusterId); no list API exists",
    "tke_cluster_authentication":
        "DescribeClusterAuthenticationOptions is a per-cluster singleton "
        "read (requires ClusterId); no list API exists",
    "tke_cluster_endpoint":
        "DescribeClusterEndpoints is a per-cluster singleton read "
        "(requires ClusterId); no list API exists",
    "tse_config_file":
        "config files are scoped to a group and read individually via "
        "DescribeConfigFile (requires a config file id); no free-standing "
        "list API exists",
    "tse_config_file_deployment":
        "deployment is the atomic create of a config file plus release; "
        "its read side is DescribeConfigFileRelease, keyed by release id, "
        "no list API exists",
    "tse_gateway_autoscaler_strategy":
        "DescribeAutoScalerResourceStrategies is a strategy-detail call "
        "keyed by strategy id; no list API exists",
    "tse_gateway_console_network":
        "console network access is part of the per-gateway "
        "DescribeCloudNativeAPIGatewayConfig singleton; no list API "
        "exists",
    "tse_gateway_consumer_group_membership":
        "consumer-group membership is an association; "
        "DescribeCloudNativeAPIGatewayConsumerGroup (group detail) is the "
        "only read, no list API exists",
    "tse_gateway_cors":
        "CORS is a per-gateway singleton read via "
        "DescribeCloudNativeAPIGatewayCORS (requires GatewayId); no list "
        "API exists",
    "tse_gateway_ip_restriction":
        "IP access control is a per-gateway singleton read via "
        "DescribeCloudNativeAPIGatewayIPRestriction (requires GatewayId); "
        "no list API exists",
    "tse_gateway_model_api_group_auth":
        "Model API consumer-group authorization is read from each API "
        "detail (DescribeCloudNativeAPIGatewayLLMModelAPI); no list API "
        "enumerates the bindings",
    "tse_gateway_public_network":
        "public network access is a per-gateway/per-group detail read via "
        "DescribePublicNetwork; no list API exists",
    "tse_gateway_rate_limit":
        "rate limiting is a per-service/per-route singleton detail read "
        "(DescribeCloudNativeAPIGateway*RateLimit); no list API exists",
    "tse_gateway_upstream_node_status":
        "upstream node health is read through "
        "DescribeCloudNativeAPIGatewayUpstream keyed by gateway; no list "
        "API exists",
    "tse_gateway_waf_domains":
        "WAF domains are returned by the per-gateway DescribeWafDomains "
        "singleton; no list API exists",
    "tse_gateway_waf_protection":
        "WAF protection state is a per-gateway singleton detail "
        "(DescribeWafProtection); no list API exists",
    "waf_area_ban_rule":
        "DescribeAreaBanRule is a per-domain singleton rule read "
        "(requires Domain); no list API exists",
    "waf_auto_deny":
        "DescribeWafAutoDenyRules is a per-domain singleton auto-deny "
        "config read (requires Domain); no list API exists",
    "waf_ip_access_control":
        "DescribeIpAccessControl is a per-domain access-control read with "
        "non-standard paging; no supported list API exists",
    "waf_protect_group":
        "DescribeProtectGroup is a per-domain protection-group detail "
        "read; no supported list API exists",
    "waf_threat_intelligence":
        "DescribeWafThreatenIntelligence returns the per-domain singleton "
        "threat-intel feed config; no list API exists",
}

# Coverage backlog: write modules whose read surface is not wired up yet.
# Each name here is a known gap, reported by the audit and accepted by
# --check; close a gap by adding a SPECS entry (preferred) or a curated
# KNOWN_COVERAGE mapping, and remove the name from this set.
#
# Empty since 1.5.0: the last 28 gaps were closed by 13 curated
# ``info_specs_targets.py`` entries (each verified against the SDK response
# shape), 14 ``KNOWN_COVERAGE`` mappings onto an existing ``_info`` module
# that already returns the resource, and one hand-written module
# (``gaap_layer4_listener_info``) for the one resource whose list API is
# split across two sibling actions. A new write module must therefore be
# covered on arrival -- this set is not a parking lot.
KNOWN_GAPS = set()


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
        gap_tables & set(KNOWN_COVERAGE)
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
