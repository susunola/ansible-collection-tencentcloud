"""Main-path unit tests for the eks_container_instance module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import eks_container_instance
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CI_NAME = "ci-prod"


class FakeSdkError(Exception):
    def __init__(self, code, request_id="req-fake"):
        super(FakeSdkError, self).__init__(code)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


class FakeTkeClient(object):
    """In-memory stand-in for the TkeClient EKS container instance operations."""

    def __init__(self, instances=None):
        self.instances = list(instances or [])
        self.describe_offsets = []
        self.DescribeEKSContainerInstances = MagicMock(side_effect=self._describe)
        self.CreateEKSContainerInstances = MagicMock(side_effect=self._create)
        self.UpdateEKSContainerInstance = MagicMock(side_effect=self._update)
        self.DeleteEKSContainerInstances = MagicMock(side_effect=self._delete)

    def _describe(self, request):
        self.describe_offsets.append(request.Offset)
        start = request.Offset or 0
        end = start + (request.Limit or 100)
        items = [FakeResource(c) for c in self.instances[start:end]]
        return SimpleNamespace(EksCis=items)

    def _create(self, request):
        self.instances.append({
            "EksCiId": "eksci-2222",
            "EksCiName": request.EksCiName,
            "Status": "Pending",
            "RestartPolicy": getattr(request, "RestartPolicy", "Always"),
        })
        return SimpleNamespace(EksCiId="eksci-2222")

    def _update(self, request):
        for instance in self.instances:
            if instance["EksCiId"] == request.EksCiId:
                instance["RestartPolicy"] = request.RestartPolicy
        return SimpleNamespace()

    def _delete(self, request):
        self.instances = [c for c in self.instances if c["EksCiId"] not in request.EksCiIds]
        return SimpleNamespace()


def make_ci(eks_ci_id="eksci-1111", name=CI_NAME, status="Running", policy="Always"):
    return {
        "EksCiId": eks_ci_id,
        "EksCiName": name,
        "Status": status,
        "RestartPolicy": policy,
    }


@pytest.fixture
def client(monkeypatch):
    fake = FakeTkeClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        eks_container_instance, "_load_tke",
        lambda: (FakeModels(), SimpleNamespace(TkeClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


CREATE_ARGS = dict(
    eks_ci_name=CI_NAME,
    vpc_id="vpc-abcdef",
    subnet_id="subnet-1111",
    cpu=2,
    memory=4,
    containers=[{"name": "app", "image": "nginx:latest"}],
)


def test_absent_noop_when_instance_missing(client):
    module_args(eks_ci_name=CI_NAME, state="absent")
    result = run(eks_container_instance.run_module)
    assert result["changed"] is False
    client.DeleteEKSContainerInstances.assert_not_called()


def test_absent_deletes_existing_instance(client):
    client.instances = [make_ci()]
    module_args(eks_ci_name=CI_NAME, state="absent")
    result = run(eks_container_instance.run_module)
    assert result["changed"] is True
    request = client.DeleteEKSContainerInstances.call_args[0][0]
    assert request.EksCiIds == ["eksci-1111"]
    assert request.ReleaseAutoCreatedEip is True


def test_absent_release_eip_flag_forwarded(client):
    client.instances = [make_ci()]
    module_args(eks_ci_name=CI_NAME, state="absent", release_auto_created_eip=False)
    run(eks_container_instance.run_module)
    request = client.DeleteEKSContainerInstances.call_args[0][0]
    assert request.ReleaseAutoCreatedEip is False


def test_absent_check_mode_does_not_delete(client):
    client.instances = [make_ci()]
    module_args(eks_ci_name=CI_NAME, state="absent", _ansible_check_mode=True)
    result = run(eks_container_instance.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.DeleteEKSContainerInstances.assert_not_called()


def test_present_noop_when_policy_matches(client):
    client.instances = [make_ci(policy="Always")]
    module_args(**dict(CREATE_ARGS, restart_policy="Always"))
    result = run(eks_container_instance.run_module)
    assert result["changed"] is False
    assert result["eks_ci_id"] == "eksci-1111"
    assert result["status"] == "Running"
    client.CreateEKSContainerInstances.assert_not_called()
    client.UpdateEKSContainerInstance.assert_not_called()


def test_present_updates_policy_when_changed(client):
    client.instances = [make_ci(policy="Always")]
    module_args(**dict(CREATE_ARGS, restart_policy="OnFailure"))
    result = run(eks_container_instance.run_module)
    assert result["changed"] is True
    request = client.UpdateEKSContainerInstance.call_args[0][0]
    assert request.EksCiId == "eksci-1111"
    assert request.RestartPolicy == "OnFailure"
    client.CreateEKSContainerInstances.assert_not_called()


def test_present_update_check_mode_no_write(client):
    client.instances = [make_ci(policy="Always")]
    module_args(**dict(CREATE_ARGS, restart_policy="Never", _ansible_check_mode=True))
    result = run(eks_container_instance.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.UpdateEKSContainerInstance.assert_not_called()


def test_present_creates_when_absent(client):
    module_args(**CREATE_ARGS)
    result = run(eks_container_instance.run_module)
    assert result["changed"] is True
    assert result["eks_ci_id"] == "eksci-2222"
    request = client.CreateEKSContainerInstances.call_args[0][0]
    assert request.EksCiName == CI_NAME
    assert request.VpcId == "vpc-abcdef"
    assert request.SubnetId == "subnet-1111"
    assert request.Cpu == 2
    assert request.Memory == 4
    assert request.RestartPolicy == "Always"
    assert len(request.Containers) == 1
    assert request.Containers[0].Name == "app"
    assert request.Containers[0].Image == "nginx:latest"


def test_present_containers_nested_fields_built(client):
    containers = [{
        "name": "app",
        "image": "nginx:latest",
        "args": ["-g", "daemon off;"],
        "commands": ["/bin/sh"],
        "cpu": 1,
        "memory": 2,
        "gpu_limit": 1,
        "working_dir": "/app",
        "environment_vars": [{"name": "ENV", "value": "production"}],
        "volume_mounts": [{"name": "data", "mount_path": "/data", "read_only": True}],
    }]
    args = dict(CREATE_ARGS)
    args["containers"] = containers
    module_args(**args)
    run(eks_container_instance.run_module)
    request = client.CreateEKSContainerInstances.call_args[0][0]
    container = request.Containers[0]
    assert container.Args == ["-g", "daemon off;"]
    assert container.Commands == ["/bin/sh"]
    assert container.Cpu == 1
    assert container.Memory == 2
    assert container.GpuLimit == 1
    assert container.WorkingDir == "/app"
    assert len(container.EnvironmentVars) == 1
    assert container.EnvironmentVars[0].Name == "ENV"
    assert container.EnvironmentVars[0].Value == "production"
    assert len(container.VolumeMounts) == 1
    assert container.VolumeMounts[0].Name == "data"
    assert container.VolumeMounts[0].MountPath == "/data"
    assert container.VolumeMounts[0].ReadOnly is True


def test_present_optional_fields_forwarded(client):
    module_args(**dict(
        CREATE_ARGS,
        restart_policy="OnFailure",
        init_containers=[{"name": "init", "image": "busybox:latest"}],
        security_group_ids=["sg-1111"],
        replicas=2,
        image_registry_credentials=[{"server": "hub.example.com", "username": "robot", "password": "secret"}],
        eks_ci_volume={"nfs_volumes": [{"name": "data", "server": "10.0.0.1", "path": "/export", "read_only": True}],
                       "cbs_volumes": [{"name": "disk", "cbs_disk_id": "disk-1111"}]},
        auto_create_eip=True,
        cpu_type="intel",
        gpu_type="T4",
        gpu_count=1,
        cam_role_name="eks-role",
    ))
    run(eks_container_instance.run_module)
    request = client.CreateEKSContainerInstances.call_args[0][0]
    assert request.RestartPolicy == "OnFailure"
    assert len(request.InitContainers) == 1
    assert request.InitContainers[0].Name == "init"
    assert request.SecurityGroupIds == ["sg-1111"]
    assert request.Replicas == 2
    assert len(request.ImageRegistryCredentials) == 1
    assert request.ImageRegistryCredentials[0].Server == "hub.example.com"
    assert request.ImageRegistryCredentials[0].Username == "robot"
    assert request.ImageRegistryCredentials[0].Password == "secret"
    assert len(request.EksCiVolume.NfsVolumes) == 1
    assert request.EksCiVolume.NfsVolumes[0].Name == "data"
    assert request.EksCiVolume.NfsVolumes[0].ReadOnly is True
    assert len(request.EksCiVolume.CbsVolumes) == 1
    assert request.EksCiVolume.CbsVolumes[0].CbsDiskId == "disk-1111"
    assert request.AutoCreateEip is True
    assert request.CpuType == "intel"
    assert request.GpuType == "T4"
    assert request.GpuCount == 1
    assert request.CamRoleName == "eks-role"


def test_present_check_mode_does_not_create(client):
    module_args(**CREATE_ARGS, _ansible_check_mode=True)
    result = run(eks_container_instance.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateEKSContainerInstances.assert_not_called()


def test_present_missing_create_params_fails(client):
    module_args(eks_ci_name=CI_NAME)
    with pytest.raises(AnsibleFailJson) as exc:
        run(eks_container_instance.run_module)
    msg = exc.value.args[0]["msg"]
    assert "vpc_id" in msg
    assert "subnet_id" in msg
    assert "cpu" in msg
    assert "memory" in msg
    assert "containers" in msg
    client.CreateEKSContainerInstances.assert_not_called()


def test_find_eks_ci_scans_beyond_first_page(client):
    first_page = [make_ci(eks_ci_id="eksci-{0}".format(i), name="other-{0}".format(i))
                  for i in range(100)]
    client.instances = first_page + [make_ci(eks_ci_id="eksci-9999", name=CI_NAME)]
    module_args(**CREATE_ARGS)
    result = run(eks_container_instance.run_module)
    assert result["changed"] is False
    assert result["eks_ci_id"] == "eksci-9999"
    # recorded inside the fake client because the module reuses one request
    assert client.describe_offsets == [0, 100]


def test_sdk_error_fails(client, monkeypatch):
    def boom(self, fn, request, **kwargs):
        raise FakeSdkError("InternalError")

    monkeypatch.setattr(TencentCloudModule, "sdk_call", boom)
    module_args(**CREATE_ARGS)
    with pytest.raises(AnsibleFailJson) as exc:
        run(eks_container_instance.run_module)
    assert exc.value.args[0]["failed"] is True
