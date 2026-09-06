import pytest
from ansible_collections.susunola.tencentcloud.plugins.modules.tione_notebook import create_request, modify_request, drift, normalize, status, converge_stopped


class Object:
    def from_json_string(self, value):
        self.value = value


class Models:
    CreateNotebookRequest = ModifyNotebookRequest = ResourceConf = CFSConfig = GooseFS = LogConfig = Tag = DataConfig = ImageInfo = SSHConfig = Object


def params():
    return {
        "name": "nb",
        "charge_type": "POSTPAID_BY_HOUR",
        "resource_conf": {"Cpu": 4},
        "log_enable": True,
        "root_access": False,
        "auto_stopping": True,
        "direct_internet_access": False,
        "resource_group_id": None,
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
        "volume_source_type": "CLOUD_PREMIUM",
        "volume_size_gb": 100,
        "volume_source_cfs": None,
        "volume_source_goosefs": None,
        "log_config": None,
        "lifecycle_script_id": None,
        "default_code_repo_id": None,
        "additional_code_repo_ids": ["r2", "r1"],
        "automatic_stop_time": 4,
        "tags": [{"TagKey": "b", "TagValue": "2"}],
        "data_configs": None,
        "image_info": {"ImageId": "img-1"},
        "image_type": "SYSTEM",
        "ssh_config": None,
        "description": "workbench",
    }


def test_create_maps_full_notebook_configuration():
    request = create_request(Models, params())
    assert request.Name == "nb" and request.ChargeType == "POSTPAID_BY_HOUR" and request.VolumeSizeInGB == 100
    assert request.ResourceConf is not None and request.ImageInfo is not None and len(request.Tags) == 1


def test_modify_excludes_unmodifiable_goosefs_but_maps_mutable_fields():
    p = params()
    p["volume_source_goosefs"] = {"Id": "g1"}
    request = modify_request(Models, "nb-1", p)
    assert request.Id == "nb-1" and request.Name == "nb" and request.AutoStopping is True
    assert not hasattr(request, "VolumeSourceGooseFS")


def test_drift_separates_mutable_and_immutable_fields_and_normalizes_tags():
    p = params()
    current = {key: value for key, value in normalize({"Name": "nb", "ChargeType": "PREPAID", "ResourceConf": {"Cpu": 2}, "Tags": p["tags"]}).items()}
    mutable, immutable = drift(p, current)
    assert "ResourceConf" in mutable and "ChargeType" in immutable and "Tags" not in mutable


def test_status_is_case_insensitive_and_null_safe():
    assert status({"Status": "Running"}) == "running" and status(None) == ""


class FailingModule:
    def fail_json(self, **kwargs):
        raise RuntimeError(kwargs["msg"])


def test_converge_rejects_unknown_operational_state():
    with pytest.raises(RuntimeError, match="unsupported operational state"):
        converge_stopped(FailingModule(), object(), object(), {"notebook_id": "nb-1", "project_id": None, "wait": True}, {"Status": "Unknown"})
