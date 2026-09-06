import json

from ansible_collections.susunola.tencentcloud.plugins.modules.tse_config_file_release import delete_request, desired, publish_request, rollback_request


class Value(object):
    def from_json_string(self, raw):
        self.raw = raw


class Request(object):
    pass


class Models(object):
    ConfigFileRelease = Value
    ConfigFileReleaseDeletion = Value
    PublishConfigFilesRequest = Request
    RollbackConfigFileReleasesRequest = Request
    DeleteConfigFileReleasesRequest = Request


def test_config_release_requests_map_publish_rollback_and_delete():
    p = {
        "instance_id": "ins1",
        "namespace": "production",
        "group": "application",
        "name": "orders.yaml",
        "release_name": "stable",
        "strict_enable": True,
        "content": "port: 8080",
        "format": "YAML",
        "comment": None,
        "release_description": "deploy",
        "supported_client": None,
        "persistent": None,
        "beta_labels": None,
        "release_type": None,
        "rollback_version": "2",
    }
    target = desired(p)
    publish = publish_request(Models, p, target)
    assert publish.StrictEnable is True and json.loads(publish.ConfigFileReleases.raw)["Content"] == "port: 8080"
    current = dict(target, Id="release-1", Version="3")
    rollback = rollback_request(Models, p, current)
    assert json.loads(rollback.RollbackConfigFileReleases[0].raw)["Version"] == "2"
    delete = delete_request(Models, p, current)
    assert json.loads(delete.ConfigFileReleases[0].raw)["ReleaseVersion"] == "3"
