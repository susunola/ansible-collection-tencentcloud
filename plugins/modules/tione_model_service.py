#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tione_model_service
short_description: Manage Tencent Cloud TIONE online model service configuration
version_added: "0.14.0"
description:
  - Creates a service version and reconciles every configuration field reliably returned by C(DescribeModelService).
  - Existing resources require stable C(service_id). Create-only drift is rejected and must be deployed as a new version.
  - Use C(tione_model_service_state) for operational start and stop.
options:
  state:
    description:
      - Desired configuration presence.
    type: str
    choices: [present, absent]
    default: present
  service_id:
    description:
      - Stable service-version ID for update or deletion.
    type: str
  project_id:
    description:
      - Optional TI workspace ID.
    type: str
  service_group_id:
    description:
      - Existing group ID when creating a new version.
    type: str
  service_group_name:
    description:
      - New service-group name.
    type: str
  service_description:
    description:
      - Human-readable service description.
    type: str
  charge_type:
    description:
      - Create-only billing mode.
    type: str
    choices: [PREPAID, POSTPAID_BY_HOUR, HYBRID_PAID]
  resource_group_id:
    description:
      - Dedicated resource-group ID.
    type: str
  model_info:
    description:
      - ModelInfo-compatible model selection.
    type: dict
  image_info:
    description:
      - ImageInfo-compatible runtime image.
    type: dict
  env:
    description:
      - EnvVar-compatible environment variables.
    type: list
    elements: dict
  resources:
    description:
      - ResourceInfo-compatible prepaid resources.
    type: dict
  instance_type:
    description:
      - Postpaid billing specification.
    type: str
  scale_mode:
    description:
      - Replica scaling mode.
    type: str
    choices: [AUTO, MANUAL]
  replicas:
    description:
      - Desired replica count.
    type: int
  horizontal_pod_autoscaler:
    description:
      - HorizontalPodAutoscaler-compatible policy.
    type: dict
  log_enable:
    description:
      - Enable service log delivery.
    type: bool
  log_config:
    description:
      - LogConfig-compatible CLS destination.
    type: dict
  authorization_enable:
    description:
      - Create-only request authentication setting.
    type: bool
  tags:
    description:
      - Create-only Tag-compatible tags.
    type: list
    elements: dict
  scale_strategy:
    description:
      - Automatic scaling strategy such as HPA or CRON.
    type: str
  cron_scale_jobs:
    description:
      - CronScaleJob-compatible schedules.
    type: list
    elements: dict
  hybrid_billing_prepaid_replicas:
    description:
      - Prepaid replicas in hybrid billing mode.
    type: int
  create_source:
    description:
      - Create-only service source.
    type: str
  model_hot_update_enable:
    description:
      - Enable model hot update.
    type: bool
  scheduled_action:
    description:
      - ScheduledAction-compatible stop policy.
    type: dict
  volume_mount:
    description:
      - Legacy VolumeMount-compatible mount.
    type: dict
  service_limit:
    description:
      - ServiceLimit-compatible rate limits.
    type: dict
  model_turbo_enable:
    description:
      - Enable model acceleration.
    type: bool
  command:
    description:
      - Container start command.
    type: str
  service_eip:
    description:
      - ServiceEIP-compatible outbound access.
    type: dict
  service_port:
    description:
      - Custom inference service port.
    type: int
  deploy_type:
    description:
      - Create-only deployment topology.
    type: str
    choices: [STANDARD, DIST, ROLE_SET]
  instance_per_replicas:
    description:
      - Instances in each distributed replica.
    type: int
  termination_grace_period_seconds:
    description:
      - Graceful shutdown timeout.
    type: int
  pre_stop_command:
    description:
      - Commands run before instance termination.
    type: list
    elements: str
  grpc_enable:
    description:
      - Enable the gRPC port.
    type: bool
  health_probe:
    description:
      - HealthProbe-compatible health checks.
    type: dict
  rolling_update:
    description:
      - RollingUpdate-compatible deployment policy.
    type: dict
  volume_mounts:
    description:
      - VolumeMount-compatible data mounts.
    type: list
    elements: dict
  scheduling_strategy:
    description:
      - Workload scheduling strategy.
    type: str
    choices: [binpack, spread]
  resource_supply_attribute:
    description:
      - Create-only ResourceSupplyAttribute-compatible supply mode.
    type: dict
  infer_template_id:
    description:
      - Inference template ID.
    type: str
  allow_delete:
    description:
      - Explicit destructive-operation guard.
    type: bool
    default: false
  wait:
    description:
      - Wait for asynchronous convergence.
    type: bool
    default: true
  waiter_delay:
    description:
      - Seconds between state checks.
    type: int
    default: 10
  waiter_timeout:
    description:
      - Overall convergence timeout.
    type: int
    default: 1800

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  idempotency:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tione_model_service:
    service_group_name: fraud-detection
    charge_type: POSTPAID_BY_HOUR
    image_info: {ImageType: TCR, ImageUrl: ccr.ccs.tencentyun.com/ml/fraud:v3}
    instance_type: TI.S.LARGE.POST
    replicas: 2
