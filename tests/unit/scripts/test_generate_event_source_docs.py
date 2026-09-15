# -*- coding: utf-8 -*-
"""Tests for scripts/generate_event_source_docs.py.

The page exists because ``event_source`` is invisible to ansible-core *and*
to antsibull-docs, so nothing upstream would ever notice it rotting. These
tests are therefore the only thing standing between "the docsite documents
the event sources" and "the docsite claims to".

Two kinds of assertion matter and both are here:

* anti-vacuity -- the guard really reads four plugins with real options and
  payload fields, in this repository, right now;
* every rule can actually fail -- each one is driven to failure against a
  synthetic tree, because a rule that cannot fail is not a rule.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_event_source_docs.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load(SCRIPT_PATH, "gen_event_source_docs")

PLUGIN_TEMPLATE = """# -*- coding: utf-8 -*-
DOCUMENTATION = '''
---
module: {name}
short_description: Poll something (event source)
description:
  - Polls something and yields I(event.{name}.field) for each hit.
  - See L(the docs, https://example.com/docs) for the O(interval) knob.
version_added: "1.0.0"
options:
  interval:
    description: Seconds between C(polls).
    type: float
    default: 5
  region:
    description: Region to poll.
    type: str
'''

EXAMPLES = '''
- name: demo
  hosts: all
  sources:
    - susunola.tencentcloud.{name}:
        interval: 10
'''
"""

NO_PAYLOAD_TEMPLATE = PLUGIN_TEMPLATE.replace(
    "I(event.{name}.field) for each hit", "one event per hit"
)
NO_EXAMPLES_TEMPLATE = PLUGIN_TEMPLATE.split("EXAMPLES =", maxsplit=1)[0]


def _write_plugin(directory: Path, name: str, template: str = PLUGIN_TEMPLATE) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.py"
    path.write_text(template.format(name=name))
    return path


def _setup(tmp_path, names, page=True, build_sh=None, index_rst=None, template=PLUGIN_TEMPLATE,
           monkeypatch=None):
    """Point the module at a synthetic docsite tree and return its root."""
    root = tmp_path / "repo"
    plugin_dir = root / "plugins" / "event_source"
    if names:
        for name in names:
            _write_plugin(plugin_dir, name, template)
    else:
        plugin_dir.mkdir(parents=True, exist_ok=True)

    docsite = root / "docs" / "docsite"
    extra = docsite / "extra_rst"
    extra.mkdir(parents=True, exist_ok=True)
    (docsite / "rst").mkdir(parents=True, exist_ok=True)

    if build_sh is None:
        build_sh = "#!/usr/bin/env bash\ncp extra_rst/*.rst rst/\n"
    (docsite / "build.sh").write_text(build_sh)
    if index_rst is None:
        index_rst = ".. toctree::\n\n   event_source_plugins\n"
    (docsite / "rst" / "index.rst").write_text(index_rst)

    page_path = extra / "event_source_plugins.rst"
    if page is True:
        page_path.write_text(MODULE.render(MODULE.collect_plugins.__wrapped__()
                                           if hasattr(MODULE.collect_plugins, "__wrapped__")
                                           else []))
    elif isinstance(page, str):
        page_path.write_text(page)

    monkeypatch.setattr(MODULE, "EVENT_SOURCE_DIR", plugin_dir)
    monkeypatch.setattr(MODULE, "DOCSITE", docsite)
    monkeypatch.setattr(MODULE, "EXTRA_RST", extra)
    monkeypatch.setattr(MODULE, "PAGE_PATH", page_path)
    monkeypatch.setattr(MODULE, "BUILD_SH", docsite / "build.sh")
    monkeypatch.setattr(MODULE, "INDEX_RST", docsite / "rst" / "index.rst")
    return root


def _setup_rendered(tmp_path, names, monkeypatch, **kwargs):
    """Build a synthetic tree whose page matches what render() produces."""
    root = _setup(tmp_path, names, page=False, monkeypatch=monkeypatch, **kwargs)
    page = MODULE.EXTRA_RST / "event_source_plugins.rst"
    page.write_text(MODULE.render(MODULE.collect_plugins()))
    return root


# --------------------------------------------------------------------------
# Anti-vacuity: the guard is looking at real content, not an empty set
# --------------------------------------------------------------------------


def test_the_real_repository_passes():
    assert MODULE.audit() == []


def test_the_real_repository_really_has_four_event_sources():
    plugins = MODULE.collect_plugins()
    assert [plugin["name"] for plugin in plugins] == [
        "cls_topic",
        "cmq_queue",
        "cos_bucket",
        "tke_cluster",
    ]


def test_every_real_plugin_has_options_and_payload_fields():
    plugins = MODULE.collect_plugins()
    assert plugins, "no plugins found -- the guard would be vacuous"
    for plugin in plugins:
        assert len(plugin["doc"].get("options") or {}) >= 8, plugin["name"]
        assert plugin["payload"], plugin["name"]
        assert all(field.startswith("event.") for field in plugin["payload"])


def test_every_real_payload_field_is_a_dotted_event_path():
    for plugin in MODULE.collect_plugins():
        for field in plugin["payload"]:
            assert re.fullmatch(r"event\.[A-Za-z0-9_.]+", field), field


def test_the_real_page_has_a_section_for_every_plugin():
    page = MODULE.PAGE_PATH.read_text()
    anchors = set(MODULE.ANCHOR_RE.findall(page))
    assert anchors == {"cls_topic", "cmq_queue", "cos_bucket", "tke_cluster"}


def test_the_real_page_lists_the_documented_payload_fields():
    page = MODULE.PAGE_PATH.read_text()
    for field in ("event.cls.level", "event.cmq.msg_body", "event.cos.key",
                  "event.tke.cluster_state"):
        assert field in page, field


def test_the_real_wiring_is_present():
    assert "extra_rst" in MODULE.BUILD_SH.read_text()
    assert re.search(r"^\s+event_source_plugins\s*$", MODULE.INDEX_RST.read_text(), re.M)


def test_the_real_page_is_reproducible():
    assert MODULE.PAGE_PATH.read_text() == MODULE.render(MODULE.collect_plugins())


# --------------------------------------------------------------------------
# Rendering rules
# --------------------------------------------------------------------------


def test_semantic_markup_becomes_rst_literals():
    assert MODULE._macro_to_rst("set O(interval) to C(5)") == "set ``interval`` to ``5``"


def test_link_macros_keep_only_their_title():
    assert MODULE._macro_to_rst("see L(the docs, https://example.com/x)") == \
        "see the docs"


def test_no_single_backticks_survive_rendering():
    """``default_role = any`` + ``-W`` turns a stray `x` into a build failure."""
    rendered = MODULE.render(MODULE.collect_plugins())
    for line in rendered.splitlines():
        assert not re.search(r"(^|\s)`[^`]", line), line


def test_the_heading_does_not_repeat_event_source(tmp_path, monkeypatch):
    _setup(tmp_path, ["demo"], page=False, monkeypatch=monkeypatch)
    rendered = MODULE.render(MODULE.collect_plugins())
    assert "demo event source -- Poll something (event source)" not in rendered
    assert "susunola.tencentcloud.demo event source -- Poll something" in rendered


def test_defaults_are_rendered(tmp_path, monkeypatch):
    _setup(tmp_path, ["demo"], page=False, monkeypatch=monkeypatch)
    rendered = MODULE.render(MODULE.collect_plugins())
    assert "Default: ``5``." in rendered


def test_string_defaults_are_not_quoted_yaml():
    """yaml.safe_dump would render the CLS query default as ``'*'``."""
    assert MODULE._scalar("*") == "*"
    assert MODULE._scalar(True) == "true"
    assert MODULE._scalar(False) == "false"
    assert MODULE._scalar(20) == "20"


def test_the_real_page_renders_the_query_default_bare():
    assert "Default: ``*``." in MODULE.PAGE_PATH.read_text()


def test_option_tables_have_a_row_per_option(tmp_path, monkeypatch):
    _setup(tmp_path, ["demo"], page=False, monkeypatch=monkeypatch)
    rendered = MODULE.render(MODULE.collect_plugins())
    assert "``interval``" in rendered
    assert "``region``" in rendered


# --------------------------------------------------------------------------
# Every rule can fail
# --------------------------------------------------------------------------


def test_a_missing_page_is_reported(tmp_path, monkeypatch):
    _setup(tmp_path, ["demo"], page=False, monkeypatch=monkeypatch)
    problems = MODULE.audit()
    assert any("docsite page is missing" in problem for problem in problems)


def test_a_stale_page_is_reported(tmp_path, monkeypatch):
    _setup(tmp_path, ["demo"], page=False, monkeypatch=monkeypatch)
    (MODULE.EXTRA_RST / "event_source_plugins.rst").write_text("stale\n")
    problems = MODULE.audit()
    assert any("out of date" in problem for problem in problems)


def test_a_plugin_without_a_section_is_reported(tmp_path, monkeypatch):
    _setup_rendered(tmp_path, ["demo"], monkeypatch=monkeypatch)
    _write_plugin(MODULE.EVENT_SOURCE_DIR, "extra_src")
    problems = MODULE.audit()
    assert any("extra_src" in problem and "no section" in problem for problem in problems)


def test_a_section_without_a_plugin_is_reported(tmp_path, monkeypatch):
    _setup_rendered(tmp_path, ["demo"], monkeypatch=monkeypatch)
    page = MODULE.EXTRA_RST / "event_source_plugins.rst"
    page.write_text(
        page.read_text()
        + "\n.. _ansible_collections.susunola.tencentcloud.ghost_event_source:\n"
    )
    problems = MODULE.audit()
    assert any("ghost" in problem and "not in" in problem for problem in problems)


def test_a_plugin_without_payload_fields_is_reported(tmp_path, monkeypatch):
    _setup(tmp_path, ["demo"], page=False, template=NO_PAYLOAD_TEMPLATE,
           monkeypatch=monkeypatch)
    (MODULE.EXTRA_RST / "event_source_plugins.rst").write_text(
        MODULE.render(MODULE.collect_plugins())
    )
    problems = MODULE.audit()
    assert any("declares no" in problem for problem in problems)


def test_a_plugin_without_examples_is_reported(tmp_path, monkeypatch):
    _setup(tmp_path, ["demo"], page=False, template=NO_EXAMPLES_TEMPLATE,
           monkeypatch=monkeypatch)
    (MODULE.EXTRA_RST / "event_source_plugins.rst").write_text(
        MODULE.render(MODULE.collect_plugins())
    )
    problems = MODULE.audit()
    assert any("no EXAMPLES block" in problem for problem in problems)


def test_a_build_script_that_does_not_copy_extra_rst_is_reported(tmp_path, monkeypatch):
    _setup_rendered(tmp_path, ["demo"], monkeypatch=monkeypatch,
                    build_sh="#!/usr/bin/env bash\nsphinx-build -M html rst build\n")
    problems = MODULE.audit()
    assert any("does not mention extra_rst" in problem for problem in problems)


def test_a_missing_build_script_is_reported(tmp_path, monkeypatch):
    _setup_rendered(tmp_path, ["demo"], monkeypatch=monkeypatch)
    MODULE.BUILD_SH.unlink()
    problems = MODULE.audit()
    assert any("build script is missing" in problem for problem in problems)


def test_an_index_without_a_toctree_entry_is_reported(tmp_path, monkeypatch):
    _setup_rendered(tmp_path, ["demo"], monkeypatch=monkeypatch,
                    index_rst=".. toctree::\n\n   collections/index\n")
    problems = MODULE.audit()
    assert any("toctree entry" in problem for problem in problems)


def test_a_missing_index_is_reported(tmp_path, monkeypatch):
    _setup_rendered(tmp_path, ["demo"], monkeypatch=monkeypatch)
    MODULE.INDEX_RST.unlink()
    problems = MODULE.audit()
    assert any("docsite index is missing" in problem for problem in problems)


def test_an_empty_plugin_directory_is_reported(tmp_path, monkeypatch):
    _setup(tmp_path, [], page=False, monkeypatch=monkeypatch)
    problems = MODULE.audit()
    assert any("no event source plugins found" in problem for problem in problems)


def test_check_reports_and_exits_non_zero(tmp_path, monkeypatch, capsys):
    _setup(tmp_path, ["demo"], page=False, monkeypatch=monkeypatch)
    monkeypatch.setattr("sys.argv", ["generate_event_source_docs.py", "--check"])
    assert MODULE.main() == 1


def test_check_reports_zero_when_the_page_is_current(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["generate_event_source_docs.py", "--check"])
    assert MODULE.main() == 0
    assert "ok" in capsys.readouterr().out


def test_generation_rewrites_the_page(tmp_path, monkeypatch, capsys):
    _setup(tmp_path, ["demo"], page=False, monkeypatch=monkeypatch)
    monkeypatch.setattr("sys.argv", ["generate_event_source_docs.py"])
    assert MODULE.main() == 0
    page = MODULE.EXTRA_RST / "event_source_plugins.rst"
    assert page.read_text() == MODULE.render(MODULE.collect_plugins())
    assert "1 event source plugins" in capsys.readouterr().out


@pytest.mark.parametrize("missing", ["build_sh", "index_rst", "page"])
def test_each_link_in_the_chain_is_load_bearing(tmp_path, monkeypatch, missing):
    """Remove any one link and the guard must notice."""
    _setup_rendered(tmp_path, ["demo"], monkeypatch=monkeypatch)
    if missing == "build_sh":
        MODULE.BUILD_SH.unlink()
    elif missing == "index_rst":
        MODULE.INDEX_RST.unlink()
    else:
        MODULE.PAGE_PATH.unlink()
    assert MODULE.audit()
