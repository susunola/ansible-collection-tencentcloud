"""Governance tests over the module sources."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import re
from pathlib import Path

import yaml

# Resolved from the test file, not from the working directory: these tests
# used to glob a relative path, so running pytest from anywhere but the
# collection root found no modules and passed without checking anything.
MODULES_DIR = Path(__file__).resolve().parents[3] / "plugins" / "modules"


def _module_paths():
    paths = sorted(MODULES_DIR.glob("*.py"))
    assert paths, "no modules found under %s" % MODULES_DIR
    return paths


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


def _documentation_blocks(path):
    """Yield (block name, parsed YAML) for a module's documentation blocks.

    A block that does not parse is skipped: ``validate-modules`` owns that
    failure, and this test is about documentation that *does* parse into
    something other than what was written.
    """
    text = path.read_text(encoding="utf-8")
    for name in ("DOCUMENTATION", "RETURN"):
        match = re.search(r"%s = r?'''(.*?)'''" % name, text, re.S)
        if not match:
            continue
        try:
            parsed = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue
        yield name, parsed


def _walk(node, path=""):
    """Yield (key, value, full path) for every mapping entry, recursively.

    The path names the *value*, so a failure says which option and which
    field it came from rather than which mapping happened to contain them.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            here = "%s.%s" % (path, key) if path else str(key)
            yield key, value, here
            yield from _walk(value, here)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, "%s[%d]" % (path, index))


def description_offenders(parsed):
    """Return the paths where a description is not a string.

    A colon followed by a space inside an unquoted YAML sequence item --
    ``- Instance type: C(1)`` -- is not a string with a colon in it. YAML
    parses it as a mapping, so the sentence a reader sees on the docsite is
    not the sentence the module author wrote, and nothing fails. The check
    is therefore on the parsed value rather than on the source line: an
    option genuinely *named* ``description`` is a mapping with a ``type``,
    which is how it is told apart from a description that went wrong.

    Checking the parsed value also means the rule is about the defect and
    not about syntax. ``seealso`` is a list of mappings on purpose --
    ``- module: susunola.tencentcloud.alb_listener`` is what ansible-core
    documents -- and a source-line rule flags all 451 of them.
    """
    found = []
    for key, value, path in _walk(parsed):
        if key != "description" or (isinstance(value, dict) and "type" in value):
            continue
        for item in (value if isinstance(value, list) else [value]):
            if not isinstance(item, str):
                found.append("%s: %r" % (path, item))
    return found


def seealso_offenders(parsed):
    """Return the paths of ``seealso`` entries that cannot render.

    Every entry is a mapping naming either a ``module`` or a ``ref``, with a
    description string. An entry that names neither is a link to nowhere,
    and an entry whose description is a list renders as a Python
    representation on the docsite.
    """
    found = []
    for key, value, path in _walk(parsed):
        if key != "seealso":
            continue
        if not isinstance(value, list):
            found.append("%s: not a list" % path)
            continue
        for index, item in enumerate(value):
            where = "%s[%d]" % (path, index)
            if not isinstance(item, dict):
                found.append("%s: not a mapping" % where)
            elif "module" not in item and "ref" not in item:
                found.append("%s: names neither module nor ref" % where)
            elif not isinstance(item.get("description", ""), str):
                found.append("%s: description is not a string" % where)
    return found


def test_descriptions_are_strings():
    """A colon+space inside a documentation list item silently becomes a mapping.

    For example ``- Instance type: C(1)`` parses as ``{"Instance type":
    "C(1)"}``, so the docsite renders a key and a value where the author
    wrote a sentence. Reword to avoid the colon, or quote the item.
    """
    offenders = []
    for path in _module_paths():
        for name, parsed in _documentation_blocks(path):
            for detail in description_offenders(parsed):
                offenders.append("%s %s%s" % (path.name, name, detail))
    assert not offenders, "documentation list items parsed as mappings:\n%s" % "\n".join(offenders)


