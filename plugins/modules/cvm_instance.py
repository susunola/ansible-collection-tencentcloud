#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cvm_instance
short_description: Manage Tencent Cloud CVM instances
version_added: "0.4.0"
description:
  - Create, update, start, stop and terminate Tencent Cloud CVM instances
    through the C(cvm.v20170312) API.
  - This module is idempotent. Running it twice leaves the instance unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the instance with V(RunInstances) when it does not
        exist, and updates its name, security groups and tags when it does.
      - C(absent) terminates the instance with V(TerminateInstances) and waits
        until it is gone.
      - C(running) starts a stopped instance with V(StartInstances) and waits
        for the V(RUNNING) state. The instance must already exist.
      - C(stopped) stops a running instance with V(StopInstances) and waits
        for the V(STOPPED) state. The instance must already exist.
      - C(rebooted) reboots a running instance with V(RebootInstances) and
        waits for it to come back to the V(RUNNING) state. The instance must
        already exist and be running; rebooting a stopped instance fails.
        Reboot is a one-shot action - every run with C(state=rebooted) issues
        a reboot, so the module always reports C(changed=true).
    type: str
    choices: [present, absent, running, stopped, rebooted]
    default: present
  instance_id:
    description:
      - ID of an existing instance, e.g. C(ins-xxxxxxxx).
      - When given, the module operates on that instance; otherwise the
        instance is matched by O(instance_name) through the C(instance-name)
        filter and the first match is used.
    type: str
  instance_name:
    description:
      - Display name of the instance.
      - Used to look up the instance when O(instance_id) is not given, and as
        the desired name to enforce on an existing instance.
    type: str
  image_id:
    description:
      - Image ID (C(img-xxxxxxxx)) used to create the instance.
      - Required when the instance does not exist yet.
      - Only applied at creation; changing it on an existing instance fails
        with a message asking to recreate the instance.
    type: str
  instance_type:
    description:
      - Instance model, e.g. C(S5.MEDIUM2). See V(DescribeInstanceTypeConfigs)
        for the available values.
      - Required when the instance does not exist yet.
      - On an existing instance a different value is applied with
        V(ResetInstancesType) (instance resizing). The instance must be
        stopped first - change O(instance_type) together with C(state=stopped),
        or stop it beforehand, otherwise the module fails with guidance.
        Resizing keeps the instance stopped; start it afterwards with
        C(state=running).
    type: str
  vpc_id:
    description:
      - VPC ID (C(vpc-xxxxxxxx)) the instance belongs to.
      - Only applied at creation; changing it on an existing instance fails
        with a message asking to recreate the instance.
    type: str
  subnet_id:
    description:
      - Subnet ID (C(subnet-xxxxxxxx)) the instance belongs to.
      - Only applied at creation; changing it on an existing instance fails
        with a message asking to recreate the instance.
    type: str
  security_group_ids:
    description:
      - Security group IDs bound to the instance.
      - On an existing instance the bindings are reconciled through
        V(ModifyInstancesAttribute), replacing the current set.
    type: list
    elements: str
  hostname:
    description:
      - Instance host name. Only applied at creation.
    type: str
  password:
    description:
      - Login password set at creation through V(LoginSettings.Password).
      - Mutually exclusive with O(key_ids) on the API side; Windows instances
        do not support key pairs.
    type: str
  reset_password:
    description:
      - When C(true), resets the login password of an existing instance with
        V(ResetInstancesPassword) using the value of O(password).
      - Only applies with C(state=present); requires O(password). The module
        cannot read the current password, so every run with
        C(reset_password=true) resets it and reports C(changed=true). Use it
        as an explicit one-shot action, not as a reconciliation flag.
    type: bool
    default: false
  key_ids:
    description:
      - Key pair IDs associated with the instance at creation through
        V(LoginSettings.KeyIds).
    type: list
    elements: str
  internet_charge_type:
    description:
      - Network billing mode written to V(InternetAccessible.InternetChargeType).
    type: str
    choices: [BANDWIDTH_PREPAID, TRAFFIC_POSTPAID_BY_HOUR, BANDWIDTH_POSTPAID_BY_HOUR, BANDWIDTH_PACKAGE]
  internet_max_bandwidth_out:
    description:
      - Maximum outbound public bandwidth in Mbps, written to
        V(InternetAccessible.InternetMaxBandwidthOut).
    type: int
  public_ip_assigned:
    description:
      - Whether a public IP is assigned, written to
        V(InternetAccessible.PublicIpAssigned).
      - Only meaningful when O(internet_max_bandwidth_out) is greater than 0.
    type: bool
  instance_charge_type:
    description:
      - Instance billing mode written to V(RunInstancesRequest.InstanceChargeType).
    type: str
    choices: [PREPAID, POSTPAID_BY_HOUR]
    default: POSTPAID_BY_HOUR
  exact_count:
    description:
      - Desired number of instances in the pool matched by O(count_tag).
      - When O(state=present) and O(exact_count) are both given, the module
        counts the instances matching O(count_tag) and brings the pool to the
        requested size (fewer instances are created in one V(RunInstances)
        call, extra instances are terminated oldest first).
      - Mutually exclusive with O(instance_id); requires O(count_tag).
      - Instances that are already in the desired count are left untouched.
      - PREPAID instances are never terminated automatically; if a matched
        instance that would be removed is PREPAID the module fails instead.
    type: int
  count_tag:
    description:
      - Tag key/value pairs identifying the pool of instances managed through
        O(exact_count), for example I(role=web).
      - Matching uses one C(tag:key) instance filter per pair, combined with
        AND, so an instance must carry every pair to count towards the pool.
      - The tag must already be attached to the instances; tags passed in
        O(tags) are attached at creation and therefore match on subsequent
        runs.
    type: dict
  dry_run:
    description:
      - When C(true), creation calls V(RunInstances) with the API C(DryRun)
        flag so the request is validated without creating an instance.
      - Only applies to creation; it is ignored once the instance exists.
    type: bool
    default: false
  tags:
    description:
      - Tags to apply to the instance as a dict, for example I(env=prod).
      - At creation the tags are bound through V(TagSpecification); on an
        existing instance they are reconciled through the tag service
        (C(ServiceType=cvm), C(ResourcePrefix=instance)).
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
      - Maximum time in seconds to wait for the instance to reach the desired
        state (V(RUNNING) after create, start or update; V(STOPPED) after stop;
        gone after terminate).
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
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-cvm) package on the controller.
  - Tag reconciliation additionally requires C(tencentcloud-sdk-python-tag).
  - Uses the C(cvm.tencentcloudapi.com) endpoint by default.
  - After a create or a start the module waits for the instance to reach
    V(RUNNING) before returning; make sure the instance is able to run, a
    stopped instance would keep the waiter waiting until O(waiter_timeout).
    Updates on an existing instance never change the power state, so a
    stopped instance stays stopped and no wait is performed.
  - Image, VPC and subnet changes require recreating the
    instance; the module fails with a clear message when they drift on an
    existing instance instead of silently ignoring them.
  - Updates on an existing instance cover the name, security group bindings
    and tags via V(ModifyInstancesAttribute) and the tag service, the
    instance model via V(ResetInstancesType) (instance must be stopped) and
    the login password via V(ResetInstancesPassword) when O(reset_password)
    is set.
  - When O(exact_count) creates several instances at once the platform appends
    a numeric suffix to O(instance_name), so the created instances are named
    I(web-01), I(web-02) and so on.
  - O(exact_count) reads the pool through the C(tag:key) filter; tags attached
    after creation through the console or the tag service are matched the same
    way as tags set through O(tags).
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a CVM instance
  susunola.tencentcloud.cvm_instance:
    region: ap-guangzhou
    state: present
    instance_name: web-01
    image_id: img-xxxxxxxx
    instance_type: S5.MEDIUM2
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    security_group_ids:
      - sg-xxxxxxxx
    key_ids:
      - skey-xxxxxxxx
    internet_charge_type: TRAFFIC_POSTPAID_BY_HOUR
    internet_max_bandwidth_out: 10
    public_ip_assigned: true
    tags:
      env: prod
      tier: web

