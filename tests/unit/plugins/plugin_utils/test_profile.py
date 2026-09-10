"""Unit tests for the shared TCCLI credential-profile reader.

``load_profile`` lives in ``plugins/plugin_utils/profile.py`` because modules
and controller-side plugins (lookup, inventory, connection) resolve the
profile the same way. The tests patch ``profile.PROFILE_FILE`` — the module
global the function actually reads — so they fail loudly if the reader is ever
moved again.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.plugin_utils import profile


PROFILE_BODY = """\
[default]
secret_id = akid-default
secret_key = secret-default
region = ap-guangzhou

[prod]
secret_id = akid-prod
secret_key = secret-prod
region = ap-shanghai
"""


@pytest.fixture
def profile_path(tmp_path, monkeypatch):
    """Point the reader at a TCCLI configuration file in a temp directory."""
    path = tmp_path / "default.configure"
    path.write_text(PROFILE_BODY)
    monkeypatch.setattr(profile, "PROFILE_FILE", str(path))
    return str(path)


def test_default_profile_file_is_the_tccli_location():
    assert profile.DEFAULT_PROFILE_NAME == "default"
    assert profile.PROFILE_FILE.endswith(".tencentcloud/default.configure")


def test_load_profile_returns_section_keys(profile_path):
    settings = profile.load_profile()
    assert settings == {
        "secret_id": "akid-default",
        "secret_key": "secret-default",
        "region": "ap-guangzhou",
    }


def test_load_profile_named_section(profile_path):
    settings = profile.load_profile("prod")
    assert settings["secret_id"] == "akid-prod"
    assert settings["region"] == "ap-shanghai"


def test_load_profile_explicit_path_overrides_module_global(tmp_path, monkeypatch):
    path = tmp_path / "explicit.configure"
    path.write_text(PROFILE_BODY)
    monkeypatch.setattr(profile, "PROFILE_FILE", str(tmp_path / "never-read"))
    assert profile.load_profile("prod", path=str(path))["secret_id"] == "akid-prod"


def test_load_profile_missing_file_tolerated(tmp_path, monkeypatch):
    monkeypatch.setattr(profile, "PROFILE_FILE", str(tmp_path / "does-not-exist"))
    assert profile.load_profile() == {}
    assert profile.load_profile("prod") == {}


def test_load_profile_corrupt_file_tolerated(tmp_path, monkeypatch):
    path = tmp_path / "default.configure"
    path.write_text("this is [not = valid ini\n")
    monkeypatch.setattr(profile, "PROFILE_FILE", str(path))
    assert profile.load_profile() == {}


def test_load_profile_unknown_section(profile_path):
    assert profile.load_profile("no-such-profile") == {}


def test_load_profile_drops_empty_values(tmp_path, monkeypatch):
    path = tmp_path / "default.configure"
    path.write_text("[default]\nsecret_id =\nregion = ap-beijing\n")
    monkeypatch.setattr(profile, "PROFILE_FILE", str(path))
    assert profile.load_profile() == {"region": "ap-beijing"}
