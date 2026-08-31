from ansible_collections.susunola.tencentcloud.plugins.modules.oceanus_cluster import valid_cu
def test_valid_cu_accepts_service_sequence(): assert all(valid_cu(x) for x in (12,19,26,47))
def test_valid_cu_rejects_below_minimum_and_wrong_step(): assert not valid_cu(11) and not valid_cu(20)
