#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: clb_load_balancer
short_description: Manage Tencent Cloud CLB load balancers
version_added: "0.10.0"
description:
  - Create, update, and delete Tencent Cloud CLB (Cloud Load Balancer)
    instances through the C(clb.v20180317) API.
  - This module is idempotent. Running it twice leaves the load balancer
    unchanged and the second run reports C(changed=false). When
    O(load_balancer_id) is not given, the instance is matched by the exact
    O(name) (and O(vpc_id) when given) from the fuzzy V(DescribeLoadBalancers)
    result set.
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the load balancer with V(CreateLoadBalancer) when
        it does not exist, and updates its name, network billing and tags when
        it does.
      - C(absent) deletes the load balancer with V(DeleteLoadBalancer) and
        waits until it is gone.
    type: str
    choices: [present, absent]
    default: present
  load_balancer_id:
    description:
      - ID of an existing load balancer, e.g. C(lb-xxxxxxxx).
      - When given, the module operates on that instance; otherwise the
        instance is matched by O(name) through V(DescribeLoadBalancers).
    type: str
  name:
    description:
      - Name of the load balancer. Required when C(state=present).
      - V(DescribeLoadBalancers) matches names fuzzily; the module filters the
        result for an exact name match before acting.
    type: str
  load_balancer_type:
    description:
      - Network type of the load balancer, C(OPEN) for public or C(INTERNAL)
        for private.
      - Only applied at creation; changing it on an existing instance fails
        with a message asking to recreate the load balancer.
    type: str
    choices: [OPEN, INTERNAL]
  vpc_id:
    description:
      - VPC ID (C(vpc-xxxxxxxx)) the load balancer belongs to.
      - Only applied at creation; changing it on an existing instance fails
        with a message asking to recreate the load balancer.
      - Also used to disambiguate the name match when O(load_balancer_id) is
        not given.
    type: str
  subnet_id:
    description:
      - Subnet ID (C(subnet-xxxxxxxx)) the VIP of a private load balancer is
        allocated from. Required by the API when creating an C(INTERNAL)
        load balancer.
      - Only applied at creation; changing it on an existing instance fails
        with a message asking to recreate the load balancer.
    type: str
  project_id:
    description:
      - Project ID the load balancer belongs to. Only applied at creation;
        changing it after creation is a no-op.
    type: int
    default: 0
  internet_charge_type:
    description:
      - Network billing mode written to
        V(InternetAccessible.InternetChargeType).
      - On an existing instance the value is reconciled through
        V(ModifyLoadBalancerAttributes).
    type: str
    choices: [BANDWIDTH_PREPAID, TRAFFIC_POSTPAID_BY_HOUR, BANDWIDTH_POSTPAID_BY_HOUR, BANDWIDTH_PACKAGE]
  internet_max_bandwidth_out:
    description:
      - Maximum outbound bandwidth in Mbps, written to
        V(InternetAccessible.InternetMaxBandwidthOut).
      - On an existing instance the value is reconciled through
        V(ModifyLoadBalancerAttributes).
    type: int
  client_token:
    description:
      - Idempotency token passed to V(CreateLoadBalancer) as C(ClientToken),
        so a retried creation does not provision a second instance.
      - Only applied at creation; the value is not sensitive.
    type: str
  tags:
    description:
      - Tags to apply to the load balancer as a dict, for example
        I(env=prod).
      - At creation the tags are bound through V(CreateLoadBalancer); on an
        existing instance they are reconciled through the tag service
        (C(ServiceType=clb), C(ResourcePrefix=clb)).
      - Existing tags not listed are removed; listed tags with a different
        value are updated. Requires the C(tencentcloud-sdk-python-tag) package
        and the tag service to be enabled for the account.
    type: dict
    default: {}
  retries:
    description:
      - Maximum number of retry attempts for throttled or transient API
        failures, using exponential backoff with jitter.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Maximum time in seconds to wait for the load balancer to reach the
        running state after creation, or to disappear after deletion.
    type: int
    default: 120
  waiter_delay:
    description: Interval in seconds between state polls while waiting.
    type: int
    default: 5
  user_agent:
    description:
      - User-Agent string sent with API requests.
    type: str
    default: ansible-collection.tencentcloud.cloud
