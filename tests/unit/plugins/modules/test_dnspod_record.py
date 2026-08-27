"""Unit tests for the dnspod_record write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.dnspod_record import (
    build_describe_request,
    find_record,
    _create,
    _update,
    _delete,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    DescribeRecordListRequest = FakeRequest
    CreateRecordRequest = FakeRequest
    ModifyRecordRequest = FakeRequest
    DeleteRecordRequest = FakeRequest


class FakeRecord(object):
    def __init__(self, record_id, name, rtype, value, line="默认", ttl=600, status="ENABLE"):
        self.RecordId = record_id
        self.Name = name
        self.Type = rtype
        self.Value = value
        self.Line = line
        self.TTL = ttl
        self.Weight = 1
        self.MX = None
        self.Remark = ""
        self.Status = status

    def _serialize(self, allow_none=True):
        return {
            "RecordId": self.RecordId,
            "Name": self.Name,
            "Type": self.Type,
            "Value": self.Value,
            "Line": self.Line,
            "TTL": self.TTL,
            "Weight": self.Weight,
            "MX": self.MX,
            "Remark": self.Remark,
            "Status": self.Status,
        }


class FakeListResponse(object):
    def __init__(self, records):
        self.RecordList = records


class FakeCreateResponse(object):
    def __init__(self, record_id):
        self.RecordId = record_id


class FakeClient(object):
    def __init__(self, list_response=None, create_response=None, exc=None):
        self.list_response = list_response
        self.create_response = create_response
        self.exc = exc
        self.calls = []

    def DescribeRecordList(self, request):
        self.calls.append(("DescribeRecordList", request))
        if self.exc:
            raise self.exc
        return self.list_response

    def CreateRecord(self, request):
        self.calls.append(("CreateRecord", request))
        return self.create_response

    def ModifyRecord(self, request):
        self.calls.append(("ModifyRecord", request))

    def DeleteRecord(self, request):
        self.calls.append(("DeleteRecord", request))


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


BASE_PARAMS = {
    "domain": "example.com",
    "domain_id": None,
    "subdomain": "www",
    "record_type": "A",
    "record_line": "默认",
    "value": "1.2.3.4",
    "ttl": 600,
    "weight": None,
    "mx": None,
    "remark": None,
    "status": None,
}


def test_build_describe_request_sends_identity_fields():
    request = build_describe_request(FakeModels, "example.com", None, "www", "A", "默认")
    assert request.Domain == "example.com"
    assert request.Subdomain == "www"
    assert request.RecordType == "A"
    assert not hasattr(request, "RecordLine")


def test_build_describe_request_with_custom_line():
    request = build_describe_request(FakeModels, "example.com", None, "www", "A", "电信")
    assert request.RecordLine == "电信"


def test_build_describe_request_with_domain_id():
    request = build_describe_request(FakeModels, None, 123, "www", "A", "默认")
    assert request.DomainId == 123


def test_find_record_returns_first_match():
    client = FakeClient(FakeListResponse([FakeRecord(1, "www", "A", "1.2.3.4")]))
    module = FakeModule()
    record = find_record(module, client, FakeModels, "example.com", None, "www", "A", "默认")
    assert record["RecordId"] == 1
    assert len(client.calls) == 1


def test_find_record_filters_by_custom_line():
    client = FakeClient(FakeListResponse([
        FakeRecord(1, "www", "A", "1.2.3.4", line="电信"),
        FakeRecord(2, "www", "A", "5.6.7.8", line="默认"),
    ]))
    module = FakeModule()
    record = find_record(module, client, FakeModels, "example.com", None, "www", "A", "电信")
    assert record["RecordId"] == 1


def test_find_record_returns_none_when_absent():
    client = FakeClient(FakeListResponse([]))
    module = FakeModule()
    assert find_record(module, client, FakeModels, "example.com", None, "www", "A", "默认") is None


def test_create_sends_all_provided_fields():
    client = FakeClient(create_response=FakeCreateResponse(42))
    module = FakeModule()
    record_id = _create(module, client, FakeModels, dict(BASE_PARAMS, value="1.2.3.4", ttl=300, weight=2, mx=10, remark="web", status="DISABLE"))
    assert record_id == 42
    request = client.calls[-1][1]
    assert request.Domain == "example.com"
    assert request.SubDomain == "www"
    assert request.RecordType == "A"
    assert request.RecordLine == "默认"
    assert request.Value == "1.2.3.4"
    assert request.TTL == 300
    assert request.Weight == 2
    assert request.MX == 10
    assert request.Remark == "web"
    assert request.Status == "DISABLE"


def test_create_omits_optional_fields():
    client = FakeClient(create_response=FakeCreateResponse(42))
    module = FakeModule()
    _create(module, client, FakeModels, dict(BASE_PARAMS, ttl=None))
    request = client.calls[-1][1]
    assert request.Value == "1.2.3.4"
    assert not hasattr(request, "TTL")
    assert not hasattr(request, "Weight")
    assert not hasattr(request, "MX")
    assert not hasattr(request, "Remark")
    assert not hasattr(request, "Status")


def test_update_sets_record_id_and_fields():
    client = FakeClient()
    module = FakeModule()
    _update(module, client, FakeModels, dict(BASE_PARAMS, value="5.6.7.8", ttl=60), 42)
    request = client.calls[-1][1]
    assert request.RecordId == 42
    assert request.Domain == "example.com"
    assert request.SubDomain == "www"
    assert request.RecordType == "A"
    assert request.Value == "5.6.7.8"
    assert request.TTL == 60


def test_update_with_domain_id():
    client = FakeClient()
    module = FakeModule()
    _update(module, client, FakeModels, dict(BASE_PARAMS, domain=None, domain_id=123), 42)
    request = client.calls[-1][1]
    assert request.DomainId == 123
    assert not hasattr(request, "Domain")


def test_delete_sends_record_id():
    client = FakeClient()
    module = FakeModule()
    _delete(module, client, FakeModels, BASE_PARAMS, 42)
    request = client.calls[-1][1]
    assert request.RecordId == 42
    assert request.Domain == "example.com"