- name: Validate a creation request without creating (API dry run)
  susunola.tencentcloud.cvm_instance:
    region: ap-guangzhou
    state: present
    instance_name: web-01
    image_id: img-xxxxxxxx
    instance_type: S5.MEDIUM2
    dry_run: true

- name: Stop an instance
  susunola.tencentcloud.cvm_instance:
    region: ap-guangzhou
    state: stopped
    instance_name: web-01

- name: Start an instance
  susunola.tencentcloud.cvm_instance:
    region: ap-guangzhou
    state: running
    instance_name: web-01

- name: Reboot a running instance (one-shot action, always changed)
  susunola.tencentcloud.cvm_instance:
    region: ap-guangzhou
    state: rebooted
    instance_name: web-01

- name: Stop the instance before resizing it
  susunola.tencentcloud.cvm_instance:
    region: ap-guangzhou
    state: stopped
    instance_name: web-01

- name: Resize the stopped instance to a larger model
  susunola.tencentcloud.cvm_instance:
    region: ap-guangzhou
    state: present
    instance_name: web-01
    instance_type: S5.LARGE4

- name: Reset the login password of an existing instance
  susunola.tencentcloud.cvm_instance:
    region: ap-guangzhou
    state: present
    instance_name: web-01
    reset_password: true
    password: "N3w-Sup3r-Secret!"

