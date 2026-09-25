#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Say which of the identity options identifies the resource, and how.

Why
---
Forty-four core modules accept an id and a name for the same resource, and
describe them as "Existing policy ID." and "Policy name." A reader cannot tell
from that whether both are needed, which one wins when both are given, or
whether the name is only good for creating. It is the first question these
modules raise and the code answers all of it:

* the argument spec declares ``required_one_of=[("policy_id", "name")]``, so
  exactly one of them must be given;
* the lookup helper tests ``not p.get("policy_id")`` before falling back to the
  name, so the id wins when both are given.

Both facts are read from the module, and the sentence is built from them:

    policy_id:
      description:
        - Identifies the policy to manage; one of this or O(name) is required,
          and the module matches on the id when it is given.
    name:
      description:
        - Identifies the policy to manage; one of this or O(policy_id) is
          required, and the name is only used when the id is not given.

When the precedence cannot be read the first clause is still written, because
it comes from the argument spec alone; the second is not guessed.

What it will not touch
----------------------
Only an option whose description is still under ``MIN_DESCRIPTION``
characters, only groups made of an id and a name, and only groups where both
members are optional. A group that also requires one member outright is saying
something this sentence would contradict.

Usage
-----
    python scripts/enrich_identity_docs.py            # insert
    python scripts/enrich_identity_docs.py --check    # exit 1 if any remain thin
