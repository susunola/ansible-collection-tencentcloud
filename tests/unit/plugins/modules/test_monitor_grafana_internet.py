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

from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_internet as mod


class Request:
    pass


MODELS = types.SimpleNamespace(DescribeGrafanaInstancesRequest=Request)


class Module:
    params = {"waiter_timeout": 10, "waiter_delay": 0}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise ValueError(kwargs["msg"])


def test_read_uses_current_instances_field_and_exact_id():
    class Client:
        def DescribeGrafanaInstances(self, request):
            return types.SimpleNamespace(Instances=[
                types.SimpleNamespace(InstanceId="other", InternetUrl="https://other"),
                types.SimpleNamespace(InstanceId="grafana-1", InternetUrl=""),
            ], InstanceSet=None)

    assert mod.read_internet_state(Module(), Client(), MODELS, "grafana-1") is False


def test_read_rejects_missing_instance():
    class Client:
        def DescribeGrafanaInstances(self, request):
            return types.SimpleNamespace(Instances=[], InstanceSet=[])

    with pytest.raises(ValueError, match="was not found"):
        mod.read_internet_state(Module(), Client(), MODELS, "grafana-1")


def test_waiter_observes_internet_url(monkeypatch):
    responses = iter(["", "https://grafana.example"])

    class Client:
        def DescribeGrafanaInstances(self, request):
            return types.SimpleNamespace(Instances=[
                types.SimpleNamespace(InstanceId="grafana-1", InternetUrl=next(responses)),
            ])

    monkeypatch.setattr(mod.time, "sleep", lambda delay: None)
    assert mod.wait_for_internet_state(Module(), Client(), MODELS, "grafana-1", True) is True
