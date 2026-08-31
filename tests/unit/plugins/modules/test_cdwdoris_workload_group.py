from ansible_collections.susunola.tencentcloud.plugins.modules.cdwdoris_workload_group import comparable, desired, update_payload


def test_desired_only_manages_explicit_limits():
    value = desired({"name": "interactive", "cpu_share": 800, "memory_limit": None,
                     "enable_memory_overcommit": None, "cpu_hard_limit": None,
                     "min_cpu_percent": None, "min_memory_percent": None,
                     "max_concurrency": 30, "max_queue_size": None, "queue_timeout": None})
    assert value == {"WorkloadGroupName": "interactive", "CpuShare": 800, "MaxConcurrencyNum": 30}


def test_comparable_ignores_server_computed_fields():
    target = {"WorkloadGroupName": "batch", "MemoryLimit": 60}
    current = {"WorkloadGroupName": "batch", "MemoryLimit": 60, "ServerOnly": "ignored"}
    assert comparable(current, target) == target


def test_update_payload_preserves_unspecified_resource_limits():
    current = {"WorkloadGroupName": "batch", "CpuShare": 200, "MemoryLimit": 60, "ServerOnly": "ignored"}
    assert update_payload(current, {"WorkloadGroupName": "batch", "CpuShare": 300}) == {
        "WorkloadGroupName": "batch", "CpuShare": 300, "MemoryLimit": 60,
    }