- susunola.tencentcloud.tione_model_service:
    service_id: ms-xxxxxxxx
    replicas: 4
"""
RETURN = r"""
service: {description: Effective service detail., type: dict, returned: always}
service_id: {description: Stable service-version ID., type: str, returned: when available}
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

# option: (SDK property, SDK value class, mutable)
FIELDS = {
    "service_group_name": ("ServiceGroupName", None, False),
    "service_description": ("ServiceDescription", None, True),
    "charge_type": ("ChargeType", None, False),
    "resource_group_id": ("ResourceGroupId", None, True),
    "model_info": ("ModelInfo", "ModelInfo", True),
    "image_info": ("ImageInfo", "ImageInfo", True),
    "env": ("Env", "EnvVar", True),
    "resources": ("Resources", "ResourceInfo", True),
    "instance_type": ("InstanceType", None, True),
    "scale_mode": ("ScaleMode", None, True),
    "replicas": ("Replicas", None, True),
    "horizontal_pod_autoscaler": ("HorizontalPodAutoscaler", "HorizontalPodAutoscaler", True),
    "log_enable": ("LogEnable", None, True),
    "log_config": ("LogConfig", "LogConfig", True),
    "authorization_enable": ("AuthorizationEnable", None, False),
    "tags": ("Tags", "Tag", False),
    "scale_strategy": ("ScaleStrategy", None, True),
    "cron_scale_jobs": ("CronScaleJobs", "CronScaleJob", True),
    "hybrid_billing_prepaid_replicas": ("HybridBillingPrepaidReplicas", None, True),
    "create_source": ("CreateSource", None, False),
    "model_hot_update_enable": ("ModelHotUpdateEnable", None, True),
    "scheduled_action": ("ScheduledAction", "ScheduledAction", True),
    "volume_mount": ("VolumeMount", "VolumeMount", True),
    "service_limit": ("ServiceLimit", "ServiceLimit", True),
    "model_turbo_enable": ("ModelTurboEnable", None, True),
    "command": ("Command", None, True),
    "service_eip": ("ServiceEIP", "ServiceEIP", True),
    "service_port": ("ServicePort", None, True),
    "deploy_type": ("DeployType", None, False),
    "instance_per_replicas": ("InstancePerReplicas", None, True),
    "termination_grace_period_seconds": ("TerminationGracePeriodSeconds", None, True),
    "pre_stop_command": ("PreStopCommand", None, True),
    "grpc_enable": ("GrpcEnable", None, True),
    "health_probe": ("HealthProbe", "HealthProbe", True),
    "rolling_update": ("RollingUpdate", "RollingUpdate", True),
    "volume_mounts": ("VolumeMounts", "VolumeMount", True),
    "scheduling_strategy": ("SchedulingStrategy", None, True),
    "resource_supply_attribute": ("ResourceSupplyAttribute", "ResourceSupplyAttribute", False),
    "infer_template_id": ("InferTemplateId", None, True),
}
FAILED = {"create_failed", "timeout_exception", "abnormal"}


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client

    return models, tione_client


def _model(cls, value):
    item = cls()
    item.from_json_string(json.dumps(value))
    return item


def normalize(value):
    result = dict(value or {})
    result.update(result.pop("ServiceInfo", None) or {})
    for key in ("Tags", "Env", "CronScaleJobs", "VolumeMounts"):
        if result.get(key) is not None:
            result[key] = sorted(result[key], key=lambda x: json.dumps(x, sort_keys=True))
    return result


