"""Re-export guard for the ``plugin_utils.profile`` shim.

The reader itself is implemented in ``plugins/module_utils/client.py`` and its
behaviour is covered by ``tests/unit/plugins/module_utils/test_profile.py``.
This file only guards the controller-side import path, because action, lookup,
inventory and connection plugins import ``plugin_utils.profile`` and the
re-export must not quietly turn into a second implementation.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils import client
from ansible_collections.susunola.tencentcloud.plugins.plugin_utils import profile


def test_load_profile_is_the_module_utils_function():
    """One function, two import paths: the shim must not define a second copy."""
    assert profile.load_profile is client.load_profile


def test_the_reader_global_stays_with_its_implementation():
    """The shim must not re-export ``PROFILE_FILE``.

    A re-exported constant is a separate binding: patching it through the shim
    would not affect ``load_profile``, which reads the global in the module
    where it is defined.
    """
    assert not hasattr(profile, "PROFILE_FILE")
    assert not hasattr(profile, "DEFAULT_PROFILE_NAME")
    assert profile.__all__ == ["load_profile"]
