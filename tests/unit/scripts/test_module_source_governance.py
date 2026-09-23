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
