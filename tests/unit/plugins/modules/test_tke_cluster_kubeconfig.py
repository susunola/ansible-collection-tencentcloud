"""Unit tests for the tke_cluster_kubeconfig request builder."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.modules.tke_cluster_kubeconfig import (
    build_request,
    fetch_kubeconfig,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    DescribeClusterKubeconfigRequest = FakeRequest


class FakeClient(object):
    def __init__(self, kubeconfig="apiVersion: v1", exc=None):
        self.kubeconfig = kubeconfig
        self.exc = exc
        self.calls = []

    def DescribeClusterKubeconfig(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return SimpleNamespace(Kubeconfig=self.kubeconfig, RequestId="req-fake")


class FakeModule(object):
    def sdk_call(self, operation, request):
        return operation(request)


def test_build_request_intranet():
    request = build_request(FakeModels, "cls-xxxxxxxx", False)
    assert request.ClusterId == "cls-xxxxxxxx"
    assert request.IsExtranet is False


def test_build_request_extranet():
    request = build_request(FakeModels, "cls-xxxxxxxx", True)
    assert request.ClusterId == "cls-xxxxxxxx"
    assert request.IsExtranet is True


def test_fetch_kubeconfig_returns_content():
    client = FakeClient(kubeconfig="clusters: []")
    result = fetch_kubeconfig(FakeModule(), client, FakeModels, "cls-xxxxxxxx", False)
    assert result == "clusters: []"
    assert client.calls[0].ClusterId == "cls-xxxxxxxx"


def test_fetch_kubeconfig_surfaces_sdk_exceptions():
    client = FakeClient(exc=RuntimeError("boom"))
    try:
        fetch_kubeconfig(FakeModule(), client, FakeModels, "cls-xxxxxxxx", False)
        raise AssertionError("expected exception")
    except RuntimeError:
        pass
