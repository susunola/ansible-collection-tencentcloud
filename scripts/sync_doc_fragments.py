#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Migrate and enforce doc_fragment usage across plugins.

Background
----------
Common module options used to live in a single doc fragment
(plugins/doc_fragments/tencentcloud.py) while the runtime options
(``retries``, ``user_agent``, ``waiter_delay``, ``waiter_timeout``) were
copied inline into each module's DOCUMENTATION block.  Inline copies drift;
validate-modules then reports the drift as documentation errors.

This script splits the fragments (credentials/region/connection for the
base connection options; retry/user_agent/waiter for the runtime options)
and rewrites every carrier so that:

* the ``extends_documentation_fragment`` block references the exact set of
  fragments the module needs, and
* an inline option is kept only when its text is product-specific or its
  default deviates from the fragment default (a genuine per-module
  override, which Ansible merges module-first over the fragment).

Modules always carry the fragments.  Non-module plugins (e.g. the TAT
connection plugin) are rewritten only when they reference a collection
fragment, so plugins extending third-party fragments are left alone.

Usage
-----
    python scripts/sync_doc_fragments.py            # rewrite carrier files
    python scripts/sync_doc_fragments.py --check    # verify no drift (CI)

``--check`` invariants:

1. every carrier references ``credentials``, ``region`` and ``connection``
   and nothing from the legacy ``tencentcloud`` fragment;
2. no carrier documents an inline option whose text matches the generic
   families owned by retry/user_agent/waiter fragments (product-specific
   or custom-default overrides are allowed and are detected by not
   matching those families);
3. fragment references are unique and name fragments that exist;
4. a DOCUMENTATION ``options:`` block that would be a YAML null (a bare
   ``options:`` with nothing under it) is rejected; option-less carriers
   must write ``options: {}``.
