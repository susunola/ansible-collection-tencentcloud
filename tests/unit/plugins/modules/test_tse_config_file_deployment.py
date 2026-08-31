from ansible_collections.susunola.tencentcloud.plugins.modules.tse_config_file_deployment import (
    delete_file_request, deploy_request, desired, expected, release_detail_request,
)


class Value(object):
    def from_json_string(self, value): self.json = value


class Models(object):
    DescribeConfigFileReleaseRequest = Value
    ConfigFilePublishInfo = Value
    CreateOrUpdateConfigFileAndReleaseRequest = Value
    DeleteConfigFilesRequest = Value


PARAMS = {"instance_id": "ins-1", "namespace": "prod", "group": "app", "name": "a.yaml",
          "release_name": "stable", "content": "x: 1", "format": "YAML", "comment": None,
          "create_by": None, "modify_by": None, "tags": None, "strict_enable": True}


def test_desired_and_atomic_request_mapping():
    target = desired(PARAMS)
    value = deploy_request(Models, PARAMS, target)
    assert target == {"ReleaseName": "stable", "Namespace": "prod", "Group": "app", "FileName": "a.yaml",
                      "Content": "x: 1", "Format": "YAML"}
    assert value.InstanceId == "ins-1" and value.StrictEnable is True
    release, config_file = expected(target)
    assert release["Name"] == "stable" and "ReleaseName" not in release
    assert config_file["Name"] == "a.yaml" and "FileName" not in config_file


def test_detail_and_delete_file_requests_map_identity():
    detail = release_detail_request(Models, PARAMS)
    deletion = delete_file_request(Models, PARAMS, {"Id": "file-1"})
    assert (detail.Name, detail.ReleaseName) == ("a.yaml", "stable")
    assert (deletion.Name, deletion.Id) == ("a.yaml", "file-1")
