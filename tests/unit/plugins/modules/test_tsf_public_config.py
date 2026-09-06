from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_public_config import desired


def test_public_config_maps_exact_version_state():
    params = {"name": "shared", "version": "v1", "value": "logging: INFO", "version_description": "initial"}
    assert desired(params) == {"ConfigName": "shared", "ConfigVersion": "v1", "ConfigValue": "logging: INFO", "ConfigVersionDesc": "initial", "ConfigType": "public"}
