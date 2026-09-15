# -*- coding: utf-8 -*-
"""Curated ``_info`` targets that close the read-surface backlog.

``scripts/discover_info_specs.py`` proposes **one** list action per SDK
product: it scores every ``Describe*``/``List*`` method of a product and
keeps the best. That is the right default for a product with a single
obvious list API, but it systematically under-covers products where many
resources live behind their own list API -- exactly the products the
read-surface backlog (``scripts/gap_backlog.py``) reports as the worst
offenders: apigateway, ckafka, trabbit, cfw, dts.

This table names, per write module, the SDK action that really returns
that resource. It is reviewed by hand and every entry is verified against
the installed SDK at generation time: an action that disappears, or a
request/response shape that no longer carries an items list, is reported
as a skip instead of silently producing a module that returns nothing.

The value is either the action name (the resource name is then derived
from the write module) or a dict with ``action`` and ``resource`` when the
derived name would read badly (``elasticsearch_index`` -> ``index``).

Adding an entry here is how a read-surface gap is closed: run
``python scripts/discover_info_specs.py`` and
``python scripts/generate_info_modules.py``, then drop the module from
``KNOWN_GAPS`` in ``scripts/audit_info_coverage.py``.

Unmanaged request fields are turned into ``extra_params`` (see
``_extra_params`` in the discovery script), so a list API that is scoped
to a parent -- ``DescribeAccessRules(AccessGroupId)`` -- is expressible
rather than rejected.
"""

from __future__ import absolute_import, division, print_function

# ``version_added`` stamped on every module generated from this table. It
# doubles as the marker ``scripts/check_info_targets.py`` uses to prove the
# generated specs and this table still agree, so it lives here next to the
# targets rather than in the discovery script.
TARGET_VERSION_ADDED = "1.5.0"

