"""Every plugin doc block must be valid YAML.

Ansible parses ``DOCUMENTATION`` (and validates ``EXAMPLES``/``RETURN``) when
it loads a plugin, so a syntax error there is not a documentation defect: it
makes the plugin **unloadable**. Ansible reports it as a generic

    Failed to parse inventory with 'auto' plugin: mapping values are not
    allowed in this context

which points at the inventory file, not at the plugin, so the failure is
almost impossible to attribute by reading the error alone.

The trap is easy to fall into because the blocks *look* like prose: a bullet
such as ``- Filters are per source: the namespace differs`` is a mapping to
YAML, and so is any plain scalar containing ``": "`` or ending in ``:``. Unit
tests do not catch it either, because they import the module rather than
letting Ansible load it.

This test is the cheap guard: parse every block with the same loader Ansible
uses, and fail with the file and block name.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGINS_DIR = REPO_ROOT / "plugins"

# ``DOCUMENTATION = r'''...'''`` / ``EXAMPLES = r'''...'''`` / RETURN likewise.
BLOCK_RE = re.compile(r"^(DOCUMENTATION|EXAMPLES|RETURN) = r?'''(.*?)'''", re.S | re.M)


def _plugin_files():
    if not PLUGINS_DIR.is_dir():
        raise AssertionError("plugins/ not found at {0}".format(PLUGINS_DIR))
    return sorted(PLUGINS_DIR.rglob("*.py"))


def _blocks():
    """Yield ``(relative path, block name, text)`` for every doc block."""
    for path in _plugin_files():
        source = path.read_text()
        for match in BLOCK_RE.finditer(source):
            yield path.relative_to(REPO_ROOT).as_posix(), match.group(1), match.group(2)


def test_the_repo_actually_has_doc_blocks():
    """Guard against the scan silently matching nothing."""
    count = sum(1 for _ in _blocks())
    assert count > 100, "only {0} doc blocks found; the scan is broken".format(count)


@pytest.mark.parametrize("relative,name,text", list(_blocks()))
def test_doc_block_is_valid_yaml(relative, name, text):
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise AssertionError(
            "{0}: {1} is not valid YAML, so ansible cannot load the plugin:\n{2}".format(
                relative, name, exc
            )
        )
    if name == "DOCUMENTATION":
        assert isinstance(parsed, dict), "{0}: DOCUMENTATION must be a mapping".format(relative)
        assert parsed.get("name") or parsed.get("module") or parsed.get("short_description"), (
            "{0}: DOCUMENTATION has neither name/module nor short_description".format(relative)
        )
