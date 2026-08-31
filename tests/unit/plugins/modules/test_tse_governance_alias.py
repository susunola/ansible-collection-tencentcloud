import json

from ansible_collections.susunola.tencentcloud.plugins.modules.tse_governance_alias import desired, write_request


class Value(object):
    def from_json_string(self,raw): self.raw=raw
class DeleteValue(object): pass
class Models(object):
    CreateGovernanceAliasRequest=Value
    ModifyGovernanceAliasRequest=Value
    DeleteGovernanceAliasesRequest=DeleteValue
    GovernanceAlias=Value


def test_governance_alias_requests_map_full_lifecycle():
    p={"instance_id":"ins1","alias":"orders-api","alias_namespace":"shared","service":"orders","namespace":"production","comment":"stable"}
    target=desired(p)
    assert json.loads(write_request(Models.CreateGovernanceAliasRequest,Models,p,target).raw)["Service"]=="orders"
    delete=write_request(Models.DeleteGovernanceAliasesRequest,Models,p,target)
    assert delete.InstanceId=="ins1" and json.loads(delete.GovernanceAliases[0].raw)["AliasNamespace"]=="shared"


def test_governance_alias_update_preserves_unspecified_fields():
    p={"alias":"orders-api","alias_namespace":"shared","service":None,"namespace":None,"comment":"new"}
    assert desired(p,{"Service":"orders","Namespace":"production","Comment":"old"})=={"Alias":"orders-api","AliasNamespace":"shared","Service":"orders","Namespace":"production","Comment":"new"}