"""

from __future__ import absolute_import, division, print_function

import argparse
import ast
import glob
import os
import re
import sys

__metaclass__ = type

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enrich_state_docs import (  # noqa: E402  (path setup must happen first)
    DOC_RE,
    MIN_DESCRIPTION,
    _wrapped,
    resource_noun,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES_DIR = os.path.join(REPO_ROOT, "plugins", "modules")
CORE_SUBSET = os.path.join(REPO_ROOT, "tests", "quality", "core-subset.yml")

# Followed by a comma when another argument follows and by a closing
# parenthesis when it is the last one, which both shapes in this
# collection do.
ONE_OF_RE = re.compile(r"required_one_of=\[(.*?)\]\s*[,)]", re.S)

#: The sentence starts with this. A description that starts with it is one
#: this script wrote, and the script keeps it up to date: when the rule that
#: builds the sentence improves, ``--check`` has to notice that the text on
#: disk is no longer what the rule produces. Checking only for *thin* options
#: would miss that, because the text it wrote is not thin.
GENERATED_PREFIX = "Identifies the "

#: ...and contains this, which no hand-written description in the collection
#: does. The prefix alone is not enough to claim a description: the curated
#: ``state`` sentences in this repository open with the same "C(present) "
#: that the sibling generator writes, and treating a shared opening as
#: ownership nearly overwrote 46 hand-written descriptions.
GENERATED_MARKER = "one of this or O("


def core_products():
    import yaml

    with open(CORE_SUBSET, encoding="utf-8") as handle:
        return set(yaml.safe_load(handle)["products"])


def module_paths():
    products = core_products()
    found = []
    for path in sorted(glob.glob(os.path.join(MODULES_DIR, "*.py"))):
        name = os.path.basename(path)[:-3]
        if name.split("_")[0] in products:
            found.append(path)
    return found


def documentation(body):
    import yaml

    try:
        parsed = yaml.safe_load(body)
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _generated(spec):
    """True when this option carries the sentence this script writes."""
    if not isinstance(spec, dict):
        return False
    description = spec.get("description")
    items = description if isinstance(description, list) else [description]
    return any(isinstance(item, str) and item.startswith(GENERATED_PREFIX)
               and GENERATED_MARKER in item for item in items)


def thin_options(body):
    """Option names whose documented description says almost nothing."""
    parsed = documentation(body)
    if not parsed:
        return {}
    found = {}
    for name, spec in (parsed.get("options") or {}).items():
        if not isinstance(spec, dict):
            continue
        description = spec.get("description")
        items = description if isinstance(description, list) else [description]
        text = " ".join(str(item) for item in items if item is not None).strip()
        if len(text) < MIN_DESCRIPTION:
            found[name] = spec
    return found


def identity_groups(source):
    """``required_one_of`` groups made of one id and one name, both optional.

    The pair is what the sentence is about, so a group of three, a group
    without an id, or a group whose id is required outright is left alone.
    """
    match_doc = DOC_RE.search(source)
    if not match_doc:
        return []
    body = match_doc.group("body")
    options = thin_options(body)
    declared = (documentation(body) or {}).get("options") or {}
    match = ONE_OF_RE.search(source)
    if not match:
        return []
    try:
        groups = ast.literal_eval("[" + match.group(1) + "]")
    except (SyntaxError, ValueError):
        return []

    found = []
    for group in groups:
        members = [str(item) for item in group]
        if len(members) != 2:
            continue
        identifiers = [name for name in members if name.endswith("_id")]
        names = [name for name in members if name == "name" or name.endswith("_name")]
        if len(identifiers) != 1 or len(names) != 1:
            continue
        if not all(isinstance(declared.get(name), dict) for name in members):
            continue
        if any((declared[name] or {}).get("required") for name in members):
            continue
        # At least one member has to need the sentence -- either it is still
        # thin, or it carries the sentence already and has to keep matching
        # what the rule produces. The other member is left alone whatever it
        # says: a description that already explains itself is not improved by
        # this sentence.
        if not any(name in options or _generated(declared.get(name)) for name in members):
            continue
        found.append((identifiers[0], names[0]))
    return found


def id_precedence(source, id_option):
    """True when the module falls back to the name only without an id.

    The lookup helpers in this collection are written the same way --
    ``(id and ...) or (not id and ... by name)`` -- and the id arrives either
    as ``p["id"]`` inside ``run_module`` (alb_load_balancer) or as a parameter
    of a ``find`` helper the module passes it to (cam_group). Both spellings
    are accepted, and the bare one only counts when the module actually feeds
    the option into that name somewhere, so an unrelated local of the same
    name cannot be mistaken for it.
    """
    quoted = re.search(r"(?:p\.get\(|p\[)\s*[\"']%s[\"']" % re.escape(id_option), source)
    if not quoted:
        return False
    if re.search(r"not\s+%s\b" % re.escape(id_option), source):
        return True
    return bool(re.search(r"not\s+p\.get\(\s*[\"']%s[\"']", source))


def option_span(body, option):
    """Span of the ``description`` value under ``options.<option>``."""
    lines = body.split("\n")
    in_options = False
    for index, line in enumerate(lines):
        if re.match(r"^options:\s*$", line):
            in_options = True
            continue
        if in_options and re.match(r"^[a-z_]+:", line):
            break
        if not in_options or not re.match(r"^  %s:\s*$" % re.escape(option), line):
            continue
        for offset in range(index + 1, len(lines)):
            if re.match(r"^  \S", lines[offset]):
                break
            if re.match(r"^    description:\s*", lines[offset]):
                end = offset + 1
                while end < len(lines) and re.match(r"^ {6,}\S", lines[end]):
                    end += 1
                return offset, end
    return None


def build_description(noun, option, partner, is_identifier, prefers_id):
    """Return the description lines for one member of an identity pair."""
    the = "the %s" % noun if noun else "the resource"
    text = "Identifies %s to manage; one of this or O(%s) is required" % (the, partner)
    if prefers_id:
        if is_identifier:
            text += ", and the module matches on the id when it is given"
        else:
            text += ", and the name is only used when O(%s) is not given" % partner
    return [text + "."]


def enrich(source):
    """Return a new module source with identity descriptions, or None."""
    match = DOC_RE.search(source)
    if not match:
        return None
    body = match.group("body")
    groups = identity_groups(source)
    if not groups:
        return None
    noun = resource_noun(source)
    pairs = {}
    for identifier, name in groups:
        prefers = id_precedence(source, identifier)
        pairs[identifier] = (name, True, prefers)
        pairs[name] = (identifier, False, prefers)

    new_body = body
    changed = False
    thin = thin_options(body)
    declared = (documentation(body) or {}).get("options") or {}
    for option, (partner, is_identifier, prefers) in pairs.items():
        if option not in thin and not _generated(declared.get(option)):
            continue
        span = option_span(new_body, option)
        if span is None:
            continue
        start, end = span
        lines = new_body.split("\n")
        replacement = ["    description:"] + _wrapped(
            build_description(noun, option, partner, is_identifier, prefers))
        new_body = "\n".join(lines[:start] + replacement + lines[end:])
        changed = True
    if not changed:
        return None
    return source[:match.start("body")] + new_body + source[match.end("body"):]


def candidates():
    """Return [(path, source, new_source)] for modules still thin."""
    found = []
    for path in module_paths():
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        new_source = enrich(source)
        if new_source is None or new_source == source:
            # Nothing to change. The generator owns the sentences it wrote, so
            # a module it has already described comes back through here on
            # every run; only a difference is a finding.
            continue
        found.append((path, source, new_source))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="exit 1 while any identity pair is still thin")
    parser.add_argument("--print", dest="show", action="store_true",
                        help="print the generated descriptions instead of writing")
    args = parser.parse_args(argv)

    found = candidates()
    if args.show:
        for path, source, new_source in found[:4]:
            print("── %s" % os.path.relpath(path, REPO_ROOT))
            body = DOC_RE.search(new_source).group("body")
            for identifier, name in identity_groups(source):
                for option in (identifier, name):
                    span = option_span(body, option)
                    if span:
                        print("\n".join(body.split("\n")[span[0]:span[1]]))
        return 0

    if args.check:
        if found:
            for path, _source, _new in found:
                print("%s: identity option(s) still say nothing about the alternative"
                      % os.path.relpath(path, REPO_ROOT))
            print("identity docs: %d core module(s) still describe an id/name pair "
                  "as two unrelated options" % len(found))
            return 1
        print("identity docs: every core id/name pair says which to give")
        return 0

    for path, _source, new_source in found:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(new_source)
    print("identity docs: described %d module(s)" % len(found))
    return 0


if __name__ == "__main__":
    sys.exit(main())