- name: Terminate an instance
  susunola.tencentcloud.cvm_instance:
    region: ap-guangzhou
    state: absent
    instance_name: web-01

- name: Scale the web pool to exactly 3 instances
  susunola.tencentcloud.cvm_instance:
    region: ap-guangzhou
    state: present
    exact_count: 3
    count_tag:
      role: web
    instance_name: web
    image_id: img-xxxxxxxx
    instance_type: S5.MEDIUM2
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    tags:
      role: web

- name: Scale the web pool down to 1 (terminates the oldest extras)
  susunola.tencentcloud.cvm_instance:
    region: ap-guangzhou
    state: present
    exact_count: 1
    count_tag:
      role: web
'''

RETURN = r'''
instance:
  description: The instance as reported by V(DescribeInstances) after the operation.
  returned: success
  type: dict
  sample:
    InstanceId: ins-xxxxxxxx
    InstanceName: web-01
    InstanceState: RUNNING
    InstanceType: S5.MEDIUM2
    ImageId: img-xxxxxxxx
    SecurityGroupIds:
      - sg-xxxxxxxx
    Tags: []
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import (
    is_idempotent_success,
)
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tagging import (
    build_sdk_tags,
    compare_tags,
)
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import (
    wait_for_state,
    wait_until_gone,
)


def _load_cvm():
    from tencentcloud.cvm.v20170312 import models, cvm_client
    return models, cvm_client


def _load_tag():
    from tencentcloud.tag.v20180813 import models as tag_models, tag_client
    return tag_models, tag_client


class _InstanceGone(Exception):
    """Synthetic not-found error so wait_until_gone accepts an empty result."""

    def get_code(self):
        return "InvalidInstanceId.NotFound"


def build_describe_request(models, instance_id, instance_name, count_tag=None):
    request = models.DescribeInstancesRequest()
    request.Offset = 0
    request.Limit = 100
    if instance_id:
        request.InstanceIds = [instance_id]
    elif instance_name:
        name_filter = models.Filter()
        name_filter.Name = "instance-name"
        name_filter.Values = [instance_name]
        request.Filters = [name_filter]
    elif count_tag:
        # The tag:key filter matches instances that carry the exact tag
        # key/value pair, regardless of how the tag was attached.
        filters = []
        for key, value in sorted(count_tag.items()):
            tag_filter = models.Filter()
            tag_filter.Name = "tag:%s" % key
            tag_filter.Values = [value]
            filters.append(tag_filter)
        request.Filters = filters
    return request