notes:
  - Requires the C(tencentcloud-sdk-python-clb) package on the controller.
  - Tag reconciliation additionally requires C(tencentcloud-sdk-python-tag).
  - Uses the C(clb.tencentcloudapi.com) endpoint by default.
  - CLB operations are asynchronous. After creation the module polls
    V(DescribeLoadBalancers) until the instance C(Status) is C(1) (running),
    and V(ModifyLoadBalancerAttributes) is confirmed through
    V(DescribeTaskStatus).
  - Network type, VPC and subnet cannot be changed on an existing load
    balancer; the module fails with a clear message when they drift instead of
    silently ignoring them.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a public CLB load balancer
  tencentcloud.cloud.clb_load_balancer:
    region: ap-guangzhou
    state: present
    name: web-lb
    load_balancer_type: OPEN
    vpc_id: vpc-xxxxxxxx
    internet_charge_type: TRAFFIC_POSTPAID_BY_HOUR
    internet_max_bandwidth_out: 10
    tags:
      env: prod
      tier: web

- name: Create a private CLB load balancer
  tencentcloud.cloud.clb_load_balancer:
    region: ap-guangzhou
    state: present
    name: internal-lb
    load_balancer_type: INTERNAL
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx

- name: Preview the changes without applying them
  tencentcloud.cloud.clb_load_balancer:
    region: ap-guangzhou
    state: present
    name: web-lb
    load_balancer_type: OPEN
  check_mode: true

- name: Delete a load balancer
  tencentcloud.cloud.clb_load_balancer:
    region: ap-guangzhou
    state: absent
    name: web-lb
'''

RETURN = r'''
load_balancer:
  description: The load balancer as reported by V(DescribeLoadBalancers) after the operation.
  returned: success
  type: dict
  sample:
    LoadBalancerId: lb-xxxxxxxx
    LoadBalancerName: web-lb
    LoadBalancerType: OPEN
    Status: 1
    VpcId: vpc-xxxxxxxx
    LoadBalancerVips:
      - 1.2.3.4
    Tags: []
