from ansible_collections.susunola.tencentcloud.plugins.modules.tse_sre_access_address_info import request, serialize_response


class Value(object):
    pass


class Models(object):
    DescribeSREInstanceAccessAddressRequest = Value


class Response(object):
    RequestId = "request-1"

    def _serialize(self, allow_none=False):
        return {"IntranetAddress": "10.0.0.8:8848", "InternetAddress": "203.0.113.8:8848", "RequestId": self.RequestId}


def test_access_address_request_and_response_mapping():
    value = request(Models, {"instance_id": "ins1", "vpc_id": "vpc1", "subnet_id": "subnet1", "workload": "polaris-limiter", "engine_region": "ap-guangzhou"})
    assert value.InstanceId == "ins1" and value.Workload == "polaris-limiter"
    assert serialize_response(Response()) == {"IntranetAddress": "10.0.0.8:8848", "InternetAddress": "203.0.113.8:8848"}
