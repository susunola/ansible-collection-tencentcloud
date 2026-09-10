# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""TCCLI credential-profile resolution, shared by every plugin type.

TCCLI stores its configuration as an INI file whose sections are profile names
(``[default]``, ``[prod]``, ...) holding ``secret_id``, ``secret_key`` and
``region`` keys. The profile is the lowest-precedence source in the
credential chain (explicit option > environment variable > profile), so every
plugin that can talk to the API needs to read it — modules, but also the
lookup, inventory and connection plugins that resolve credentials themselves
instead of going through :class:`~...module_utils.base.TencentCloudModule`.

That is why this file lives in ``plugin_utils`` rather than ``module_utils``:
it has no ``AnsibleModule`` dependency and is imported directly by controller
side plugins. See ``plugins/plugin_utils/README.md``.

Layering: this module imports nothing else from the collection.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import configparser
import os


DEFAULT_PROFILE_NAME = "default"
PROFILE_FILE = os.path.join(os.path.expanduser("~"), ".tencentcloud", "default.configure")


def load_profile(profile=None, path=None):
    """Return the settings stored in a TCCLI profile section.

    Reads ``~/.tencentcloud/default.configure`` (the TCCLI INI format) and
    returns the keys of the requested section, or of ``[default]`` when no
    profile name is given. A missing, unreadable or corrupt file — or a
    missing section — yields an empty dict: profile data is only ever a
    fallback and must never crash a plugin that does not rely on it.

    :param profile: section name; ``None`` selects ``[default]``.
    :param path: configuration file override, mainly for tests. When omitted
        the module-level ``PROFILE_FILE`` is read, so a caller that rebinds
        that name also redirects this function.
    """
    parser = configparser.ConfigParser()
    try:
        with open(path or PROFILE_FILE) as handle:
            parser.read_file(handle)
    except (OSError, configparser.Error):
        return {}
    section = profile or DEFAULT_PROFILE_NAME
    if not parser.has_section(section):
        return {}
    return {key: value for key, value in parser.items(section) if value}
