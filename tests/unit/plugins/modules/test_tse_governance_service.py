from ansible_collections.susunola.tencentcloud.plugins.modules.tse_governance_service import comparable, desired, mutation


def test_service_identity_and_exact_access_sets():
    p={"name":"orders","namespace":"prod","comment":None,"department":None,"business":None,"metadata":None,"user_ids":["u2"],"group_ids":[],"export_to":["shared"],"sync_to_global_registry":None,"service_type":0}
    target=desired(p)
    current={"Name":"orders","Namespace":"prod","UserIds":["u1"],"GroupIds":[],"ExportTo":["shared"],"Type":0,"HealthyInstanceCount":3}
    value=mutation(current,target)
    assert value["UserIds"]==["u2"] and value["RemoveUserIds"]==["u1"]
    assert comparable(dict(current,UserIds=["u2"]),target)==target
