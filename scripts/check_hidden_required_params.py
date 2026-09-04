# -*- coding: utf-8 -*-
"""Detect hidden required request parameters in generated ``*_info`` specs.

A generated module is unusable when the underlying SDK request model has a
required field the module cannot supply: every call fails with a confusing
API error ("The parameter X is required") instead of a clear argument error.
This script introspects every spec's request model and reports required
fields that are not covered by the module's own options.

Requiredness is encoded in three ways across the SDK's model generations:

1. Old-style docstrings mark each field ``<li> name - Type - 是否必填：是 -``
   (or ``name - 是否必填：是``); only the pre-2022 models carry these.
2. New-style docstrings list defaults: ``:param _Field: 1`` means the field
   has a default (optional), ``:param _Field: <description>`` without a
   default value means required.
3. Newer models drop the parameter list entirely; those are covered by the
   curated ``KNOWN_REQUIRED`` map below, populated from live API failures.

The generator's ``REQUIRED_PARAM_OVERRIDES`` layer is the fix surface: add
the missing field as an ``extra_params`` entry there (or an ``ids``/``filters``
mapping when the API supports it). Run with ``--check`` to fail CI when a
spec hides a required parameter, mirroring ``check_sdk_drift.py``.

Run from the repository root with the collection virtualenv python so the
full SDK is importable:

    python scripts/check_hidden_required_params.py            # report
    python scripts/check_hidden_required_params.py --check   # CI gate
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_info_modules import SPECS  # noqa: E402  (applies REQUIRED_PARAM_OVERRIDES)

# Fields the generated module always supplies itself, by pagination type.
PAGINATION_FIELDS = {
    "int": {"Offset", "Limit"},
    "page": {"PageNumber", "PageSize"},
    # token pagination uses per-spec names; covered separately below.
    "token": set(),
    "list": set(),
    "none": set(),
}

# Required fields verified through live API failures for models whose
# docstrings do not encode requiredness (2022+ SDK generations). Keeping
# this map forces the generator to expose the parameter; entries must match
# an actual spec or the script fails loudly (mirrors
# REQUIRED_PARAM_OVERRIDES validation).
KNOWN_REQUIRED = {
    "lcic_answer_info": {"QuestionId"},
}

# Old-style marker: <li> field - Type - 是否必填：是 - desc</li> or the
# loose "field - 是否必填：是" form.
_OLD_REQUIRED_RE = re.compile(
    r"(?:<li>\s*)?([A-Za-z][A-Za-z0-9_:.-]*)\s*-\s*[^<]*?\s*-\s*是否必填：是\b"
)
# New-style docstring param line: ":param _Field: <default-or-description>".
_NEW_PARAM_RE = re.compile(r":param _([A-Za-z][A-Za-z0-9]*):\s*(.*)")
# A default value is a bare literal occupying the whole description
# (numbers, booleans, lists, quoted strings). Anchored so prose that merely
# starts with a digit ("1：倒序，0：顺序...") is not mistaken for a default.
_DEFAULT_RE = re.compile(
    r"^(-?\d+(?:\.\d+)?|True|False|None|\[.*\]|['\"].*['\"])$"
)


# Fields the module can set through its ids/filters/extra_params options.
def _covered_fields(spec):
    covered = set(PAGINATION_FIELDS.get(spec.get("pagination_type", "int"), set()))
    for param in spec.get("extra_params", []):
        covered.add(param["field"])
    ids = spec.get("ids")
    if ids:
        covered.add(ids["field"])
    if spec.get("filters"):
        # The generator always maps the filters option to a "Filters" field.
        covered.add("Filters")
    token_field = spec.get("token_request_field", "NextToken")
    if spec.get("pagination_type") == "token":
        covered.add(token_field)
        page_size = spec.get("page_size_field", "MaxResults")
        if page_size is not None:
            covered.add(page_size)
    return covered


def _docstring_fields(request_class):
    """Return {field: has_default} from the request class ``__init__`` docstring.

    Requiredness is encoded inconsistently across SDK generations:

    - Old-style docstrings mark each field ``<li> name - Type - 是否必填：是``;
      those fields are required regardless of the param list below.
    - New-style docstrings either list ``:param _Field: <default literal>``
      (a bare number/boolean/string means the field defaults to that value,
      so a field *without* a literal is required - lcic, ccc, ...) or list
      ``:param _Field: <prose description>`` for every field with no defaults
      at all (bm, acp, ...), in which case requiredness is not encoded.

    The no-default heuristic is therefore only applied to models whose
    docstring encodes at least one default literal (Format B); Format A
    models yield no signal and rely on the curated KNOWN_REQUIRED map.
    """
    doc = inspect.getdoc(getattr(request_class, "__init__", None)) or ""
    fields = {}
    for match in _OLD_REQUIRED_RE.finditer(doc):
        name = match.group(1).split(":")[0].strip("`")
        fields[name] = False
    param_lines = [(m.group(1), m.group(2).strip())
                   for m in _NEW_PARAM_RE.finditer(doc)]
    if not any(_DEFAULT_RE.match(desc) for _field_name, desc in param_lines):
        # Format A: no default literals, requiredness not encoded. Keep only
        # fields pinned by an old-style marker.
        return fields
    for name, desc in param_lines:
        if name in fields:
            continue  # old-style marker wins
        fields[name] = bool(_DEFAULT_RE.match(desc))
    return fields


def _load_request_model(spec):
    try:
        # Models live in a submodule; importlib.import_module of the version
        # package does not bind ``models`` as an attribute until imported.
        models_mod = importlib.import_module("%s.models" % spec["service_package"])
    except ImportError:
        return None, "import error for %s.models" % spec["service_package"]
    request_class = getattr(models_mod, spec["request_class"], None)
    if request_class is None:
        return None, "%s.models has no %s" % (spec["service_package"], spec["request_class"])
    return request_class, None


def scan(spec):
    """Return a list of (field, source) uncovered required fields for *spec*."""
    problems = {}
    known = KNOWN_REQUIRED.get(spec["module"], set())
    covered = _covered_fields(spec)
    for field in sorted(known - covered):
        problems[field] = "curated KNOWN_REQUIRED"
    request_class, error = _load_request_model(spec)
    if error:
        return sorted(problems.items()), error
    for field, has_default in _docstring_fields(request_class).items():
        if not has_default and field not in covered:
            problems.setdefault(field, "SDK docstring")
    return sorted(problems.items()), None


def _validate_known_required():
    """Fail loudly when KNOWN_REQUIRED references a spec that does not exist.

    Mirrors the generator's REQUIRED_PARAM_OVERRIDES validation: a discover
    re-run that renames or removes a module would otherwise silently leave
    the curated entry hanging (and the guard would never run against it).
    """
    known = {spec["module"] for spec in SPECS}
    missing = sorted(set(KNOWN_REQUIRED) - known)
    if missing:
        raise SystemExit(
            "KNOWN_REQUIRED references specs that no longer exist "
            "(removed or renamed by discover_info_specs.py?): %s"
            % ", ".join(missing))


def main(argv=None, out=None, err=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="exit 1 when any spec hides a required request parameter",
    )
    args = parser.parse_args(argv)
    out = out or sys.stdout
    err = err or sys.stderr

    _validate_known_required()
    findings = []
    import_errors = []
    for spec in SPECS:
        problems, error = scan(spec)
        if error:
            import_errors.append((spec["module"], error))
        for field, source in problems:
            findings.append((spec["module"], field, source))

    print("specs scanned: %d" % len(SPECS), file=out)
    if import_errors:
        print("import errors (%d, not fatal):" % len(import_errors), file=out)
        for module, error in sorted(import_errors):
            print("  %-40s %s" % (module, error), file=out)
    if findings:
        print("hidden required params (%d):" % len(findings), file=out)
        for module, field, source in sorted(findings):
            print("  %-44s %-20s %s" % (module, field, source), file=out)
    else:
        print("no hidden required params found", file=out)

    if import_errors and args.check:
        # Import errors are fatal in --check mode: a broken spec means the
        # module cannot be generated at all.
        print("import errors prevent full verification", file=err)
        return 1
    if findings and args.check:
        print(
            "fix by adding the field to REQUIRED_PARAM_OVERRIDES in "
            "scripts/generate_info_modules.py (extra_params/ids/filters) or "
            "to KNOWN_REQUIRED here, then regenerate.",
            file=err,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
