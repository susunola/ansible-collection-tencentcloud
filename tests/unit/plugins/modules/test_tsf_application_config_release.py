from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_application_config_release import desired


def test_application_config_release_maps_identity_and_description():
    assert desired({"config_id": "config-a", "group_id": "group-a", "release_description": "production"}) == {"ConfigId": "config-a", "GroupId": "group-a", "ReleaseDesc": "production"}
