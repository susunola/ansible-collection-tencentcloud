from __future__ import absolute_import, division, print_function

import sys
import types

import pytest

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_whitelist as write
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_whitelist_info as info


class Request:
    pass


MODELS = types.SimpleNamespace(DescribeGrafanaWhiteListRequest=Request)


class Module:
    params = {"instance_id": "grafana-1", "waiter_timeout": 10, "waiter_delay": 0}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise ValueError(kwargs["msg"])


def test_info_request_addresses_exact_instance():
    request = info.build_request(MODELS, "grafana-1")
    assert request.InstanceId == "grafana-1"


def test_write_waits_for_observed_whitelist(monkeypatch):
    responses = iter([["192.0.2.1"], ["203.0.113.1"]])

    class Client:
        def DescribeGrafanaWhiteList(self, request):
            assert request.InstanceId == "grafana-1"
            return types.SimpleNamespace(WhiteList=next(responses))

    monkeypatch.setattr(write.time, "sleep", lambda seconds: None)
    assert write.wait_for_whitelist(Module(), Client(), MODELS,
                                    "grafana-1", ["203.0.113.1"]) == ["203.0.113.1"]


def test_write_fails_when_whitelist_does_not_converge(monkeypatch):
    class Client:
        def DescribeGrafanaWhiteList(self, request):
            return types.SimpleNamespace(WhiteList=["192.0.2.1"])

    ticks = iter([0, 11])
    monkeypatch.setattr(write.time, "monotonic", lambda: next(ticks))
    with pytest.raises(ValueError, match="Timed out waiting"):
        write.wait_for_whitelist(Module(), Client(), MODELS,
                                 "grafana-1", ["203.0.113.1"])
