from ansible_collections.susunola.tencentcloud.plugins.modules.tse_governance_namespace import comparable, desired, mutation


def test_namespace_exact_access_sets_generate_adds_and_removes():
    current={"Name":"prod","UserIds":["u1","u2"],"GroupIds":["g1"]}
    target={"Name":"prod","UserIds":["u2","u3"],"GroupIds":[]}
    value=mutation(current,target)
    assert value["UserIds"]==["u3"] and value["RemoveUserIds"]==["u1"]
    assert value["GroupIds"]==[] and value["RemoveGroupIds"]==["g1"]


def test_namespace_comparison_ignores_server_statistics():
    p={"name":"prod","comment":"x","user_ids":[],"group_ids":None,"service_export_to":None,"sync_to_global_registry":None}
    target=desired(p)
    assert comparable({"Name":"prod","Comment":"x","TotalServiceCount":9,"UserIds":None},target)==target
