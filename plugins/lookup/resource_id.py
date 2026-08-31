# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Resolve common Tencent Cloud resource names to stable resource IDs."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: resource_id
short_description: Resolve Tencent Cloud resource names to IDs
version_added: "0.14.0"
description:
  - Resolves exact resource names through Tencent Cloud read APIs.
  - Returns one ID per lookup term and fails when a name is absent or ambiguous.
  - Supports core network, compute, Auto Scaling, load-balancing, Kubernetes,
    database, API Gateway, container-registry and TEM application resources.
options:
  _terms:
    description: Exact resource names to resolve.
    required: true
  resource_type:
    description: Resource family to query.
    type: str
    required: true
    choices: [vpc, subnet, security_group, cvm_instance, lighthouse_instance, autoscaling_group, cbs_disk, clb_load_balancer, alb_load_balancer, tke_cluster, cdb_instance, postgresql_instance, mariadb_instance, cynosdb_cluster, redis_instance, mongodb_instance, cfs_file_system, ckafka_instance, mqtt_instance, rocketmq_cluster, rabbitmq_instance, prometheus_instance, edgeone_zone, event_bus, api_gateway_service, tcr_instance, tem_environment, tem_application]
  vpc_id:
    description: Optional VPC scope for subnet and CLB lookups.
    type: str
  region:
    description: Tencent Cloud region, falling back to C(TENCENTCLOUD_REGION).
    type: str
    env: [{name: TENCENTCLOUD_REGION}]
  secret_id:
    description: Tencent Cloud API secret ID.
    type: str
    env: [{name: TENCENTCLOUD_SECRET_ID}]
  secret_key:
    description: Tencent Cloud API secret key.
    type: str
    env: [{name: TENCENTCLOUD_SECRET_KEY}]
  token:
    description: Temporary credential token.
    type: str
    env: [{name: TENCENTCLOUD_TOKEN}]
  profile:
    description: TCCLI credential profile used as a fallback.
    type: str
    env: [{name: TENCENTCLOUD_PROFILE}]
  role_arn:
    description: CAM role ARN to assume before resolving resources.
    type: str
    env: [{name: TENCENTCLOUD_ROLE_ARN}]
  role_session_name:
    description: Session name used by STS AssumeRole.
    type: str
    default: ansible-tencentcloud-resource-lookup
  role_session_duration:
    description: STS session duration in seconds.
    type: int
    default: 7200
  endpoint:
    description: Override the selected product API endpoint.
    type: str
  timeout:
    description: API request timeout in seconds.
    type: int
    default: 60
  user_agent:
    description: Client identifier appended to Tencent Cloud SDK requests.
    type: str
    default: ansible-collection.susunola.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Resolve a VPC by exact name
  ansible.builtin.set_fact:
    production_vpc_id: >-
      {{ lookup('susunola.tencentcloud.resource_id', 'production',
                resource_type='vpc', region='ap-guangzhou') }}

- name: Resolve a subnet inside one VPC
  ansible.builtin.set_fact:
    app_subnet_id: >-
      {{ lookup('susunola.tencentcloud.resource_id', 'app-a',
                resource_type='subnet', vpc_id=production_vpc_id,
                region='ap-guangzhou') }}

- name: Resolve through an assumed cross-account role
  ansible.builtin.set_fact:
    shared_vpc_id: >-
      {{ lookup('susunola.tencentcloud.resource_id', 'shared-services',
                resource_type='vpc', role_arn=shared_account_role,
                region='ap-guangzhou') }}
'''

RETURN = r'''
_raw:
  description: IDs corresponding to the input terms in the same order.
  type: list
  elements: str
