"""Static contracts for safe solution-role composition and teardown."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def role_tasks(name):
    return (ROOT / "roles" / name / "tasks" / "main.yml").read_text(encoding="utf-8")


def assert_order(text, *task_names):
    positions = [text.index("- name: " + name) for name in task_names]
    assert positions == sorted(positions), "unsafe task order: %s" % ", ".join(task_names)


def test_serverless_teardown_removes_public_entrypoint_before_function():
    text = role_tasks("tc_serverless_application")
    assert_order(
        text,
        "Unrelease API Gateway service",
        "Remove API Gateway APIs",
        "Remove API Gateway service",
        "Remove SCF triggers",
        "Remove SCF aliases",
        "Remove SCF function",
    )
    assert "tc_serverless_application_api_service_id | length > 0" in text


def test_tke_teardown_removes_children_before_cluster():
    text = role_tasks("tc_tke_platform")
    assert_order(text, "Remove TKE addons", "Remove TKE endpoints", "Remove TKE node pools", "Remove TKE cluster")
    assert "tc_tke_platform_cluster_id | length > 0" in text


def test_vpc_teardown_removes_children_before_vpc():
    text = role_tasks("tc_vpc_foundation")
    assert_order(text, "Remove route tables", "Remove NAT gateways", "Remove subnets", "Remove VPC")
    assert "tc_vpc_foundation_vpc_id | length > 0" in text


def test_database_teardown_removes_logical_children_before_instance():
    text = role_tasks("tc_database_stack")
    assert_order(text, "Remove database accounts", "Remove databases", "Remove CDB instance")
    assert "tc_database_stack_instance_id | length > 0" in text


def test_redis_teardown_removes_accounts_before_instance_and_optional_template():
    text = role_tasks("tc_redis_stack")
    assert_order(text, "Remove Redis accounts", "Remove Redis instance", "Remove Redis parameter template")
    assert "tc_redis_stack_instance_id | length > 0" in text


def test_mongodb_teardown_removes_accounts_before_instance():
    text = role_tasks("tc_mongodb_stack")
    assert_order(text, "Remove MongoDB accounts", "Remove MongoDB instance")
    assert "tc_mongodb_stack_mongo_user_password | length > 0" in text


def test_observability_teardown_removes_topics_before_logset():
    text = role_tasks("tc_observability_baseline")
    assert_order(text, "Remove CLS topics", "Remove CLS logset")
    assert "tc_observability_baseline_logset_id | length > 0" in text


def test_object_storage_teardown_removes_reversible_configuration_before_bucket():
    text = role_tasks("tc_object_storage_baseline")
    assert_order(
        text,
        "Remove COS replication configuration",
        "Remove COS website configuration",
        "Remove COS access logging",
        "Remove COS bucket policy",
        "Remove COS default encryption",
        "Remove empty COS bucket",
    )
    teardown = text[text.index("- name: Remove COS replication configuration"):]
    assert "cos_bucket_object_lock" not in teardown
    assert "cos_bucket_intelligent_tiering" not in teardown


def test_shared_file_storage_teardown_unbinds_policy_before_parent_resources():
    text = role_tasks("tc_shared_file_storage")
    assert_order(
        text,
        "Remove CFS automatic snapshot policy",
        "Remove CFS file system",
        "Remove CFS permission rules",
        "Remove CFS permission group",
    )
    assert "force_delete: true" in text


def test_kafka_teardown_removes_access_and_data_children_before_instance():
    text = role_tasks("tc_kafka_platform")
    assert_order(
        text,
        "Remove CKafka ACL rules",
        "Remove CKafka ACL entries",
        "Remove CKafka topics",
        "Remove CKafka users",
        "Remove CKafka access routes",
        "Disable CKafka deletion protection before teardown",
        "Remove CKafka instance",
    )
    assert "deletion_protection: false" in text


def test_alb_teardown_removes_listeners_and_backends_before_parents():
    main = role_tasks("tc_alb_application_entry")
    group = (ROOT / "roles" / "tc_alb_application_entry" / "tasks" / "target_group.yml").read_text(encoding="utf-8")
    assert_order(group, "Remove ALB listeners before target group", "Remove ALB target group backends", "Remove ALB target group")
    assert "deletion_protection: false" in main


def test_mqtt_teardown_removes_policies_and_children_before_instance():
    text = role_tasks("tc_mqtt_broker")
    assert_order(text, "Remove MQTT authorization policies", "Remove MQTT topics", "Remove MQTT users", "Remove MQTT instance")
    assert "passwords are creation-only" in (ROOT / "roles" / "tc_mqtt_broker" / "defaults" / "main.yml").read_text(encoding="utf-8")


def test_postgresql_teardown_removes_children_before_two_stage_instance_action():
    text = role_tasks("tc_postgresql_stack")
    assert_order(text, "Remove PostgreSQL backup plans", "Remove PostgreSQL accounts", "Isolate or purge PostgreSQL instance")
    assert "purge: \"{{ tc_postgresql_stack_purge }}\"" in text


def test_mariadb_teardown_clears_privileges_before_accounts_and_instance():
    main = role_tasks("tc_mariadb_stack")
    account = (ROOT / "roles" / "tc_mariadb_stack" / "tasks" / "account.yml").read_text(encoding="utf-8")
    assert_order(account, "Remove MariaDB account privilege scopes", "Remove MariaDB account")
    assert main.index("Reconcile MariaDB accounts and privileges") < main.index("Isolate or purge MariaDB instance")
    assert "purge: \"{{ tc_mariadb_stack_purge }}\"" in main


def test_dcdb_teardown_clears_privileges_before_accounts_and_instance():
    main = role_tasks("tc_dcdb_stack")
    account = (ROOT / "roles" / "tc_dcdb_stack" / "tasks" / "teardown_account.yml").read_text(encoding="utf-8")
    assert_order(account, "Clear DCDB account privilege scopes", "Remove DCDB account")
    assert main.index("Remove DCDB account privileges and accounts") < main.index("Isolate or purge DCDB instance")
    assert "tc_dcdb_stack_instance.instance_id is defined" in main
    assert "tc_dcdb_stack_allow_isolate" in main


def test_cynosdb_teardown_clears_privileges_before_accounts_and_cluster():
    main = role_tasks("tc_cynosdb_cluster")
    account = (ROOT / "roles" / "tc_cynosdb_cluster" / "tasks" / "account.yml").read_text(encoding="utf-8")
    assert_order(account, "Clear CynosDB account privileges", "Remove CynosDB account")
    assert main.index("Reconcile CynosDB accounts and privileges") < main.index("Isolate or purge CynosDB cluster")
    assert "purge: \"{{ tc_cynosdb_cluster_purge }}\"" in main


def test_autoscaling_teardown_removes_children_before_group():
    text = role_tasks("tc_autoscaling_group")
    assert_order(
        text,
        "Remove Auto Scaling scheduled actions",
        "Remove Auto Scaling policies",
        "Remove Auto Scaling group",
    )
    assert "tc_autoscaling_group_desired_capacity: 0" in (
        ROOT / "roles" / "tc_autoscaling_group" / "defaults" / "main.yml"
    ).read_text(encoding="utf-8")


def test_eventbridge_teardown_removes_targets_before_rules_and_bus():
    main = role_tasks("tc_eventbridge_router")
    rule = (ROOT / "roles" / "tc_eventbridge_router" / "tasks" / "teardown_rule.yml").read_text(encoding="utf-8")
    assert_order(rule, "Remove EventBridge rule targets", "Remove EventBridge rule")
    assert_order(main, "Remove EventBridge rule targets and rules", "Remove EventBridge connections", "Remove EventBridge event bus")
    assert "rule_id is required" in rule


def test_dns_zone_teardown_removes_children_before_domain():
    text = role_tasks("tc_dns_zone")
    assert_order(
        text,
        "Remove DNSPod records",
        "Remove DNSPod custom line groups",
        "Remove DNSPod custom lines",
        "Remove DNSPod domain",
    )


def test_block_storage_teardown_clears_protection_and_detaches_before_disk():
    text = role_tasks("tc_block_storage")
    assert_order(
        text,
        "Remove CBS snapshot sharing",
        "Remove CBS snapshots",
        "Remove CBS disk backup points",
        "Unbind and remove CBS automatic snapshot policies",
        "Detach CBS disk before teardown",
        "Terminate CBS disk",
    )
    assert "force_delete: true" in text
    assert "account_ids: []" in text


def test_lighthouse_teardown_removes_children_before_isolation():
    text = role_tasks("tc_lighthouse_stack")
    assert_order(
        text,
        "Remove Lighthouse snapshots",
        "Clear Lighthouse firewall rules",
        "Detach and remove Lighthouse data disks",
        "Disassociate and remove Lighthouse key pairs",
        "Isolate Lighthouse instance",
    )
    assert "state: absent" in text
    assert "permanent" in (ROOT / "roles" / "tc_lighthouse_stack" / "README.md").read_text(encoding="utf-8")


def test_rocketmq_teardown_removes_permissions_and_resources_before_cluster():
    main = role_tasks("tc_rocketmq_platform")
    namespace = (ROOT / "roles" / "tc_rocketmq_platform" / "tasks" / "teardown_namespace.yml").read_text(encoding="utf-8")
    assert_order(namespace, "Remove RocketMQ namespace permissions", "Remove RocketMQ consumer groups", "Remove RocketMQ topics", "Delete RocketMQ namespace")
    assert_order(main, "Remove RocketMQ namespace permissions and resources", "Remove RocketMQ roles", "Remove RocketMQ cluster")
    assert "credential fields" in (ROOT / "roles" / "tc_rocketmq_platform" / "README.md").read_text(encoding="utf-8")


def test_rabbitmq_teardown_removes_access_before_protected_instance():
    main = role_tasks("tc_rabbitmq_platform")
    vhost = (ROOT / "roles" / "tc_rabbitmq_platform" / "tasks" / "teardown_virtual_host.yml").read_text(encoding="utf-8")
    assert_order(vhost, "Remove RabbitMQ bindings", "Remove RabbitMQ virtual host permissions", "Delete RabbitMQ virtual host")
    assert_order(main, "Remove RabbitMQ bindings permissions and virtual hosts", "Remove RabbitMQ users", "Disable RabbitMQ deletion protection and remove instance")
    assert "deletion_protection: false" in main
    assert "no_log:" in main


def test_cmq_teardown_removes_subscriptions_before_topics_and_queues():
    text = role_tasks("tc_cmq_messaging")
    assert_order(text, "Remove CMQ subscriptions", "Remove CMQ topics", "Remove CMQ queues")
    teardown = (ROOT / "roles" / "tc_cmq_messaging" / "tasks" / "teardown_subscriptions.yml").read_text(encoding="utf-8")
    assert "Delete CMQ topic subscriptions" in teardown


def test_rabbitmq_serverless_teardown_removes_bindings_before_resources():
    main = role_tasks("tc_rabbitmq_serverless")
    vhost = (ROOT / "roles" / "tc_rabbitmq_serverless" / "tasks" / "teardown_virtual_host.yml").read_text(encoding="utf-8")
    assert_order(vhost, "Remove RabbitMQ Serverless bindings", "Remove RabbitMQ Serverless permissions", "Remove RabbitMQ Serverless queues", "Remove RabbitMQ Serverless exchanges", "Delete RabbitMQ Serverless virtual host")
    assert "Remove RabbitMQ Serverless users" in main
    assert "existing instance ID" in main


def test_prometheus_teardown_removes_jobs_and_children_before_instance():
    main = role_tasks("tc_prometheus_platform")
    agent = (ROOT / "roles" / "tc_prometheus_platform" / "tasks" / "teardown_cluster_agent.yml").read_text(encoding="utf-8")
    assert_order(agent, "Remove Prometheus scrape jobs", "Remove Prometheus cluster agent")
    assert_order(main, "Remove Prometheus scrape jobs and cluster agents", "Remove Prometheus alert groups", "Remove Prometheus recording rules", "Unbind Prometheus Grafana instances", "Remove Managed Prometheus instance")
    assert "agent_id is required" in agent


def test_waf_teardown_removes_groups_and_rules_before_hosts():
    main = role_tasks("tc_waf_application")
    domain = (ROOT / "roles" / "tc_waf_application" / "tasks" / "teardown_domain.yml").read_text(encoding="utf-8")
    assert_order(main, "Remove WAF protection groups before domains", "Remove WAF domain rules and protected hosts", "Disable WAF global threat intelligence")
    assert domain.index("Remove WAF anti-information-leak rules") < domain.index("Remove WAF protected host")
    assert domain.index("Remove WAF IP access controls") < domain.index("Remove WAF protected host")
    assert "enabled: false" in main


def test_edgeone_teardown_clears_security_and_delivery_before_zone():
    main = role_tasks("tc_edgeone_application")
    template = (ROOT / "roles" / "tc_edgeone_application" / "tasks" / "teardown_security_template.yml").read_text(encoding="utf-8")
    assert_order(template, "Clear EdgeOne template security policies", "Unbind EdgeOne security template domains", "Delete EdgeOne web security template")
    assert_order(main, "Clear EdgeOne zone and host security scopes", "Unbind and remove EdgeOne web security templates", "Remove EdgeOne acceleration domains", "Remove EdgeOne origin groups", "Remove EdgeOne zone")
    assert "template_id is required" in template


def test_api_gateway_teardown_removes_bindings_and_children_before_service():
    main = role_tasks("tc_api_gateway_platform")
    plan = (ROOT / "roles" / "tc_api_gateway_platform" / "tasks" / "teardown_usage_plan.yml").read_text(encoding="utf-8")
    assert_order(plan, "Remove API Gateway usage plan service bindings", "Remove API Gateway usage plan key bindings", "Delete API Gateway usage plan")
    assert_order(main, "Remove API Gateway usage plan bindings and plans", "Unrelease API Gateway environments", "Remove API Gateway APIs", "Remove API Gateway API keys", "Remove API Gateway service")
    assert "usage_plan_id is required" in plan
    assert "no_log:" in main


def test_config_governance_teardown_removes_policy_layers_before_rules_and_recorder():
    main = role_tasks("tc_config_governance")
    rule = (ROOT / "roles" / "tc_config_governance" / "tasks" / "teardown_rule.yml").read_text(encoding="utf-8")
    assert_order(rule, "Remove Config rule remediations", "Remove Config governance rule")
    assert_order(
        main,
        "Remove Config alarm policies",
        "Remove Config compliance packs",
        "Remove Config remediations and rules",
        "Disable Config delivery",
        "Disable Config resource recorder",
    )
    assert "aggregators cannot be removed" in main


def test_chdfs_teardown_disassociates_and_removes_children_before_file_system():
    main = role_tasks("tc_chdfs_data_lake")
    mount = (ROOT / "roles" / "tc_chdfs_data_lake" / "tasks" / "teardown_mount.yml").read_text(encoding="utf-8")
    access_group = (ROOT / "roles" / "tc_chdfs_data_lake" / "tasks" / "teardown_access_group.yml").read_text(encoding="utf-8")
    assert_order(mount, "Disassociate CHDFS mount access groups", "Remove CHDFS mount point")
    assert_order(access_group, "Remove CHDFS access rules", "Remove CHDFS access group")
    assert_order(
        main,
        "Disassociate and remove CHDFS mount points",
        "Clear rules and remove CHDFS access groups",
        "Remove CHDFS file system",
    )


def test_cloud_firewall_removes_all_rule_layers_before_templates():
    text = role_tasks("tc_cloud_firewall_policy")
    assert_order(
        text,
        "Remove Cloud Firewall NAT DNAT rules",
        "Remove Cloud Firewall VPC ACL rules",
        "Remove Cloud Firewall NAT ACL rules",
        "Remove Cloud Firewall internet ACL rules",
        "Remove Cloud Firewall address templates",
    )


def test_elasticsearch_teardown_removes_data_children_before_cluster():
    text = role_tasks("tc_elasticsearch_platform")
    assert_order(
        text,
        "Remove Elasticsearch snapshots",
        "Remove Elasticsearch indexes",
        "Remove Elasticsearch instance",
    )
    assert text.count("no_log:") >= 2


def test_sqlserver_teardown_removes_accounts_before_two_stage_instance_action():
    text = role_tasks("tc_sqlserver_stack")
    assert_order(
        text,
        "Remove SQL Server accounts before instance action",
        "Isolate or purge SQL Server instance",
    )
    assert 'purge: "{{ tc_sqlserver_stack_purge }}"' in text
    assert "no_log:" in text


def test_gwlb_teardown_disassociates_and_deregisters_before_parents():
    main = role_tasks("tc_gwlb_service_chain")
    group = (ROOT / "roles" / "tc_gwlb_service_chain" / "tasks" / "teardown_target_group.yml").read_text(encoding="utf-8")
    assert_order(
        group,
        "Disassociate GWLB target group",
        "Deregister GWLB appliance instances",
        "Remove GWLB target group",
    )
    assert_order(
        main,
        "Disassociate and remove GWLB target groups",
        "Disable GWLB deletion protection and remove load balancer",
    )
    assert "deletion_protection: false" in main


def test_organization_teardown_removes_access_before_members_and_nodes():
    main = role_tasks("tc_organization_governance")
    member = (ROOT / "roles" / "tc_organization_governance" / "tasks" / "teardown_member.yml").read_text(encoding="utf-8")
    assert_order(
        member,
        "Remove Organization member policies",
        "Remove Organization member identities",
        "Delete Organization member",
    )
    assert "resource_type='organization_member'" in member
    assert_order(
        main,
        "Remove Organization policies identities and members",
        "Remove Organization nodes child first",
    )
    assert "| reverse | list" in main


def test_kms_keyring_requires_explicit_scheduled_deletion_authorization():
    text = role_tasks("tc_kms_keyring")
    assert "tc_kms_keyring_allow_deletion | bool" in text
    assert "deletion_protection: false" in text
    assert "Schedule KMS key deletion" in text


def test_direct_connect_removes_tunnels_before_guarded_physical_connection():
    text = role_tasks("tc_direct_connect_fabric")
    assert_order(
        text,
        "Remove Direct Connect tunnels before physical connection",
        "Remove physical Direct Connect when explicitly authorized",
    )
    assert "tc_direct_connect_fabric_delete_physical_connection | bool" in text
    assert "no_log:" in text


def test_cdn_delivery_removes_log_topics_before_domains():
    text = role_tasks("tc_cdn_delivery")
    assert_order(
        text,
        "Remove CDN real-time CLS log topics",
        "Stop and remove CDN domains",
    )


def test_goosefs_teardown_removes_filesets_before_file_system():
    text = role_tasks("tc_goosefs_cache")
    assert_order(
        text,
        "Remove GooseFS filesets before file system",
        "Remove GooseFS file system",
    )


def test_cloud_audit_removes_tracks_before_stop_only_account_teardown():
    text = role_tasks("tc_cloud_audit_governance")
    assert_order(
        text,
        "Remove CloudAudit tracks before stopping account audit",
        "Stop account-level CloudAudit logging",
    )
    assert "combine({'enabled': false" in text


def test_container_registry_disables_protection_and_removes_children_first():
    text = role_tasks("tc_container_registry")
    assert_order(
        text,
        "Disable TCR deletion protection before teardown",
        "Remove TCR replication rules",
        "Remove TCR repositories",
        "Remove TCR namespaces",
        "Remove TCR instance",
    )
    assert "tc_container_registry_id | length > 0" in text


def test_dlc_governance_teardown_removes_access_before_group():
    teardown = (ROOT / "roles" / "tc_dlc_access_governance" / "tasks" / "teardown_work_group.yml").read_text(encoding="utf-8")
    assert_order(
        teardown,
        "Remove DLC work-group policies before members",
        "Remove DLC work-group members before group",
        "Remove empty DLC work group",
    )
    main = role_tasks("tc_dlc_access_governance")
    assert "tc_dlc_access_governance_allow_destroy" in main


def test_dlc_governance_orders_engines_around_access_resources():
    main = role_tasks("tc_dlc_access_governance")
    engine_module = "susunola.tencentcloud.dlc_data_engine:\n"
    assert main.index("include_tasks: vpc_connection.yml") < main.index("include_tasks: data_engine.yml")
    assert main.index("include_tasks: data_engine.yml") < main.index("include_tasks: work_group.yml")
    assert main.index("include_tasks: data_engine.yml") < main.index("susunola.tencentcloud.dlc_engine_resource_group")
    assert main.index("susunola.tencentcloud.dlc_engine_resource_group") < main.index("susunola.tencentcloud.dlc_database")
    assert main.index("susunola.tencentcloud.dlc_engine_resource_group") < main.index("susunola.tencentcloud.dlc_spark_job")
    assert main.index("susunola.tencentcloud.dlc_engine_resource_group") < main.index("susunola.tencentcloud.dlc_lab")
    assert main.index("susunola.tencentcloud.dlc_cluster_group") < main.index("susunola.tencentcloud.dlc_lab")
    assert main.index("susunola.tencentcloud.dlc_cluster_group") < main.index("susunola.tencentcloud.dlc_ray_cluster")
    assert main.index("susunola.tencentcloud.dlc_partition_queue") < main.index("susunola.tencentcloud.dlc_lab")
    assert main.index("susunola.tencentcloud.dlc_resource_config") < main.index("susunola.tencentcloud.dlc_lab")
    assert main.index("susunola.tencentcloud.dlc_resource_config") < main.index("susunola.tencentcloud.dlc_ray_cluster")
    assert main.index("susunola.tencentcloud.dlc_ray_cluster") < main.index("susunola.tencentcloud.dlc_job_spec")
    assert "susunola.tencentcloud.dlc_inference_model" in main
    assert main.index("susunola.tencentcloud.dlc_inference_model") < main.index("susunola.tencentcloud.dlc_model_version")
    assert main.index("susunola.tencentcloud.dlc_model_version") < main.index("susunola.tencentcloud.dlc_inference_service")
    assert "Each DLC model version requires exactly one model_uid or managed model_name reference" in main
    assert "Each DLC inference service requires exactly one model_uid or managed model_name reference" in main
    assert "_tc_dlc_inference_model_uids[_tc_dlc_model_version.model_name]" in main
    assert "_tc_dlc_inference_model_uids[_tc_dlc_inference_service.model_name]" in main
    assert "DLC Ray cluster references must use one valid managed name or direct ID" in main
    assert "DLC job specifications require one valid compute target" in main
    assert "DLC laboratory references must use one valid managed name or direct ID" in main
    assert "_tc_dlc_cluster_group_ids[_tc_dlc_ray.group_name]" in main
    assert "_tc_dlc_resource_config_ids[_tc_dlc_ray.resource_config_name]" in main
    assert "_tc_dlc_ray_cluster_ids[_tc_dlc_job_spec.cluster_name]" in main
    assert main.count("'resource_config_name': omit") >= 6
    assert main.count("'group_name': omit") >= 6
    assert main.count("'cluster_name': omit") >= 2
    assert main.index("susunola.tencentcloud.dlc_database") < main.index("include_tasks: work_group.yml")
    assert main.index("susunola.tencentcloud.dlc_database") < main.index("susunola.tencentcloud.dlc_script")
    assert main.index("susunola.tencentcloud.dlc_database") < main.index("susunola.tencentcloud.dlc_table")
    assert main.index("susunola.tencentcloud.dlc_table:\n") < main.index("susunola.tencentcloud.dlc_table_partition:\n")
    assert main.index("include_tasks: user.yml") < main.index("include_tasks: work_group.yml")
    assert main.index("include_tasks: work_group.yml") < main.index("susunola.tencentcloud.dlc_data_mask_strategy")
    assert main.index("include_tasks: work_group.yml") < main.index("susunola.tencentcloud.dlc_udf_policy")
    assert main.index("susunola.tencentcloud.dlc_udf_policy") < main.index("susunola.tencentcloud.dlc_data_mask_strategy")
    assert main.index("include_tasks: teardown_work_group.yml") < main.index(engine_module)
    assert main.rindex("susunola.tencentcloud.dlc_data_mask_strategy") < main.index("include_tasks: teardown_work_group.yml")
    assert main.rindex("susunola.tencentcloud.dlc_udf_policy") < main.index("include_tasks: teardown_work_group.yml")
    assert main.index("include_tasks: teardown_work_group.yml") < main.index("include_tasks: teardown_user.yml")
    assert main.index("include_tasks: teardown_user.yml") < main.rindex("susunola.tencentcloud.dlc_database")
    assert main.rindex("susunola.tencentcloud.dlc_database") < main.index(engine_module)
    assert main.rindex("susunola.tencentcloud.dlc_script") < main.rindex("susunola.tencentcloud.dlc_database")
    assert main.rindex("susunola.tencentcloud.dlc_table:\n") < main.rindex("susunola.tencentcloud.dlc_database")
    assert main.rindex("susunola.tencentcloud.dlc_table_partition:\n") < main.rindex("susunola.tencentcloud.dlc_table:\n")
    assert main.rindex("susunola.tencentcloud.dlc_database") < main.rindex("susunola.tencentcloud.dlc_engine_resource_group")
    assert main.rindex("susunola.tencentcloud.dlc_engine_resource_group") < main.index(engine_module)
    assert main.rindex("susunola.tencentcloud.dlc_spark_job") < main.rindex("susunola.tencentcloud.dlc_engine_resource_group")
    assert main.rindex("susunola.tencentcloud.dlc_lab") < main.rindex("susunola.tencentcloud.dlc_engine_resource_group")
    assert main.rindex("susunola.tencentcloud.dlc_lab") < main.rindex("susunola.tencentcloud.dlc_partition_queue")
    assert main.rindex("susunola.tencentcloud.dlc_lab") < main.rindex("susunola.tencentcloud.dlc_resource_config")
    assert main.rindex("susunola.tencentcloud.dlc_ray_cluster") < main.rindex("susunola.tencentcloud.dlc_resource_config")
    assert main.rindex("susunola.tencentcloud.dlc_job_spec") < main.rindex("susunola.tencentcloud.dlc_ray_cluster")
    assert main.rindex("susunola.tencentcloud.dlc_ray_cluster") < main.rindex("susunola.tencentcloud.dlc_cluster_group")
    assert main.rindex("susunola.tencentcloud.dlc_resource_config") < main.rindex("susunola.tencentcloud.dlc_partition_queue")
    assert main.index(engine_module) < main.index("susunola.tencentcloud.dlc_user_vpc_connection")
    assert "allow_delete': true" in main
    defaults = (ROOT / "roles" / "tc_dlc_access_governance" / "defaults" / "main.yml").read_text(encoding="utf-8")
    assert "tc_dlc_access_governance_vpc_connections: []" in defaults
    assert "tc_dlc_access_governance_store_location: {}" in defaults
    assert main.index("susunola.tencentcloud.dlc_store_location") < main.index("include_tasks: data_engine.yml")
    assert "tc_dlc_access_governance_store_location | length == 0" in main
    assert "tc_dlc_access_governance_data_engines: []" in defaults
    assert "tc_dlc_access_governance_data_engine_configs: []" in defaults
    assert "tc_dlc_access_governance_network_connections: []" in defaults
    assert "tc_dlc_access_governance_notebook_sessions: []" in defaults
    assert main.index("include_tasks: data_engine.yml") < main.index("susunola.tencentcloud.dlc_data_engine_config")
    assert main.index("susunola.tencentcloud.dlc_data_engine_config") < main.index("susunola.tencentcloud.dlc_notebook_session")
    assert main.rindex("susunola.tencentcloud.dlc_notebook_session") < main.rindex(engine_module)
    assert "tc_dlc_access_governance_engine_resource_groups: []" in defaults
    assert "tc_dlc_access_governance_cluster_groups: []" in defaults
    assert "tc_dlc_access_governance_spark_jobs: []" in defaults
    assert "tc_dlc_access_governance_labs: []" in defaults
    assert "tc_dlc_access_governance_partition_queues: []" in defaults
    assert "tc_dlc_access_governance_resource_configs: []" in defaults
    assert "tc_dlc_access_governance_ray_clusters: []" in defaults
    assert "tc_dlc_access_governance_job_specs: []" in defaults
    assert "tc_dlc_access_governance_inference_models: []" in defaults
    assert "tc_dlc_access_governance_model_versions: []" in defaults
    assert "tc_dlc_access_governance_model_artifact_checks: []" in defaults
    assert "tc_dlc_access_governance_inference_services: []" in defaults
    assert "tc_dlc_access_governance_inference_models | length == 0" in main
    assert "tc_dlc_access_governance_model_versions | length == 0" in main
    assert "tc_dlc_access_governance_model_artifact_checks | length == 0" in main
    assert "tc_dlc_access_governance_inference_services | length == 0" in main
    assert "susunola.tencentcloud.dlc_model_artifact_info" in main
    assert "model_artifacts:" in main
    assert "tc_dlc_access_governance_databases: []" in defaults
    assert "tc_dlc_access_governance_tables: []" in defaults
    assert "tc_dlc_access_governance_table_partitions: []" in defaults
    assert "tc_dlc_access_governance_scripts: []" in defaults
    assert "tc_dlc_access_governance_users: []" in defaults
    assert "tc_dlc_access_governance_data_mask_strategies: []" in defaults
    assert "tc_dlc_access_governance_udf_policies: []" in defaults
    teardown_user = (ROOT / "roles" / "tc_dlc_access_governance" / "tasks" / "teardown_user.yml").read_text(encoding="utf-8")
    assert_order(teardown_user, "Remove DLC direct-user policies before user", "Remove unbound DLC user")


def test_solution_roles_resolve_parent_ids_before_validation_and_teardown():
    expectations = {
        "tc_vpc_foundation": "resource_type='vpc'",
        "tc_tke_platform": "resource_type='tke_cluster'",
        "tc_database_stack": "resource_type='cdb_instance'",
        "tc_redis_stack": "resource_type='redis_instance'",
        "tc_mongodb_stack": "resource_type='mongodb_instance'",
        "tc_shared_file_storage": "resource_type='cfs_file_system'",
        "tc_kafka_platform": "resource_type='ckafka_instance'",
        "tc_alb_application_entry": "resource_type='alb_load_balancer'",
        "tc_mqtt_broker": "resource_type='mqtt_instance'",
        "tc_postgresql_stack": "resource_type='postgresql_instance'",
        "tc_mariadb_stack": "resource_type='mariadb_instance'",
        "tc_cynosdb_cluster": "resource_type='cynosdb_cluster'",
        "tc_autoscaling_group": "resource_type='autoscaling_group'",
        "tc_block_storage": "resource_type='cbs_disk'",
        "tc_lighthouse_stack": "resource_type='lighthouse_instance'",
        "tc_prometheus_platform": "resource_type='prometheus_instance'",
        "tc_edgeone_application": "resource_type='edgeone_zone'",
        "tc_api_gateway_platform": "resource_type='api_gateway_service'",
        "tc_chdfs_data_lake": "resource_type='chdfs_file_system'",
        "tc_elasticsearch_platform": "resource_type='elasticsearch_instance'",
        "tc_sqlserver_stack": "resource_type='sqlserver_instance'",
        "tc_gwlb_service_chain": "resource_type='gwlb_load_balancer'",
        "tc_rocketmq_platform": "resource_type='rocketmq_cluster'",
        "tc_rabbitmq_platform": "resource_type='rabbitmq_instance'",
        "tc_eventbridge_router": "resource_type='event_bus'",
        "tc_container_registry": "resource_type='tcr_instance'",
        "tc_tem_application": "resource_type='tem_environment'",
        "tc_serverless_application": "resource_type='api_gateway_service'",
        "tc_direct_connect_fabric": "resource_type='direct_connect'",
        "tc_goosefs_cache": "resource_type='goosefs_file_system'",
    }
    for role, lookup_type in expectations.items():
        text = role_tasks(role)
        assert lookup_type in text
        assert text.index("resource_type=") < text.index("- name: Validate")