def build_run_request(models, params):
    request = models.RunInstancesRequest()
    # Placement is required by RunInstances even when every field is left to
    # the platform default (random availability zone, default project).
    request.Placement = models.Placement()
    request.ImageId = params["image_id"]
    request.InstanceType = params["instance_type"]
    request.InstanceChargeType = params["instance_charge_type"]
    if params["instance_name"]:
        request.InstanceName = params["instance_name"]
    if params["hostname"]:
        request.HostName = params["hostname"]
    if params["security_group_ids"]:
        request.SecurityGroupIds = params["security_group_ids"]
    if params["vpc_id"] or params["subnet_id"]:
        request.VirtualPrivateCloud = models.VirtualPrivateCloud()
        if params["vpc_id"]:
            request.VirtualPrivateCloud.VpcId = params["vpc_id"]
        if params["subnet_id"]:
            request.VirtualPrivateCloud.SubnetId = params["subnet_id"]
    if (params["internet_charge_type"] is not None
            or params["internet_max_bandwidth_out"] is not None
            or params["public_ip_assigned"] is not None):
        request.InternetAccessible = models.InternetAccessible()
        if params["internet_charge_type"] is not None:
            request.InternetAccessible.InternetChargeType = params["internet_charge_type"]
        if params["internet_max_bandwidth_out"] is not None:
            request.InternetAccessible.InternetMaxBandwidthOut = params["internet_max_bandwidth_out"]
        if params["public_ip_assigned"] is not None:
            request.InternetAccessible.PublicIpAssigned = params["public_ip_assigned"]
    if params["password"] or params["key_ids"]:
        request.LoginSettings = models.LoginSettings()
        if params["password"]:
            request.LoginSettings.Password = params["password"]
        if params["key_ids"]:
            request.LoginSettings.KeyIds = params["key_ids"]
    if params["tags"]:
        tag_spec = models.TagSpecification()
        tag_spec.ResourceType = "instance"
        tag_spec.Tags = build_sdk_tags(models, params["tags"])
        request.TagSpecification = [tag_spec]
    if params.get("instance_count"):
        request.InstanceCount = params["instance_count"]
    if params["dry_run"]:
        request.DryRun = True
    return request


def _first(collection):
    return collection[0] if collection else None


def find_instance(module, client, models, instance_id, instance_name):
    """Return the matching instance dict or None."""
    request = build_describe_request(models, instance_id, instance_name)
    response = module.sdk_call(client.DescribeInstances, request)
    instance = _first(response.InstanceSet or [])
    if instance is None:
        return None
    return instance._serialize(allow_none=True)


def find_instances_by_tags(module, client, models, count_tag):
    """Return every non-terminated instance carrying the count_tag key/value.

    DescribeInstances caps the page at 100 results, so the page offset is
    advanced by the number of *scanned* instances on each page (not the
    number kept after filtering), which keeps the paging correct even when
    terminated instances are dropped from the result set. The loop stops
    once the offset has passed TotalCount, the collected matches reach
    TotalCount, or the API returns an empty page.
    """
    request = build_describe_request(models, None, None, count_tag)
    instances = []
    while True:
        response = module.sdk_call(client.DescribeInstances, request)
        page = response.InstanceSet or []
        for item in page:
            serialized = item._serialize(allow_none=True)
            if serialized.get("InstanceState") != "TERMINATED":
                instances.append(serialized)
        request.Offset += len(page)
        total = response.TotalCount or 0
        if not page or request.Offset >= total or len(instances) >= total:
            break
    return instances


def immutable_drift(current, image_id=None, vpc_id=None, subnet_id=None):
    """Return the creation-only fields that drifted on an existing instance.

    The instance model is deliberately not listed here: a different
    O(instance_type) on an existing (stopped) instance is applied with
    V(ResetInstancesType) instead of failing.
    """
    drifted = []
    if image_id and current.get("ImageId") != image_id:
        drifted.append("image_id")
    vpc = current.get("VirtualPrivateCloud") or {}
    if vpc_id and vpc.get("VpcId") != vpc_id:
        drifted.append("vpc_id")
    if subnet_id and vpc.get("SubnetId") != subnet_id:
        drifted.append("subnet_id")
    return drifted


