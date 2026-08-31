from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_udf_policy import describe_request, normalize, update_request


class Model:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items(): setattr(self, key, item)


class Models:
    DescribeUDFPolicyRequest = UpdateUDFPolicyRequest = UDFPolicyInfo = Model


def params(): return {"name": "normalize_email", "database_name": "analytics", "catalog_name": "DataLakeCatalog", "policy_infos": [{"accesses": ["select", "select"], "users": ["u2", "u1"], "groups": ["g1"]}]}


def test_policy_normalization_is_set_semantic():
    expected = [{"Accesses": ["select"], "Users": ["u1", "u2"], "Groups": ["g1"]}]
    assert normalize(params()["policy_infos"]) == expected
    assert normalize([{"Groups": ["g1"], "Users": ["u1", "u2"], "Accesses": ["select"]}]) == expected
    assert normalize([{"accesses": ["select"], "users": ["u1"]}, {"accesses": ["select"], "users": ["u2"], "groups": ["g1"]}]) == expected


def test_describe_and_update_requests_preserve_exact_udf_identity():
    p = params(); describe = describe_request(Models, p); update = update_request(Models, p)
    assert describe.Name == "normalize_email" and describe.DatabaseName == "analytics" and describe.CatalogName == "DataLakeCatalog"
    assert update.UDFPolicyInfos[0].Users == ["u1", "u2"]
