#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: eks_container_instance
short_description: Manage Tencent Cloud EKS container instances
version_added: "0.14.0"
description:
  - Create or remove an Elastic Kubernetes Service (EKS) container instance
    (EksCi) through the C(tke.v20180525) API C(CreateEKSContainerInstances),
    C(UpdateEKSContainerInstance), C(DeleteEKSContainerInstances) and
    C(DescribeEKSContainerInstances).
  - This module is idempotent. The instance is matched by its name
    (C(eks_ci_name)). When an instance with the same name already exists the
    module compares the restart policy and issues an update only when it
    differs; all other fields are create-only.
  - Supports check mode; no API write happens in check mode, only reads.
options:
  eks_ci_name:
    description: Name of the EKS container instance, e.g. C(ci-prod).
    type: str
    required: true
  state:
    description: Whether the container instance should exist.
    type: str
    choices: [present, absent]
    default: present
  vpc_id:
    description:
      - VPC the instance runs in, written to
        V(CreateEKSContainerInstancesRequest.VpcId). Required when the
        instance has to be created.
    type: str
  subnet_id:
    description:
      - Subnet the instance runs in, written to
        V(CreateEKSContainerInstancesRequest.SubnetId). Required when the
        instance has to be created.
    type: str
  cpu:
    description:
      - CPU size in cores, written to
        V(CreateEKSContainerInstancesRequest.Cpu). Required when the
        instance has to be created.
    type: float
  memory:
    description:
      - Memory size in GiB, written to
        V(CreateEKSContainerInstancesRequest.Memory). Required when the
        instance has to be created.
    type: float
  containers:
    description:
      - List of container specifications, written to
        V(CreateEKSContainerInstancesRequest.Containers). Each entry
        supports C(name), C(image), C(args), C(commands), C(cpu), C(memory),
        C(gpu_limit), C(working_dir), C(environment_vars) and
        C(volume_mounts). Required when the instance has to be created.
    type: list
    elements: dict
    suboptions:
      name:
        description: Container name.
        type: str
        required: true
      image:
        description: Container image.
        type: str
        required: true
      args:
        description: Container startup arguments.
        type: list
        elements: str
      commands:
        description: Container startup commands.
        type: list
        elements: str
      cpu:
        description: CPU limit for this container, in cores.
        type: float
      memory:
        description: Memory limit for this container, in GiB.
        type: float
      gpu_limit:
        description: GPU limit for this container.
        type: int
      working_dir:
        description: Container working directory.
        type: str
      environment_vars:
        description:
          - List of environment variables. Each entry has C(name) and
            C(value).
        type: list
        elements: dict
        suboptions:
          name:
            description: Environment variable name.
            type: str
            required: true
          value:
            description: Environment variable value.
            type: str
            required: true
      volume_mounts:
        description:
          - List of volume mounts. Each entry supports C(name),
            C(mount_path), C(read_only), C(mount_propagation) and C(sub_path).
        type: list
        elements: dict
        suboptions:
          name:
            description: Name of the volume to mount.
            type: str
            required: true
          mount_path:
            description: Mount path inside the container.
            type: str
            required: true
          read_only:
            description: Whether the mount is read-only.
            type: bool
          mount_propagation:
            description: Mount propagation mode.
            type: str
          sub_path:
            description: Sub path of the volume to mount.
            type: str
  init_containers:
    description:
      - List of init container specifications, written to
        V(CreateEKSContainerInstancesRequest.InitContainers). Uses the same
        schema as C(containers).
    type: list
    elements: dict
    suboptions:
      name:
        description: Init container name.
        type: str
        required: true
      image:
        description: Init container image.
        type: str
        required: true
  security_group_ids:
    description:
      - Security group IDs, written to
        V(CreateEKSContainerInstancesRequest.SecurityGroupIds).
    type: list
    elements: str
  replicas:
    description:
      - Number of replicas, written to
        V(CreateEKSContainerInstancesRequest.Replicas).
    type: int
  restart_policy:
    description:
      - Restart policy of the container group. Compared against the remote
        value and written through V(UpdateEKSContainerInstanceRequest.
        RestartPolicy) when it differs.
    type: str
    choices: [Always, Never, OnFailure]
    default: Always
  image_registry_credentials:
    description:
      - Image registry credentials, written to
        V(CreateEKSContainerInstancesRequest.ImageRegistryCredentials).
    type: list
    elements: dict
    suboptions:
      server:
        description: Registry server address.
        type: str
        required: true
      username:
        description: Registry user name.
        type: str
        required: true
      password:
        description: Registry password.
        type: str
        required: true
  eks_ci_volume:
    description:
      - Data volume configuration, written to
        V(CreateEKSContainerInstancesRequest.EksCiVolume). Supports
        C(nfs_volumes) and C(cbs_volumes).
    type: dict
    suboptions:
      nfs_volumes:
        description:
          - NFS volumes. Each entry has C(name), C(server), C(path) and
            optionally C(read_only).
        type: list
        elements: dict
      cbs_volumes:
        description:
          - CBS volumes. Each entry has C(name) and C(cbs_disk_id).
        type: list
        elements: dict
  auto_create_eip:
    description:
      - Whether to auto-create an EIP for the instance, written to
        V(CreateEKSContainerInstancesRequest.AutoCreateEip). Mutually
        exclusive with C(existed_eip_ids).
    type: bool
  existed_eip_ids:
    description:
      - Existing EIP IDs to bind, written to
        V(CreateEKSContainerInstancesRequest.ExistedEipIds). Mutually
        exclusive with C(auto_create_eip).
    type: list
    elements: str
  cpu_type:
    description:
      - CPU model preference, written to
        V(CreateEKSContainerInstancesRequest.CpuType).
    type: str
  gpu_type:
    description:
      - GPU model, written to V(CreateEKSContainerInstancesRequest.GpuType).
    type: str
  gpu_count:
    description:
      - Number of GPUs, written to
        V(CreateEKSContainerInstancesRequest.GpuCount).
    type: int
  cam_role_name:
    description:
      - CAM role name to associate, written to
        V(CreateEKSContainerInstancesRequest.CamRoleName).
    type: str
  release_auto_created_eip:
    description:
      - Whether to release the auto-created EIP on removal, written to
        V(DeleteEKSContainerInstancesRequest.ReleaseAutoCreatedEip).
    type: bool
    default: true
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
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-tke) package on the controller.
  - Instance creation is asynchronous; this module returns as soon as the
    create/delete request is accepted and does not wait for the instance to
    reach a running state.
  - Changing the VPC, subnet, CPU, memory or container definitions of an
    existing instance is not supported by this module; remove the instance
    (state=absent) and re-run to rebuild it.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create an EKS container instance
  susunola.tencentcloud.eks_container_instance:
    region: ap-guangzhou
    eks_ci_name: ci-prod
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    cpu: 2
    memory: 4
    restart_policy: OnFailure
    containers:
      - name: app
        image: nginx:latest
        cpu: 1
        memory: 2
        environment_vars:
          - name: ENV
            value: production