def _create(module, client, models, params):
    request = build_run_request(models, params)
    response = module.sdk_call(client.RunInstances, request)
    return response.InstanceIdSet or []


def _delete(module, client, models, instance_id):
    request = models.TerminateInstancesRequest()
    request.InstanceIds = [instance_id]
    module.sdk_call(client.TerminateInstances, request)


def _start(module, client, models, instance_id):
    request = models.StartInstancesRequest()
    request.InstanceIds = [instance_id]
    module.sdk_call(client.StartInstances, request)


def _stop(module, client, models, instance_id):
    request = models.StopInstancesRequest()
    request.InstanceIds = [instance_id]
    module.sdk_call(client.StopInstances, request)


def _reboot(module, client, models, instance_id):
    request = models.RebootInstancesRequest()
    request.InstanceIds = [instance_id]
    module.sdk_call(client.RebootInstances, request)


def _reset_password(module, client, models, instance_id, password):
    request = models.ResetInstancesPasswordRequest()
    request.InstanceIds = [instance_id]
    request.Password = password
    module.sdk_call(client.ResetInstancesPassword, request)


def _reset_type(module, client, models, instance_id, instance_type):
    request = models.ResetInstancesTypeRequest()
    request.InstanceIds = [instance_id]
    request.InstanceType = instance_type
    module.sdk_call(client.ResetInstancesType, request)


def _update_attributes(module, client, models, instance_id, instance_name, security_group_ids):
    request = models.ModifyInstancesAttributeRequest()
    request.InstanceIds = [instance_id]
    if instance_name is not None:
        request.InstanceName = instance_name
    if security_group_ids is not None:
        request.SecurityGroups = security_group_ids
    module.sdk_call(client.ModifyInstancesAttribute, request)


