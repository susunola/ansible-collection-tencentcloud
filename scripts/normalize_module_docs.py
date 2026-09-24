#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Rewrite flow-style option documentation as block style.

Why
---
The reviewer called the documentation "not human readable" and named
``plugins/modules/alb_listener.py``.  The shape they objected to is a whole
option collapsed onto one line:

    load_balancer_id: {type: str, required: true, description: ALB ID.}

432 of the 1,025 modules documented their options that way -- 381 of the 456
write modules.  Nothing in CI could see it: a flow mapping is legal YAML, so
the block parses, ``validate-modules`` accepts it, and
``sync_doc_fragments.py`` accepts ``{...}`` option bodies by design.

What it does
------------
Rewrites *only* the option entries that are written as a single-line flow
mapping, and leaves every other byte of the file alone -- including the
``r'''`` quoting, the surrounding keys and the code below.  A full YAML
round-trip of the whole DOCUMENTATION block would be shorter to write, but it
would also reflow ``version_added`` and every description in the file, and the
reviewer has to be able to read this diff.

Lists stay in flow style (``choices: [present, absent]``) because that is the
house style in the modules that were already readable, e.g. ``vpc.py``.

Usage
-----
    python scripts/normalize_module_docs.py           # rewrite
    python scripts/normalize_module_docs.py --check   # exit 1 if any remain
"""

from __future__ import absolute_import, division, print_function

import argparse
import glob
import os
import re
import sys

import yaml

__metaclass__ = type

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_GLOB = os.path.join(REPO_ROOT, "plugins", "modules", "*.py")

_DOC_RE = re.compile(
    r"(?P<open>DOCUMENTATION\s*=\s*r?)(?P<q>'''|\"\"\")(?P<body>.*?)(?P=q)", re.S)
# A top-level option written as one flow mapping on a single line.
_FLOW_OPTION_RE = re.compile(r"^(?P<indent> +)(?P<name>[A-Za-z0-9_]+): (?P<flow>\{.*\})$", re.M)
_VERSION_RE = re.compile(r"^(?P<key> *version_added: )(?P<value>[0-9][^\s]*)$", re.M)


class _Dumper(yaml.SafeDumper):
    """Dumper that keeps sequences in flow style (choices, elements lists)."""

    def increase_indent(self, flow=False, indentless=False):
        # PyYAML puts a block sequence at the same column as its key by
        # default; indent it so ``description:`` reads as a normal nested list.
        return super(_Dumper, self).increase_indent(flow, False)


class _BlockSeq(list):
    """A sequence rendered in block style -- used for description lists."""


def _represent_list(dumper, data):
    return dumper.represent_sequence("tag:yaml.org,2002:seq", list(data), flow_style=True)


def _represent_block_seq(dumper, data):
    return dumper.represent_sequence("tag:yaml.org,2002:seq", list(data), flow_style=False)


_Dumper.add_representer(list, _represent_list)
_Dumper.add_representer(_BlockSeq, _represent_block_seq)

# House order, taken from the modules that were already readable (vpc.py,
# cvm_instance.py): prose first, then the machine-readable facts.
_KEY_ORDER = ("description", "type", "required", "choices", "default",
              "elements", "aliases", "suboptions", "version_added")


def _wrap_descriptions(value):
    """Render every ``description`` list in block style, recursively."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "description" and isinstance(item, list):
                out[key] = _BlockSeq(_wrap_descriptions(item))
            else:
                out[key] = _wrap_descriptions(item)
        return out
    if isinstance(value, list):
        return [_wrap_descriptions(item) for item in value]
    return value


def _order_keys(mapping):
    known = [k for k in _KEY_ORDER if k in mapping]
    rest = [k for k in mapping if k not in _KEY_ORDER]
    return {k: mapping[k] for k in known + rest}


def _dump_option(name, indent, mapping):
    """Render one option mapping as block-style YAML lines."""
    mapping = _order_keys(_wrap_descriptions(mapping))
    text = yaml.dump(mapping, Dumper=_Dumper, default_flow_style=False,
                     sort_keys=False, width=100, allow_unicode=True, indent=2)
    text = _VERSION_RE.sub(lambda m: '%s"%s"' % (m.group("key"), m.group("value")), text)
    lines = text.rstrip("\n").split("\n")
    return ["%s%s:" % (indent, name)] + ["%s  %s" % (indent, line) for line in lines]


def normalize_text(source):
    """Return (new_source, changed) with flow-style options expanded."""
    match = _DOC_RE.search(source)
    if not match:
        return source, False
    body = match.group("body")
    if ": {" not in body:
        return source, False

    out, changed = [], False
    for line in body.split("\n"):
        hit = _FLOW_OPTION_RE.match(line)
        if not hit:
            out.append(line)
            continue
        indent = hit.group("indent")
        try:
            mapping = yaml.safe_load(hit.group("flow"))
        except yaml.YAMLError:
            out.append(line)
            continue
        if not isinstance(mapping, dict):
            out.append(line)
            continue
        # validate-modules and the style guide want description as a list.
        for key in ("description",):
            if isinstance(mapping.get(key), str):
                mapping[key] = [mapping[key]]
        out.extend(_dump_option(hit.group("name"), indent, mapping))
        changed = True

    if not changed:
        return source, False
    new_body = "\n".join(out)
    start = match.start("body")
    return source[:start] + new_body + source[match.end("body"):], True


def module_paths():
    return sorted(glob.glob(MODULE_GLOB))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="report flow-style options without editing")
    args = parser.parse_args()

    remaining = []
    for path in module_paths():
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        new_source, changed = normalize_text(source)
        if not changed:
            continue
        remaining.append(path)
        if not args.check:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(new_source)

    if args.check:
        if remaining:
            for path in remaining:
                print("%s: options documented as single-line flow mappings"
                      % os.path.relpath(path, REPO_ROOT))
            print("doc style: %d module(s) still use flow-style option docs" % len(remaining))
            return 1
        print("doc style: all %d module(s) use block-style option docs" % len(module_paths()))
        return 0

    print("normalized option documentation in %d module(s)" % len(remaining))
    return 0


if __name__ == "__main__":
    sys.exit(main())
