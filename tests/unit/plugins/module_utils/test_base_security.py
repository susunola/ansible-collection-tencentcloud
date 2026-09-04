from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import sanitize_error


def test_sanitize_error_redacts_common_credentials():
    text = sanitize_error("SecretId=abc SecretKey: xyz token=123 password=pw Authorization: Bearer")
    assert "abc" not in text
    assert "xyz" not in text
    assert "123" not in text
    assert "pw" not in text
    assert "Bearer" not in text
    assert text.count("<redacted>") == 5
