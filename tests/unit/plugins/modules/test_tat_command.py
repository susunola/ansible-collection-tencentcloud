"""Tests for tat_command."""

from ansible_collections.susunola.tencentcloud.plugins.modules import tat_command
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


PARAMS = {"name": "hello", "content": "#!/bin/bash\necho {{word}}", "description": "hello", "command_type": "SHELL", "working_directory": "/root", "timeout": 60, "enable_parameters": True, "default_parameters": {"word": "hello"}, "username": "root", "output_cos_bucket_url": None, "output_cos_key_prefix": None, "tags": {"env": "prod"}}


def test_request_builders_encode_content_and_parameters():
    models = FakeModels()
    create = tat_command.build_create_request(models, PARAMS)
    assert create.Content == "IyEvYmluL2Jhc2gKZWNobyB7e3dvcmR9fQ=="
    assert create.DefaultParameters == '{"word":"hello"}'
    assert create.Tags[0].Key == "env"
    update = tat_command.build_update_request(models, "cmd-x", PARAMS)
    assert update.CommandId == "cmd-x"
    assert tat_command.build_delete_request(models, "cmd-x").CommandId == "cmd-x"


def test_exact_idempotency():
    desired = tat_command._desired(PARAMS)
    current = dict(desired)
    current["Tags"] = [{"Key": "env", "Value": "prod"}]
    assert tat_command._matches(current, desired)
    current["Timeout"] = 120
    assert not tat_command._matches(current, desired)
