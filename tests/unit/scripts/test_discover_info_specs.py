# -*- coding: utf-8 -*-
# Copyright (c) 2026 Tencent Cloud International / susunola
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Guard the SDK-field -> module-option rules in ``discover_info_specs``.

Every rule here exists because a missing one only surfaces much later, as an
``ansible-test sanity`` failure on a freshly regenerated module:

* a ``type: list`` option without ``elements`` -> parameter-list-no-elements;
* a cursor (``next_token``) exposed as an option -> duplicate keyword argument;
* a real credential (``Password``) without ``no_log`` -> no-log-needed;
* a read filter merely named like one (``Keyword``) with no explicit marker
  -> no-log-needed as well.

Sanity only catches those when someone regenerates, so the rules are pinned
here instead. See G1-k in ``docs/gap-closure.md``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import os
import re

import pytest
import yaml

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
DISCOVER_PATH = os.path.join(REPO_ROOT, "scripts", "discover_info_specs.py")
SPECS_AUTO_PATH = os.path.join(REPO_ROOT, "scripts", "info_specs_auto.py")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def discover():
    return _load(DISCOVER_PATH, "discover_info_specs")


def _prop(rtype, doc="A field."):
    """Build a stand-in for a SDK request-model property."""

    def fget(self):
        return None

    fget.__doc__ = "%s\n:rtype: %s" % (doc, rtype)
    return property(fget)


def _fields(**rtypes):
    return {name: _prop(rtype) for name, rtype in rtypes.items()}


def _one(discover, action=None, **rtypes):
    params, dropped = discover._extra_params(
        _fields(**rtypes), set(), discover._RESERVED, action)
    return params, dropped


# --------------------------------------------------------------------------
# elements
# --------------------------------------------------------------------------


def test_list_of_str_gets_elements(discover):
    params, dropped = _one(discover, action="DescribeIndexList", IndexStatusList="list of str")
    assert dropped == []
    assert params == [{
        "name": "index_status_list",
        "field": "IndexStatusList",
        "type": "list",
        "elements": "str",
        "required": False,
        "doc": "Sets the C(IndexStatusList) field of V(DescribeIndexList); omit it to "
               "leave that field unset.",
    }]


def test_extra_param_doc_names_the_action_and_field(discover):
    """A reader needs the API call and the field to look either one up. The
    first version of this text said "Index status list. API field
    C(IndexStatusList)." -- the first clause restating the option and the
    action nowhere."""
    params, _dropped = _one(discover, action="DescribeIndexList", IndexStatusList="list of str")
    assert "V(DescribeIndexList)" in params[0]["doc"]
    assert "C(IndexStatusList)" in params[0]["doc"]


def test_extra_param_doc_does_not_restate_the_option(discover):
    params, _dropped = _one(discover, action="DescribeIndexList", IndexStatusList="list of str")
    words = set(re.sub(r"[^a-z0-9]+", " ", params[0]["doc"].lower()).split())
    assert "index" not in words
    assert "status" not in words


def test_required_extra_param_says_the_api_needs_it(discover):
    """The SDK marks a required request field in its own docstring; the option
    the generator exposes has to repeat that, or a user meets the failure at
    call time instead of reading it in the docs."""
    prop = _prop("str", doc="Question id.\n是否必填：是")
    params, _dropped = discover._extra_params(
        {"QuestionId": prop}, set(), discover._RESERVED, "DescribeQuestionList")
    assert params[0]["required"] is True
    assert params[0]["doc"] == ("Sets the C(QuestionId) field of V(DescribeQuestionList), "
                                "which the API requires.")


def test_list_of_int_gets_elements(discover):
    params, _dropped = _one(discover, SignIdSet="list of int")
    assert params[0]["type"] == "list"
    assert params[0]["elements"] == "int"


def test_scalar_has_no_elements(discover):
    params, _dropped = _one(discover, InstanceId="str")
    assert "elements" not in params[0]


# --------------------------------------------------------------------------
# reserved names
# --------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["NextToken", "PageToken", "Offset", "Limit"])
def test_generator_owned_names_are_dropped(discover, field):
    params, dropped = _one(discover, **{field: "str"})
    assert params == []
    assert [name for name, _reason, _req in dropped] == [field]
    assert "clashes with a module option" in dropped[0][1]


