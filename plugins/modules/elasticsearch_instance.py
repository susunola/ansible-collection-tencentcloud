#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: elasticsearch_instance
short_description: Manage Tencent Cloud Elasticsearch clusters
version_added: "0.13.0"
description:
  - Create, rename and destroy Tencent Cloud Elasticsearch clusters
    through the C(es.v20180416) API.
  - This module is idempotent. Running it twice leaves the cluster
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - A cluster is identified by O(instance_id) or by O(name). The cluster
    configuration (version, node spec, disk) is only applied at creation;
    only the O(name) is enforced on an existing cluster with
    V(UpdateInstance).
  - Creation and destruction are asynchronous; the module waits for the
    cluster to reach Status 1 (running) or to disappear before returning,
    bounded by O(waiter_timeout).
options:
  state:
    description:
      - C(present) creates the cluster when it does not exist and renames
        it when O(name) differs. After creation the module waits for the
        cluster to reach Status 1 (running) before returning.
      - C(absent) destroys the cluster with V(DeleteInstance). The module
        waits for the cluster to disappear before returning.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - ID of an existing cluster, e.g. C(es-xxxxxxxx).
      - When given, the module operates on that cluster; otherwise it is
        matched by O(name).
    type: str
  name:
    description:
      - Name of the cluster, written to
        V(CreateInstanceRequest.InstanceName) and
        V(UpdateInstanceRequest.InstanceName).
    type: str
  zone:
    description:
      - Availability zone of the cluster, e.g. C(ap-guangzhou-3), written
        to V(CreateInstanceRequest.Zone).
      - Required when creating the cluster.
    type: str
  es_version:
    description:
      - Version of Elasticsearch, written to
        V(CreateInstanceRequest.EsVersion).
      - For example C(7.10.1), C(7.5.1) or C(6.8.2).
      - Required when creating the cluster.
    type: str
  vpc_id:
    description:
      - ID of the VPC the cluster runs in, written to
        V(CreateInstanceRequest.VpcId).
      - Required when creating the cluster.
    type: str
  subnet_id:
    description:
      - ID of the subnet the cluster runs in, written to
        V(CreateInstanceRequest.SubnetId).
      - Required when creating the cluster.
    type: str
  password:
    description:
      - Password of the C(elastic) user, written to
        V(CreateInstanceRequest.Password).
      - Required when creating the cluster.
      - The value is marked I(no_log) in the argument spec and never logged.
    type: str
  node_type:
    description:
      - Node spec of the data nodes, e.g. C(ES.S1.MEDIUM8), written to
        V(NodeInfo.NodeType).
      - Required when creating the cluster.
    type: str
  node_num:
    description:
      - Number of data nodes (2-50), written to V(NodeInfo.NodeNum).
      - Required when creating the cluster.
    type: int
  disk_type:
    description:
      - Disk type of the data nodes, written to V(NodeInfo.DiskType).
      - For example C(CLOUD_SSD) or C(CLOUD_PREMIUM).
      - Required when creating the cluster.
    type: str
  disk_size:
    description:
      - Disk size of each data node in GB, written to V(NodeInfo.DiskSize).
      - Required when creating the cluster.
    type: int
  license_type:
    description:
      - License type of the cluster, written to
        V(CreateInstanceRequest.LicenseType).
      - C(oss) is the open-source edition, C(basic) the basic edition and
        C(platinum) the platinum edition.
      - Only applied at creation.
    type: str
    choices: [oss, basic, platinum]
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 900
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-es) package on the controller.
  - Elasticsearch clusters are billed while present; destroy them as soon
    as they are no longer needed to avoid unnecessary charges.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a three-node Elasticsearch cluster
  susunola.tencentcloud.elasticsearch_instance:
    region: ap-guangzhou
    state: present
    name: logs-es
    zone: ap-guangzhou-3
    es_version: 7.10.1
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    password: "{{ es_password }}"
    node_type: ES.S1.MEDIUM8
    node_num: 3
    disk_type: CLOUD_SSD
    disk_size: 200
    license_type: basic

- name: Rename it
  susunola.tencentcloud.elasticsearch_instance:
    region: ap-guangzhou
    state: present
    name: logs-es-v2

- name: Destroy it
  susunola.tencentcloud.elasticsearch_instance:
    region: ap-guangzhou
    state: absent
    name: logs-es-v2
'''

RETURN = r'''
instance:
  description: The cluster as reported by V(DescribeInstances) after the
    operation.
  returned: success
  type: dict
  sample:
    InstanceId: es-xxxxxxxx
    InstanceName: logs-es
    Status: 1
    EsVersion: 7.10.1
    EsDomain: es-xxxxxxxx.ap-guangzhou.es.tencentcloudcs.com
    EsVip: 10.0.0.8
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load_es():
    from tencentcloud.es.v20180416 import models, es_client
    return models, es_client