'''

import importlib

from ansible.errors import AnsibleError
from ansible.module_utils.common.text.converters import to_native
from ansible.plugins.lookup import LookupBase

from ansible_collections.susunola.tencentcloud.plugins.module_utils.client import load_profile

try:
    from tencentcloud.common import credential as tc_credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    tc_credential = ClientProfile = HttpProfile = None
    HAS_TENCENTCLOUD_SDK = False


RESOURCE_SPECS = {
    "vpc": ("vpc.v20170312", "VpcClient", "vpc.tencentcloudapi.com", "DescribeVpcs", "VpcSet", "VpcId", "VpcName"),
    "subnet": ("vpc.v20170312", "VpcClient", "vpc.tencentcloudapi.com", "DescribeSubnets", "SubnetSet", "SubnetId", "SubnetName"),
    "security_group": ("vpc.v20170312", "VpcClient", "vpc.tencentcloudapi.com", "DescribeSecurityGroups", "SecurityGroupSet", "SecurityGroupId", "SecurityGroupName"),
    "cvm_instance": ("cvm.v20170312", "CvmClient", "cvm.tencentcloudapi.com", "DescribeInstances", "InstanceSet", "InstanceId", "InstanceName"),
    "lighthouse_instance": ("lighthouse.v20200324", "LighthouseClient", "lighthouse.tencentcloudapi.com", "DescribeInstances", "InstanceSet", "InstanceId", "InstanceName"),
    "autoscaling_group": ("autoscaling.v20180419", "AutoscalingClient", "as.tencentcloudapi.com", "DescribeAutoScalingGroups", "AutoScalingGroupSet", "AutoScalingGroupId", "AutoScalingGroupName"),
    "cbs_disk": ("cbs.v20170312", "CbsClient", "cbs.tencentcloudapi.com", "DescribeDisks", "DiskSet", "DiskId", "DiskName"),
    "clb_load_balancer": ("clb.v20180317", "ClbClient", "clb.tencentcloudapi.com", "DescribeLoadBalancers", "LoadBalancerSet", "LoadBalancerId", "LoadBalancerName"),
    "alb_load_balancer": ("alb.v20251030", "AlbClient", "alb.tencentcloudapi.com", "DescribeLoadBalancers", "LoadBalancers", "LoadBalancerId", "LoadBalancerName"),
    "tke_cluster": ("tke.v20180525", "TkeClient", "tke.tencentcloudapi.com", "DescribeClusters", "Clusters", "ClusterId", "ClusterName"),
    "cdb_instance": ("cdb.v20170320", "CdbClient", "cdb.tencentcloudapi.com", "DescribeDBInstances", "Items", "InstanceId", "InstanceName"),
    "postgresql_instance": ("postgres.v20170312", "PostgresClient", "postgres.tencentcloudapi.com", "DescribeDBInstances", "DBInstanceSet", "DBInstanceId", "DBInstanceName"),
    "mariadb_instance": ("mariadb.v20170312", "MariadbClient", "mariadb.tencentcloudapi.com", "DescribeDBInstances", "Instances", "InstanceId", "InstanceName"),
    "cynosdb_cluster": ("cynosdb.v20190107", "CynosdbClient", "cynosdb.tencentcloudapi.com", "DescribeClusters", "ClusterSet", "ClusterId", "ClusterName"),
    "redis_instance": ("redis.v20180412", "RedisClient", "redis.tencentcloudapi.com", "DescribeInstances", "InstanceSet", "InstanceId", "InstanceName"),
    "mongodb_instance": ("mongodb.v20190725", "MongodbClient", "mongodb.tencentcloudapi.com", "DescribeDBInstances", "InstanceDetails", "InstanceId", "InstanceName"),
    "cfs_file_system": ("cfs.v20190719", "CfsClient", "cfs.tencentcloudapi.com", "DescribeCfsFileSystems", "FileSystems", "FileSystemId", "Name"),
    "ckafka_instance": ("ckafka.v20190819", "CkafkaClient", "ckafka.tencentcloudapi.com", "DescribeInstancesDetail", "Result.InstanceList", "InstanceId", "InstanceName"),
    "mqtt_instance": ("mqtt.v20240516", "MqttClient", "mqtt.tencentcloudapi.com", "DescribeInstanceList", "Data", "InstanceId", "InstanceName"),
    "rocketmq_cluster": ("tdmq.v20200217", "TdmqClient", "tdmq.tencentcloudapi.com", "DescribeRocketMQClusters", "ClusterList", "Info.ClusterId", "Info.ClusterName"),
    "rabbitmq_instance": ("tdmq.v20200217", "TdmqClient", "tdmq.tencentcloudapi.com", "DescribeRabbitMQVipInstances", "Instances", "InstanceId", "InstanceName"),
    "prometheus_instance": ("monitor.v20180724", "MonitorClient", "monitor.tencentcloudapi.com", "DescribePrometheusInstances", "InstanceSet", "InstanceId", "InstanceName"),
    "edgeone_zone": ("teo.v20220901", "TeoClient", "teo.tencentcloudapi.com", "DescribeZones", "Zones", "ZoneId", "ZoneName"),
    "event_bus": ("eb.v20210416", "EbClient", "eb.tencentcloudapi.com", "ListEventBuses", "EventBuses", "EventBusId", "EventBusName"),
    "api_gateway_service": ("apigateway.v20180808", "ApigatewayClient", "apigateway.tencentcloudapi.com", "DescribeServicesStatus", "Result.ServiceSet", "ServiceId", "ServiceName"),
    "tcr_instance": ("tcr.v20190924", "TcrClient", "tcr.tencentcloudapi.com", "DescribeInstances", "Registries", "RegistryId", "RegistryName"),
    "tem_environment": ("tem.v20210701", "TemClient", "tem.tencentcloudapi.com", "DescribeEnvironments", "Result.Records", "EnvironmentId", "EnvironmentName"),
    "tem_application": ("tem.v20210701", "TemClient", "tem.tencentcloudapi.com", "DescribeApplications", "Result.Records", "ApplicationId", "ApplicationName"),
}


def build_request(resource_type, models, name, vpc_id=None, offset=0, page_token=None):
    """Build the narrowest supported exact-name request."""
    request_names = {
        "vpc": "DescribeVpcsRequest",
        "subnet": "DescribeSubnetsRequest",
        "security_group": "DescribeSecurityGroupsRequest",
        "cvm_instance": "DescribeInstancesRequest",
        "lighthouse_instance": "DescribeInstancesRequest",
        "autoscaling_group": "DescribeAutoScalingGroupsRequest",
        "cbs_disk": "DescribeDisksRequest",
        "clb_load_balancer": "DescribeLoadBalancersRequest",
        "alb_load_balancer": "DescribeLoadBalancersRequest",
        "tke_cluster": "DescribeClustersRequest",
        "cdb_instance": "DescribeDBInstancesRequest",
        "postgresql_instance": "DescribeDBInstancesRequest",
        "mariadb_instance": "DescribeDBInstancesRequest",
        "cynosdb_cluster": "DescribeClustersRequest",
        "redis_instance": "DescribeInstancesRequest",
        "mongodb_instance": "DescribeDBInstancesRequest",
        "cfs_file_system": "DescribeCfsFileSystemsRequest",
        "ckafka_instance": "DescribeInstancesDetailRequest",
        "mqtt_instance": "DescribeInstanceListRequest",
        "rocketmq_cluster": "DescribeRocketMQClustersRequest",
        "rabbitmq_instance": "DescribeRabbitMQVipInstancesRequest",
        "prometheus_instance": "DescribePrometheusInstancesRequest",
        "edgeone_zone": "DescribeZonesRequest",
        "event_bus": "ListEventBusesRequest",
        "api_gateway_service": "DescribeServicesStatusRequest",
        "tcr_instance": "DescribeInstancesRequest",
        "tem_environment": "DescribeEnvironmentsRequest",
        "tem_application": "DescribeApplicationsRequest",
    }
    request = getattr(models, request_names[resource_type])()
    if resource_type == "alb_load_balancer":
        request.MaxResults = 100
        request.NextToken = page_token
    elif resource_type in ("vpc", "subnet", "security_group"):
        request.Limit = "100"
        request.Offset = str(offset)
    else:
        request.Limit = 100
        request.Offset = offset
    if resource_type == "cdb_instance":
        request.InstanceNames = [name]
    elif resource_type == "postgresql_instance":
        api_filter = models.Filter()
        api_filter.Name, api_filter.Values = "db-instance-name", [name]
        request.Filters = [api_filter]
    elif resource_type == "mariadb_instance":
        request.SearchName = name
    elif resource_type == "cynosdb_cluster":
        api_filter = models.QueryFilter()
        api_filter.Names, api_filter.Values = ["ClusterName"], [name]
        request.Filters = [api_filter]
    elif resource_type == "redis_instance":
        request.InstanceName = name
    elif resource_type == "mongodb_instance":
        request.SearchKey = name
    elif resource_type == "cfs_file_system":
        pass
    elif resource_type == "ckafka_instance":
        api_filter = models.Filter()
        api_filter.Name, api_filter.Values = "instance-name", [name]
        request.Filters = [api_filter]
    elif resource_type == "mqtt_instance":
        pass
    elif resource_type == "event_bus":
        pass
    elif resource_type == "rocketmq_cluster":
        request.NameKeyword = name
    elif resource_type == "rabbitmq_instance":
        api_filter = models.Filter()
        api_filter.Name, api_filter.Values = "instanceName", [name]
        request.Filters = [api_filter]
    elif resource_type == "prometheus_instance":
        request.InstanceName = name
    elif resource_type == "edgeone_zone":
        api_filter = models.AdvancedFilter()
        api_filter.Name, api_filter.Values = "zone-name", [name]
        request.Filters = [api_filter]
    elif resource_type == "alb_load_balancer":
        pass
    elif resource_type == "api_gateway_service":
        api_filter = models.Filter()
        api_filter.Name, api_filter.Values = "ServiceName", [name]
        request.Filters = [api_filter]
    elif resource_type == "tem_environment":
        request.SourceChannel = 0
    elif resource_type == "tem_application":
        request.Keyword = name
        request.SourceChannel = 0
    elif resource_type == "tcr_instance":
        pass
    elif resource_type == "autoscaling_group":
        api_filter = models.Filter()
        api_filter.Name, api_filter.Values = "auto-scaling-group-name", [name]
        request.Filters = [api_filter]
    elif resource_type == "cbs_disk":
        api_filter = models.Filter()
        api_filter.Name, api_filter.Values = "disk-name", [name]
        request.Filters = [api_filter]
    elif resource_type == "lighthouse_instance":
        api_filter = models.Filter()
        api_filter.Name, api_filter.Values = "instance-name", [name]
        request.Filters = [api_filter]
    elif resource_type == "clb_load_balancer":
        request.LoadBalancerName = name
        if vpc_id:
            request.VpcId = vpc_id
    else:
        filter_names = {
            "vpc": "vpc-name",
            "subnet": "subnet-name",
            "security_group": "security-group-name",
            "cvm_instance": "instance-name",
            "tke_cluster": "cluster-name",
        }
        api_filter = models.Filter()
        api_filter.Name = filter_names[resource_type]
        api_filter.Values = [name]
        request.Filters = [api_filter]
        if resource_type == "subnet" and vpc_id:
            scope = models.Filter()
            scope.Name = "vpc-id"
            scope.Values = [vpc_id]
            request.Filters.append(scope)
    return request


def resolve_resource(client, models, resource_type, name, vpc_id=None):
    """Return one exact-match ID or raise a useful lookup error."""
    spec = RESOURCE_SPECS[resource_type]
    matches = []
    offset = 0
    page_token = None
    while True:
        response = getattr(client, spec[3])(
            build_request(resource_type, models, name, vpc_id, offset, page_token))
        values = response
        for attribute in spec[4].split("."):
            values = getattr(values, attribute, None)
            if values is None:
                break
        page = list(values or [])
        matches.extend(item for item in page if nested_attribute(item, spec[6]) == name)
        if resource_type == "alb_load_balancer":
            page_token = getattr(response, "NextToken", None)
            if not page_token:
                break
            continue
        if len(page) < 100:
            break
        offset += len(page)
    if not matches:
        raise AnsibleError("No %s named %r was found" % (resource_type, name))
    if len(matches) > 1:
        raise AnsibleError("Multiple %s resources named %r matched; use an explicit ID" % (resource_type, name))
    return str(nested_attribute(matches[0], spec[5]))


def nested_attribute(value, path):
    """Resolve dotted SDK response attributes without serializing secrets."""
    for attribute in path.split("."):
        value = getattr(value, attribute, None)
        if value is None:
            break
    return value


def sdk_error_message(resource_type, name, exc):
    detail = to_native(exc)
    code = getattr(exc, "get_code", lambda: None)()
    request_id = getattr(exc, "get_request_id", lambda: None)()
    if code:
        detail += " (%s)" % code
    if request_id:
        detail += " [RequestId: %s]" % request_id
    return "Resolve %s %r failed: %s" % (resource_type, name, detail)


def build_client_profile(endpoint, timeout=60, user_agent=None):
    """Build the same endpoint, timeout and client identifier profile as modules."""
    http_profile = HttpProfile()
    http_profile.endpoint = endpoint
    http_profile.reqTimeout = timeout
    profile = ClientProfile()
    profile.httpProfile = http_profile
    profile.language = "en-US"
    if user_agent:
        profile.request_client = user_agent
    return profile


def assume_role(base_credential, role_arn, session_name, duration, region, timeout, user_agent,
                models=None, client_module=None):
    """Exchange base credentials for temporary STS role credentials."""
    if models is None or client_module is None:
        package = "tencentcloud.sts.v20180813"
        models = importlib.import_module(package + ".models")
        client_module = importlib.import_module(package + ".sts_client")
    client = client_module.StsClient(
        base_credential,
        region,
        build_client_profile("sts.tencentcloudapi.com", timeout, user_agent),
    )
    request = models.AssumeRoleRequest()
    request.RoleArn = role_arn
    request.RoleSessionName = session_name
    request.DurationSeconds = duration
    temporary = client.AssumeRole(request).Credentials
    return tc_credential.Credential(
        temporary.TmpSecretId,
        temporary.TmpSecretKey,
        temporary.Token,
    )


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):
        if not HAS_TENCENTCLOUD_SDK:
            raise AnsibleError("The tencentcloud-sdk-python package is required on the Ansible controller.")
        self.set_options(var_options=variables, direct=kwargs)
        resource_type = self.get_option("resource_type")
        if resource_type not in RESOURCE_SPECS:
            raise AnsibleError("Unsupported resource_type %r" % resource_type)
        secret_id = self.get_option("secret_id")
        secret_key = self.get_option("secret_key")
        region = self.get_option("region")
        if not secret_id or not secret_key or not region:
            profile = load_profile(self.get_option("profile"))
            secret_id = secret_id or profile.get("secret_id")
            secret_key = secret_key or profile.get("secret_key")
            region = region or profile.get("region")
        if not secret_id or not secret_key or not region:
            raise AnsibleError("Set Tencent Cloud credentials and region explicitly, through environment variables, or in a TCCLI profile.")

        spec = RESOURCE_SPECS[resource_type]
        package = "tencentcloud.%s" % spec[0]
        models = importlib.import_module(package + ".models")
        client_module = importlib.import_module(package + "." + spec[0].split(".")[0] + "_client")
        timeout = self.get_option("timeout")
        user_agent = self.get_option("user_agent")
        profile = build_client_profile(self.get_option("endpoint") or spec[2], timeout, user_agent)
        credential = tc_credential.Credential(secret_id, secret_key, self.get_option("token"))
        if self.get_option("role_arn"):
            try:
                credential = assume_role(
                    credential,
                    self.get_option("role_arn"),
                    self.get_option("role_session_name"),
                    self.get_option("role_session_duration"),
                    region,
                    timeout,
                    user_agent,
                )
            except Exception as exc:
                raise AnsibleError(sdk_error_message("sts_role", self.get_option("role_arn"), exc))
        client = getattr(client_module, spec[1])(credential, region, profile)
        values = []
        for name in terms:
            try:
                values.append(resolve_resource(client, models, resource_type, name, self.get_option("vpc_id")))
            except AnsibleError:
                raise
            except Exception as exc:
                raise AnsibleError(sdk_error_message(resource_type, name, exc))
        return values