'''

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.tencentcloud.cloud.plugins.module_utils.errors import (
    is_idempotent_success,
)
from ansible_collections.tencentcloud.cloud.plugins.module_utils.tagging import (
    compare_tags,
)
from ansible_collections.tencentcloud.cloud.plugins.module_utils.waiters import (
    wait_for_state,
    wait_for_task,
    wait_until_gone,
)


def _load_clb():
    from tencentcloud.clb.v20180317 import models, clb_client
    return models, clb_client


def _load_tag():
    from tencentcloud.tag.v20180813 import models as tag_models, tag_client
    return tag_models, tag_client


class _LoadBalancerGone(Exception):
    """Synthetic not-found error so wait_until_gone accepts an empty result."""

    def get_code(self):
        return "InvalidParameter.LBIdNotFound"


def build_describe_request(models, load_balancer_id, name, vpc_id):
    request = models.DescribeLoadBalancersRequest()
    request.Offset = 0
    request.Limit = 100
    if load_balancer_id:
        request.LoadBalancerIds = [load_balancer_id]
    else:
        if name:
            # LoadBalancerName is a fuzzy filter; exact matching is done
            # client-side on the result set.
            request.LoadBalancerName = name
        if vpc_id:
            request.VpcId = vpc_id
    return request


def _build_tag_infos(models, tags):
    """Build a list of SDK ``TagInfo`` objects from a normalized dict.

    CLB models use ``TagInfo`` (``TagKey``/``TagValue``) instead of the
    ``Tag`` (``Key``/``Value``) class most other services expose, so the
    shared ``build_sdk_tags`` helper does not apply here.
    """
    if not tags:
        return None
    tag_infos = []
    for key, value in sorted(tags.items()):
        tag_info = models.TagInfo()
        tag_info.TagKey = key
        tag_info.TagValue = value
        tag_infos.append(tag_info)
    return tag_infos


def build_create_request(models, params):
    request = models.CreateLoadBalancerRequest()
    # Forward=1 selects the current (non-classic) load balancer type; the API
    # accepts no other value.
    request.Forward = 1
    request.LoadBalancerName = params["name"]
    request.ProjectId = params["project_id"]
    if params["load_balancer_type"]:
        request.LoadBalancerType = params["load_balancer_type"]
    if params["vpc_id"]:
        request.VpcId = params["vpc_id"]
    if params["subnet_id"]:
        request.SubnetId = params["subnet_id"]
    if params["client_token"]:
        request.ClientToken = params["client_token"]
    if (params["internet_charge_type"] is not None
            or params["internet_max_bandwidth_out"] is not None):
        request.InternetAccessible = models.InternetAccessible()
        if params["internet_charge_type"] is not None:
            request.InternetAccessible.InternetChargeType = params["internet_charge_type"]
        if params["internet_max_bandwidth_out"] is not None:
            request.InternetAccessible.InternetMaxBandwidthOut = params["internet_max_bandwidth_out"]
    if params["tags"]:
        request.Tags = _build_tag_infos(models, params["tags"])
    return request


def find_load_balancer(module, client, models, load_balancer_id, name, vpc_id):
    """Return the matching load balancer dict or None.

    The API matches ``LoadBalancerName`` fuzzily, so the result set is
    filtered client-side for an exact name (and VPC) match.
    """
    request = build_describe_request(models, load_balancer_id, name, vpc_id)
    response = module.sdk_call(client.DescribeLoadBalancers, request)
    for candidate in response.LoadBalancerSet or []:
        current = candidate._serialize(allow_none=True)
        if load_balancer_id:
            # An ID lookup addresses exactly one instance; the name is the
            # desired value to enforce, not a lookup criterion.
            if current.get("LoadBalancerId") != load_balancer_id:
                continue
        else:
            if name and current.get("LoadBalancerName") != name:
                continue
            if vpc_id and current.get("VpcId") != vpc_id:
                continue
        return current
    return None


def immutable_drift(current, load_balancer_type=None, vpc_id=None, subnet_id=None):
    """Return the creation-only fields that drifted on an existing instance."""
    drifted = []
    if load_balancer_type and current.get("LoadBalancerType") != load_balancer_type:
        drifted.append("load_balancer_type")
    if vpc_id and current.get("VpcId") != vpc_id:
        drifted.append("vpc_id")
    if subnet_id and current.get("SubnetId") != subnet_id:
        drifted.append("subnet_id")
    return drifted


def _create(module, client, models, params):
    """Create the load balancer and return its ID.

    ``CreateLoadBalancer`` occasionally returns an empty ``LoadBalancerIds``
    list while the order is still processing; in that case the instance ID is
    recovered from ``DescribeTaskStatus`` once the task finishes.
    """
    request = build_create_request(models, params)
    response = module.sdk_call(client.CreateLoadBalancer, request)
    ids = response.LoadBalancerIds or []
    if ids:
        return ids[0]
    task = _wait_task(module, client, models, response.RequestId)
    ids = getattr(task, "LoadBalancerIds", None) or []
    if not ids:
        module.fail_json(
            msg="CreateLoadBalancer returned no instance ID and the task "
                "reported none either; check the console for task %s" % response.RequestId,
            request_id=response.RequestId,
        )
    return ids[0]


def _delete(module, client, models, load_balancer_id):
    request = models.DeleteLoadBalancerRequest()
    request.LoadBalancerIds = [load_balancer_id]
    module.sdk_call(client.DeleteLoadBalancer, request)


def _update_attributes(module, client, models, load_balancer_id, name, internet_charge_type, internet_max_bandwidth_out):
    """Update the mutable attributes; returns the async task request ID."""
    request = models.ModifyLoadBalancerAttributesRequest()
    request.LoadBalancerId = load_balancer_id
    if name is not None:
        request.LoadBalancerName = name
    if internet_charge_type is not None or internet_max_bandwidth_out is not None:
        request.InternetChargeInfo = models.InternetAccessible()
        if internet_charge_type is not None:
            request.InternetChargeInfo.InternetChargeType = internet_charge_type
        if internet_max_bandwidth_out is not None:
            request.InternetChargeInfo.InternetMaxBandwidthOut = internet_max_bandwidth_out
    response = module.sdk_call(client.ModifyLoadBalancerAttributes, request)
    return response.RequestId


def _apply_tags(module, client, tag_models, load_balancer_id, to_add, to_remove):
    """Reconcile tags through the tag service.

    The tag service model differs from the CLB model: resources are addressed
    by a plural ``ResourceIds`` list and tags by ``TagKey``/``TagValue``.
    CLB instances use ``ServiceType=clb`` and ``ResourcePrefix=clb``.
    Each tag key is processed independently.
    """
    for key, value in sorted(to_add.items()):
        request = tag_models.AttachResourcesTagRequest()
        request.ServiceType = "clb"
        request.ResourceIds = [load_balancer_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "clb"
        request.TagKey = key
        request.TagValue = value
        module.sdk_call(client.AttachResourcesTag, request)
    for key in to_remove:
        request = tag_models.DetachResourcesTagRequest()
        request.ServiceType = "clb"
        request.ResourceIds = [load_balancer_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "clb"
        request.TagKey = key
        module.sdk_call(client.DetachResourcesTag, request)


def _clb_tags_to_sdk_shape(tag_infos):
    """Convert serialized ``TagInfo`` dicts to the Key/Value shape compare_tags expects."""
    return [
        {"Key": tag.get("TagKey"), "Value": tag.get("TagValue")}
        for tag in tag_infos or []
    ]


def _wait_task(module, client, models, task_id):
    """Wait for an asynchronous CLB task; returns the task response."""
    def poll():
        request = models.DescribeTaskStatusRequest()
        request.TaskId = task_id
        response = module.sdk_call(client.DescribeTaskStatus, request)
        return response.Status, response.Message, response

    return wait_for_task(
        module,
        poll,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def _state_poll(module, client, models, load_balancer_id):
    def poll():
        current = find_load_balancer(module, client, models, load_balancer_id, None, None)
        if current is None:
            raise _LoadBalancerGone("load balancer %s is gone" % load_balancer_id)
        return current.get("Status")
    return poll


def _wait_running(module, client, models, load_balancer_id):
    return wait_for_state(
        module,
        _state_poll(module, client, models, load_balancer_id),
        [1],
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def _wait_gone(module, client, models, load_balancer_id):
    def poll():
        current = find_load_balancer(module, client, models, load_balancer_id, None, None)
        if current is None:
            raise _LoadBalancerGone("load balancer %s is gone" % load_balancer_id)
    return wait_until_gone(
        module,
        poll,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def _desired_state(params):
    desired = {
        "LoadBalancerName": params["name"],
        "LoadBalancerType": params["load_balancer_type"],
        "VpcId": params["vpc_id"],
        "SubnetId": params["subnet_id"],
        "InternetChargeType": params["internet_charge_type"],
        "InternetMaxBandwidthOut": params["internet_max_bandwidth_out"],
        "Tags": params["tags"],
    }
    return {key: value for key, value in desired.items() if value is not None}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "load_balancer_id": {"type": "str"},
            "name": {"type": "str"},
            "load_balancer_type": {"type": "str", "choices": ["OPEN", "INTERNAL"]},
            "vpc_id": {"type": "str"},
            "subnet_id": {"type": "str"},
            "project_id": {"type": "int", "default": 0},
            "internet_charge_type": {
                "type": "str",
                "choices": [
                    "BANDWIDTH_PREPAID",
                    "TRAFFIC_POSTPAID_BY_HOUR",
                    "BANDWIDTH_POSTPAID_BY_HOUR",
                    "BANDWIDTH_PACKAGE",
                ],
            },
            "internet_max_bandwidth_out": {"type": "int"},
            "client_token": {"type": "str", "no_log": False},
            "tags": {"type": "dict", "default": {}},
        },
        required_if=[("state", "present", ["name"])],
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    load_balancer_id = module.params["load_balancer_id"]
    name = module.params["name"]
    tags = module.params["tags"]

    if state == "absent" and not name and not load_balancer_id:
        module.fail_json(msg="name or load_balancer_id is required when state=absent")

    models, clb_client = _load_clb()
    client = module.create_client(clb_client.ClbClient, "clb.tencentcloudapi.com")

    try:
        current = find_load_balancer(
            module, client, models, load_balancer_id, name, module.params["vpc_id"])

        if state == "absent":
            if current is None:
                module.exit_json(changed=False, msg="Load balancer already absent")
            target_id = current["LoadBalancerId"]
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would delete load balancer")
            try:
                _delete(module, client, models, target_id)
                _wait_gone(module, client, models, target_id)
            except Exception as exc:
                if is_idempotent_success(exc):
                    module.exit_json(changed=True, **(diff or {}), msg="Load balancer deleted")
                raise
            module.exit_json(changed=True, **(diff or {}), load_balancer=None, msg="Load balancer deleted")

        # state == present
        desired = _desired_state(module.params)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would create load balancer")
            new_id = _create(module, client, models, module.params)
            _wait_running(module, client, models, new_id)
            created = find_load_balancer(module, client, models, new_id, None, None)
            module.exit_json(changed=True, **(diff or {}), load_balancer=created, msg="Load balancer created")

        target_id = current["LoadBalancerId"]
        drifted = immutable_drift(
            current,
            load_balancer_type=module.params["load_balancer_type"],
            vpc_id=module.params["vpc_id"],
            subnet_id=module.params["subnet_id"],
        )
        if drifted:
            module.fail_json(
                msg=(
                    "Fields %s cannot be changed on an existing load balancer; "
                    "recreate the instance to apply them" % ", ".join(drifted)
                ),
                load_balancer=current,
            )

        changes = []
        if name and current.get("LoadBalancerName") != name:
            changes.append("name")
        network = current.get("NetworkAttributes") or {}
        internet_charge_type = module.params["internet_charge_type"]
        internet_max_bandwidth_out = module.params["internet_max_bandwidth_out"]
        if (internet_charge_type is not None
                and network.get("InternetChargeType") != internet_charge_type):
            changes.append("internet_charge_type")
        if (internet_max_bandwidth_out is not None
                and network.get("InternetMaxBandwidthOut") != internet_max_bandwidth_out):
            changes.append("internet_max_bandwidth_out")
        tags_equal, to_add, to_remove = compare_tags(tags, _clb_tags_to_sdk_shape(current.get("Tags")))
        if not tags_equal:
            changes.append("tags")

        if not changes:
            module.exit_json(changed=False, load_balancer=current, msg="Load balancer is up to date")

        if module.check_mode:
            module.exit_json(changed=True, **(maybe_diff(module, current, desired) or {}), msg="Would update load balancer")

        if "name" in changes or "internet_charge_type" in changes or "internet_max_bandwidth_out" in changes:
            task_id = _update_attributes(
                module, client, models, target_id,
                name if "name" in changes else None,
                internet_charge_type if "internet_charge_type" in changes else None,
                internet_max_bandwidth_out if "internet_max_bandwidth_out" in changes else None,
            )
            if task_id:
                _wait_task(module, client, models, task_id)
        if not tags_equal:
            tag_models, tag_client = _load_tag()
            tag_client_instance = module.create_client(
                tag_client.TagClient, "tag.tencentcloudapi.com"
            )
            _apply_tags(module, tag_client_instance, tag_models, target_id, to_add, to_remove)

        updated = find_load_balancer(module, client, models, target_id, None, None)
        module.exit_json(
            changed=True,
            **(maybe_diff(module, current, desired) or {}),
            load_balancer=updated,
            msg="Load balancer updated",
        )
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
