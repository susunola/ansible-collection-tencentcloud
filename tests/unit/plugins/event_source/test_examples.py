"""The event_source examples must agree with the events the plugins emit.

ansible-core does not load ``plugins/event_source`` -- it is an ansible.eda
plugin type -- so no sanity test renders or validates these doc blocks, and
``ansible-doc`` never sees them. The examples are therefore the only
documentation a user has, and the only thing that can go stale unnoticed.

Two of them already had. The cmq example matched on ``event.cmq.MsgBody``
while the source emits ``msg_body``, and the cls example matched on
``event.level`` while the source nests the whole record under ``cls``. Both
conditions would have silently matched nothing in a real rulebook, and
nothing in the gate could have caught it.

Checking the payload key alone is not enough: ``event.cmq.MsgBody`` contains
``event.cmq``, so a key-only assertion passes on the very bug it exists to
catch. These tests therefore compare the *fields* the doc blocks address
against the fields each source's DOCUMENTATION promises -- written as
``I(event.<key>.<field>)`` -- and cross-check those promises against the
payload keys the source builds and the ones its unit test asserts on. Both
directions are checked, so the documentation cannot claim a field nobody
emits and an example cannot match a field nobody documented.
"""

from __future__ import absolute_import, division, print_function

import re
from pathlib import Path

import pytest
import yaml

# This file lives at tests/unit/plugins/event_source/, one level deeper than
# the other plugin tests, so the repo root is four parents up -- not three.
REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCES_DIR = REPO_ROOT / "plugins" / "event_source"
TESTS_DIR = REPO_ROOT / "tests" / "unit" / "plugins" / "event_source"

# queue.put({"cls": record, ...}) -- the top-level key the rulebook sees.
PUT_KEY_RE = re.compile(r"queue\.put\(\{\s*[\"'](\w+)[\"']\s*:")
# I(event.cos.key) in DOCUMENTATION -- the fields we promise a rule can use.
DOC_FIELD_TMPL = r"I\(event\.%s\.(\w+)\)"
# event.cos.key inside a rule condition.
USED_FIELD_TMPL = r"event\.%s\.(\w+)"
# Any quoted snake_case token. The payload keys a source builds and the ones
# its unit test asserts on are the ground truth for what is really emitted.
TOKEN_RE = re.compile(r"[\"']([a-z][a-z0-9_]*)[\"']")


def _source_files():
    return sorted(p for p in SOURCES_DIR.glob("*.py") if p.name != "__init__.py")


def _block(text, name):
    match = re.search(r"^%s = r?'''(.*?)'''" % name, text, re.S | re.M)
    return match.group(1) if match else None


def _payload_key(text):
    match = PUT_KEY_RE.search(text)
    return match.group(1) if match else None


def _documented_fields(text, key):
    documentation = _block(text, "DOCUMENTATION") or ""
    return set(re.findall(DOC_FIELD_TMPL % key, documentation))


def _used_fields(text, key):
    return set(re.findall(USED_FIELD_TMPL % key, text))


def _observed_tokens(path):
    """Quoted snake_case tokens in the source and in its unit test."""
    test_path = TESTS_DIR / ("test_%s.py" % path.stem)
    tokens = set(TOKEN_RE.findall(path.read_text(encoding="utf-8")))
    if test_path.is_file():
        tokens |= set(TOKEN_RE.findall(test_path.read_text(encoding="utf-8")))
    return tokens


@pytest.fixture(scope="module")
def sources():
    return [(path, path.read_text(encoding="utf-8")) for path in _source_files()]


def test_the_guard_finds_the_sources():
    """A wrong REPO_ROOT would leave `sources` empty and every check below vacuous."""
    files = _source_files()
    assert files, "no event_source plugins found under %s" % SOURCES_DIR
    assert {path.stem for path in files} >= {
        "cls_topic", "cmq_queue", "cos_bucket", "tke_cluster"}


@pytest.mark.parametrize("name", ["DOCUMENTATION", "EXAMPLES"])
def test_every_source_has_the_block(sources, name):
    for path, text in sources:
        assert _block(text, name) is not None, (
            "%s is missing an %s block" % (path.name, name))


@pytest.mark.parametrize("name", ["DOCUMENTATION", "EXAMPLES"])
def test_blocks_are_valid_yaml(sources, name):
    for path, text in sources:
        block = _block(text, name)
        if block is None:
            pytest.fail("%s has no %s block" % (path.name, name))
        yaml.safe_load(block)  # raises with the file name in the traceback


def test_examples_use_the_collection_fqcn(sources):
    for path, text in sources:
        examples = _block(text, "EXAMPLES")
        assert examples is not None, path.name
        assert "susunola.tencentcloud.%s" % path.stem in examples, (
            "%s: the example must invoke the source by its FQCN" % path.name)


def test_the_source_emits_a_scrapable_payload_key(sources):
    """Guard the scraper itself -- a silent miss would make the next test vacuous."""
    for path, text in sources:
        assert _payload_key(text), (
            "%s: no queue.put({<key>: ...}) call found; the payload-key "
            "test below would pass without checking anything" % path.name)


def test_every_source_documents_its_payload_fields(sources):
    """No documented fields would make the two checks below vacuous."""
    for path, text in sources:
        key = _payload_key(text)
        assert key, path.name
        fields = _documented_fields(text, key)
        assert fields, (
            "%s: DOCUMENTATION promises no I(event.%s.<field>), so nothing "
            "validates the example's rule condition" % (path.name, key))


def test_documented_payload_fields_are_observable(sources):
    """The other direction: do not promise a field the code never emits."""
    for path, text in sources:
        key = _payload_key(text)
        assert key, path.name
        observed = _observed_tokens(path)
        for field in sorted(_documented_fields(text, key)):
            assert field in observed, (
                "%s: DOCUMENTATION promises I(event.%s.%s) but neither the "
                "source nor its unit test ever emits that field"
                % (path.name, key, field))


def test_examples_address_documented_payload_fields(sources):
    for path, text in sources:
        key = _payload_key(text)
        assert key, path.name
        examples = _block(text, "EXAMPLES")
        assert examples is not None, path.name
        assert "event.%s" % key in examples, (
            "%s: the source emits events under the %r key, so the example "
            "rule must address event.%s" % (path.name, key, key))
        documented = _documented_fields(text, key)
        for field in sorted(_used_fields(examples, key)):
            assert field in documented, (
                "%s: the example matches event.%s.%s but DOCUMENTATION never "
                "promises that field; documented fields are %s"
                % (path.name, key, field, sorted(documented)))


def test_module_docstring_example_addresses_documented_fields(sources):
    """The docstring repeats the example; it drifted once already."""
    for path, text in sources:
        key = _payload_key(text)
        assert key, path.name
        docstring = text.split('"""')[1] if '"""' in text else ""
        conditions = [line for line in docstring.splitlines()
                      if "condition:" in line]
        assert conditions, "%s: docstring has no example condition" % path.name
        documented = _documented_fields(text, key)
        for condition in conditions:
            assert "event.%s" % key in condition, (
                "%s: docstring condition %r does not address event.%s"
                % (path.name, condition.strip(), key))
            for field in sorted(_used_fields(condition, key)):
                assert field in documented, (
                    "%s: docstring matches event.%s.%s but DOCUMENTATION "
                    "never promises that field; documented fields are %s"
                    % (path.name, key, field, sorted(documented)))
