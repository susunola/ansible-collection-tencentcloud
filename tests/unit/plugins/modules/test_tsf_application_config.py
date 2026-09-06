from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_application_config import desired


def test_application_config_maps_exact_version_state():
    params = {"application_id": "app-a", "name": "settings", "version": "v1", "value": "feature: true", "version_description": "initial"}
    assert desired(params) == {"ApplicationId": "app-a", "ConfigName": "settings", "ConfigVersion": "v1", "ConfigValue": "feature: true", "ConfigVersionDesc": "initial", "ConfigType": "application"}
