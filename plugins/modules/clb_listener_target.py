#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: clb_listener_target
short_description: Manage backend targets of Tencent Cloud CLB listeners
version_added: "0.10.0"
description:
  - Register and deregister backend targets (CVM instances or ENI private
    IPs) on a Tencent Cloud CLB listener through the C(clb.v20180317) API.
  - A target is identified by its backend (O(targets.instance_id) or
    O(targets.eni_ip)) plus its O(targets.port).
  - With C(state=present) the module reconciles the exact target set of the
    listener (or of the forwarding rule when O(location_id) is given).
    Missing targets are registered, targets whose weight differs are
    re-registered, and - when O(purge=true) - targets not listed in
    O(targets) are deregistered.
  - This module is idempotent. Running it twice leaves the target set
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) reconciles the target set through V(RegisterTargets) and
        V(DeregisterTargets).
      - C(absent) deregisters the targets listed in O(targets) when they are
        currently registered.
    type: str
    choices: [present, absent]
    default: present
  load_balancer_id:
    description: ID of the CLB instance, e.g. C(lb-xxxxxxxx).
    type: str
    required: true
  listener_id:
    description: ID of the listener whose targets are managed, e.g. C(lbl-xxxxxxxx).
    type: str
    required: true
  location_id:
    description:
      - ID of a layer-7 forwarding rule, e.g. C(loc-xxxxxxxx).
      - Only meaningful for HTTP and HTTPS listeners; when given, targets are
        bound to this rule instead of the listener itself.
    type: str
  targets:
    description:
      - Desired backend targets.
      - Exactly one of O(targets.instance_id) and O(targets.eni_ip) must be
        set per target; C(eni_ip) binds an ENI (or cross-region) IP instead of
        the primary IP of a CVM instance.
    type: list
    elements: dict
    default: []
    suboptions:
      instance_id:
        description: CVM instance ID, e.g. C(ins-xxxxxxxx). Mutually exclusive with O(targets.eni_ip).
        type: str
      eni_ip:
        description: ENI or other private IP to bind. Mutually exclusive with O(targets.instance_id).
        type: str
      port:
        description: Backend service port.
        type: int
        required: true
      weight:
        description: Forwarding weight, 0-100.
        type: int
        default: 10
  purge:
    description:
      - When C(true) and C(state=present), registered targets not listed in
        O(targets) are deregistered.
      - When C(false), targets from O(targets) are registered when missing,
        but no target is ever deregistered.
      - Purged ENI targets are deregistered by their first reported private
        IP, because V(DescribeTargets) reports the ENI ID rather than the IP
        the target was registered with.
    type: bool
    default: true
  retries:
    description:
      - Maximum number of retry attempts for throttled or transient API
        failures, using exponential backoff with jitter.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Maximum time in seconds to wait for an asynchronous register or
        deregister task to finish.
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
  - Uses the C(clb.tencentcloudapi.com) endpoint by default.
  - V(RegisterTargets) and V(DeregisterTargets) are asynchronous; the module
    polls V(DescribeTaskStatus) until each task succeeds.
  - V(RegisterTargets) also updates the weight of an already registered
    target, so weight drift is fixed by re-registering.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Set the exact backend targets of a TCP listener
  tencentcloud.cloud.clb_listener_target:
    region: ap-guangzhou
    load_balancer_id: lb-xxxxxxxx
    listener_id: lbl-xxxxxxxx
    targets:
      - instance_id: ins-aaaaaaaa
        port: 8080
        weight: 20
      - instance_id: ins-bbbbbbbb
        port: 8080
        weight: 10

- name: Add an ENI target without removing existing ones
  tencentcloud.cloud.clb_listener_target:
    region: ap-guangzhou
    load_balancer_id: lb-xxxxxxxx
    listener_id: lbl-xxxxxxxx
    purge: false
    targets:
      - eni_ip: 10.0.1.15
        port: 8080

- name: Bind targets to an HTTPS forwarding rule
  tencentcloud.cloud.clb_listener_target:
    region: ap-guangzhou
    load_balancer_id: lb-xxxxxxxx
    listener_id: lbl-xxxxxxxx
    location_id: loc-xxxxxxxx
    targets:
      - instance_id: ins-aaaaaaaa
        port: 443

