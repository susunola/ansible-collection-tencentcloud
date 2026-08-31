"""Unit tests for the generic resource_id lookup helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest
from ansible.errors import AnsibleError

from ansible_collections.susunola.tencentcloud.plugins.lookup.resource_id import (
    assume_role,
    build_client_profile,
    build_request,
    resolve_resource,
    sdk_error_message,
)
from ansible_collections.susunola.tencentcloud.plugins.lookup import resource_id as lookup_mod


class Object(object):
    def __init__(self, **values):
        self.__dict__.update(values)


class Filter(Object):
    pass


class Request(Object):
    def __init__(self):
        pass


class Models(object):
    Filter = Filter
    QueryFilter = Filter
    DescribeVpcsRequest = Request
    DescribeSubnetsRequest = Request
    DescribeSecurityGroupsRequest = Request
    DescribeInstancesRequest = Request
    DescribeAutoScalingGroupsRequest = Request
    DescribeDisksRequest = Request
    DescribeLoadBalancersRequest = Request
    DescribeClustersRequest = Request
    DescribeDBInstancesRequest = Request
    DescribeServicesStatusRequest = Request
    DescribeEnvironmentsRequest = Request
    DescribeApplicationsRequest = Request
    DescribeCfsFileSystemsRequest = Request
    DescribeInstancesDetailRequest = Request
    DescribeInstanceListRequest = Request
    DescribeRocketMQClustersRequest = Request
    DescribeRabbitMQVipInstancesRequest = Request
    DescribePrometheusInstancesRequest = Request
    ListEventBusesRequest = Request


class Client(object):
    def __init__(self, response):
        self.response = response
        self.request = None

    def __getattr__(self, name):
        def call(request):
            self.request = request
            return self.response
        return call


def test_vpc_request_uses_exact_name_filter():
    request = build_request("vpc", Models, "production")
    assert request.Limit == "100"
    assert request.Offset == "0"
    assert request.Filters[0].Name == "vpc-name"
    assert request.Filters[0].Values == ["production"]


def test_subnet_request_scopes_to_vpc():
    request = build_request("subnet", Models, "app-a", "vpc-1")
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("subnet-name", ["app-a"]),
        ("vpc-id", ["vpc-1"]),
    ]


def test_cdb_request_uses_instance_names():
    request = build_request("cdb_instance", Models, "orders")
    assert request.InstanceNames == ["orders"]


def test_autoscaling_group_request_uses_exact_name_filter():
    request = build_request("autoscaling_group", Models, "web-fleet")
    assert request.Limit == 100
    assert request.Offset == 0
    assert request.Filters[0].Name == "auto-scaling-group-name"
    assert request.Filters[0].Values == ["web-fleet"]


def test_cbs_disk_request_uses_exact_name_filter():
    request = build_request("cbs_disk", Models, "application-data", offset=100)
    assert request.Limit == 100
    assert request.Offset == 100
    assert request.Filters[0].Name == "disk-name"
    assert request.Filters[0].Values == ["application-data"]


def test_lighthouse_instance_request_uses_exact_name_filter():
    request = build_request("lighthouse_instance", Models, "edge-node")
    assert request.Filters[0].Name == "instance-name"
    assert request.Filters[0].Values == ["edge-node"]


def test_postgresql_request_uses_instance_name_filter():
    request = build_request("postgresql_instance", Models, "orders")
    assert request.Filters[0].Name == "db-instance-name"
    assert request.Filters[0].Values == ["orders"]


def test_mariadb_request_uses_search_name():
    request = build_request("mariadb_instance", Models, "orders")
    assert request.SearchName == "orders"


def test_cynosdb_request_uses_cluster_name_query_filter():
    request = build_request("cynosdb_cluster", Models, "orders")
    assert request.Filters[0].Names == ["ClusterName"]
    assert request.Filters[0].Values == ["orders"]


def test_cfs_request_scans_names_with_numeric_pagination():
    request = build_request("cfs_file_system", Models, "shared-data", offset=100)
    assert request.Limit == 100
    assert request.Offset == 100


def test_ckafka_request_uses_instance_name_filter():
    request = build_request("ckafka_instance", Models, "event-platform")
    assert request.Filters[0].Name == "instance-name"
    assert request.Filters[0].Values == ["event-platform"]


def test_mqtt_request_scans_names_with_numeric_pagination():
    request = build_request("mqtt_instance", Models, "device-broker", offset=200)
    assert request.Limit == 100
    assert request.Offset == 200


def test_event_bus_request_scans_names_with_numeric_pagination():
    request = build_request("event_bus", Models, "application-events", offset=100)
    assert request.Limit == 100
    assert request.Offset == 100


def test_rocketmq_cluster_request_uses_name_keyword():
    request = build_request("rocketmq_cluster", Models, "orders", offset=100)
    assert request.NameKeyword == "orders"
    assert request.Offset == 100


def test_resolve_rocketmq_cluster_supports_nested_identity():
    response = Object(ClusterList=[Object(Info=Object(
        ClusterId="rocketmq-1", ClusterName="orders"))])
    assert resolve_resource(
        Client(response), Models, "rocketmq_cluster", "orders") == "rocketmq-1"


def test_rabbitmq_instance_request_uses_instance_name_filter():
    request = build_request("rabbitmq_instance", Models, "orders", offset=100)
    assert request.Filters[0].Name == "instanceName"
    assert request.Filters[0].Values == ["orders"]
    assert request.Offset == 100


def test_prometheus_instance_request_uses_instance_name():
    request = build_request("prometheus_instance", Models, "platform-metrics")
    assert request.InstanceName == "platform-metrics"
    assert request.Limit == 100


def test_alb_request_uses_token_pagination():
    request = build_request("alb_load_balancer", Models, "application", page_token="next-1")
    assert request.MaxResults == 100
    assert request.NextToken == "next-1"


def test_resolve_alb_follows_next_token():
    class TokenClient(object):
        def __init__(self):
            self.tokens = []

        def DescribeLoadBalancers(self, request):
            self.tokens.append(request.NextToken)
            if request.NextToken is None:
                return Object(LoadBalancers=[], NextToken="page-2")
            return Object(
                LoadBalancers=[Object(LoadBalancerId="alb-1", LoadBalancerName="application")],
                NextToken=None,
            )

    client = TokenClient()
    assert resolve_resource(client, Models, "alb_load_balancer", "application") == "alb-1"
    assert client.tokens == [None, "page-2"]


def test_tem_and_api_gateway_requests_use_product_specific_filters():
    environment = build_request("tem_environment", Models, "production")
    assert environment.SourceChannel == 0
    application = build_request("tem_application", Models, "orders")
    assert application.Keyword == "orders"
    service = build_request("api_gateway_service", Models, "orders-api")
    assert service.Filters[0].Name == "ServiceName"
    assert service.Filters[0].Values == ["orders-api"]


def test_resolve_resource_returns_exact_match_only():
    response = Object(VpcSet=[
        Object(VpcId="vpc-fuzzy", VpcName="production-old"),
        Object(VpcId="vpc-exact", VpcName="production"),
    ])
    assert resolve_resource(Client(response), Models, "vpc", "production") == "vpc-exact"


def test_resolve_resource_rejects_absent_and_ambiguous_names():
    with pytest.raises(AnsibleError, match="No vpc"):
        resolve_resource(Client(Object(VpcSet=[])), Models, "vpc", "missing")
    response = Object(VpcSet=[
        Object(VpcId="vpc-1", VpcName="duplicate"),
        Object(VpcId="vpc-2", VpcName="duplicate"),
    ])
    with pytest.raises(AnsibleError, match="Multiple vpc"):
        resolve_resource(Client(response), Models, "vpc", "duplicate")


def test_resolve_resource_supports_nested_result_collections():
    response = Object(Result=Object(ServiceSet=[
        Object(ServiceId="service-1", ServiceName="orders-api"),
    ]))
    assert resolve_resource(
        Client(response), Models, "api_gateway_service", "orders-api") == "service-1"


def test_resolve_resource_paginates_and_detects_cross_page_match():
    first = [Object(RegistryId="tcr-%03d" % index, RegistryName="other-%03d" % index)
             for index in range(100)]
    second = [Object(RegistryId="tcr-target", RegistryName="production")]

    class PagedClient(object):
        def __init__(self):
            self.offsets = []

        def DescribeInstances(self, request):
            self.offsets.append(request.Offset)
            return Object(Registries=first if request.Offset == 0 else second)

    client = PagedClient()
    assert resolve_resource(client, Models, "tcr_instance", "production") == "tcr-target"
    assert client.offsets == [0, 100]


def test_sdk_error_message_keeps_code_and_request_id():
    class Failure(Exception):
        def get_code(self):
            return "UnauthorizedOperation"

        def get_request_id(self):
            return "req-1"

    message = sdk_error_message("vpc", "production", Failure("denied"))
    assert "UnauthorizedOperation" in message
    assert "req-1" in message


def test_build_client_profile_applies_enterprise_client_options(monkeypatch):
    monkeypatch.setattr(lookup_mod, "HttpProfile", Object)
    monkeypatch.setattr(lookup_mod, "ClientProfile", Object)
    profile = build_client_profile("vpc.internal.example", 17, "ansible-test-client")
    assert profile.httpProfile.endpoint == "vpc.internal.example"
    assert profile.httpProfile.reqTimeout == 17
    assert profile.request_client == "ansible-test-client"
    assert profile.language == "en-US"


def test_assume_role_returns_temporary_credential(monkeypatch):
    class Credential(object):
        def __init__(self, secret_id, secret_key, token=None):
            self.values = (secret_id, secret_key, token)

    class StsClient(object):
        def __init__(self, credential, region, profile):
            self.region = region

        def AssumeRole(self, request):
            assert request.RoleArn == "qcs::cam::uin/1:roleName/reader"
            assert request.RoleSessionName == "lookup"
            assert request.DurationSeconds == 900
            return Object(Credentials=Object(
                TmpSecretId="tmp-id", TmpSecretKey="tmp-key", Token="tmp-token"))

    monkeypatch.setattr(lookup_mod, "tc_credential", Object(Credential=Credential))
    monkeypatch.setattr(lookup_mod, "HttpProfile", Object)
    monkeypatch.setattr(lookup_mod, "ClientProfile", Object)
    result = assume_role(
        Credential("base", "base-key"),
        "qcs::cam::uin/1:roleName/reader",
        "lookup", 900, "ap-guangzhou", 30, "agent",
        models=Object(AssumeRoleRequest=Request),
        client_module=Object(StsClient=StsClient),
    )
    assert result.values == ("tmp-id", "tmp-key", "tmp-token")