TARGETS = {
    # --- apigateway -----------------------------------------------------
    "api_gateway_api_key": "DescribeApiKeysStatus",
    "api_gateway_service_release": "DescribeServiceEnvironmentReleaseHistory",
    "api_gateway_usage_plan": "DescribeUsagePlansStatus",
    "api_gateway_usage_plan_binding": "DescribeServiceUsagePlan",
    "api_gateway_usage_plan_key_binding": "DescribeUsagePlanSecretIds",
    "apigateway_api_app": "DescribeApiAppsStatus",
    "apigateway_ip_strategy": "DescribeIPStrategysStatus",
    "apigateway_plugin": "DescribePlugins",
    # --- ckafka ---------------------------------------------------------
    "ckafka_acl": "DescribeACL",
    "ckafka_acl_rule": "DescribeAclRule",
    "ckafka_datahub_connection": {
        "action": "DescribeConnectResources",
        "resource": "datahub_connection",
    },
    "ckafka_datahub_task": "DescribeDatahubTasks",
    "ckafka_datahub_topic": "DescribeDatahubTopics",
    "ckafka_route": "DescribeRoute",
    # --- trabbit --------------------------------------------------------
    "trabbit_serverless_binding": {
        "action": "DescribeRabbitMQServerlessBindings",
        "resource": "serverless_binding",
    },
    "trabbit_serverless_exchange": {
        "action": "DescribeRabbitMQServerlessExchanges",
        "resource": "serverless_exchange",
    },
    "trabbit_serverless_permission": {
        "action": "DescribeRabbitMQServerlessPermission",
        "resource": "serverless_permission",
    },
    "trabbit_serverless_queue": {
        "action": "DescribeRabbitMQServerlessQueues",
        "resource": "serverless_queue",
    },
    "trabbit_serverless_user": {
        "action": "DescribeRabbitMQServerlessUser",
        "resource": "serverless_user",
    },
    "trabbit_serverless_vhost": {
        "action": "DescribeRabbitMQServerlessVirtualHost",
        "resource": "serverless_vhost",
    },
    # --- autoscaling ----------------------------------------------------
    "as_scaling_policy": "DescribeScalingPolicies",
    "as_scheduled_action": "DescribeScheduledActions",
    # --- cbs ------------------------------------------------------------
    "cbs_disk_backup": "DescribeDiskBackups",
    "cbs_snapshot_share": "DescribeSnapshotSharePermission",
    # --- cdb ------------------------------------------------------------
    "cdb_audit_rule": "DescribeAuditRules",
    "cdb_audit_rule_template": "DescribeAuditRuleTemplates",
    # --- cdn ------------------------------------------------------------
    "cdn_cls_log_topic": "ListClsLogTopics",
    # --- cdwch ----------------------------------------------------------
    "cdwch_instance": "DescribeCNInstances",
    # --- cdwdoris -------------------------------------------------------
    "cdwdoris_cooldown_policy": "DescribeCoolDownPolicies",
    "cdwdoris_instance": "DescribeInstances",
    "cdwdoris_user_workload_group": "DescribeUserBindWorkloadGroup",
    "cdwdoris_workload_group": "DescribeWorkloadGroup",
    # --- cdwpg ----------------------------------------------------------
    "cdwpg_hba_config": "DescribeUserHbaConfig",
    "cdwpg_instance": "DescribeInstances",
    # --- cfw ------------------------------------------------------------
    "cfw_address_template": "DescribeAddressTemplateList",
    "cfw_nat_dnat_rule": "DescribeNatFwDnatRule",
    # --- chdfs ----------------------------------------------------------
    "chdfs_access_group": "DescribeAccessGroups",
    "chdfs_access_rules": "DescribeAccessRules",
    "chdfs_mount_point": "DescribeMountPoints",
    # --- cloudaudit -----------------------------------------------------
    "cloudaudit_audit": "ListAudits",
    "cloudaudit_track": "DescribeAuditTracks",
    # --- cls ------------------------------------------------------------
    "cls_alarm": "DescribeAlarms",
    "cls_alarm_notice": "DescribeAlarmNotices",
    # --- cmq (tdmq) -----------------------------------------------------
    "cmq_topic": "DescribeCmqTopics",
    # --- cynosdb --------------------------------------------------------
    "cynosdb_account_privilege": "DescribeAccountPrivileges",
    # --- dbbrain --------------------------------------------------------
    "dbbrain_sql_filter": "DescribeSqlFilters",
    # --- dcdb -----------------------------------------------------------
    "dcdb_account": "DescribeAccounts",
    "dcdb_account_privilege": "DescribeAccountPrivileges",
    "dcdb_backup_config": "DescribeBackupConfigs",
    # --- dnspod ---------------------------------------------------------
    "dnspod_custom_line": "DescribeDomainCustomLineList",
    "dnspod_domain": "DescribeDomainList",
    "dnspod_line_group": "DescribeLineGroupList",
    # --- dts ------------------------------------------------------------
    "dts_consumer_group": "DescribeConsumerGroups",
    "dts_migration_check": "DescribeMigrationCheckJob",
    "dts_migration_job": "DescribeMigrationJobs",
    # --- eb -------------------------------------------------------------
    "eb_connection": "ListConnections",
    "eb_rule": "ListRules",
    "eb_target": "ListTargets",
    # --- es -------------------------------------------------------------
    "elasticsearch_index": {"action": "DescribeIndexList", "resource": "index"},
    # --- emr ------------------------------------------------------------
    "emr_auto_scale_strategy": "DescribeAutoScaleStrategies",
    # --- gaap -----------------------------------------------------------
    "gaap_listener_real_servers": "DescribeListenerRealServers",
    "gaap_real_server": "DescribeRealServers",
    # --- goosefs --------------------------------------------------------
    "goosefs_fileset": "DescribeFilesets",
    # --- gwlb -----------------------------------------------------------
    "gwlb_load_balancer": "DescribeGatewayLoadBalancers",
    "gwlb_target_group": "DescribeTargetGroups",
    "gwlb_target_group_instances": "DescribeTargetGroupInstances",
    # --- mariadb --------------------------------------------------------
    "mariadb_account_privilege": "DescribeAccountPrivileges",
    # --- mqtt -----------------------------------------------------------
    "mqtt_authorization_policy": "DescribeAuthorizationPolicies",
    "mqtt_instance": "DescribeInstanceList",
    "mqtt_topic": "DescribeTopicList",
    "mqtt_user": "DescribeUserList",
    # --- organization ---------------------------------------------------
    "organization_member_identity": "DescribeOrganizationMemberAuthIdentities",
    "organization_member_policy": "DescribeOrganizationMemberPolicies",
    "organization_node": "DescribeOrganizationNodes",
    # --- privatedns -----------------------------------------------------
    "private_dns_account": "DescribePrivateDNSAccountList",
    "private_dns_record": "DescribePrivateZoneRecordList",
    "private_dns_zone": "DescribePrivateZoneList",
    # --- privatelink (vpc) ----------------------------------------------
    "privatelink_endpoint": "DescribeVpcEndPoint",
    "privatelink_endpoint_service": "DescribeVpcEndPointService",
    # --- redis ----------------------------------------------------------
    "redis_replication_group": "DescribeReplicationGroup",
    # --- scf ------------------------------------------------------------
    "scf_custom_domain": "ListCustomDomains",
    # --- tat ------------------------------------------------------------
    "tat_invoker": "DescribeInvokers",
    # --- tcb ------------------------------------------------------------
    "tcb_auth_domain": "DescribeAuthDomains",
    "tcb_environment": "DescribeEnvs",
    "tcb_http_service_route": "DescribeHTTPServiceRoute",
    "tcb_static_store": "DescribeStaticStore",
    # --- tcm ------------------------------------------------------------
    "tcm_access_log": "DescribeAccessLogConfig",
    # --- tcr ------------------------------------------------------------
    "tcr_immutable_tag_rule": "DescribeImmutableTagRules",
    "tcr_webhook_trigger": "DescribeWebhookTrigger",
    # --- tdcpg ----------------------------------------------------------
    "tdcpg_account": "DescribeAccounts",
    "tdcpg_endpoint_wan": "DescribeClusterEndpoints",
    "tdcpg_instance_state": "DescribeClusterInstances",
    # --- tdmysql --------------------------------------------------------
    "tdmysql_account_privilege": "DescribeUserPrivileges",
    "tdmysql_maintenance_window": "DescribeMaintenanceWindow",
    "tdmysql_ssl": "DescribeInstanceSSLStatus",
    # --- tem ------------------------------------------------------------
    "tem_application_service": "DescribeApplicationServiceList",
    "tem_environment": "DescribeEnvironments",
    # --- tke ------------------------------------------------------------
    "tke_cluster_route": "DescribeClusterRoutes",
    "tke_cluster_route_table": "DescribeClusterRouteTables",
    "tke_cls_log_config": "DescribeLogConfigs",
}


def entry(value):
    """Normalise a TARGETS value into ``(action, resource_or_None)``."""
    if isinstance(value, dict):
        return value["action"], value.get("resource")
    return value, None