def test_seealso_entries_are_renderable():
    """Every cross-reference names a module or ref and describes it in prose."""
    offenders = []
    for path in _module_paths():
        for name, parsed in _documentation_blocks(path):
            for detail in seealso_offenders(parsed):
                offenders.append("%s %s%s" % (path.name, name, detail))
    assert not offenders, "unrenderable seealso entries:\n%s" % "\n".join(offenders)


# ``fail_sdk_error(exc[, message])`` - the trailing positional message is
# optional, so the fragment is matched without the closing parenthesis.
DIAGNOSTIC_HELPERS = (
    "sdk_error_payload(exc)",
    "fail_sdk_error(exc",
    "fail_from_sdk_error(",
)

INLINE_ENVELOPE_FRAGMENTS = (
    'error=str(exc)',
    'get_code", lambda: None',
    'get_request_id", lambda: None',
)


def has_diagnostic_error_envelope(text):
    """True when a module surfaces the SDK error code and request id on failure."""
    if any(helper in text for helper in DIAGNOSTIC_HELPERS):
        return True
    if all(fragment in text for fragment in INLINE_ENVELOPE_FRAGMENTS):
        return True
    return "fail_on_cos_error(module, exc" in text


def test_write_modules_use_diagnostic_error_envelopes():
    """Every write module must retain error code and request ID on failure."""
    offenders = []
    for path in _module_paths():
        if path.stem.endswith("_info"):
            continue
        if not has_diagnostic_error_envelope(path.read_text(encoding="utf-8")):
            offenders.append(path.name)
    assert not offenders, "write modules without diagnostic SDK errors: %s" % ", ".join(offenders)


def test_diagnostic_envelope_accepts_the_message_overload():
    """Regression: fail_sdk_error(exc, "msg") keeps the envelope.

    TencentCloudModule.fail_sdk_error() takes an optional trailing message and
    still emits error / error_code / request_id, so the detector must accept
    both call shapes - and must still reject a bare fail_json().
    """
    assert has_diagnostic_error_envelope('module.fail_sdk_error(exc, "Tencent Cloud CLS alarm notice request failed")')
    assert has_diagnostic_error_envelope("module.fail_sdk_error(exc)")
    assert has_diagnostic_error_envelope("module.fail_from_sdk_error(exc)")
    assert not has_diagnostic_error_envelope("module.fail_json(msg=str(exc))")


# The rule is on the parsed value, so these pin both directions: it must
# still catch a description that YAML turned into a mapping, and it must not
# start flagging the mappings that are supposed to be there.

def test_description_rule_catches_a_colon_that_became_a_mapping():
    parsed = yaml.safe_load(
        "options:\n"
        "  instance_type:\n"
        "    description:\n"
        "      - Instance type: C(1)\n"
        "    type: str\n")
    assert description_offenders(parsed) == [
        "options.instance_type.description: {'Instance type': 'C(1)'}"]


def test_description_rule_allows_an_option_named_description():
    """``options.description`` is a mapping with a type; it is not a sentence."""
    parsed = yaml.safe_load(
        "options:\n"
        "  description:\n"
        "    description: Human-readable description.\n"
        "    type: str\n")
    assert description_offenders(parsed) == []


def test_seealso_entries_are_not_description_offenders():
    """The cross-references added by scripts/add_module_seealso.py are
    mappings inside a list, which is the shape ansible-core documents, so the
    rule that catches a stray colon must not catch them."""
    parsed = yaml.safe_load(
        "seealso:\n"
        "  - module: susunola.tencentcloud.alb_listener\n"
        "    description: Manage Tencent Cloud ALB listeners.\n")
    assert description_offenders(parsed) == []
    assert seealso_offenders(parsed) == []


def test_seealso_entry_without_a_target_is_reported():
    parsed = yaml.safe_load(
        "seealso:\n"
        "  - description: Nowhere.\n")
    assert seealso_offenders(parsed) == ["seealso[0]: names neither module nor ref"]