- name: Remove an EKS container instance
  susunola.tencentcloud.eks_container_instance:
    region: ap-guangzhou
    eks_ci_name: ci-prod
    state: absent
'''

RETURN = r'''
eks_ci_id:
  description: ID of the matched or newly created container instance.
  returned: when known
  type: str
eks_ci_name:
  description: Name of the managed container instance.
  returned: always
  type: str
status:
  description: Status of the existing container instance.
  returned: when a matching instance exists
  type: str
changed:
  description: Whether an API write happened.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load_tke():
    from tencentcloud.tke.v20180525 import models, tke_client
    return models, tke_client


def find_eks_ci(module, client, models, eks_ci_name):
    """Return the serialized EKS container instance dict with the given name, or None."""
    request = models.DescribeEKSContainerInstancesRequest()
    offset = 0
    while True:
        request.Offset = offset
        request.Limit = 100
        response = module.sdk_call(client.DescribeEKSContainerInstances, request)
        items = response.EksCis or []
        for item in items:
            data = item._serialize(allow_none=True)
            if data.get("EksCiName") == eks_ci_name:
                return data
        if len(items) < 100:
            break
        offset += len(items)
    return None


def build_containers(models, specs):
    """Convert container dicts into SDK Container model objects."""
    containers = []
    for spec in specs:
        container = models.Container()
        container.Name = spec.get("name")
        container.Image = spec.get("image")
        if spec.get("args") is not None:
            container.Args = spec["args"]
        if spec.get("commands") is not None:
            container.Commands = spec["commands"]
        if spec.get("cpu") is not None:
            container.Cpu = spec["cpu"]
        if spec.get("memory") is not None:
            container.Memory = spec["memory"]
        if spec.get("gpu_limit") is not None:
            container.GpuLimit = spec["gpu_limit"]
        if spec.get("working_dir"):
            container.WorkingDir = spec["working_dir"]
        env_specs = spec.get("environment_vars")
        if env_specs:
            env_vars = []
            for env in env_specs:
                env_var = models.EnvironmentVariable()
                env_var.Name = env.get("name")
                env_var.Value = env.get("value")
                env_vars.append(env_var)
            container.EnvironmentVars = env_vars
        mount_specs = spec.get("volume_mounts")
        if mount_specs:
            mounts = []
            for mount in mount_specs:
                volume_mount = models.VolumeMount()
                volume_mount.Name = mount.get("name")
                volume_mount.MountPath = mount.get("mount_path")
                if mount.get("read_only") is not None:
                    volume_mount.ReadOnly = mount["read_only"]
                if mount.get("mount_propagation"):
                    volume_mount.MountPropagation = mount["mount_propagation"]
                if mount.get("sub_path"):
                    volume_mount.SubPath = mount["sub_path"]
                mounts.append(volume_mount)
            container.VolumeMounts = mounts
        containers.append(container)
    return containers


