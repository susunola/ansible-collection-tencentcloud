from __future__ import absolute_import, division, print_function

import sys
import types

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_encryption_info, cos_bucket_logging_info


def test_encryption_normalize_extracts_rules():
    value = {"ServerSideEncryptionConfiguration": {"Rule": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}}
    assert cos_bucket_encryption_info.normalize(value) == value["ServerSideEncryptionConfiguration"]


def test_logging_normalize_handles_disabled_and_defaults_prefix():
    assert cos_bucket_logging_info.normalize({"BucketLoggingStatus": {}}) is None
    value = {"BucketLoggingStatus": {"LoggingEnabled": {"TargetBucket": "logs-1250000000"}}}
    assert cos_bucket_logging_info.normalize(value) == {"LoggingEnabled": {"TargetBucket": "logs-1250000000", "TargetPrefix": ""}}
