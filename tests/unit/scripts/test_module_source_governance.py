"""Governance tests over the module sources."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import re

MODULES_DIR = "plugins/modules"


def _module_paths():
    from pathlib import Path

    return sorted(Path(MODULES_DIR).glob("*.py"))


def test_no_sdk_model_kwargs_instantiation():
    """SDK models do not accept keyword arguments in __init__.

    The Tencent SDK's AbstractModel subclasses build attributes from
    _deserialize, so `models.Tag(Key=...)` raises TypeError at runtime.
    Module code must construct models and assign attributes instead.
    """
    pattern = re.compile(r"models\.\w+\(\*\*\{")
    offenders = []
    for path in _module_paths():
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(path))
    assert not offenders, "SDK model kwargs instantiation found in: %s" % ", ".join(offenders)


def test_no_colon_space_in_yaml_list_items():
    """A colon followed by a space inside a DOCUMENTATION list item breaks
    YAML parsing (e.g. '- Instance type: C(1)'); reword to avoid ':'.
    """
    pattern = re.compile(r"^\s+- [^\n]*: [^\n]*$", re.M)
    offenders = []
    for path in _module_paths():
        text = path.read_text(encoding="utf-8")
        match = re.search(r"DOCUMENTATION = r'''(.*?)'''", text, re.S)
        if not match:
            continue
        for line in match.group(1).splitlines():
            if pattern.match(line):
                offenders.append("%s: %s" % (path.name, line.strip()))
    assert not offenders, "Colon+space in DOCUMENTATION list items:\n%s" % "\n".join(offenders)