def test_reserved_table_covers_the_cursor_names(discover):
    # Anti-vacuity: the reserved set is what makes the drop above meaningful.
    assert {"next_token", "page_token"} <= discover._RESERVED


# --------------------------------------------------------------------------
# no_log
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field", ["Password", "SecretName", "Credential", "PrivateKey"]
)
def test_real_secrets_are_marked_no_log(discover, field):
    params, dropped = _one(discover, **{field: "str"})
    assert dropped == []
    assert params[0]["no_log"] is True


@pytest.mark.parametrize("field", ["Keyword", "SearchKey", "TagKey", "ClientToken"])
def test_filters_merely_named_like_secrets_are_marked_not_no_log(discover, field):
    params, _dropped = _one(discover, **{field: "str"})
    # Explicitly *not* a secret, so validate-modules stops demanding no_log.
    # ClientToken is TencentCloud's idempotency token, not a credential.
    assert params[0]["no_log"] is False


def test_ordinary_field_carries_no_no_log_key(discover):
    params, _dropped = _one(discover, InstanceId="str")
    assert "no_log" not in params[0]


def test_secret_like_beats_the_mere_name_rule(discover):
    # A field matching both patterns must end up no_log, not "not a secret".
    assert discover._NO_LOG_RE.search("secret_key")
    assert discover._SECRET_LIKE_RE.search("secret_key")
    params, _dropped = _one(discover, SecretKey="str")
    assert params[0]["no_log"] is True


# --------------------------------------------------------------------------
# anti-vacuity: the real collection actually exercises all three rules
# --------------------------------------------------------------------------


def _real_params():
    module = _load(SPECS_AUTO_PATH, "info_specs_auto")
    for entry in module.SPECS_AUTO:
        for param in entry["extra_params"]:
            yield entry["module"], param


def test_real_specs_exercise_the_elements_rule():
    hits = [m for m, p in _real_params() if p.get("elements")]
    assert hits, "no generated spec carries elements -- the rule is dead code"


def test_real_specs_exercise_the_no_log_true_rule():
    hits = [(m, p["name"]) for m, p in _real_params() if p.get("no_log") is True]
    assert ("elasticsearch_index_info", "password") in hits


def test_real_specs_exercise_the_no_log_false_rule():
    hits = [(m, p["name"]) for m, p in _real_params() if p.get("no_log") is False]
    assert hits, "no generated spec is marked not-a-secret -- the rule is dead code"


def test_no_generated_cursor_option_survives():
    offenders = [
        (m, p["name"]) for m, p in _real_params()
        if p["name"] in ("next_token", "page_token")
    ]
    assert offenders == []


_DOC_RE = re.compile(r"^DOCUMENTATION\s*=\s*(?P<quote>r?'''|r?\"\"\")", re.M)


def _doc_block(text):
    """Return the YAML inside a module's ``DOCUMENTATION = r'''...'''``.

    Both triple-quote flavours occur in the collection (hand-finished modules
    use ``'''``, generated ones ``\"\"\"``), so the delimiter is matched rather
    than assumed.
    """
    match = _DOC_RE.search(text)
    quote = match.group("quote")
    delimiter = quote.lstrip("r")
    start = match.end()
    return text[start:text.index(delimiter, start)]


def test_generated_documentation_never_declares_no_log():
    # ``no_log`` is an argument_spec key only; putting it in DOCUMENTATION
    # makes validate-modules fail with "extra keys not allowed". Module-level
    # ``no_log: true`` in an EXAMPLES block is fine and must not trip this.
    modules_dir = os.path.join(REPO_ROOT, "plugins", "modules")
    checked = 0
    for name in sorted(os.listdir(modules_dir)):
        if not name.endswith("_info.py"):
            continue
        with open(os.path.join(modules_dir, name)) as handle:
            text = handle.read()
        options = yaml.safe_load(_doc_block(text)).get("options") or {}
        checked += 1
        for option, body in options.items():
            if "no_log" in (body or {}):
                pytest.fail(
                    "%s: DOCUMENTATION.options.%s declares no_log" % (name, option))
    # Anti-vacuity: an empty loop would make the assertion above meaningless.
    assert checked > 400, "only %d info modules scanned" % checked