"""

from __future__ import absolute_import, division, print_function

import argparse
import glob
import os
import re
import sys

__metaclass__ = type

FQCN_PREFIX = "susunola.tencentcloud."
BASE_FRAGMENTS = ("credentials", "region", "connection")
# Single-option fragments are referenced independently; the waiter fragment
# covers both waiter options and therefore needs both to be satisfied.
OPTION_FRAGMENTS = {
    "retries": "retry",
    "user_agent": "user_agent",
    "waiter_delay": "waiter",
    "waiter_timeout": "waiter",
}
KNOWN_FRAGMENTS = set(BASE_FRAGMENTS) | set(OPTION_FRAGMENTS.values())

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_GLOB = os.path.join(REPO_ROOT, "plugins", "modules", "*.py")
# The legacy single fragment was referenced by modules and by non-module
# plugins (e.g. the TAT connection plugin).  Scan every plugin directory
# so migration and --check cover the whole tree, not just modules.
PLUGIN_GLOBS = [
    os.path.join(REPO_ROOT, "plugins", directory, "*.py") for directory in ("modules", "connection", "callback", "event_source", "inventory", "lookup")
]

# Generic description families that are safe to fold into a fragment.  Each
# entry is the whitespace-collapsed, lower-cased description of an inline
# option that adds no product-specific information.  Anything else is
# treated as a deliberate per-module override and left inline.

RETRIES_OK = {
    "number of retries for transient failures.",
    "number of retries for transient sdk failures.",
    "transient api retry count.",
    "retries for transient failures.",
    "retries for transient api failures.",
    "maximum number of retry attempts for throttled or transient api failures, using exponential backoff with jitter.",
}

USER_AGENT_OK = {
    "user-agent suffix.",
    "user-agent suffix for api requests.",
    "user-agent value appended to sdk requests.",
    "user-agent string sent with api requests.",
    "value appended to the sdk user-agent header so api usage can be attributed to this collection.",
}

WAITER_TIMEOUT_OK = {
    "overall polling timeout in seconds.",
    "overall timeout in seconds for state polling.",
    "maximum time in seconds to wait for an asynchronous resource to reach the desired state.",
    "polling timeout.",
    "overall convergence timeout.",
    "overall convergence timeout in seconds.",
    "convergence timeout.",
}

WAITER_DELAY_OK = {
    "seconds between polling attempts.",
    "seconds to wait between state-polling attempts.",
    "interval in seconds between state polls while waiting.",
    "seconds between polls.",
    "polling interval.",
    "seconds between state-polling attempts.",
    "seconds between convergence polls.",
    "seconds between state checks.",
    "seconds between checks.",
    "reconciliation polling interval.",
    "async polling interval.",
}

FRAGMENT_DEFAULTS = {
    "retries": ("int", "5"),
    "user_agent": ("str", "ansible-collection.susunola.tencentcloud"),
    "waiter_timeout": ("int", "120"),
    "waiter_delay": ("int", "5"),
}

_EXTENDS_SCALAR = re.compile(r"^extends_documentation_fragment: (?P<value>[^\n]*)\n", re.M)
_EXTENDS_LIST = re.compile(r"^extends_documentation_fragment:\n(?P<items>(?:  - [^\n]*\n?)+)", re.M)


def _norm(value):
    return re.sub(r"\s+", " ", value).strip().lower()


def find_option_block(text, name):
    """Locate a top-level inline option and parse its fields.

    Returns (block_start, block_end, fields) where block covers the whole
    option (one-line or multi-line).  ``fields`` is a dict with keys such as
    type/default/description.  Returns None when the option is not inline.
    """
    pattern = re.compile(
        r"^  %s:(\s*\{[^}]*\}|(?:\n(?:    .*\n?)+))" % re.escape(name),
        re.M,
    )
    match = pattern.search(text)
    if not match:
        return None
    body = match.group(1)
    fields = {}
    if body.lstrip().startswith("{"):
        fields.update(dict(re.findall(r"(\w+):\s*([^,}]+)", body)))
    else:
        current = None
        for line in body.splitlines():
            stripped = line.strip()
            key_match = re.match(r"(\w+):(.*)$", stripped)
            if key_match and key_match.group(1) in (
                "type",
                "default",
                "required",
                "choices",
                "elements",
                "no_log",
                "description",
                "suboptions",
            ):
                fields[key_match.group(1)] = key_match.group(2).strip()
                current = key_match.group(1)
            elif current == "description":
                parts = fields.setdefault("description_parts", [])
                parts.append(stripped.lstrip("-* ").strip())
        if "description_parts" in fields:
            fields["description"] = " ".join(fields.pop("description_parts"))
    return match.start(), match.end(), fields


def option_is_generic(name, fields):
    """True when *fields* match the generic family owned by the fragment."""
    expected_type, expected_default = FRAGMENT_DEFAULTS[name]
    if fields.get("type", "").strip() != expected_type:
        return False
    if fields.get("default", "").strip() != expected_default:
        return False
    description = fields.get("description")
    if not description:
        return False
    ok_sets = {
        "retries": RETRIES_OK,
        "user_agent": USER_AGENT_OK,
        "waiter_timeout": WAITER_TIMEOUT_OK,
        "waiter_delay": WAITER_DELAY_OK,
    }
    return _norm(description) in ok_sets[name]


def _empty_options_block(text):
    """True when DOCUMENTATION has a bare ``options:`` (YAML null value).

    Stripping the last inline option can leave ``options:`` with nothing
    under it; validate-modules rejects the module because it cannot merge
    fragment options over a null value.  The generator writes option-less
    modules as ``options: {}``.
    """
    doc_match = re.search(r'(DOCUMENTATION = [ru]*("""|\'\'\')(.*?)\2)', text, re.S)
    if not doc_match:
        return False
    return re.search(r"^options:\n+(?=\S)", doc_match.group(3), re.M) is not None


def current_fragment_names(text):
    """Parse the extends_documentation_fragment block into fragment names."""
    scalar = _EXTENDS_SCALAR.search(text)
    if scalar and scalar.group("value").strip():
        value = scalar.group("value").strip()
        if "," in value:
            return [entry.strip().rsplit(".", 1)[-1] for entry in value.split(",") if entry.strip()]
        return [value.rsplit(".", 1)[-1]]
    listed = _EXTENDS_LIST.search(text)
    if listed:
        return [entry.strip()[2:].strip().rsplit(".", 1)[-1] for entry in listed.group("items").splitlines() if entry.strip().startswith("-")]
    return []


def fragments_and_stripped(text):
    """Return (desired_fragment_names, inline_option_names_to_strip)."""
    fragments = list(BASE_FRAGMENTS)
    verdicts = {}
    for name in OPTION_FRAGMENTS:
        parsed = find_option_block(text, name)
        if parsed:
            verdicts[name] = option_is_generic(name, parsed[2])
    waiter_ok = "waiter_delay" in verdicts and "waiter_timeout" in verdicts and verdicts["waiter_delay"] and verdicts["waiter_timeout"]
    stripped = []
    for name, fragment in sorted(OPTION_FRAGMENTS.items()):
        if name not in verdicts:
            continue
        if fragment == "waiter" and not waiter_ok:
            continue
        if verdicts[name]:
            if fragment not in fragments:
                fragments.append(fragment)
            stripped.append(name)
    return fragments, stripped


