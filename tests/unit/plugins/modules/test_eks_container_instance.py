"""Unit tests for the eks_container_instance write module (helpers + run_module).

Covers the create / update-restart-policy / delete flows of
``plugins/modules/eks_container_instance.py`` with an in-memory fake TKE
client whose write operations mutate the EKS CI store, so ``find_eks_ci``
sees the effect of each write immediately. The module returns as soon as a
create/update/delete request is accepted (it never polls), so no waiter or
patched-clock logic is needed.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import eks_container_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

EKS_CI = {
    "EksCiId": "eksci-8b0a1c2d",
    "EksCiName": "ci-prod",
    "RestartPolicy": "Always",
    "Status": "Running",
}

WRITE_OPS = (
    "CreateEKSContainerInstances",
    "UpdateEKSContainerInstance",
    "DeleteEKSContainerInstances",
)


def _eks_ci(**overrides):
    """Return an EKS CI fixture isolated from the shared constant."""
    instance = copy.deepcopy(EKS_CI)
    instance.update(overrides)
    return instance


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base params included)."""
    params = {
        'auto_create_eip': False,
        'cam_role_name': None,
        'containers': [],
        'cpu': None,
        'cpu_type': None,
        'eks_ci_name': 'eks-ci-name-xxxx',
        'eks_ci_volume': None,
        'existed_eip_ids': [],
        'gpu_count': 0,
        'gpu_type': None,
        'image_registry_credentials': [],
        'init_containers': [],
        'memory': None,
        'release_auto_created_eip': True,
        'replicas': 0,
        'restart_policy': 'Always',
        'security_group_ids': [],
        'state': 'present',
        'subnet_id': None,
        'vpc_id': None,
        'retries': 5,
        'waiter_delay': 5,
        'waiter_timeout': 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeTkeClient(object):
    """In-memory TKE client that mutates a small EKS CI store.

    Store entries are SDK-serialized dicts (PascalCase keys). Write
    operations mutate the store; ``DescribeEKSContainerInstances`` pages it
    so ``find_eks_ci`` converges on the first attempt.
    """

    def __init__(self, items=None):
        self.items = [dict(item) for item in (items or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeEKSContainerInstances(self, request):
        self._record("DescribeEKSContainerInstances", request)
        offset = request.Offset or 0
        limit = request.Limit or len(self.items)
        page = self.items[offset:offset + limit]
        return SimpleNamespace(
            EksCis=[FakeResource(dict(item)) for item in page],
            TotalCount=len(self.items),
        )

    def CreateEKSContainerInstances(self, request):
        self._record("CreateEKSContainerInstances", request)
        eks_ci_id = "eksci-fake-001"
        self.items.append(
            {
                "EksCiId": eks_ci_id,
                "EksCiName": request.EksCiName,
                "RestartPolicy": request.RestartPolicy,
                "Status": "Pending",
            }
        )
        return SimpleNamespace(EksCiId=eks_ci_id, RequestId="req-fake")

    def UpdateEKSContainerInstance(self, request):
        self._record("UpdateEKSContainerInstance", request)
        for item in self.items:
            if item["EksCiId"] == request.EksCiId:
                item["RestartPolicy"] = request.RestartPolicy
        return SimpleNamespace(RequestId="req-fake")

    def DeleteEKSContainerInstances(self, request):
        self._record("DeleteEKSContainerInstances", request)
        ids = list(request.EksCiIds)
        self.items = [item for item in self.items if item["EksCiId"] not in ids]
        return SimpleNamespace(RequestId="req-fake")


@pytest.fixture
def client(monkeypatch):
    fake = FakeTkeClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        '_load_tke',
        lambda: (FakeModels(), SimpleNamespace(TkeClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_find_eks_ci_returns_matching_entry():
    module = FakeModule()
    client = FakeTkeClient(items=[_eks_ci(), _eks_ci(EksCiName="ci-other")])
    found = mod.find_eks_ci(module, client, FakeModels(), "ci-prod")
    assert found["EksCiId"] == "eksci-8b0a1c2d"
    assert found["RestartPolicy"] == "Always"
    assert found["Status"] == "Running"


def test_find_eks_ci_missing_returns_none():
    module = FakeModule()
    client = FakeTkeClient()
    assert mod.find_eks_ci(module, client, FakeModels(), "ci-prod") is None


def test_find_eks_ci_paginates_past_one_hundred():
    module = FakeModule()
    items = [_eks_ci(EksCiName="ci-%03d" % index) for index in range(101)]
    items.append(_eks_ci())
    client = FakeTkeClient(items=items)
    found = mod.find_eks_ci(module, client, FakeModels(), "ci-prod")
    assert found["EksCiId"] == "eksci-8b0a1c2d"
    # The module reuses one request object and mutates Offset in place, so
    # snapshot the offset at call time instead of reading the recorded object.
    offsets = []
    real_describe = client.DescribeEKSContainerInstances

    def describe(request):
        offsets.append(request.Offset)
        return real_describe(request)

    client.DescribeEKSContainerInstances = describe
    mod.find_eks_ci(module, client, FakeModels(), "ci-missing")
    assert offsets == [0, 100]


def test_build_containers_maps_scalar_and_nested_fields():
    containers = mod.build_containers(
        FakeModels(),
        [
            {
                "name": "app",
                "image": "nginx:latest",
                "args": ["-c", "serve"],
                "commands": ["/bin/sh"],
                "cpu": 1.0,
                "memory": 2.0,
                "gpu_limit": 1,
                "working_dir": "/app",
                "environment_vars": [{"name": "ENV", "value": "production"}],
                "volume_mounts": [{"name": "data", "mount_path": "/var/lib", "read_only": True}],
            }
        ],
    )
    assert len(containers) == 1
    container = containers[0]
    assert container.Name == "app"
    assert container.Image == "nginx:latest"
    assert container.Args == ["-c", "serve"]
    assert container.Commands == ["/bin/sh"]
    assert container.Cpu == 1.0
    assert container.Memory == 2.0
    assert container.GpuLimit == 1
    assert container.WorkingDir == "/app"
    assert container.EnvironmentVars[0].Name == "ENV"
    assert container.EnvironmentVars[0].Value == "production"
    assert container.VolumeMounts[0].Name == "data"
    assert container.VolumeMounts[0].MountPath == "/var/lib"
    assert container.VolumeMounts[0].ReadOnly is True


def test_build_containers_omits_unset_optional_fields():
    containers = mod.build_containers(FakeModels(), [{"name": "app", "image": "nginx:latest"}])
    assert len(containers) == 1
    container = containers[0]
    assert container.Name == "app"
    assert container.Image == "nginx:latest"
    assert not hasattr(container, "Args")
    assert not hasattr(container, "GpuLimit")
    assert not hasattr(container, "EnvironmentVars")
    assert not hasattr(container, "VolumeMounts")


def test_build_image_registry_credentials_maps_fields():
    credentials = mod.build_image_registry_credentials(
        FakeModels(),
        [{"server": "registry.example.com", "username": "robot", "password": "secret"}],
    )
    assert len(credentials) == 1
    assert credentials[0].Server == "registry.example.com"
    assert credentials[0].Username == "robot"
    assert credentials[0].Password == "secret"


def test_build_eks_ci_volume_maps_nfs_and_cbs():
    volume = mod.build_eks_ci_volume(
        FakeModels(),
        {
            "nfs_volumes": [
                {"name": "nfs-data", "server": "10.0.0.1", "path": "/exports", "read_only": True}
            ],
            "cbs_volumes": [{"name": "cbs-data", "cbs_disk_id": "disk-8b0a1c2d"}],
        },
    )
    assert volume.NfsVolumes[0].Name == "nfs-data"
    assert volume.NfsVolumes[0].Server == "10.0.0.1"
    assert volume.NfsVolumes[0].Path == "/exports"
    assert volume.NfsVolumes[0].ReadOnly is True
    assert volume.CbsVolumes[0].Name == "cbs-data"
    assert volume.CbsVolumes[0].CbsDiskId == "disk-8b0a1c2d"


def test_build_eks_ci_volume_skips_absent_sections():
    volume = mod.build_eks_ci_volume(FakeModels(), {"nfs_volumes": []})
    assert not hasattr(volume, "NfsVolumes")
    assert not hasattr(volume, "CbsVolumes")


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_arguments_enforced(client):
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]


def test_present_creates_instance(client):
    _run_args(
        eks_ci_name="ci-prod",
        vpc_id="vpc-8b0a1c2d",
        subnet_id="subnet-8b0a1c2d",
        cpu=2.0,
        memory=4.0,
        containers=[{"name": "app", "image": "nginx:latest", "cpu": 1.0, "memory": 2.0}],
        restart_policy="OnFailure",
        security_group_ids=["sg-8b0a1c2d"],
        replicas=1,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "creation submitted" in result["msg"]
    assert result["eks_ci_id"] == "eksci-fake-001"
    assert result["eks_ci_name"] == "ci-prod"
    assert len(client.items) == 1
    assert client.items[0]["EksCiName"] == "ci-prod"
    assert client.items[0]["RestartPolicy"] == "OnFailure"
    create_request = next(
        request for name, request in client.calls if name == "CreateEKSContainerInstances"
    )
    assert create_request.VpcId == "vpc-8b0a1c2d"
    assert create_request.SubnetId == "subnet-8b0a1c2d"
    assert create_request.Cpu == 2.0
    assert create_request.Memory == 4.0
    assert create_request.RestartPolicy == "OnFailure"
    assert create_request.SecurityGroupIds == ["sg-8b0a1c2d"]
    assert create_request.Replicas == 1
    assert create_request.Containers[0].Name == "app"


def test_present_creates_instance_with_every_optional_field(client):
    _run_args(
        eks_ci_name="ci-prod",
        vpc_id="vpc-8b0a1c2d",
        subnet_id="subnet-8b0a1c2d",
        cpu=2.0,
        memory=4.0,
        containers=[{"name": "app", "image": "nginx:latest"}],
        init_containers=[{"name": "init", "image": "busybox:latest"}],
        security_group_ids=["sg-8b0a1c2d"],
        replicas=2,
        restart_policy="Never",
        image_registry_credentials=[{"server": "registry.example.com", "username": "robot", "password": "secret"}],
        eks_ci_volume={
            "nfs_volumes": [{"name": "nfs-data", "server": "10.0.0.1", "path": "/exports"}],
            "cbs_volumes": [{"name": "cbs-data", "cbs_disk_id": "disk-8b0a1c2d"}],
        },
        auto_create_eip=True,
        existed_eip_ids=["eip-8b0a1c2d"],
        cpu_type="Intel",
        gpu_type="V100",
        gpu_count=1,
        cam_role_name="eks-role",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    create_request = next(
        request for name, request in client.calls if name == "CreateEKSContainerInstances"
    )
    assert create_request.InitContainers[0].Name == "init"
    assert create_request.SecurityGroupIds == ["sg-8b0a1c2d"]
    assert create_request.Replicas == 2
    assert create_request.RestartPolicy == "Never"
    assert create_request.ImageRegistryCredentials[0].Server == "registry.example.com"
    assert create_request.EksCiVolume.NfsVolumes[0].Name == "nfs-data"
    assert create_request.EksCiVolume.CbsVolumes[0].CbsDiskId == "disk-8b0a1c2d"
    assert create_request.AutoCreateEip is True
    assert create_request.ExistedEipIds == ["eip-8b0a1c2d"]
    assert create_request.CpuType == "Intel"
    assert create_request.GpuType == "V100"
    assert create_request.GpuCount == 1
    assert create_request.CamRoleName == "eks-role"


def test_present_create_missing_create_params_fails(client):
    # containers=None exercises the "is None" create-parameter gate; the
    # argument-spec default leaves the parameter None when the user omits it.
    _run_args(eks_ci_name="ci-prod", containers=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Parameters required to create" in payload["msg"]
    assert "vpc_id" in payload["msg"]
    assert "containers" in payload["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_existing_unchanged(client):
    client.items = [_eks_ci()]
    _run_args(eks_ci_name="ci-prod", vpc_id="vpc-8b0a1c2d", subnet_id="subnet-8b0a1c2d", cpu=2.0, memory=4.0)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "already present" in result["msg"]
    assert result["eks_ci_id"] == "eksci-8b0a1c2d"
    assert result["status"] == "Running"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_updates_restart_policy(client):
    client.items = [_eks_ci(RestartPolicy="Never")]
    _run_args(eks_ci_name="ci-prod", restart_policy="Always")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Updated restart policy" in result["msg"]
    assert any(name == "UpdateEKSContainerInstance" for name, request in client.calls)
    assert client.items[0]["RestartPolicy"] == "Always"
    update_request = next(
        request for name, request in client.calls if name == "UpdateEKSContainerInstance"
    )
    assert update_request.EksCiId == "eksci-8b0a1c2d"
    assert update_request.RestartPolicy == "Always"


def test_absent_missing_instance_is_unchanged(client):
    _run_args(eks_ci_name="ci-prod", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "not present" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_absent_deletes_instance(client):
    client.items = [_eks_ci()]
    _run_args(eks_ci_name="ci-prod", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Deleted EKS container instance eksci-8b0a1c2d" in result["msg"]
    assert any(name == "DeleteEKSContainerInstances" for name, request in client.calls)
    assert client.items == []
    delete_request = next(
        request for name, request in client.calls if name == "DeleteEKSContainerInstances"
    )
    assert delete_request.EksCiIds == ["eksci-8b0a1c2d"]
    assert delete_request.ReleaseAutoCreatedEip is True


def test_check_mode_create_makes_no_writes(client):
    _run_args(
        eks_ci_name="ci-prod",
        vpc_id="vpc-8b0a1c2d",
        subnet_id="subnet-8b0a1c2d",
        cpu=2.0,
        memory=4.0,
        containers=[{"name": "app", "image": "nginx:latest"}],
        _ansible_check_mode=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would create EKS container instance ci-prod" in result["msg"]
    assert client.items == []
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_check_mode_update_makes_no_writes(client):
    client.items = [_eks_ci(RestartPolicy="Never")]
    _run_args(eks_ci_name="ci-prod", restart_policy="Always", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would update restart policy" in result["msg"]
    assert result["diff"]["before"]["RestartPolicy"] == "Never"
    assert result["diff"]["after"]["RestartPolicy"] == "Always"
    assert client.items[0]["RestartPolicy"] == "Never"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_check_mode_delete_makes_no_writes(client):
    client.items = [_eks_ci()]
    _run_args(eks_ci_name="ci-prod", state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would delete EKS container instance eksci-8b0a1c2d" in result["msg"]
    assert result["diff"]["before"]["EksCiId"] == "eksci-8b0a1c2d"
    assert len(client.items) == 1
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_sdk_error_on_describe_is_reported(client):
    def boom(request):
        raise RuntimeError("tke api exploded")

    client.DescribeEKSContainerInstances = boom
    _run_args(eks_ci_name="ci-prod")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "tke api exploded"
    assert payload["error_code"] is None
