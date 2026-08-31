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
        "tc_container_registry": "resource_type='tcr_instance'",
        "tc_tem_application": "resource_type='tem_environment'",
        "tc_serverless_application": "resource_type='api_gateway_service'",
    }
    for role, lookup_type in expectations.items():
        text = role_tasks(role)
        assert lookup_type in text
        assert text.index("resource_type=") < text.index("- name: Validate")
