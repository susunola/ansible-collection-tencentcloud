from ansible_collections.susunola.tencentcloud.plugins.modules.tse_governance_service_contract_info import (
    contract_request, fetch_contracts, version_request,
)


class Request(object): pass
class Models(object):
    DescribeGovernanceServiceContractsRequest = Request
    DescribeGovernanceServiceContractVersionsRequest = Request


PARAMS = {"instance_id": "ins-1", "namespace": "prod", "service": "orders", "name": "openapi",
          "contract_version": "v2", "protocol": "http", "brief": False, "page_size": 2}


def test_contract_requests_map_service_and_filters():
    contract = contract_request(Models, PARAMS, 4)
    version = version_request(Models, PARAMS)
    assert (contract.Namespace, contract.Service, contract.Name, contract.Offset) == ("prod", "orders", "openapi", 4)
    assert (version.InstanceId, version.Namespace, version.Service) == ("ins-1", "prod", "orders")


class Item(object):
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=False): return {"Value": self.value}


class Response(object):
    def __init__(self, values, total, request_id):
        self.ServiceContracts, self.TotalCount, self.RequestId = [Item(v) for v in values], total, request_id


class Client(object):
    def __init__(self): self.offsets = []
    def DescribeGovernanceServiceContracts(self, request):
        self.offsets.append(request.Offset)
        return Response([1, 2] if request.Offset == 0 else [3], 3, "request-%s" % request.Offset)


class Module(object):
    def sdk_call(self, operation, request): return operation(request)


def test_fetch_contracts_paginates():
    client = Client()
    contracts, total, request_id = fetch_contracts(Module(), client, Models, PARAMS)
    assert contracts == [{"Value": 1}, {"Value": 2}, {"Value": 3}]
    assert (total, request_id, client.offsets) == (3, "request-2", [0, 2])
