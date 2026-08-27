# -*- coding: utf-8 -*-
"""Auto-propose ``_info`` generator specs by introspecting the installed SDK.

For every product package of the installed ``tencentcloud`` meta package
that is not already covered by the curated SPECS in
``scripts/generate_info_modules.py`` (or by a hand-written module), this
tool finds the best paginated ``Describe*``/``List*`` action and emits a
spec dict the generator can consume.

A candidate action qualifies when:

- the request model paginates with int ``Offset``/``Limit`` ("int") or int
  page-number/page-size pairs ("page", field names PageNumber/PageSize,
  Page/PageSize, Page/Limit, PageNo/PageSize, PageNum/PageSize,
  PageIndex/PageSize), or continues with a request/response token pair
  ("token", e.g. NextToken/NextToken, PageToken, Marker/NextMarker,
  Cursor/NextCursor) with an optional MaxResults/Limit page-size field, or
  takes no request fields at all and returns the full list in one call
  ("list"),
- the response model carries an items list (``list of <model>``) and
  optionally a total-count field (``TotalCount``/``Total``/``TotalNumber``/
  ``TotalNum``), either top-level or nested one level deep (``Result.X``);
  without a total-count field offset/page pagination stops at the first
  short page,
- no old-style docstring marks a request field we cannot manage as required
  (``是否必填：是``).

On top of that the tool detects the ids field (``*Ids``/``*IdSet``/
``*IdList`` request field of ``list of str``) and the ``Filters`` model
shape (``Filter{Name,Values}``, ``QueryFilter{Names,Values}``,
``DomainFilter{Name,Value}``, ``Filter{Key,Values}`` ...).

Confident specs are written to ``scripts/info_specs_auto.py`` (a plain
``SPECS_AUTO = [...]`` list the generator appends). Specs for products that
already have one are reused verbatim so existing module output stays
byte-identical. Products without a usable list API go to the skip report
(stdout, or ``--report PATH``) with the reason. Run with the repository
virtualenv python so the full SDK is importable.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import inspect
import keyword
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_info_modules.py"
AUTO_SPECS_PATH = REPO_ROOT / "scripts" / "info_specs_auto.py"
MODULES_DIR = REPO_ROOT / "plugins" / "modules"

VERSION_ADDED = "0.9.0"

# Products already covered by curated SPECS or hand-written modules, or
# deliberately out of scope (cos uses the qcloud_cos SDK, sts/ssm/tag are
# exercised through module_utils rather than list modules). Derived from
# the curated SPECS at runtime; this constant pins the rest.
COVERED_PRODUCTS = {
    "vpc", "cvm", "cam", "cos", "tag", "sts", "ssm",
}

# Short module-name prefixes for products whose package name is awkward
# (the endpoint/host prefix differs from the SDK package name, or the short
# form is a Python keyword and unusable as a package name).
PRODUCT_ALIASES = {
    "autoscaling": "as",
}

_RTYPE_RE = re.compile(r":rtype:\s*(?P<rtype>[^\n]+)")
_NESTED_RE = re.compile(r":class:`tencentcloud\.\w+\.\w+\.models\.(?P<cls>\w+)`")
_ACTION_RE = re.compile(r"^(Describe|List|Get|Query|Search)[A-Z]")
_ACTION_PREFIX_RE = re.compile(r"^(Describe|List|Get|Query|Search)")
_IDS_RE = re.compile(r"(Ids|IdSet|IdList|IDList|IDSet)$", re.IGNORECASE)
_REQUIRED_RE = re.compile(r"是否必填：是")
_NO_LOG_RE = re.compile(r"key|secret|token|passw", re.IGNORECASE)
_TOTAL_FIELDS = ("TotalCount", "Total", "TotalNumber", "TotalNum")
_DROP_TOKENS = {"list", "detail", "details", "status", "info", "infos", "all", "new"}

# Pagination shapes beyond the classic int Offset/Limit.
_INT_SIZE_FIELDS = ("Limit", "Length")
_PAGE_PAIRS = (
    ("PageNumber", "PageSize"),
    ("PageNumber", "Limit"),
    ("Page", "PageSize"),
    ("Page", "Limit"),
    ("PageNo", "PageSize"),
    ("PageNum", "PageSize"),
    ("PageIndex", "PageSize"),
)
# Token request fields: the standard names plus product-specific markers
# (chdfs FileSystemIdMarker). The response continuation field is either
# "Next" + the request field (NextCursor, NextFileSystemIdMarker) or one of
# the standard response names.
_TOKEN_REQ_RE = re.compile(r"^(NextToken|Token|PageToken|Cursor|Marker|.*Marker)$")
_TOKEN_RESP_FIELDS = ("NextToken", "NextMarker", "NextCursor", "PageToken", "Token")
_TOKEN_SIZE_FIELDS = ("MaxResults", "Limit", "PageSize")
_LIST_OVER_FIELDS = ("ListOver", "IsOver")
_HAS_MORE_FIELDS = ("HasMore", "HasNextPage")
_PAGINATION_NAMES = frozenset(
    ["Offset", "NextToken", "Token", "PageToken", "Cursor"]
    + list(_INT_SIZE_FIELDS)
    + [name for pair in _PAGE_PAIRS for name in pair]
    + list(_TOKEN_SIZE_FIELDS))


def _props(cls):
    """Return the ``@property`` descriptors declared on *cls*."""
    return {name: attr for name, attr in vars(cls).items()
            if isinstance(attr, property)}


def _rtype(prop):
    doc = prop.fget.__doc__ or ""
    match = _RTYPE_RE.search(doc)
    return match.group("rtype").strip() if match else ""


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _curated_specs():
    """Return (curated SPECS, previously auto-generated SPECS_AUTO).

    The generator appends ``SPECS_AUTO`` at import time, so the previously
    generated entries are filtered back out by module name to keep
    re-runs of this tool idempotent. The auto specs themselves are returned
    too: products that already have one get it reused verbatim, keeping the
    existing module output byte-identical across re-runs.
    """
    generator = _load_module(GENERATOR_PATH, "generate_info_modules")
    auto = []
    if AUTO_SPECS_PATH.exists():
        auto = _load_module(AUTO_SPECS_PATH, "info_specs_auto").SPECS_AUTO
    auto_names = {spec["module"] for spec in auto}
    curated = [spec for spec in generator.SPECS if spec["module"] not in auto_names]
    return curated, auto


def _camel_words(name):
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*", name)


# Plural words the simple suffix rules get wrong.
_SINGULAR_OVERRIDES = {"buses": "bus", "sms": "sms", "apis": "api"}


def _singular(word):
    if word in _SINGULAR_OVERRIDES:
        return _SINGULAR_OVERRIDES[word]
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith(("sses", "shes", "ches", "xes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def _plural(word):
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "ch", "sh")):
        return word + "es"
    return word + "s"


def _resource_name(action):
    """Derive the snake_case singular resource from an action name."""
    name = _ACTION_PREFIX_RE.sub("", action)
    raw = _camel_words(name)
    # Rejoin plural suffixes split off all-caps abbreviations ("APIs" -> AP+Is).
    while len(raw) > 1 and raw[-1] in ("Is", "Ds") and raw[-2].isupper():
        raw[-2] += raw[-1]
        raw.pop()
    words = [w.lower() for w in raw]
    while len(words) > 1 and words[-1] in _DROP_TOKENS:
        words.pop()
    if not words:
        return ""
    words[-1] = _singular(words[-1])
    return "_".join(words)


def _scan_response(models, pmap, prefix=""):
    """Find (total field, items field) in a response-shaped property map."""
    total = next((prefix + name for name in _TOTAL_FIELDS
                  if name in pmap and _rtype(pmap[name]) == "int"), None)
    items = None
    for name, prop in pmap.items():
        rtype = _rtype(prop)
        if name == "RequestId" or not rtype.startswith("list of "):
            continue
        if rtype in ("list of str", "list of int"):
            continue
        items = prefix + name
        break
    return total, items


def _response_shape(models, resp):
    """Locate items/total fields, following one level of nesting.

    The total-count field is optional: without it, offset/page pagination
    stops at the first short page and the module reports the number of
    items collected.
    """
    total, items = _scan_response(models, _props(resp))
    if items:
        return total, items
    for name, prop in _props(resp).items():
        match = _NESTED_RE.match(_rtype(prop))
        if match and hasattr(models, match.group("cls")):
            nested = _props(getattr(models, match.group("cls")))
            t2, i2 = _scan_response(models, nested, name + ".")
            if i2:
                return t2, i2
    return total, items


def _filter_spec(models, request_props):
    """Map the request's Filters field onto the generator's filter keys."""
    prop = request_props.get("Filters")
    if prop is None:
        return None, None
    rtype = _rtype(prop)
    if not rtype.startswith("list of "):
        return None, "Filters field is not a list"
    model_name = rtype[len("list of "):].strip()
    filter_cls = getattr(models, model_name, None)
    if filter_cls is None or not inspect.isclass(filter_cls):
        return None, "filter model %s not found in models" % model_name
    fields = {name: _rtype(p) for name, p in _props(filter_cls).items()}
    name_field = name_wrap = None
    if fields.get("Name") == "str":
        name_field, name_wrap = "Name", False
    elif fields.get("Names", "").startswith("list of str"):
        name_field, name_wrap = "Names", True
    elif fields.get("Key") == "str":
        name_field, name_wrap = "Key", False
    value_field = None
    if fields.get("Values", "").startswith("list of str"):
        value_field = "Values"
    elif fields.get("Value", "").startswith("list of str"):
        # e.g. cdn's DomainFilter{Name, Value}; a scalar Value cannot hold
        # the values list the generator assigns, so it is not mappable.
        value_field = "Value"
    if not name_field or not value_field:
        return None, "filter model %s has an unrecognized shape: %s" % (
            model_name, ", ".join(sorted(fields)))
    spec = {"model": model_name}
    if name_field != "Name":
        spec["name_field"] = name_field
    if name_wrap:
        spec["name_wrap"] = True
    if value_field != "Values":
        spec["value_field"] = value_field
    return spec, None


def _ids_field(request_props, resource):
    """Pick the request field carrying a list of resource IDs.

    The field name must reference the resource (InstanceIds for instances);
    a lone *Ids-style field named after something else (bi's ModuleIdList on
    DescribeProjectList) is not an ID selector for the listed resource.
    """
    candidates = [name for name, prop in request_props.items()
                  if _rtype(prop) == "list of str" and _IDS_RE.search(name)]
    if not candidates:
        return None, None
    tokens = [token for token in resource.split("_") if len(token) > 2]
    matching = [name for name in candidates
                if any(token in name.lower() for token in tokens)]
    if len(matching) == 1:
        return matching[0], None
    if len(matching) > 1:
        return None, "ambiguous ids fields: %s" % ", ".join(sorted(matching))
    return None, None


def _detect_pagination(request_props, response_props):
    """Classify the pagination shape; return (mode, info) or (None, reason).

    ``info`` carries the generator spec keys whose values differ from the
    generator defaults (``page_number_field``, ``page_size_field``,
    ``token_request_field``, ``token_response_field``, ``list_over_field``,
    ``has_more_field``); an explicit None disables a default (token specs
    without a page-size or list-over field).
    """
    def field_type(props, name):
        prop = props.get(name)
        return _rtype(prop) if prop is not None else None

    if "Offset" in request_props:
        if field_type(request_props, "Offset") != "int":
            return None, "Offset is not int-typed"
        for size in _INT_SIZE_FIELDS:
            if field_type(request_props, size) == "int":
                info = {}
                if size != "Limit":
                    info["page_size_field"] = size
                return "int", info
        return None, "Offset without an int Limit/Length field"
    page_number_seen = False
    for number, size in _PAGE_PAIRS:
        if number not in request_props:
            continue
        page_number_seen = True
        if (field_type(request_props, number) == "int"
                and field_type(request_props, size) == "int"):
            info = {}
            if number != "PageNumber":
                info["page_number_field"] = number
            if size != "PageSize":
                info["page_size_field"] = size
            return "page", info
    if page_number_seen:
        return None, "page number field without a supported int page-size field"
    req_token = next((name for name, prop in request_props.items()
                      if _TOKEN_REQ_RE.match(name)
                      and _rtype(prop) in ("str", "int")), None)
    if req_token is not None:
        candidates = ("Next" + req_token,) + _TOKEN_RESP_FIELDS
        resp_token = next((name for name in candidates
                           if field_type(response_props, name) in ("str", "int")), None)
        if resp_token is None:
            return None, ("token request field %s has no response "
                          "continuation field" % req_token)
        size = next((name for name in _TOKEN_SIZE_FIELDS
                     if field_type(request_props, name) == "int"), None)
        list_over = next((name for name in _LIST_OVER_FIELDS
                          if field_type(response_props, name) == "bool"), None)
        has_more = next((name for name in _HAS_MORE_FIELDS
                         if field_type(response_props, name) == "bool"), None)
        info = {}
        if req_token != "NextToken":
            info["token_request_field"] = req_token
        if resp_token != "NextToken":
            info["token_response_field"] = resp_token
        if size != "MaxResults":
            info["page_size_field"] = size
        if list_over != "ListOver":
            info["list_over_field"] = list_over
        if list_over is None and has_more is not None:
            info["has_more_field"] = has_more
        return "token", info
    if any(name in _PAGINATION_NAMES or _TOKEN_REQ_RE.match(name)
           for name in request_props):
        return None, ("no supported pagination (int Offset/Limit, int page "
                      "pair, or token continuation)")
    if request_props:
        return None, "unpaginated with request fields that cannot be managed"
    return "list", {}


def _analyze_action(models, action):
    """Inspect one Describe/List-style action; return (candidate, reason)."""
    request_cls = getattr(models, action + "Request", None)
    response_cls = getattr(models, action + "Response", None)
    if request_cls is None or response_cls is None:
        return None, "no request/response model"
    request_props = _props(request_cls)
    response_props = _props(response_cls)

    total, items = _response_shape(models, response_cls)
    if not items:
        return None, "response has no list-of-model items field"

    pagination, info = _detect_pagination(request_props, response_props)
    if pagination is None:
        return None, info

    resource = _resource_name(action)
    if not resource or not resource.isidentifier() or keyword.iskeyword(resource):
        return None, "cannot derive a usable resource name from %s" % action

    ids_name, ids_note = _ids_field(request_props, resource)
    filters, filters_note = _filter_spec(models, request_props)

    managed = {"Filters", ids_name}
    if pagination == "int":
        managed.add("Offset")
        managed.add(info.get("page_size_field") or "Limit")
    elif pagination == "page":
        managed.add(info.get("page_number_field") or "PageNumber")
        managed.add(info.get("page_size_field") or "PageSize")
    elif pagination == "token":
        managed.add(info.get("token_request_field") or "NextToken")
        size_field = info.get("page_size_field", "MaxResults")
        if size_field:
            managed.add(size_field)
    for name, prop in request_props.items():
        if name in managed:
            continue
        if _REQUIRED_RE.search(prop.fget.__doc__ or ""):
            return None, "request field %s is marked required and is not manageable" % name

    # Unmanaged optional fields (Query, ActivityId, ...) hint at an action
    # that cannot be usefully called through the generic module options, so
    # prefer the cleanest candidate of the product.
    extras = [name for name in request_props if name not in managed]

    score = 0
    if ids_name:
        score += 4
    if filters:
        score += 2
    if total and "." not in total:
        score += 1
    words = _camel_words(_ACTION_PREFIX_RE.sub("", action))
    if words and words[-1].endswith(("s", "List")):
        score += 2
    score -= 2 * len(extras)

    return {
        "action": action,
        "request_class": action + "Request",
        "pagination": pagination,
        "pagination_info": info,
        "response_items": items,
        "response_total": total,
        "resource": resource,
        "ids_field": ids_name,
        "filters": filters,
        "score": score,
        "notes": [note for note in (ids_note, filters_note) if note],
    }, None


def _build_spec(product, version, client_cls, candidate):
    """Assemble the generator spec dict for one accepted candidate."""
    prefix = PRODUCT_ALIASES.get(product, product)
    resource = candidate["resource"]
    module = "%s_%s_info" % (prefix, resource)
    plural = _plural(resource)
    words = plural.replace("_", " ")
    service = product.upper()

    ids = None
    if candidate["ids_field"]:
        doc = "%s IDs to return." % resource.replace("_", " ").capitalize()
        if candidate["filters"]:
            doc += " Mutually exclusive with O(filters)."
        ids = {
            "param": "%s_ids" % resource,
            "field": candidate["ids_field"],
            "doc": doc,
        }
        if _NO_LOG_RE.search(ids["param"]):
            # IDs are not credentials; make that explicit for the
            # validate-modules no_log heuristics on key/secret-like names.
            ids["no_log"] = False

    filters = None
    if candidate["filters"]:
        filters = dict(candidate["filters"])
        filters["doc"] = "%s API filter names mapped to lists of values." % service
        # Generator default is the Filter model; keep the spec compact.
        if filters.get("model") == "Filter":
            del filters["model"]
        filters = {"doc": filters.pop("doc"), **filters}

    examples = """\
