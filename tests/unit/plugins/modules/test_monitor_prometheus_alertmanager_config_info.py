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

from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_prometheus_alertmanager_config as write
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_prometheus_alertmanager_config_info as info


class Request:
    pass


class Item:
    def __init__(self, config):
        self.config = config

    def _serialize(self, allow_none=True):
        return self.config


MODELS = types.SimpleNamespace(DescribePrometheusAlertmanagerConfigRequest=Request)


class Module:
    params = {"waiter_timeout": 10, "waiter_delay": 0}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise ValueError(kwargs["msg"])


def test_info_request_targets_instance():
    assert info.build_request(MODELS, "prom-1").InstanceId == "prom-1"


def test_write_waits_for_observed_config(monkeypatch):
    configs = iter([{"InhibitRules": []}, {"InhibitRules": [{"Equal": ["cluster"]}]}])

    class Client:
        def DescribePrometheusAlertmanagerConfig(self, request):
            assert request.InstanceId == "prom-1"
            return types.SimpleNamespace(AlertmanagerConfig=Item(next(configs)))

    monkeypatch.setattr(write.time, "sleep", lambda delay: None)
    target = {"InhibitRules": [{"Equal": ["cluster"]}]}
    assert write.wait_for_config(Module(), Client(), MODELS, "prom-1", target) == target


def test_write_timeout_reports_unsatisfied_config(monkeypatch):
    class Client:
        def DescribePrometheusAlertmanagerConfig(self, request):
            return types.SimpleNamespace(AlertmanagerConfig=Item({"InhibitRules": []}))

    ticks = iter([0, 11])
    monkeypatch.setattr(write.time, "monotonic", lambda: next(ticks))
    with pytest.raises(ValueError, match="Timed out waiting"):
        write.wait_for_config(Module(), Client(), MODELS, "prom-1", {"InhibitRules": [1]})
