from ansible_collections.susunola.tencentcloud.plugins.modules.ssm_ssh_key_pair_secret import comparable, create_request, request


class Value(object):
    pass


class Models(object):
    CreateSSHKeyPairSecretRequest = Value
    DescribeSecretRequest = Value
    Tag = Value


def test_create_request_maps_key_metadata_without_private_material():
    value = create_request(
        Models,
        {
            "secret_name": "bastion",
            "project_id": 0,
            "description": "key",
            "kms_key_id": None,
            "tags": {"env": "prod"},
            "ssh_key_name": "bastion_key",
            "kms_hsm_cluster_id": None,
            "encrypt_type": 0,
        },
    )
    assert value.SecretName == "bastion"
    assert value.SSHKeyName == "bastion_key"
    assert value.Tags[0].TagKey == "env"
    assert not hasattr(value, "PrivateKey")


def test_comparable_requires_ssh_secret_type_and_stable_identity():
    value = comparable({"SecretName": "bastion", "ResourceName": "bastion_key", "ProjectID": 3, "SecretType": 2, "Status": "Disabled"})
    assert value == {"SecretName": "bastion", "Description": "", "ResourceName": "bastion_key", "ProjectID": 3, "SecretType": 2, "Enabled": False}
    assert request(Models, "DescribeSecretRequest", SecretName="bastion").SecretName == "bastion"
