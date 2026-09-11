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
    "cos_object_sync": (
        ["cos_object_info"],
        "cos_object_info lists and filters the objects of a bucket,"
        "whichis the read side a sync reconciles against",
    ),
    "cvm_disaster_recover_group_binding": (
        ["cvm_disaster_recover_group_info"],
        "DescribeDisasterRecoverGroups returns the InstanceIds bound"
        "toeach placement group, the exact set the write module"
        "reconciles",
    ),
    "cvm_instance_security_group": (
        ["cvm_instance_info"],
        "DescribeInstances returns SecurityGroupIds per instance",
    ),
    "dlc_data_engine_config": (
        ["dlc_user_data_engine_config_info"],
        "DescribeUserDataEngineConfig returns"
        "theDataEngineConfigInstanceInfos the write module reconciles",
    ),
    "dlc_engine_resource_group": (
        ["dlc_standard_engine_resource_group_info"],
        "DescribeStandardEngineResourceGroups returns the"
        "standard-engineresource groups the write module manages",
    ),
    "dlc_spark_job": (
        ["dlc_spark_app_job_info"],
        "DescribeSparkAppJobs lists the SparkAppJob definitions the"
        "writemodule creates and updates",
    ),
    "dlc_user_policy": (
        ["dlc_user_info"],
        "DescribeUsers returns each user with its attached"
        "PolicySetinline, the exact set dlc_user_policy reconciles",
    ),
    "dlc_work_group_membership": (
        ["dlc_work_group_info"],
        "DescribeWorkGroups returns each group with its bound"
        "users(WorkGroupInfo.UserSet) inline",
    ),
    "dlc_work_group_policy": (
        ["dlc_work_group_info"],
        "DescribeWorkGroups returns each group with its attachedPolicySet"
        "(WorkGroupInfo.PolicySet) inline",
    ),
    "havip_association": (
        ["havip_info"],
        "DescribeHaVips returns the HaVipAssociationSet with boundCVM/ENI"
        "per HAVIP",
    ),
    "monitor_alarm_policy_notice": (
        ["monitor_alarm_policy_info"],
        "DescribeAlarmPolicies returns each policy with its"
        "NoticeIds, HierarchicalNotices and"
        "NoticeContentTmplBindInfos inline, the exact bindings"
        "monitor_alarm_policy_notice reconciles",
    ),
    "monitor_grafana_internet": (
        ["monitor_grafana_instance_info"],
        "DescribeGrafanaInstances returns InternetUrl per instance,"
        "the exact state monitor_grafana_internet toggles",
    ),
    "nat_gateway_rule": (
        ["nat_gateway_dnat_rule_info", "nat_gateway_snat_rule_info"],
        "the write module reconciles the DNAT and SNAT rule sets; the"
        "twogenerated modules read them via DescribeNatGateway*NatRules",
    ),
    "postgresql_instance": (
        ["postgres_instance_info"],
        "postgres_instance_info (generated) reads TencentDB forPostgreSQL"
        "instances via DescribeDBInstances, the same listsurface the"
        "write module reconciles against",
    ),
    "tdmq_namespace": (
        ["tdmq_environment_info"],
        "DescribeEnvironments lists TDMQ namespaces (the API calls"
        "anamespace an environment)",
    ),
    "tdmq_namespace_role": (
        ["tdmq_environment_role_info"],
        "DescribeEnvironmentRoles lists TDMQ namespace-role"
        "bindings(EnvironmentRoleSets)",
    ),
    "tdmq_rabbitmq_binding": (
        ["tdmq_rabbit_mq_binding_info"],
        "DescribeRabbitMQBindings lists the RabbitMQ bindings the"
        "writemodule reconciles",
    ),
    "tdmq_rabbitmq_instance": (
        ["tdmq_rabbit_mq_vip_instance_info"],
        "DescribeRabbitMQVipInstances lists the RabbitMQ instances"
        "thewrite module manages",
    ),
    "tdmq_rabbitmq_permission": (
        ["tdmq_rabbit_mq_permission_info"],
        "DescribeRabbitMQPermission lists the RabbitMQ"
        "virtual-hostpermissions the write module manages",
    ),
    "tdmq_rabbitmq_user": (
        ["tdmq_rabbit_mq_user_info"],
        "DescribeRabbitMQUser lists the RabbitMQ users the write"
        "modulemanages",
    ),
    "tdmq_rabbitmq_vhost": (
        ["tdmq_rabbit_mq_virtual_host_info"],
        "DescribeRabbitMQVirtualHost lists the RabbitMQ virtual hosts"
        "thewrite module manages",
    ),
    "tdmq_rocketmq_cluster": (
        ["tdmq_rocket_mq_cluster_info"],
        "DescribeRocketMQClusters lists the RocketMQ clusters the"
        "writemodule manages",
    ),
    "tdmq_rocketmq_group": (
        ["tdmq_rocket_mq_group_info"],
        "DescribeRocketMQGroups lists the RocketMQ groups the writemodule"
        "manages",
    ),
    "tdmq_rocketmq_namespace": (
        ["tdmq_rocket_mq_namespace_info"],
        "DescribeRocketMQNamespaces lists the RocketMQ namespaces"
        "thewrite module manages",
    ),
    "tdmq_rocketmq_permission": (
        ["tdmq_rocket_mq_environment_role_info"],
        "DescribeRocketMQEnvironmentRoles lists the"
        "RocketMQnamespace-role (permission) bindings the write module"
        "reconciles",
    ),
    "tdmq_rocketmq_role": (
        ["tdmq_rocket_mq_role_info"],
        "DescribeRocketMQRoles lists the RocketMQ roles the write"
        "modulemanages",
    ),
    "tdmq_rocketmq_topic": (
        ["tdmq_rocket_mq_topic_info"],
        "DescribeRocketMQTopics lists the RocketMQ topics the writemodule"
        "manages",
    ),
    "tke_cluster_upgrade": (
        ["tke_cluster_info"],
        "DescribeClusters returns the current ClusterVersion per cluster",
    ),
    "tse_cloud_native_gateway": (
        ["tse_cloud_native_api_gateway_info"],
        "DescribeCloudNativeAPIGateways returns the cloud-native"
        "APIgateways the write module manages",
    ),
    "tse_gateway_autoscaler_binding": (
        ["tse_auto_scaler_resource_strategy_binding_group_info"],
        "DescribeAutoScalerResourceStrategyBindingGroups returns"
        "thestrategy-to-group bindings the write module reconciles",
    ),
    "tse_gateway_canary_rule": (
        ["tse_cloud_native_api_gateway_canary_rule_info"],
        "DescribeCloudNativeAPIGatewayCanaryRules returns the canaryrules"
        "of a gateway",
    ),
    "tse_gateway_certificate": (
        ["tse_cloud_native_api_gateway_certificate_info"],
        "DescribeCloudNativeAPIGatewayCertificates returns the"
        "gatewaycertificates the write module manages",
    ),
    "tse_gateway_consumer": (
        ["tse_cloud_native_api_gateway_consumer_info"],
        "DescribeCloudNativeAPIGatewayConsumerList returns the"
        "gatewayconsumers the write module manages",
    ),
    "tse_gateway_consumer_group": (
        ["tse_cloud_native_api_gateway_consumer_group_info"],
        "DescribeCloudNativeAPIGatewayConsumerGroupList returns"
        "thegateway consumer groups the write module manages",
    ),
    "tse_gateway_model_api": (
        ["tse_cloud_native_api_gateway_llm_model_api_info"],
        "DescribeCloudNativeAPIGatewayLLMModelAPIs returns the Model"
        "APIbindings the write module manages",
    ),
    "tse_gateway_model_service": (
        ["tse_cloud_native_api_gateway_llm_model_service_info"],
        "DescribeCloudNativeAPIGatewayLLMModelServices returns the"
        "Modelservices the write module manages",
    ),
    "tse_gateway_route": (
        ["tse_cloud_native_api_gateway_route_info"],
        "DescribeCloudNativeAPIGatewayRoutes returns the gateway"
        "routesthe write module manages",
    ),
    "tse_gateway_secret_key": (
        ["tse_cloud_native_api_gateway_secret_key_info"],
        "DescribeCloudNativeAPIGatewaySecretKeyList returns the"
        "gatewaysecret keys the write module manages",
    ),
    "tse_gateway_server_group": (
        ["tse_native_gateway_server_group_info"],
        "DescribeNativeGatewayServerGroups returns the server groups of"
        "agateway",
    ),
    "tse_gateway_service": (
        ["tse_cloud_native_api_gateway_service_info"],
        "DescribeCloudNativeAPIGatewayServices returns the"
        "gatewayservices the write module manages",
    ),
    "tse_gateway_service_source": (
        ["tse_native_gateway_service_source_info"],
        "DescribeNativeGatewayServiceSources returns the service"
        "sourcesthe write module manages",
    ),
    "tse_governance_host_retirement": (
        ["tse_governance_instance_info"],
        "DescribeGovernanceInstances returns every governance"
        "instancewith its Host and isolate state; host retirement"
        "reconciles theinstances of one host",
    ),
}

