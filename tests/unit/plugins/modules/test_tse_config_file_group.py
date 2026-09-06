from ansible_collections.susunola.tencentcloud.plugins.modules.tse_config_file_group import comparable, desired, mutation


def test_config_group_reconciles_exact_operator_sets():
    p = {"name": "app", "namespace": "prod", "comment": None, "department": None, "business": None, "user_ids": ["u2"], "group_ids": [], "tags": None}
    target = desired(p)
    current = {"Name": "app", "Namespace": "prod", "UserIds": ["u1"], "GroupIds": [], "FileCount": 4}
    assert mutation(current, target)["RemoveUserIds"] == ["u1"]
    assert comparable(dict(current, UserIds=["u2"]), target) == target
