"""Tests for DCDB security configuration normalization."""
from ansible_collections.susunola.tencentcloud.plugins.modules.dcdb_security_config import desired


def test_desired_only_includes_explicit_controls():
    assert desired({"encryption_enabled": True, "ssl_enabled": None, "security_group_ids": None}) == {"encryption_enabled": True}


def test_desired_sorts_and_deduplicates_security_groups():
    value = desired({"encryption_enabled": None, "ssl_enabled": True, "security_group_ids": ["sg-b", "sg-a", "sg-a"]})
    assert value == {"ssl_enabled": True, "security_group_ids": ["sg-a", "sg-b"]}
