# -*- coding: utf-8 -*-
"""Generate the docsite page for the ``event_source`` plugins.

``plugins/event_source`` holds the ansible-rulebook event sources (CLS, CMQ,
COS, TKE). They are the one plugin type in this collection that is invisible
to every upstream documentation tool at once:

* ansible-core's plugin loader does not resolve the type, so ``ansible-doc``
  never sees it and no sanity test renders its ``DOCUMENTATION``;
* antsibull-docs does not know the type either, so it emits no page and the
  docsite ships with **zero** pages for four user-facing plugins.

The only thing keeping the docs honest today is a unit test that compares the
EXAMPLES block with the code (G1-g). That test cannot fail *loudly* anywhere a
user would look, and a reader browsing the published docsite finds nothing.

This script closes that by rendering ``docs/docsite/extra_rst/
event_source_plugins.rst`` from each plugin's ``DOCUMENTATION`` and
``EXAMPLES`` blocks, so the page cannot drift from the code it describes.

It also validates the **wiring**, which is the part a pure diff of the page
would miss. An RST file that is generated but never copied into the Sphinx
source directory, or copied but never named in a ``toctree``, ships just as
invisibly as no page at all -- and with ``-W`` a file outside every toctree
does not even build. So the guard checks the whole chain:

* every plugin on disk has a section on the page (and vice versa);
* every plugin declares at least one matchable ``event.<key>.<field>``;
* ``build.sh`` copies ``extra_rst/`` into ``rst/``;
* ``rst/index.rst`` names the page in a ``toctree``.

Run with ``--check`` to fail CI, mirroring the other ``check_*.py`` gates.

    python scripts/generate_event_source_docs.py           # rewrite the page
    python scripts/generate_event_source_docs.py --check   # CI gate
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

EVENT_SOURCE_DIR = REPO_ROOT / "plugins" / "event_source"
DOCSITE = REPO_ROOT / "docs" / "docsite"
EXTRA_RST = DOCSITE / "extra_rst"
BUILD_SH = DOCSITE / "build.sh"
INDEX_RST = DOCSITE / "rst" / "index.rst"

PAGE_NAME = "event_source_plugins"
PAGE_PATH = EXTRA_RST / f"{PAGE_NAME}.rst"

COLLECTION = "susunola.tencentcloud"

DOCUMENTATION_RE = re.compile(r"DOCUMENTATION\s*=\s*r?'''(.*?)'''", re.S)
EXAMPLES_RE = re.compile(r"EXAMPLES\s*=\s*r?'''(.*?)'''", re.S)

# Semantic markup, in the order the substitutions must run: the two-argument
# link macros first, otherwise the single-argument pattern eats "L(title,"
# and leaves a dangling ", url)" in the rendered page.
LINK_MACRO_RE = re.compile(r"[LR]\(([^,()]+),\s*([^()]*)\)")
SIMPLE_MACRO_RE = re.compile(r"[CIOMVU]\(([^()]*)\)")

# Declared matchable fields, e.g. I(event.cos.key). G1-g added these to the
# plugins precisely because nothing else rendered them.
PAYLOAD_RE = re.compile(r"I\((event\.[A-Za-z0-9_.]+)\)")

ANCHOR_RE = re.compile(r"\.\. _ansible_collections\.susunola\.tencentcloud\.([a-z0-9_]+)_event_source:")


def _macro_to_rst(text: str) -> str:
    """Turn Ansible semantic markup into RST inline literals.

    The docsite sets ``default_role = "any"`` and builds with ``-W``, so a
    single-backtick span would be resolved as a cross-reference and fail the
    build. Double backticks are plain literals and always safe.
    """
    text = LINK_MACRO_RE.sub(r"\1", text)
    text = SIMPLE_MACRO_RE.sub(r"``\1``", text)
    return " ".join(text.split())


def _as_text(value) -> str:
    if isinstance(value, str):
        return _macro_to_rst(value)
    if isinstance(value, (list, tuple)):
        return " ".join(_as_text(item) for item in value)
    return str(value)


def _scalar(value) -> str:
    """Render a default as its YAML spelling, not Python's.

    ``yaml.safe_dump`` would quote a string default (``'*'``) and ``str()``
    would capitalise a boolean (``True``); the docsite should read the way
    the option is written in a rulebook.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return str(value)