- name: Deregister a backend target
  tencentcloud.cloud.clb_listener_target:
    region: ap-guangzhou
    state: absent
    load_balancer_id: lb-xxxxxxxx
    listener_id: lbl-xxxxxxxx
    targets:
      - instance_id: ins-aaaaaaaa
        port: 8080
'''

RETURN = r'''
targets:
  description:
    - Targets of the listener (or forwarding rule) as reported by
      V(DescribeTargets) after the operation, normalized to the module's
      target format.
  returned: success
  type: list
  elements: dict
  sample:
    - instance_id: ins-aaaaaaaa
      port: 8080
      weight: 20
'''

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.tencentcloud.cloud.plugins.module_utils.waiters import (
    wait_for_task,
)


def _load_clb():
    from tencentcloud.clb.v20180317 import models, clb_client
    return models, clb_client


def build_describe_request(models, load_balancer_id, listener_id):
    request = models.DescribeTargetsRequest()
    request.LoadBalancerId = load_balancer_id
    request.ListenerIds = [listener_id]
    return request


def normalize_current_target(backend):
    """Normalize a Backend dict from DescribeTargets for comparison."""
    return {
        "instance_id": backend.get("InstanceId"),
        "private_ips": backend.get("PrivateIpAddresses") or [],
        "port": backend.get("Port"),
        "weight": backend.get("Weight"),
    }


def find_targets(module, client, models, load_balancer_id, listener_id, location_id):
    """Return the current targets of the listener (or rule) as normalized dicts.

    Layer-4 listeners report their backends in ``ListenerBackend.Targets``;
    for HTTP/HTTPS listeners the backends live on the forwarding rules, so
    O(location_id) selects the rule whose targets are managed.
    """
    request = build_describe_request(models, load_balancer_id, listener_id)
    response = module.sdk_call(client.DescribeTargets, request)
    for backend_listener in response.Listeners or []:
        if backend_listener.ListenerId != listener_id:
            continue
        if location_id:
            for rule in backend_listener.Rules or []:
                if rule.LocationId == location_id:
                    return [normalize_current_target(t._serialize(allow_none=True)) for t in rule.Targets or []]
            return []
        return [normalize_current_target(t._serialize(allow_none=True)) for t in backend_listener.Targets or []]
    return []


def normalize_desired_target(target):
    """Normalize and validate a user-supplied target dict."""
    instance_id = target.get("instance_id")
    eni_ip = target.get("eni_ip")
    if bool(instance_id) == bool(eni_ip):
        raise ValueError("exactly one of instance_id and eni_ip must be set per target")
    return {
        "instance_id": instance_id,
        "eni_ip": eni_ip,
        "port": target.get("port"),
        "weight": target.get("weight") if target.get("weight") is not None else 10,
    }


def _matches(desired, current):
    """True when the current backend is the desired target."""
    if desired["port"] != current["port"]:
        return False
    if desired["instance_id"]:
        return desired["instance_id"] == current["instance_id"]
    return desired["eni_ip"] in current["private_ips"]


def reconcile_targets(desired, current, purge):
    """Compute the register/deregister delta between desired and current targets.

    Returns (to_register, to_deregister); a desired target whose weight
    differs from the registered one is re-registered (RegisterTargets updates
    the weight in place). When purge is false the deregister list is empty.
    """
    to_register = []
    matched = set()
    for target in desired:
        match = None
        for index, backend in enumerate(current):
            if index in matched or not _matches(target, backend):
                continue
            match = backend
            matched.add(index)
            break
        if match is None or match["weight"] != target["weight"]:
            to_register.append(target)
    to_deregister = []
    if purge:
        for index, backend in enumerate(current):
            if index not in matched:
                to_deregister.append(backend)
    return to_register, to_deregister


def build_targets(models, targets):
    """Build SDK Target objects from normalized target dicts.

    ``Target`` addresses a backend either by ``InstanceId`` (CVM primary IP)
    or by ``EniIp``; the API rejects requests that carry both.
    """
    sdk_targets = []
    for target in targets:
        sdk_target = models.Target()
        if target.get("instance_id"):
            sdk_target.InstanceId = target["instance_id"]
        else:
            eni_ip = target.get("eni_ip")
            if not eni_ip:
                private_ips = target.get("private_ips") or []
                eni_ip = private_ips[0] if private_ips else None
            if eni_ip:
                sdk_target.EniIp = eni_ip
        sdk_target.Port = target["port"]
        if target.get("weight") is not None:
            sdk_target.Weight = target["weight"]
        sdk_targets.append(sdk_target)
    return sdk_targets


def _register(module, client, models, load_balancer_id, listener_id, location_id, targets):
    """Register targets; returns the async task request ID."""
    request = models.RegisterTargetsRequest()
    request.LoadBalancerId = load_balancer_id
    request.ListenerId = listener_id
    if location_id:
        request.LocationId = location_id
    request.Targets = build_targets(models, targets)
    response = module.sdk_call(client.RegisterTargets, request)
    return response.RequestId


def _deregister(module, client, models, load_balancer_id, listener_id, location_id, targets):
    """Deregister targets; returns the async task request ID."""
    request = models.DeregisterTargetsRequest()
    request.LoadBalancerId = load_balancer_id
    request.ListenerId = listener_id
    if location_id:
        request.LocationId = location_id
    request.Targets = build_targets(models, targets)
    response = module.sdk_call(client.DeregisterTargets, request)
    return response.RequestId


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


def _report_target(target):
    """Reduce a normalized target to the fields returned to the user."""
    report = {"port": target["port"], "weight": target["weight"]}
    if target.get("instance_id"):
        report["instance_id"] = target["instance_id"]
    elif target.get("eni_ip"):
        report["eni_ip"] = target["eni_ip"]
    elif target.get("private_ips"):
        report["eni_ip"] = target["private_ips"][0]
    return report


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "load_balancer_id": {"type": "str", "required": True},
            "listener_id": {"type": "str", "required": True},
            "location_id": {"type": "str"},
            "targets": {
                "type": "list",
                "elements": "dict",
                "default": [],
                "options": {
                    "instance_id": {"type": "str"},
                    "eni_ip": {"type": "str"},
                    "port": {"type": "int", "required": True},
                    "weight": {"type": "int", "default": 10},
                },
                "mutually_exclusive": [("instance_id", "eni_ip")],
            },
            "purge": {"type": "bool", "default": True},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    load_balancer_id = module.params["load_balancer_id"]
    listener_id = module.params["listener_id"]
    location_id = module.params["location_id"]
    purge = module.params["purge"]

    try:
        desired = [normalize_desired_target(t) for t in module.params["targets"]]
    except ValueError as exc:
        module.fail_json(msg=str(exc))

    models, clb_client = _load_clb()
    client = module.create_client(clb_client.ClbClient, "clb.tencentcloudapi.com")

    try:
        current = find_targets(module, client, models, load_balancer_id, listener_id, location_id)

        if state == "absent":
            to_deregister = [t for t in desired if any(_matches(t, backend) for backend in current)]
            if not to_deregister:
                module.exit_json(
                    changed=False, targets=[_report_target(t) for t in current],
                    msg="Targets already absent",
                )
            after = [t for t in current if not any(_matches(d, t) for d in desired)]
            diff = maybe_diff(
                module,
                {"targets": [_report_target(t) for t in current]},
                {"targets": [_report_target(t) for t in after]},
            )
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would deregister targets")
            task_id = _deregister(
                module, client, models, load_balancer_id, listener_id, location_id, to_deregister)
            if task_id:
                _wait_task(module, client, models, task_id)
            updated = find_targets(module, client, models, load_balancer_id, listener_id, location_id)
            module.exit_json(
                changed=True, **(diff or {}),
                targets=[_report_target(t) for t in updated], msg="Targets deregistered",
            )

        # state == present
        to_register, to_deregister = reconcile_targets(desired, current, purge)

        if not to_register and not to_deregister:
            module.exit_json(
                changed=False,
                targets=[_report_target(t) for t in current],
                msg="Targets are up to date",
            )

        after = desired if purge else current + to_register
        diff = maybe_diff(
            module,
            {"targets": [_report_target(t) for t in current]},
            {"targets": [_report_target(t) for t in after]},
        )
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would reconcile targets")

        if to_register:
            task_id = _register(
                module, client, models, load_balancer_id, listener_id, location_id, to_register)
            if task_id:
                _wait_task(module, client, models, task_id)
        if to_deregister:
            task_id = _deregister(
                module, client, models, load_balancer_id, listener_id, location_id, to_deregister)
            if task_id:
                _wait_task(module, client, models, task_id)

        updated = find_targets(module, client, models, load_balancer_id, listener_id, location_id)
        module.exit_json(
            changed=True,
            **(diff or {}),
            targets=[_report_target(t) for t in updated],
            msg="Targets reconciled",
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
