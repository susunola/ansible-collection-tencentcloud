from types import SimpleNamespace
from ansible_collections.susunola.tencentcloud.plugins.modules.cdwch_parameter import change_request
class Item:
    pass
class Request:
    pass
class Models:
    InstanceConfigItem=Item
    ModifyInstanceKeyValConfigsRequest=Request
def test_update_request_preserves_original_and_restart_metadata():
    p={"instance_id":"cdwch-1","name":"max_threads","value":"32","remark":"managed","state":"present"}
    r=change_request(Models,p,{"ConfValue":"16","NeedRestart":True},None)
    assert r.UpdateItems[0].ModifyType=="update" and r.UpdateItems[0].OriginalConfValue=="16" and r.UpdateItems[0].NeedRestart is True
def test_absent_uses_del_items():
    p={"instance_id":"cdwch-1","name":"max_threads","value":None,"remark":None,"state":"absent"}
    assert change_request(Models,p,{"ConfValue":"16"},None).DelItems[0].ModifyType=="delete"