def _apply_tags(module, client, tag_models, instance_id, to_add, to_remove):
    """Reconcile tags through the tag service.

    The tag service model differs from the CVM model: resources are addressed
    by a plural ``ResourceIds`` list and tags by ``TagKey``/``TagValue``.
    CVM instances use ``ServiceType=cvm`` and ``ResourcePrefix=instance``.
    Each tag key is processed independently.
    """
    for key, value in sorted(to_add.items()):
        request = tag_models.AttachResourcesTagRequest()
        request.ServiceType = "cvm"
        request.ResourceIds = [instance_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "instance"
        request.TagKey = key
        request.TagValue = value
        module.sdk_call(client.AttachResourcesTag, request)
    for key in to_remove:
        request = tag_models.DetachResourcesTagRequest()
        request.ServiceType = "cvm"
        request.ResourceIds = [instance_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "instance"
        request.TagKey = key
        module.sdk_call(client.DetachResourcesTag, request)


def _state_poll(module, client, models, instance_id):
    def poll():
        current = find_instance(module, client, models, instance_id, None)
        if current is None:
            raise _InstanceGone("instance %s is gone" % instance_id)
        return current.get("InstanceState")
    return poll


def _wait_state(module, client, models, instance_id, desired_states):
    return wait_for_state(
        module,
        _state_poll(module, client, models, instance_id),
        desired_states,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def _wait_gone(module, client, models, instance_id):
    def poll():
        current = find_instance(module, client, models, instance_id, None)
        if current is None:
            raise _InstanceGone("instance %s is gone" % instance_id)
    return wait_until_gone(
        module,
        poll,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def _desired_state(params):
    desired = {
        "InstanceName": params["instance_name"],
        "ImageId": params["image_id"],
        "InstanceType": params["instance_type"],
        "InstanceChargeType": params["instance_charge_type"],
        "SecurityGroupIds": params["security_group_ids"],
        "Tags": params["tags"],
    }
    return {key: value for key, value in desired.items() if value is not None}


def _manage_exact_count(module, client, models, params):
    """Bring the count_tag-matched pool to exactly ``exact_count`` instances.

    Fewer instances than the target are created in a single V(RunInstances)
    call with V(InstanceCount) set to the shortfall; more instances than the
    target are terminated oldest-first. PREPAID instances are never
    terminated automatically, the module fails instead so the operator can
    refund them manually.
    """
    exact_count = params["exact_count"]
    matches = find_instances_by_tags(module, client, models, params["count_tag"])
    current_count = len(matches)
    diff = maybe_diff(module, {"count": current_count}, {"count": exact_count})

    if current_count == exact_count:
        module.exit_json(
            changed=False, **(diff or {}), count=current_count, instances=matches,
            msg="Pool already at exact_count=%d" % exact_count,
        )

    if current_count < exact_count:
        to_create = exact_count - current_count
        if module.check_mode:
            module.exit_json(
                changed=True, **(diff or {}), count=current_count,
                msg="Would create %d instance(s) to reach exact_count=%d" % (
                    to_create, exact_count),
            )
        create_params = dict(params)
        create_params["instance_count"] = to_create
        new_ids = _create(module, client, models, create_params)
        for instance_id in new_ids:
            _wait_state(module, client, models, instance_id, ["RUNNING"])
        refreshed = find_instances_by_tags(module, client, models, params["count_tag"])
        module.exit_json(
            changed=True, **(diff or {}), count=len(refreshed), instances=refreshed,
            msg="Created %d instance(s); pool is now at exact_count=%d" % (
                to_create, exact_count),
        )

    # current_count > exact_count: terminate the oldest excess instances.
    to_terminate = current_count - exact_count
    ordered = sorted(
        matches,
        key=lambda item: (item.get("CreatedTime") is None, item.get("CreatedTime") or ""),
    )
    doomed = ordered[:to_terminate]
    prepaid = [i["InstanceId"] for i in doomed if i.get("InstanceChargeType") == "PREPAID"]
    if prepaid:
        module.fail_json(
            msg=(
                "Cannot scale down: PREPAID instance(s) %s would need to be "
                "terminated; refund prepaid instances manually first"
            ) % ", ".join(prepaid),
            count=current_count,
        )
    if module.check_mode:
        module.exit_json(
            changed=True, **(diff or {}), count=current_count,
            terminated=[i["InstanceId"] for i in doomed],
            msg="Would terminate %d instance(s) to reach exact_count=%d" % (
                to_terminate, exact_count),
        )
    for instance in doomed:
        _delete(module, client, models, instance["InstanceId"])
        _wait_gone(module, client, models, instance["InstanceId"])
    refreshed = find_instances_by_tags(module, client, models, params["count_tag"])
    module.exit_json(
        changed=True, **(diff or {}), count=len(refreshed), instances=refreshed,
        msg="Terminated %d instance(s); pool is now at exact_count=%d" % (
            to_terminate, exact_count),
    )


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent", "running", "stopped", "rebooted"], "default": "present"},
            "instance_id": {"type": "str"},
            "instance_name": {"type": "str"},
            "image_id": {"type": "str"},
            "instance_type": {"type": "str"},
            "vpc_id": {"type": "str"},
            "subnet_id": {"type": "str"},
            "security_group_ids": {"type": "list", "elements": "str"},
            "hostname": {"type": "str"},
            "password": {"type": "str", "no_log": True},
            "reset_password": {"type": "bool", "default": False},
            "key_ids": {"type": "list", "elements": "str", "no_log": False},
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
            "public_ip_assigned": {"type": "bool"},
            "instance_charge_type": {
                "type": "str",
                "choices": ["PREPAID", "POSTPAID_BY_HOUR"],
                "default": "POSTPAID_BY_HOUR",
            },
            "exact_count": {"type": "int"},
            "count_tag": {"type": "dict"},
            "dry_run": {"type": "bool", "default": False},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    instance_id = module.params["instance_id"]
    instance_name = module.params["instance_name"]
    security_group_ids = module.params["security_group_ids"]
    tags = module.params["tags"]
    exact_count = module.params["exact_count"]
    count_tag = module.params["count_tag"]
    reset_password = module.params["reset_password"]

    if exact_count is not None:
        if instance_id:
            module.fail_json(msg="exact_count is mutually exclusive with instance_id")
        if not count_tag:
            module.fail_json(msg="count_tag is required when exact_count is used")
        if state != "present":
            module.fail_json(msg="exact_count only applies to state=present")
        if exact_count < 0:
            module.fail_json(msg="exact_count must be greater than or equal to 0")
        if module.params["dry_run"]:
            module.fail_json(msg="dry_run cannot be combined with exact_count")
        if reset_password:
            module.fail_json(msg="reset_password cannot be combined with exact_count")
    if count_tag and exact_count is None:
        module.fail_json(msg="count_tag requires exact_count")

    if reset_password:
        if not module.params["password"]:
            module.fail_json(msg="password is required when reset_password=true")
        if state != "present":
            module.fail_json(msg="reset_password only applies to state=present")

    if state in ("absent", "running", "stopped", "rebooted") and not instance_id and not instance_name:
        module.fail_json(msg="instance_id or instance_name is required when state=%s" % state)

    models, cvm_client = _load_cvm()
    client = module.create_client(cvm_client.CvmClient, "cvm.tencentcloudapi.com")

    try:
        if exact_count is not None:
            return _manage_exact_count(module, client, models, module.params)
        current = find_instance(module, client, models, instance_id, instance_name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Instance already absent")
        target_id = current["InstanceId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would terminate instance")
        try:
            _delete(module, client, models, target_id)
            _wait_gone(module, client, models, target_id)
        except Exception as exc:
            if is_idempotent_success(exc):
                module.exit_json(changed=True, **(diff or {}), msg="Instance terminated")
            raise
        module.exit_json(changed=True, **(diff or {}), instance=None, msg="Instance terminated")

    if state in ("running", "stopped"):
        if current is None:
            module.fail_json(
                msg="Instance not found; use state=present to create it",
                instance_id=instance_id,
                instance_name=instance_name,
            )
        target_id = current["InstanceId"]
        current_state = current.get("InstanceState")
        if state == "running":
            if current_state == "RUNNING":
                module.exit_json(changed=False, instance=current, msg="Instance already running")
            if current_state != "STOPPED":
                module.fail_json(
                    msg="Instance is in transitional state %s; retry once it settles" % current_state,
                    instance=current,
                )
            diff = maybe_diff(module, {"InstanceState": "STOPPED"}, {"InstanceState": "RUNNING"})
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would start instance")
            _start(module, client, models, target_id)
            _wait_state(module, client, models, target_id, ["RUNNING"])
            updated = find_instance(module, client, models, target_id, None)
            module.exit_json(changed=True, **(diff or {}), instance=updated, msg="Instance started")
        # state == "stopped"
        if current_state == "STOPPED":
            module.exit_json(changed=False, instance=current, msg="Instance already stopped")
        if current_state != "RUNNING":
            module.fail_json(
                msg="Instance is in transitional state %s; retry once it settles" % current_state,
                instance=current,
            )
        diff = maybe_diff(module, {"InstanceState": "RUNNING"}, {"InstanceState": "STOPPED"})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would stop instance")
        _stop(module, client, models, target_id)
        _wait_state(module, client, models, target_id, ["STOPPED"])
        updated = find_instance(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=updated, msg="Instance stopped")

    if state == "rebooted":
        if current is None:
            module.fail_json(
                msg="Instance not found; use state=present to create it",
                instance_id=instance_id,
                instance_name=instance_name,
            )
        target_id = current["InstanceId"]
        current_state = current.get("InstanceState")
        if current_state == "STOPPED":
            module.fail_json(
                msg="Cannot reboot a stopped instance; start it first with state=running",
                instance=current,
            )
        if current_state != "RUNNING":
            module.fail_json(
                msg="Instance is in transitional state %s; retry once it settles" % current_state,
                instance=current,
            )
        diff = maybe_diff(module, {"InstanceState": "RUNNING"}, {"InstanceState": "RUNNING", "Rebooted": True})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would reboot instance")
        _reboot(module, client, models, target_id)
        _wait_state(module, client, models, target_id, ["RUNNING"])
        updated = find_instance(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=updated, msg="Instance rebooted")

    # state == present
    desired = _desired_state(module.params)
    if current is None:
        if not module.params["image_id"] or not module.params["instance_type"]:
            module.fail_json(
                msg="image_id and instance_type are required when creating an instance"
            )
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create instance")
        new_ids = _create(module, client, models, module.params)
        if module.params["dry_run"]:
            module.exit_json(
                changed=True, **(diff or {}), instance=None,
                msg="Dry run succeeded; no instance was created",
            )
        new_id = new_ids[0]
        _wait_state(module, client, models, new_id, ["RUNNING"])
        created = find_instance(module, client, models, new_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=created, msg="Instance created")

    target_id = current["InstanceId"]
    drifted = immutable_drift(
        current,
        image_id=module.params["image_id"],
        vpc_id=module.params["vpc_id"],
        subnet_id=module.params["subnet_id"],
    )
    if drifted:
        module.fail_json(
            msg=(
                "Fields %s cannot be changed on an existing instance; "
                "recreate the instance to apply them" % ", ".join(drifted)
            ),
            instance=current,
        )

    changes = []
    if instance_name and current.get("InstanceName") != instance_name:
        changes.append("instance_name")
    current_sg_ids = current.get("SecurityGroupIds") or []
    if security_group_ids is not None and sorted(security_group_ids) != sorted(current_sg_ids):
        changes.append("security_group_ids")
    tags_equal, to_add, to_remove = compare_tags(tags, current.get("Tags") or [])
    if not tags_equal:
        changes.append("tags")
    new_type = module.params["instance_type"]
    if new_type and current.get("InstanceType") != new_type:
        if current.get("InstanceState") != "STOPPED":
            module.fail_json(
                msg=(
                    "Resizing an instance requires it to be stopped; run with "
                    "state=stopped first (current state is %s)" % current.get("InstanceState")
                ),
                instance=current,
            )
        changes.append("instance_type")
    if reset_password:
        changes.append("reset_password")

    if not changes:
        module.exit_json(changed=False, instance=current, msg="Instance is up to date")

    diff = maybe_diff(module, current, desired)
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update instance")

    if "instance_name" in changes or "security_group_ids" in changes:
        _update_attributes(
            module, client, models, target_id,
            instance_name if "instance_name" in changes else None,
            security_group_ids if "security_group_ids" in changes else None,
        )
    if not tags_equal:
        tag_models, tag_client = _load_tag()
        tag_client_instance = module.create_client(
            tag_client.TagClient, "tag.tencentcloudapi.com"
        )
        _apply_tags(module, tag_client_instance, tag_models, target_id, to_add, to_remove)
    if "instance_type" in changes:
        _reset_type(module, client, models, target_id, new_type)
    if "reset_password" in changes:
        _reset_password(module, client, models, target_id, module.params["password"])

    # Updates do not change the power state: an instance that entered this
    # flow stopped stays stopped, and ResetInstancesType leaves the instance
    # stopped. Only wait for RUNNING when the instance was already running.
    if current.get("InstanceState") == "STOPPED":
        updated = find_instance(module, client, models, target_id, None)
        module.exit_json(
            changed=True,
            **(diff or {}),
            instance=updated,
            msg="Instance resized" if "instance_type" in changes else "Instance updated",
        )

    _wait_state(module, client, models, target_id, ["RUNNING"])
    updated = find_instance(module, client, models, target_id, None)
    module.exit_json(
        changed=True,
        **(diff or {}),
        instance=updated,
        msg="Instance updated",
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
