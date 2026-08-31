from ansible_collections.susunola.tencentcloud.plugins.modules.cdwdoris_user_workload_group import normalized_hosts


def test_normalized_hosts_are_stable_and_unique():
    assert normalized_hosts(["10.0.0.%", "%", "%"]) == ["%", "10.0.0.%"]