def build_describe_request(models, instance_id, name):
    request = models.DescribeInstancesRequest()
    request.Limit = 100
    if instance_id:
        request.InstanceIds = [instance_id]
    elif name:
        request.InstanceNames = [name]
    return request


def _first(collection):
    return collection[0] if collection else None


def find_instance(module, client, models, instance_id, name):
    """Return the matching cluster dict or None."""
    request = build_describe_request(models, instance_id, name)
    response = module.sdk_call(client.DescribeInstances, request)
    if instance_id:
        instance = _first(response.InstanceList or [])
        return instance._serialize(allow_none=True) if instance is not None else None
    for instance in response.InstanceList or []:
        current = instance._serialize(allow_none=True)
        if current.get("InstanceName") == name:
            return current
    return None


def build_create_request(models, params):
    request = models.CreateInstanceRequest()
    request.Zone = params["zone"]
    request.EsVersion = params["es_version"]
    request.VpcId = params["vpc_id"]
    request.SubnetId = params["subnet_id"]
    request.Password = params["password"]
    if params["name"]:
        request.InstanceName = params["name"]
    node_info = models.NodeInfo()
    node_info.Type = "hotData"
    node_info.NodeNum = params["node_num"]
    node_info.NodeType = params["node_type"]
    node_info.DiskType = params["disk_type"]
    node_info.DiskSize = params["disk_size"]
    request.NodeInfoList = [node_info]
    if params["license_type"] is not None:
        request.LicenseType = params["license_type"]
    return request


def _create(module, client, models, params):
    request = build_create_request(models, params)
    module.sdk_call(client.CreateInstance, request)


def _rename(module, client, models, instance_id, name):
    request = models.UpdateInstanceRequest()
    request.InstanceId = instance_id
    request.InstanceName = name
    module.sdk_call(client.UpdateInstance, request)


def _destroy(module, client, models, instance_id):
    request = models.DeleteInstanceRequest()
    request.InstanceId = instance_id
    module.sdk_call(client.DeleteInstance, request)


def _status_poll(module, client, models, instance_id, gone_terminal=None):
    def poll():
        current = find_instance(module, client, models, instance_id, None)
        if current is None:
            return gone_terminal
        return current.get("Status")
    return poll


def _wait_status(module, client, models, instance_id, desired_states, gone_terminal=None):
    return wait_for_state(
        module,
        _status_poll(module, client, models, instance_id, gone_terminal),
        desired_states,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "instance_id": {"type": "str"},
            "name": {"type": "str"},
            "zone": {"type": "str"},
            "es_version": {"type": "str"},
            "vpc_id": {"type": "str"},
            "subnet_id": {"type": "str"},
            "password": {"type": "str", "no_log": True},
            "node_type": {"type": "str"},
            "node_num": {"type": "int"},
            "disk_type": {"type": "str"},
            "disk_size": {"type": "int"},
            "license_type": {"type": "str", "choices": ["oss", "basic", "platinum"]},
            "waiter_timeout": {"type": "int", "default": 900},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    instance_id = module.params["instance_id"]
    name = module.params["name"]

    if not instance_id and not name:
        module.fail_json(msg="instance_id or name is required to identify the cluster")

    models, es_client = _load_es()
    client = module.create_client(es_client.EsClient, "es.tencentcloudapi.com")

    try:
        current = find_instance(module, client, models, instance_id, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Elasticsearch cluster already absent")
        target_id = current["InstanceId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete Elasticsearch cluster")
        _destroy(module, client, models, target_id)
        _wait_status(module, client, models, target_id, [None], gone_terminal=None)
        module.exit_json(changed=True, **(diff or {}), instance=None, msg="Elasticsearch cluster destroyed")

    # state == present
    if current is None:
        missing = [
            key for key in ("name", "zone", "es_version", "vpc_id", "subnet_id", "password",
                            "node_type", "node_num", "disk_type", "disk_size")
            if not module.params[key]
        ]
        if missing:
            module.fail_json(msg="%s is required when creating an Elasticsearch cluster" % ", ".join(missing))
        desired = {"InstanceName": name}
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create Elasticsearch cluster")
        _create(module, client, models, module.params)
        current = find_instance(module, client, models, None, name)
        if current is not None:
            _wait_status(module, client, models, current["InstanceId"], [1])
            current = find_instance(module, client, models, current["InstanceId"], None)
        module.exit_json(changed=True, **(diff or {}), instance=current, msg="Elasticsearch cluster created")

    if name and current.get("InstanceName") != name:
        target_id = current["InstanceId"]
        diff = maybe_diff(module, {"InstanceName": current.get("InstanceName")}, {"InstanceName": name})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would rename Elasticsearch cluster")
        _rename(module, client, models, target_id, name)
        updated = find_instance(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=updated, msg="Elasticsearch cluster renamed")

    module.exit_json(changed=False, instance=current, msg="Elasticsearch cluster is up to date")


def main():
    run_module()


if __name__ == "__main__":
    main()