def _option_rows(options):
    rows = []
    for name, spec in sorted((options or {}).items()):
        spec = spec or {}
        description = _as_text(spec.get("description"))
        default = spec.get("default")
        if default is not None:
            description = f"{description} Default: ``{_scalar(default)}``."
        rows.append((name, spec.get("type", ""), description))
    return rows


def load_plugin(path: Path):
    """Return the rendered section data for one event source plugin."""
    text = path.read_text()
    doc_match = DOCUMENTATION_RE.search(text)
    if not doc_match:
        return None
    doc = yaml.safe_load(doc_match.group(1)) or {}
    examples_match = EXAMPLES_RE.search(text)
    examples = (examples_match.group(1).strip() if examples_match else "")
    payload = []
    for field in PAYLOAD_RE.findall(doc_match.group(1)):
        if field not in payload:
            payload.append(field)
    return {
        "name": path.stem,
        "doc": doc,
        "examples": examples,
        "payload": payload,
    }


def _underline(title: str, char: str) -> str:
    return char * len(title)


def render(plugins) -> str:
    lines = [
        ".. Document meta",
        "",
        ".. |antsibull-internal-nbsp| unicode:: 0xA0",
        "    :trim:",
        "",
        ".. Anchors",
        "",
        f".. _ansible_collections.{COLLECTION}.{PAGE_NAME}:",
        "",
        ".. Title",
        "",
    ]
    title = "Event source plugins (Event-Driven Ansible)"
    lines += [title, _underline(title, "+"), ""]

    lines += [
        "The plugins on this page are event sources for Event-Driven Ansible:",
        "each one polls a Tencent Cloud service and puts what it finds on the",
        "rulebook event queue, so a rule condition can match on it.",
        "",
        ".. note::",
        "    ``event_source`` is not a plugin type ansible-core resolves, so",
        "    ``ansible-doc`` cannot show these plugins and no sanity test",
        "    renders their documentation. antsibull-docs does not know the",
        "    type either, which is why this page is written by",
        "    ``scripts/generate_event_source_docs.py`` instead of generated",
        "    with the rest of the docsite. Its content comes from the plugins'",
        "    own ``DOCUMENTATION`` and ``EXAMPLES`` blocks, and CI fails if the",
        "    two ever disagree.",
        "",
        ".. contents::",
        "   :local:",
        "   :depth: 1",
        "",
    ]

    for plugin in plugins:
        doc = plugin["doc"]
        name = plugin["name"]
        short = _as_text(doc.get("short_description") or "")
        # The short descriptions already end with "(event source)"; the
        # heading adds it too, so strip the duplicate rather than printing
        # "cls_topic event source -- Poll a ... (event source)".
        short = re.sub(r"\s*\(event source\)\s*$", "", short)
        heading = f"{COLLECTION}.{name} event source -- {short}"
        lines += [
            f".. _ansible_collections.{COLLECTION}.{name}_event_source:",
            "",
            heading,
            _underline(heading, "-"),
            "",
            ".. rst-class:: ansible-version-added",
            "",
            f"New in {COLLECTION} {doc.get('version_added', '1.0.0')}",
            "",
        ]

        lines += ["Synopsis", _underline("Synopsis", "^"), ""]
        for item in doc.get("description") or []:
            lines += [f"- {_as_text(item)}", ""]

        rows = _option_rows(doc.get("options"))
        if rows:
            lines += ["Parameters", _underline("Parameters", "^"), ""]
            lines += [
                ".. list-table::",
                "   :widths: 20 12 68",
                "   :header-rows: 1",
                "",
                "   * - Parameter",
                "     - Type",
                "     - Description",
            ]
            for option_name, option_type, description in rows:
                lines += [
                    f"   * - ``{option_name}``",
                    f"     - ``{option_type}``" if option_type else "     -",
                    f"     - {description}",
                ]
            lines += [""]

        if plugin["payload"]:
            lines += ["Event payload", _underline("Event payload", "^"), ""]
            lines += [
                "Rules match on these fields of the event the source puts on the",
                "queue:",
                "",
            ]
            for field in plugin["payload"]:
                lines += [f"- ``{field}``"]
            lines += [""]

        if plugin["examples"]:
            lines += ["Example", _underline("Example", "^"), ""]
            lines += [".. code-block:: yaml", ""]
            for example_line in plugin["examples"].splitlines():
                lines.append(f"   {example_line}" if example_line.strip() else "")
            lines += [""]

    return "\n".join(lines).rstrip() + "\n"


