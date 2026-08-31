from ansible_collections.susunola.tencentcloud.plugins.modules.cdwpg_parameter import effective_value
def test_effective_value_prefers_pending_latest_value(): assert effective_value({"RunningValue":"100","LatestValue":"200"})=="200"
def test_effective_value_falls_back_to_running_value(): assert effective_value({"RunningValue":"100","LatestValue":""})=="100"
