from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_work_group_policy import normalize_policy, delta, detach_request


class Policy:
    def from_json_string(self, value):
        self.value = value


class Request:
    pass


Models = type("Models", (), {"Policy": Policy, "DetachWorkGroupPolicyRequest": Request})


def test_normalize_policy_ignores_server_metadata_and_applies_defaults():
    value = normalize_policy({"Database": "sales", "PolicyType": "DATABASE", "PolicyId": "generated", "Source": "WORKGROUP"})
    assert value["Database"] == "sales" and value["PolicyType"] == "DATABASE"
    assert value["Catalog"] == "DataLakeCatalog" and "PolicyId" not in value


def test_delta_compares_policy_semantics_only():
    current = [{"Database": "sales", "PolicyType": "DATABASE", "PolicyId": "p-1"}]
    assert delta(current, [{"Database": "sales", "PolicyType": "DATABASE"}]) == ([], [])


def test_detach_prefers_deterministic_policy_ids():
    request = detach_request(Models, 42, [{"PolicyType": "ADMIN"}], ["p-1"])
    assert request.WorkGroupId == 42 and request.PolicyIds == ["p-1"]