def collect_plugins():
    """Return the plugin data for every event source file, sorted by name."""
    if not EVENT_SOURCE_DIR.is_dir():
        return []
    plugins = []
    for path in sorted(EVENT_SOURCE_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        plugin = load_plugin(path)
        if plugin:
            plugins.append(plugin)
    return plugins


def wiring_problems(page_text: str, plugins) -> list:
    """Check the chain from generated page to a page the docsite builds."""
    problems = []

    if not BUILD_SH.is_file():
        problems.append(f"docsite build script is missing: {BUILD_SH}")
    else:
        build_sh = BUILD_SH.read_text()
        if "extra_rst" not in build_sh:
            problems.append(
                f"{BUILD_SH} does not mention extra_rst, so the generated page "
                f"is never copied into the Sphinx source directory"
            )

    if not INDEX_RST.is_file():
        problems.append(f"docsite index is missing: {INDEX_RST}")
    else:
        index_rst = INDEX_RST.read_text()
        if not re.search(rf"^\s+{PAGE_NAME}\s*$", index_rst, re.M):
            problems.append(
                f"{INDEX_RST} has no toctree entry for {PAGE_NAME}, so the page "
                f"is generated but never built"
            )

    on_disk = {plugin["name"] for plugin in plugins}
    on_page = set(ANCHOR_RE.findall(page_text))
    for name in sorted(on_disk - on_page):
        problems.append(f"event source {name} has no section on the docsite page")
    for name in sorted(on_page - on_disk):
        problems.append(
            f"docsite page documents event source {name}, which is not in "
            f"{EVENT_SOURCE_DIR}"
        )

    for plugin in plugins:
        if not plugin["payload"]:
            problems.append(
                f"event source {plugin['name']} declares no "
                f"I(event.<key>.<field>) payload fields, so a rule author "
                f"cannot tell what to match on"
            )
        if not plugin["examples"]:
            problems.append(f"event source {plugin['name']} has no EXAMPLES block")

    return problems


def audit() -> list:
    """Return every problem with the docsite page and its wiring."""
    plugins = collect_plugins()
    if not plugins:
        return [f"no event source plugins found under {EVENT_SOURCE_DIR}"]

    if not PAGE_PATH.is_file():
        return [f"docsite page is missing: {PAGE_PATH} (run this script to create it)"]

    page_text = PAGE_PATH.read_text()
    problems = wiring_problems(page_text, plugins)

    expected = render(plugins)
    if page_text != expected:
        problems.append(
            f"{PAGE_PATH} is out of date; run "
            f"python scripts/generate_event_source_docs.py"
        )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="report and exit non-zero instead of rewriting the page",
    )
    args = parser.parse_args()

    if args.check:
        problems = audit()
        plugins = collect_plugins()
        for plugin in plugins:
            print(
                f"  {plugin['name']}: {len(plugin['doc'].get('options') or {})} "
                f"options, {len(plugin['payload'])} payload fields"
            )
        if problems:
            print(f"event source docsite page: {len(problems)} problem(s)")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        print(
            f"event source docsite page: ok "
            f"({len(plugins)} plugins on one page)"
        )
        return 0

    plugins = collect_plugins()
    if not plugins:
        print(f"no event source plugins found under {EVENT_SOURCE_DIR}", file=sys.stderr)
        return 1
    EXTRA_RST.mkdir(parents=True, exist_ok=True)
    output = render(plugins)
    PAGE_PATH.write_text(output)
    print(f"wrote {PAGE_PATH} ({len(plugins)} event source plugins)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