- name: List all %s
  susunola.tencentcloud.%s:
    region: ap-guangzhou
""" % (words, module)
    if ids:
        examples += """
- name: Find %s by ID
  susunola.tencentcloud.%s:
    region: ap-guangzhou
    %s: [x-xxxxxxxx]
""" % (words, module, ids["param"])

    endpoint = getattr(client_cls, "_endpoint", None) or "%s.tencentcloudapi.com" % product

    if candidate["response_total"] is None:
        return_total_doc = "Number of %s returned (the API reports no total count)." % words
    else:
        return_total_doc = "Number of %s reported by the API." % words

    spec = {
        "module": module,
        "version_added": VERSION_ADDED,
        "service_package": "tencentcloud.%s.%s" % (product, version),
        "client_module": "%s_client" % product,
        "client_class": client_cls.__name__,
        "sdk_package": "tencentcloud-sdk-python-%s" % product,
        "endpoint": endpoint,
        "action": candidate["action"],
        "request_class": candidate["request_class"],
        "ids": ids,
        "filters": filters,
        "extra_params": [],
        "response_items": candidate["response_items"],
        "response_total": candidate["response_total"],
        "result_key": plural,
        "pagination_type": candidate["pagination"],
        "short_description": "Gather information about Tencent Cloud %s %s" % (service, words),
        "description": "Returns %s %s visible in a Tencent Cloud region." % (service, words),
        "return_items_doc": "Matching %s %s." % (service, words),
        "return_total_doc": return_total_doc,
        "examples": examples,
    }
    pagination_info = candidate.get("pagination_info") or {}
    if pagination_info:
        items_order = list(spec.items())
        index = [key for key, _value in items_order].index("pagination_type") + 1
        for key, value in pagination_info.items():
            items_order.insert(index, (key, value))
            index += 1
        spec = dict(items_order)
    return spec


def discover():
    """Scan every SDK product; return (specs, skip report entries)."""
    import tencentcloud

    package_dir = os.path.dirname(tencentcloud.__file__)
    curated, old_auto = _curated_specs()
    auto_names = {spec["module"] for spec in old_auto}
    old_by_product = {spec["service_package"].split(".")[1]: spec for spec in old_auto}
    covered = COVERED_PRODUCTS | {
        spec["service_package"].split(".")[1] for spec in curated}
    used_names = ({spec["module"] for spec in curated}
                  | {path.stem for path in MODULES_DIR.glob("*.py")
                     if not path.name.startswith("__")}) - auto_names
    specs, skips = [], []
    for product in sorted(
            name for name in os.listdir(package_dir)
            if os.path.isdir(os.path.join(package_dir, name))
            and not name.startswith(("_", "common"))):
        if product in covered:
            continue
        product_dir = os.path.join(package_dir, product)
        versions = sorted(v for v in os.listdir(product_dir) if re.fullmatch(r"v\d+", v))
        if not versions:
            skips.append((product, None, "no API version directory"))
            continue
        version = versions[-1]
        try:
            client_module = importlib.import_module(
                "tencentcloud.%s.%s.%s_client" % (product, version, product))
            models = importlib.import_module("tencentcloud.%s.%s.models" % (product, version))
            client_cls = next(
                cls for name, cls in vars(client_module).items()
                if inspect.isclass(cls) and cls.__module__ == client_module.__name__
                and name.endswith("Client"))
        except StopIteration:
            skips.append((product, None, "no client class found"))
            continue
        except Exception as exc:  # import failures vary by product
            skips.append((product, None, "import failed: %r" % (exc,)))
            continue

        old = old_by_product.get(product)
        if old is not None:
            # Already covered by a previous discovery run: reuse the spec
            # verbatim so the existing module output stays byte-identical.
            candidate, _reason = _analyze_action(models, old["action"])
            if candidate:
                for note in candidate["notes"]:
                    skips.append((product, old["action"], "note: " + note))
            used_names.add(old["module"])
            specs.append(old)
            continue

        candidates, reasons = [], []
        for method in sorted(dir(client_cls)):
            if not _ACTION_RE.match(method):
                continue
            candidate, reason = _analyze_action(models, method)
            if candidate:
                candidates.append(candidate)
            elif reason:
                reasons.append("%s: %s" % (method, reason))
        if not candidates:
            skips.append((product, None, "no usable list API (%s)" % (
                reasons[0] if reasons else "no Describe/List-style actions")))
            continue
        candidates.sort(key=lambda c: (-c["score"], c["action"]))
        chosen = candidates[0]
        spec = _build_spec(product, version, client_cls, chosen)
        if spec["module"] in used_names:
            skips.append((product, chosen["action"],
                          "module name %s already exists" % spec["module"]))
            continue
        used_names.add(spec["module"])
        specs.append(spec)
        for note in chosen["notes"]:
            skips.append((product, chosen["action"], "note: " + note))
    return specs, skips


def _render_value(value, indent):
    """Render a spec value in the curated SPECS style (pep8-clean)."""
    pad = " " * indent
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        for key, item in value.items():
            lines.append("%s%r: %s," % (pad + "    ", key, _render_value(item, indent + 4)))
        lines.append(pad + "}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return "[]"
        lines = ["["]
        for item in value:
            lines.append(pad + "    " + _render_value(item, indent + 4) + ",")
        lines.append(pad + "]")
        return "\n".join(lines)
    if isinstance(value, str) and "\n" in value:
        # Triple-quoted like the curated SPECS examples blocks.
        assert '"""' not in value
        return '"""\\\n%s"""' % value
    return repr(value)


