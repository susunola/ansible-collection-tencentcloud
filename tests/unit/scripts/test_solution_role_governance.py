"""Static contracts for safe solution-role composition and teardown.

Only the three 2.0 solution roles remain (docs/core-allowlist.yml):
tc_vpc_foundation, tc_clb_http and tc_tke_cluster. These tests pin the
ordering that makes each of them safe: children come down before their
parents, and provisioning resolves parent ids before it validates.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def role_tasks(name, file="main.yml"):
    return (ROOT / "roles" / name / "tasks" / file).read_text(encoding="utf-8")


def assert_order(text, *task_names):
    positions = [text.index("- name: " + name) for name in task_names]
    assert positions == sorted(positions), "unsafe task order: %s" % ", ".join(task_names)


def test_vpc_teardown_removes_children_before_vpc():
    text = role_tasks("tc_vpc_foundation")
    assert_order(text, "Remove route tables", "Remove NAT gateways", "Remove subnets", "Remove VPC")
    assert "tc_vpc_foundation_vpc_id | length > 0" in text


def test_vpc_resolves_parent_id_before_validation():
    text = role_tasks("tc_vpc_foundation")
    assert "resource_type='vpc'" in text
    assert text.index("resource_type=") < text.index("- name: Validate")


def test_tke_teardown_removes_children_before_cluster():
    text = role_tasks("tc_tke_cluster", "teardown.yml")
    assert_order(text, "Remove the addons", "Remove the node pools", "Remove the TKE cluster")


def test_tke_provision_creates_cluster_before_children():
    text = role_tasks("tc_tke_cluster", "provision.yml")
    assert_order(text, "Manage the TKE cluster", "Manage the node pools", "Manage the addons")


def test_tke_main_includes_teardown_in_reverse_order():
    text = role_tasks("tc_tke_cluster")
    assert "teardown" in text
    assert "reverse" in text


def test_clb_provisions_listener_and_backends_after_load_balancer():
    text = role_tasks("tc_clb_http")
    assert_order(
        text,
        "Provision the CLB load balancer",
        "Create the HTTP listener",
        "Reconcile the backend target set",
    )