def detail_request(models, p):
    request = models.DescribeModelServiceRequest()
    request.ServiceId = p["service_id"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    return request


def get(module, client, models, p):
    try:
        response = module.sdk_call(client.DescribeModelService, detail_request(models, p))
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise
    return normalize(response.Service._serialize(allow_none=True)) if response.Service else None


def desired(p, current=None):
    result = dict(current or {})
    for source, (target, _, _) in FIELDS.items():
        if p.get(source) is not None:
            result[target] = p[source]
    return normalize(result)


def drift(p, current):
    target, mutable, immutable = desired(p, current), {}, {}
    for source, (key, _, can_modify) in FIELDS.items():
        if p.get(source) is not None and current.get(key) != target.get(key):
            (mutable if can_modify else immutable)[key] = (current.get(key), target.get(key))
    return mutable, immutable


def assign(models, request, key, cls_name, value):
    if cls_name and isinstance(value, list):
        value = [_model(getattr(models, cls_name), item) for item in value]
    elif cls_name:
        value = _model(getattr(models, cls_name), value)
    setattr(request, key, value)


def create_request(models, p):
    request = models.CreateModelServiceRequest()
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    if p.get("service_group_id") is not None:
        request.ServiceGroupId, request.NewVersion = p["service_group_id"], True
    for source, (key, cls_name, _) in FIELDS.items():
        if p.get(source) is not None:
            assign(models, request, key, cls_name, p[source])
    return request


def modify_request(models, p):
    request = models.ModifyModelServiceRequest()
    request.ServiceId = p["service_id"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    for source, (key, cls_name, mutable) in FIELDS.items():
        if mutable and p.get(source) is not None:
            assign(models, request, key, cls_name, p[source])
    return request


def delete_request(models, p):
    request = models.DeleteModelServiceRequest()
    request.ServiceId = p["service_id"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    return request


def wait_service(module, client, models, p, accepted):
    def poll():
        value = get(module, client, models, p)
        if value is None:
            return "absent"
        status = str(value.get("Status") or "").lower()
        if status in FAILED:
            module.fail_json(msg="TIONE model service entered a failed state", service=value)
        return status

    wait_for_state(module, poll, accepted, timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "service_id": {}, "project_id": {}, "service_group_id": {}}
    for source in FIELDS:
        spec[source] = {}
    spec.update(
        {
            "charge_type": {"choices": ["PREPAID", "POSTPAID_BY_HOUR", "HYBRID_PAID"]},
            "scale_mode": {"choices": ["AUTO", "MANUAL"]},
            "deploy_type": {"choices": ["STANDARD", "DIST", "ROLE_SET"]},
            "scheduling_strategy": {"choices": ["binpack", "spread"]},
            "model_info": {"type": "dict"},
            "image_info": {"type": "dict"},
            "env": {"type": "list", "elements": "dict"},
            "resources": {"type": "dict"},
            "replicas": {"type": "int"},
            "horizontal_pod_autoscaler": {"type": "dict"},
            "log_enable": {"type": "bool"},
            "log_config": {"type": "dict"},
            "authorization_enable": {"type": "bool"},
            "tags": {"type": "list", "elements": "dict"},
            "cron_scale_jobs": {"type": "list", "elements": "dict"},
            "hybrid_billing_prepaid_replicas": {"type": "int"},
            "model_hot_update_enable": {"type": "bool"},
            "scheduled_action": {"type": "dict"},
            "volume_mount": {"type": "dict"},
            "service_limit": {"type": "dict"},
            "model_turbo_enable": {"type": "bool"},
            "service_eip": {"type": "dict"},
            "service_port": {"type": "int"},
            "instance_per_replicas": {"type": "int"},
            "termination_grace_period_seconds": {"type": "int"},
            "pre_stop_command": {"type": "list", "elements": "str"},
            "grpc_enable": {"type": "bool"},
            "health_probe": {"type": "dict"},
            "rolling_update": {"type": "dict"},
            "volume_mounts": {"type": "list", "elements": "dict"},
            "resource_supply_attribute": {"type": "dict"},
            "allow_delete": {"type": "bool", "default": False},
            "wait": {"type": "bool", "default": True},
            "waiter_delay": {"type": "int", "default": 10},
            "waiter_timeout": {"type": "int", "default": 1800},
        }
    )
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p["state"] == "absent" and not p.get("service_id"):
        module.fail_json(msg="service_id is required for safe deletion")
    if p.get("service_group_id") and p.get("service_id"):
        module.fail_json(msg="service_group_id creates a new version and cannot be combined with service_id")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        current = get(module, client, models, p) if p.get("service_id") else None
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, service=None, service_id=p["service_id"])
            if not p["allow_delete"]:
                module.fail_json(msg="allow_delete=true is required to delete a TIONE model service", service=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteModelService, delete_request(models, p))
                if p["wait"]:
                    wait_service(module, client, models, p, ["absent"])
            module.exit_json(changed=True, **(diff_value or {}), service=None, service_id=p["service_id"])
        if current is None:
            if p.get("service_id"):
                module.fail_json(msg="requested service_id does not exist", service_id=p["service_id"])
            missing = [key for key in ("charge_type", "replicas") if p.get(key) is None]
            if p.get("image_info") is None and p.get("infer_template_id") is None:
                missing.append("image_info or infer_template_id")
            if not (p.get("service_group_id") or p.get("service_group_name")):
                missing.append("service_group_id or service_group_name")
            if missing:
                module.fail_json(msg="creation parameters are required for a TIONE model service", missing=missing)
            target = desired(p)
            diff_value = maybe_diff(module, None, target)
            service_id = None
            if not module.check_mode:
                response = module.sdk_call(client.CreateModelService, create_request(models, p))
                value = response.Service
                service_id = value.ServiceId if value else None
                if not service_id:
                    module.fail_json(msg="CreateModelService returned no service identity", request_id=response.RequestId)
                p = dict(p, service_id=service_id)
                if p["wait"]:
                    wait_service(module, client, models, p, ["normal", "stopped"])
                current = get(module, client, models, p)
            module.exit_json(changed=True, **(diff_value or {}), service=current if not module.check_mode else target, service_id=service_id)
        mutable, immutable = drift(p, current)
        if immutable:
            module.fail_json(
                msg="TIONE model service create-only configuration drift requires a new service version", service=current, immutable_drift=immutable
            )
        if not mutable:
            module.exit_json(changed=False, service=current, service_id=p["service_id"])
        target = desired(p, current)
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyModelService, modify_request(models, p))
            if p["wait"]:
                wait_service(module, client, models, p, ["normal", "stopped"])
            current = get(module, client, models, p)
        module.exit_json(changed=True, **(diff_value or {}), service=current if not module.check_mode else target, service_id=p["service_id"])
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