def migrate_file(path):
    """Rewrite one module to reference fragments instead of inline copies.

    Returns (changed, removed_options).
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()

    fragments, stripped = fragments_and_stripped(text)
    current = current_fragment_names(text)

    # A module is already canonical when it references exactly the desired
    # fragments and has nothing left to strip.
    if set(current) == set(fragments) and not stripped:
        return False, []

    if "tencentcloud" in current:
        # Base reference rewrite from the legacy single fragment.
        current = [fragment for fragment in current if fragment != "tencentcloud"]

    for name in stripped:
        start, end, _fields = find_option_block(text, name)
        text = text[:start] + text[end:]

    new_value = "\n".join(["extends_documentation_fragment:"] + ["  - %s%s" % (FQCN_PREFIX, fragment) for fragment in fragments])
    if _EXTENDS_LIST.search(text):
        text = _EXTENDS_LIST.sub(new_value + "\n", text, count=1)
    else:
        text = _EXTENDS_SCALAR.sub(new_value + "\n", text, count=1)

    # Removing inline blocks can leave double blank lines where the option
    # sat inside the DOCUMENTATION string.  Collapse runs of two or more
    # blank lines only inside that string; code sections keep PEP8 spacing.
    doc_match = re.search(r'(DOCUMENTATION = [ru]*("""|\'\'\')(.*?)\2)', text, re.S)
    if doc_match:
        cleaned = re.sub(r"\n{3,}", "\n\n", doc_match.group(3))
        # Stripping the last inline option leaves a bare "options:" whose
        # YAML value is null; validate-modules then rejects the module.  The
        # generator renders option-less modules as "options: {}".
        cleaned = re.sub(r"^options:\n+(?=\S)", "options: {}\n", cleaned, flags=re.M)
        text = text[: doc_match.start(3)] + cleaned + text[doc_match.end(3) :]

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return True, stripped


def module_paths():
    """Plugin files that carry (or should carry) collection fragments.

    Modules always carry them (canonical layout is enforced).  Non-module
    plugins are included only when they reference one of our fragments so
    plugins extending third-party fragments (e.g. ``constructed``) are
    never rewritten.
    """
    paths = []
    for pattern in PLUGIN_GLOBS:
        for path in glob.glob(pattern):
            if "/modules/" in path:
                paths.append(path)
                continue
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            if set(current_fragment_names(text)) & (KNOWN_FRAGMENTS | {"tencentcloud"}):
                paths.append(path)
    return sorted(paths)


def migrate_all():
    changed = []
    counts = {}
    for path in module_paths():
        was_changed, removed = migrate_file(path)
        if was_changed:
            changed.append(path)
            for name in removed:
                counts[name] = counts.get(name, 0) + 1
    return changed, counts


def check_all():
    """Return drift descriptions; empty means the tree is canonical."""
    problems = []
    for path in module_paths():
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        current = current_fragment_names(text)
        if not current:
            problems.append("%s: missing extends_documentation_fragment" % path)
            continue
        if "tencentcloud" in current:
            problems.append("%s: still references legacy tencentcloud fragment" % path)
            continue
        missing_base = [f for f in BASE_FRAGMENTS if f not in current]
        if missing_base:
            problems.append("%s: missing base fragment(s) %s" % (path, sorted(missing_base)))
        unknown = sorted(set(current) - KNOWN_FRAGMENTS)
        if unknown:
            problems.append("%s: unknown fragment reference(s) %s" % (path, unknown))
        if len(current) != len(set(current)):
            problems.append("%s: duplicate fragment reference(s)" % path)
        stripped = fragments_and_stripped(text)[1]
        if stripped:
            problems.append("%s: inline generic option(s) still present: %s" % (path, sorted(stripped)))
        if _empty_options_block(text):
            problems.append("%s: bare 'options:' must be 'options: {}'" % path)
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the tree is fragment-clean without modifying files",
    )
    args = parser.parse_args()

    if args.check:
        problems = check_all()
        if problems:
            for problem in problems:
                print(problem)
            print("doc-fragment drift: %d problem(s) (run without --check to fix)" % len(problems))
            return 1
        print("doc-fragment layout is canonical across %d carrier file(s)" % len(module_paths()))
        return 0

    changed, counts = migrate_all()
    for name in sorted(counts):
        print("  stripped %s: %d file(s)" % (name, counts[name]))
    print("rewrote %d carrier file(s)" % len(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