# Write modules that are themselves the read surface, or whose resource has
# no list API at all; keyed by module name with the reason as value.
KNOWN_NO_LIST_API = {
    "config_aggregate_delivery":
        "DescribeAggregateConfigDeliver returns the account's single"
        "aggregate-delivery config (detail call, no pagination); no"
        "free-standing list API enumerates delivery channels",
    "config_delivery":
        "DescribeConfigDeliver returns the account's single delivery"
        "channel (unpaginated singleton); no list API exists",
    "config_recorder":
        "DescribeConfigRecorder returns the region's single"
        "ConfigurationRecorder (Status plus the monitored"
        "UserConfigResource list); no list API enumerates recorders",
    "cos_bucket_domain":
        "COS bucket custom domain config is a bucket sub-resource read"
        "through the bucket-scoped GET API in module_utils.cos; no"
        "tencentcloud SDK list action exists",
    "cos_bucket_domain_certificate":
        "COS bucket domain certificate is a bucket sub-resource read"
        "through the bucket-scoped GET API in module_utils.cos; no"
        "tencentcloud SDK list action exists",
    "cos_bucket_encryption":
        "COS bucket default encryption is a bucket sub-resource read"
        "through the bucket-scoped GET API in module_utils.cos; no"
        "tencentcloud SDK list action exists",
    "cos_bucket_intelligent_tiering":
        "COS bucket intelligent-tiering config is a bucket sub-resource"
        "read through the bucket-scoped GET API in module_utils.cos; no"
        "tencentcloud SDK list action exists",
    "cos_bucket_inventory":
        "COS bucket inventory config is a bucket sub-resource read"
        "through the bucket-scoped GET API in module_utils.cos; no"
        "tencentcloud SDK list action exists",
    "cos_bucket_logging":
        "COS bucket logging config is a bucket sub-resource read through"
        "the bucket-scoped GET API in module_utils.cos; no tencentcloud"
        "SDK list action exists",
    "cos_bucket_object_lock":
        "COS bucket object-lock config is a bucket sub-resource read"
        "through the bucket-scoped GET API in module_utils.cos; no"
        "tencentcloud SDK list action exists",
    "cos_bucket_origin":
        "COS bucket origin-pull config is a bucket sub-resource read"
        "through the bucket-scoped GET API in module_utils.cos; no"
        "tencentcloud SDK list action exists",
    "cos_bucket_policy":
        "COS bucket policy is a bucket sub-resource read through the"
        "bucket-scoped GET API in module_utils.cos; no tencentcloud SDK"
        "list action exists",
    "cos_bucket_referer":
        "COS bucket referer config is a bucket sub-resource read through"
        "the bucket-scoped GET API in module_utils.cos; no tencentcloud"
        "SDK list action exists",
    "cos_bucket_replication":
        "COS bucket replication config is a bucket sub-resource read"
        "through the bucket-scoped GET API in module_utils.cos; no"
        "tencentcloud SDK list action exists",
    "cos_bucket_response_control":
        "COS bucket response-header config is a bucket sub-resource read"
        "through the bucket-scoped GET API in module_utils.cos; no"
        "tencentcloud SDK list action exists",
    "cos_bucket_website":
        "COS bucket static-website config is a bucket sub-resource read"
        "through the bucket-scoped GET API in module_utils.cos; no"
        "tencentcloud SDK list action exists",
    "dlc_udf_policy":
        "UDF access policy is read back through DescribeUDFPolicy with a"
        "required UDF identity; no list API enumerates UDF policies",
    "dlc_user_vpc_connection":
        "DescribeUserVpcConnection is an engine-network-scoped detail"
        "call returning an unpaginated connection list; no free-standing"
        "list API exists",
    "monitor_grafana_integration":
        "DescribeGrafanaIntegrations is an instance-scoped unpaginated"
        "detail call (requires InstanceId); no free-standing list API"
        "exists",
    "monitor_grafana_whitelist":
        "DescribeGrafanaWhiteList is an instance-scoped singleton"
        "returning the allowed-IP list (requires InstanceId); no list"
        "API exists",
    "monitor_prometheus_alertmanager_config":
        "DescribePrometheusAlertmanagerConfig is a per-instance singleton"
        "read (requires InstanceId); no list API exists",
    "monitor_prometheus_global_notification":
        "DescribePrometheusGlobalNotification is a per-instance singleton"
        "read (requires InstanceId); no list API exists",
    "oceanus_folder":
        "folders form an organizational tree read through"
        "DescribeTreeJobs/DescribeTreeResources scoped to a WorkSpaceId;"
        "no flat list API exists",
    "oceanus_meta_table":
        "GetMetaTable returns one meta table by composite identity; no"
        "list API enumerates meta tables",
    "teo_security_bot_lite":
        "DescribeSecurityPolicy returns the per-zone security policy with"
        "the bot-lite settings inline; no list API enumerates them alone",
    "teo_security_custom_rules":
        "DescribeSecurityPolicy returns the per-zone security policy with"
        "the custom-rule set inline; no list API enumerates custom rules"
        "alone",
    "teo_security_exception_rules":
        "DescribeSecurityPolicy returns the per-zone security policy with"
        "the exception-rule set inline; no list API enumerates exception"
        "rules alone",
    "teo_security_managed_rules":
        "DescribeSecurityPolicy returns the per-zone security policy with"
        "the managed-rule set inline; no list API enumerates managed rules"
        "alone",
    "teo_security_rate_limiting_rules":
        "DescribeSecurityPolicy returns the per-zone security policy with"
        "the rate-limiting rule set inline; no list API enumerates"
        "rate-limiting rules alone",
    "teo_security_template_binding":
        "DescribeSecurityTemplateBindings returns the template-to-entity"
        "bindings keyed by a template; no list API exists",
    "teo_web_security_template":
        "DescribeWebSecurityTemplates is a template-detail call keyed by"
        "TemplateId; no list API enumerates templates",
    "tke_cluster_kubeconfig":
        "kubeconfig is a per-cluster credential"
        "fetch(DescribeClusterKubeconfig requires a ClusterId); the"
        "moduleitself is the read surface",
    "tke_addon":
        "DescribeAddon is a per-cluster/per-addon detail call (requires"
        "ClusterId and Name); no list API enumerates addons",
    "tke_backup_storage_location":
        "DescribeBackupStorageLocations returns the cluster's configured"
        "backup-storage locations (unpaginated detail); no list API"
        "exists",
    "tke_cluster_audit":
        "audit log switches are per-cluster state read via"
        "DescribeLogSwitches (requires ClusterId); no list API exists",
    "tke_cluster_authentication":
        "DescribeClusterAuthenticationOptions is a per-cluster singleton"
        "read (requires ClusterId); no list API exists",
    "tke_cluster_endpoint":
        "DescribeClusterEndpoints is a per-cluster singleton read"
        "(requires ClusterId); no list API exists",
    "tse_config_file":
        "config files are scoped to a group and read individually via"
        "DescribeConfigFile (requires a config file id); no free-standing"
        "list API exists",
    "tse_config_file_deployment":
        "deployment is the atomic create of a config file plus release;"
        "its read side is DescribeConfigFileRelease, keyed by release id,"
        "no list API exists",
    "tse_gateway_autoscaler_strategy":
        "DescribeAutoScalerResourceStrategies is a strategy-detail call"
        "keyed by strategy id; no list API exists",
    "tse_gateway_console_network":
        "console network access is part of the per-gateway"
        "DescribeCloudNativeAPIGatewayConfig singleton; no list API"
        "exists",
    "tse_gateway_consumer_group_membership":
        "consumer-group membership is an association;"
        "DescribeCloudNativeAPIGatewayConsumerGroup (group detail) is the"
        "only read, no list API exists",
    "tse_gateway_cors":
        "CORS is a per-gateway singleton read via"
        "DescribeCloudNativeAPIGatewayCORS (requires GatewayId); no list"
        "API exists",
    "tse_gateway_ip_restriction":
        "IP access control is a per-gateway singleton read via"
        "DescribeCloudNativeAPIGatewayIPRestriction (requires GatewayId);"
        "no list API exists",
    "tse_gateway_model_api_group_auth":
        "Model API consumer-group authorization is read from each API"
        "detail (DescribeCloudNativeAPIGatewayLLMModelAPI); no list API"
        "enumerates the bindings",
    "tse_gateway_public_network":
        "public network access is a per-gateway/per-group detail read via"
        "DescribePublicNetwork; no list API exists",
    "tse_gateway_rate_limit":
        "rate limiting is a per-service/per-route singleton detail read"
        "(DescribeCloudNativeAPIGateway*RateLimit); no list API exists",
    "tse_gateway_upstream_node_status":
        "upstream node health is read through"
        "DescribeCloudNativeAPIGatewayUpstream keyed by gateway; no list"
        "API exists",
    "tse_gateway_waf_domains":
        "WAF domains are returned by the per-gateway DescribeWafDomains"
        "singleton; no list API exists",
    "tse_gateway_waf_protection":
        "WAF protection state is a per-gateway singleton detail"
        "(DescribeWafProtection); no list API exists",
    "waf_area_ban_rule":
        "DescribeAreaBanRule is a per-domain singleton rule read"
        "(requires Domain); no list API exists",
    "waf_auto_deny":
        "DescribeWafAutoDenyRules is a per-domain singleton auto-deny"
        "config read (requires Domain); no list API exists",
    "waf_ip_access_control":
        "DescribeIpAccessControl is a per-domain access-control read with"
        "non-standard paging; no supported list API exists",
    "waf_protect_group":
        "DescribeProtectGroup is a per-domain protection-group detail"
        "read; no supported list API exists",
    "waf_threat_intelligence":
        "DescribeWafThreatenIntelligence returns the per-domain singleton"
        "threat-intel feed config; no list API exists",
}

