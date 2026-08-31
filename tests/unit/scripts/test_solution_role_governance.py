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


def test_observability_teardown_removes_topics_before_logset():
    text = role_tasks("tc_observability_baseline")
    assert_order(text, "Remove CLS topics", "Remove CLS logset")
    assert "tc_observability_baseline_logset_id | length > 0" in text


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