def render_auto_specs(specs):
    """Render scripts/info_specs_auto.py deterministically."""
    lines = ["SPECS_AUTO = ["]
    for spec in specs:
        lines.append("    " + _render_value(spec, 4) + ",")
    lines.append("]")
    body = "\n".join(lines)
    return '''\
# -*- coding: utf-8 -*-
"""Auto-discovered ``_info`` module specs appended to the generator SPECS.

Written by scripts/discover_info_specs.py -- regenerate instead of editing.
Every spec was derived by introspecting the installed tencentcloud SDK
packages (request/response field names, filter model shapes, pagination
types) exactly like the curated SPECS in generate_info_modules.py.
"""

%s
''' % body


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", metavar="PATH",
                        help="also write the skip report to PATH")
    args = parser.parse_args(argv)

    specs, skips = discover()
    AUTO_SPECS_PATH.write_text(render_auto_specs(specs))
    print("wrote %d specs to %s" % (len(specs), AUTO_SPECS_PATH))

    lines = ["# Skip report: products without a confident auto spec", ""]
    for product, action, reason in skips:
        lines.append("- %s%s: %s" % (product, " (%s)" % action if action else "", reason))
    report = "\n".join(lines) + "\n"
    if args.report:
        Path(args.report).write_text(report)
        print("wrote skip report to %s" % args.report)
    else:
        sys.stdout.write("\n" + report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
