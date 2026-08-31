"""Tests for GAAP real-server lookup helpers."""
from ansible_collections.susunola.tencentcloud.plugins.modules.gaap_real_server import find


class Item(object):
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=True): return self.value


class Response(object):
    def __init__(self, values): self.RealServerSet = [Item(v) for v in values]; self.TotalCount = len(values)


class Models(object):
    class DescribeRealServersRequest(object): pass


class Client(object):
    def __init__(self, values): self.values = values
    def DescribeRealServers(self, request): return Response(self.values)


class Module(object):
    def sdk_call(self, method, request): return method(request)
    def fail_json(self, **kwargs): raise AssertionError(kwargs)


def test_find_real_server_matches_exact_address():
    values = [{"RealServerId": "rs-old", "RealServerIP": "10.0.1.100"}, {"RealServerId": "rs-1", "RealServerIP": "10.0.1.10"}]
    assert find(Module(), Client(values), Models, address="10.0.1.10")["RealServerId"] == "rs-1"


def test_find_real_server_matches_explicit_id():
    values = [{"RealServerId": "rs-1", "RealServerIP": "10.0.1.10"}]
    assert find(Module(), Client(values), Models, real_server_id="rs-1")["RealServerIP"] == "10.0.1.10"