# Coverage backlog: write modules whose read surface is not wired up yet.
# Each name here is a known gap, reported by the audit and accepted by
# --check; close a gap by adding a SPECS entry (preferred) or a curated
# KNOWN_COVERAGE mapping, and remove the name from this set.
KNOWN_GAPS = {
    'api_gateway_api_key',
    'api_gateway_service_release',
    'api_gateway_usage_plan',
    'api_gateway_usage_plan_binding',
    'api_gateway_usage_plan_key_binding',
    'as_scaling_policy',
    'as_scheduled_action',
    'cbs_disk_backup',
    'cbs_snapshot_share',
    'cdn_cls_log_topic',
    'cdwch_backup_config',
    'cdwch_instance',
    'cdwch_parameter',
    'cdwdoris_cooldown_policy',
    'cdwdoris_instance',
    'cdwdoris_user_workload_group',
    'cdwdoris_workload_group',
    'cdwpg_hba_config',
    'cdwpg_instance',
    'cdwpg_parameter',
    'cfw_address_template',
    'cfw_internet_acl_rule',
    'cfw_nat_acl_rule',
    'cfw_nat_dnat_rule',
    'cfw_vpc_acl_rule',
    'chdfs_access_group',
    'chdfs_access_rules',
    'chdfs_mount_access_groups',
    'chdfs_mount_point',
    'ckafka_acl',
    'ckafka_acl_rule',
    'ckafka_datahub_connection',
    'ckafka_datahub_task',
    'ckafka_datahub_topic',
    'ckafka_route',
    'cloudaudit_audit',
    'cloudaudit_track',
    'cmq_subscription',
    'cmq_topic',
    'cynosdb_account_privilege',
    'dbbrain_sql_filter',
    'dcdb_account',
    'dcdb_account_privilege',
    'dcdb_backup_config',
    'dcdb_security_config',
    'dnspod_custom_line',
    'dnspod_domain',
    'dnspod_line_group',
    'dts_consumer_group',
    'dts_migration_action',
    'dts_migration_check',
    'dts_migration_job',
    'dts_migration_job_config',
    'eb_connection',
    'eb_rule',
    'eb_target',
    'elasticsearch_index',
    'elasticsearch_snapshot',
    'emr_auto_scale_strategy',
    'emr_cluster',
    'gaap_layer4_listener',
    'gaap_listener_real_servers',
    'gaap_real_server',
    'goosefs_fileset',
    'gwlb_load_balancer',
    'gwlb_target_group',
    'gwlb_target_group_association',
    'gwlb_target_group_instances',
    'mariadb_account_privilege',
    'mqtt_authorization_policy',
    'mqtt_instance',
    'mqtt_topic',
    'mqtt_user',
    'organization_member_identity',
    'organization_member_policy',
    'organization_node',
    'private_dns_account',
    'private_dns_record',
    'private_dns_zone',
    'privatelink_endpoint',
    'privatelink_endpoint_service',
    'sqlserver_backup_config',
    'ssm_parameter',
    'ssm_product_secret',
    'ssm_ssh_key_pair_secret',
    'tat_invoker',
    'tcb_auth_domain',
    'tcb_environment',
    'tcb_http_service_route',
    'tcb_static_store',
    'tcm_access_log',
    'tcm_mesh_clusters',
    'tcm_prometheus',
    'tcm_tracing',
    'tdcpg_account',
    'tdcpg_endpoint_wan',
    'tdcpg_instance_state',
    'tdmysql_account_privilege',
    'tdmysql_maintenance_window',
    'tdmysql_ssl',
    'tem_application_deployment',
    'tem_application_service',
    'tem_environment',
    'tione_model_service_auth_token',
    'tione_model_service_state',
    'tione_model_service_traffic',
    'trabbit_serverless_binding',
    'trabbit_serverless_exchange',
    'trabbit_serverless_permission',
    'trabbit_serverless_queue',
    'trabbit_serverless_user',
    'trabbit_serverless_vhost',
    # theme #1 batch (roadmap #77-#84): read surface not wired up yet;
    # promote to _info (or KNOWN_COVERAGE) once SDK discovery confirms an API.
    'apigateway_api_app',
    'apigateway_ip_strategy',
    'apigateway_plugin',
    'cdb_audit_rule',
    'cdb_audit_rule_template',
    'clb_snat_ip',
    'cls_alarm',
    'cls_alarm_notice',
    'redis_replication_group',
    'scf_custom_domain',
    'tcr_immutable_tag_rule',
    'tcr_webhook_trigger',
    'tke_cls_log_config',
    'tke_cluster_deletion_protection',
    'tke_cluster_route',
    'tke_cluster_route_table',
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