def build_image_registry_credentials(models, specs):
    """Convert credential dicts into SDK ImageRegistryCredential model objects."""
    credentials = []
    for spec in specs:
        credential = models.ImageRegistryCredential()
        credential.Server = spec.get("server")
        credential.Username = spec.get("username")
        credential.Password = spec.get("password")
        credentials.append(credential)
    return credentials


def build_eks_ci_volume(models, spec):
    """Convert a volume dict into an SDK EksCiVolume model object."""
    volume = models.EksCiVolume()
    nfs_specs = spec.get("nfs_volumes")
    if nfs_specs:
        nfs_volumes = []
        for nfs in nfs_specs:
            nfs_volume = models.NfsVolume()
            nfs_volume.Name = nfs.get("name")
            nfs_volume.Server = nfs.get("server")
            nfs_volume.Path = nfs.get("path")
            if nfs.get("read_only") is not None:
                nfs_volume.ReadOnly = nfs["read_only"]
            nfs_volumes.append(nfs_volume)
        volume.NfsVolumes = nfs_volumes
    cbs_specs = spec.get("cbs_volumes")
    if cbs_specs:
        cbs_volumes = []
        for cbs in cbs_specs:
            cbs_volume = models.CbsVolume()
            cbs_volume.Name = cbs.get("name")
            cbs_volume.CbsDiskId = cbs.get("cbs_disk_id")
            cbs_volumes.append(cbs_volume)
        volume.CbsVolumes = cbs_volumes
    return volume


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "eks_ci_name": {"type": "str", "required": True},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "vpc_id": {"type": "str"},
            "subnet_id": {"type": "str"},
            "cpu": {"type": "float"},
            "memory": {"type": "float"},
            "containers": {"type": "list", "elements": "dict"},
            "init_containers": {"type": "list", "elements": "dict"},
            "security_group_ids": {"type": "list", "elements": "str"},
            "replicas": {"type": "int"},
            "restart_policy": {"type": "str", "choices": ["Always", "Never", "OnFailure"], "default": "Always"},
            "image_registry_credentials": {"type": "list", "elements": "dict", "no_log": True},
            "eks_ci_volume": {"type": "dict"},
            "auto_create_eip": {"type": "bool"},
            "existed_eip_ids": {"type": "list", "elements": "str"},
            "cpu_type": {"type": "str"},
            "gpu_type": {"type": "str"},
            "gpu_count": {"type": "int"},
            "cam_role_name": {"type": "str"},
            "release_auto_created_eip": {"type": "bool", "default": True},
        },
        supports_check_mode=True,
    )
    module.require_sdk()
    p = module.params

    models, tke_client = _load_tke()
    client = module.create_client(tke_client.TkeClient, "tke.tencentcloudapi.com")
    try:
        instance = find_eks_ci(module, client, models, p["eks_ci_name"])

        if p["state"] == "absent":
            if instance is None:
                module.exit_json(changed=False, eks_ci_name=p["eks_ci_name"], msg="EKS container instance not present")
            diff = maybe_diff(module, instance, None)
            if module.check_mode:
                module.exit_json(
                    changed=True, **(diff or {}),
                    eks_ci_name=p["eks_ci_name"],
                    msg="Would delete EKS container instance {0}".format(instance.get("EksCiId")),
                )
            request = models.DeleteEKSContainerInstancesRequest()
            request.EksCiIds = [instance["EksCiId"]]
            request.ReleaseAutoCreatedEip = p["release_auto_created_eip"]
            module.sdk_call(client.DeleteEKSContainerInstances, request)
            module.exit_json(
                changed=True, **(diff or {}),
                eks_ci_name=p["eks_ci_name"],
                msg="Deleted EKS container instance {0}".format(instance.get("EksCiId")),
            )

        # state == present
        if instance is not None:
            current_policy = instance.get("RestartPolicy") or "Always"
            if current_policy == p["restart_policy"]:
                module.exit_json(
                    changed=False,
                    eks_ci_id=instance.get("EksCiId"),
                    eks_ci_name=p["eks_ci_name"],
                    status=instance.get("Status"),
                    msg="EKS container instance already present",
                )
            after = {"RestartPolicy": p["restart_policy"]}
            diff = maybe_diff(module, {"RestartPolicy": current_policy}, after)
            if module.check_mode:
                module.exit_json(
                    changed=True, **(diff or {}),
                    eks_ci_id=instance.get("EksCiId"),
                    eks_ci_name=p["eks_ci_name"],
                    msg="Would update restart policy of EKS container instance {0}".format(instance.get("EksCiId")),
                )
            request = models.UpdateEKSContainerInstanceRequest()
            request.EksCiId = instance["EksCiId"]
            request.RestartPolicy = p["restart_policy"]
            module.sdk_call(client.UpdateEKSContainerInstance, request)
            module.exit_json(
                changed=True, **(diff or {}),
                eks_ci_id=instance.get("EksCiId"),
                eks_ci_name=p["eks_ci_name"],
                msg="Updated restart policy of EKS container instance {0}".format(instance.get("EksCiId")),
            )

        missing = [k for k in ("vpc_id", "subnet_id", "cpu", "memory", "containers") if p[k] is None]
        if missing:
            module.fail_json(
                msg="Parameters required to create an EKS container instance are missing: {0}".format(", ".join(missing)),
            )
        after = {"EksCiName": p["eks_ci_name"]}
        diff = maybe_diff(module, None, after)
        if module.check_mode:
            module.exit_json(
                changed=True, **(diff or {}),
                eks_ci_name=p["eks_ci_name"],
                msg="Would create EKS container instance {0}".format(p["eks_ci_name"]),
            )

        request = models.CreateEKSContainerInstancesRequest()
        request.EksCiName = p["eks_ci_name"]
        request.VpcId = p["vpc_id"]
        request.SubnetId = p["subnet_id"]
        request.Cpu = p["cpu"]
        request.Memory = p["memory"]
        request.Containers = build_containers(models, p["containers"])
        if p["init_containers"]:
            request.InitContainers = build_containers(models, p["init_containers"])
        if p["security_group_ids"]:
            request.SecurityGroupIds = p["security_group_ids"]
        if p["replicas"] is not None:
            request.Replicas = p["replicas"]
        request.RestartPolicy = p["restart_policy"]
        if p["image_registry_credentials"]:
            request.ImageRegistryCredentials = build_image_registry_credentials(models, p["image_registry_credentials"])
        if p["eks_ci_volume"]:
            request.EksCiVolume = build_eks_ci_volume(models, p["eks_ci_volume"])
        if p["auto_create_eip"] is not None:
            request.AutoCreateEip = p["auto_create_eip"]
        if p["existed_eip_ids"]:
            request.ExistedEipIds = p["existed_eip_ids"]
        if p["cpu_type"]:
            request.CpuType = p["cpu_type"]
        if p["gpu_type"]:
            request.GpuType = p["gpu_type"]
        if p["gpu_count"] is not None:
            request.GpuCount = p["gpu_count"]
        if p["cam_role_name"]:
            request.CamRoleName = p["cam_role_name"]
        response = module.sdk_call(client.CreateEKSContainerInstances, request)
        eks_ci_id = getattr(response, "EksCiId", None)
        module.exit_json(
            changed=True, **(diff or {}),
            eks_ci_id=eks_ci_id,
            eks_ci_name=p["eks_ci_name"],
            msg="EKS container instance creation submitted",
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
