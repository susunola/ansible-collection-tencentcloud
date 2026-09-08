from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "sync_doc_fragments.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("sync_doc_fragments", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_extends_is_rewritten_to_base_fragments(tmp_path):
    script = _load_script()
    path = tmp_path / "sample.py"
    path.write_text("DOCUMENTATION = r'''\noptions:\nextends_documentation_fragment: susunola.tencentcloud.tencentcloud\n'''\n")
    changed, stripped = script.migrate_file(str(path))
    assert changed
    assert stripped == []
    text = path.read_text()
    assert "susunola.tencentcloud.tencentcloud" not in text
    assert "susunola.tencentcloud.credentials" in text
    assert "susunola.tencentcloud.region" in text
    assert "susunola.tencentcloud.connection" in text


def test_bare_options_block_is_collapsed_to_empty_mapping(tmp_path):
    # Regression: stripping the last inline option left a bare "options:"
    # whose YAML value is null; validate-modules then fails to merge
    # fragment options over it.  The canonical form is "options: {}".
    script = _load_script()
    path = tmp_path / "bare.py"
    path.write_text(
        "DOCUMENTATION = r'''\n"
        "options:\n"
        "  retries: {type: int, default: 5, description: Transient API retry count.}\n"
        "  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}\n"
        "extends_documentation_fragment: susunola.tencentcloud.tencentcloud\n"
        "'''\n"
    )
    changed, stripped = script.migrate_file(str(path))
    assert changed
    assert stripped == ["retries", "user_agent"]
    text = path.read_text()
    assert "options: {}" in text
    assert "\noptions:\n" not in "\n" + text
    # the runtime options now come from fragments, referenced not inlined
    assert "susunola.tencentcloud.retry" in text
    assert "susunola.tencentcloud.user_agent" in text
    assert script._empty_options_block(text) is False


def test_waiter_is_all_or_nothing(tmp_path):
    # A module documenting only one of the two waiter options must not be
    # pointed at the waiter fragment (it would gain an undocumented option);
    # both options stay inline instead.
    script = _load_script()
    text = (
        "DOCUMENTATION = r'''\n"
        "options:\n"
        "  waiter_timeout:\n"
        "    description: Overall convergence timeout.\n"
        "    type: int\n"
        "    default: 120\n"
        "extends_documentation_fragment: susunola.tencentcloud.tencentcloud\n"
        "'''\n"
    )
    fragments, stripped = script.fragments_and_stripped(text)
    assert "waiter" not in fragments
    assert stripped == []
    # with both waiter options generic the fragment is used and both strip
    text_both = text.replace(
        "extends_documentation_fragment: susunola.tencentcloud.tencentcloud",
        "  waiter_delay:\n"
        "    description: Seconds to wait between state-polling attempts.\n"
        "    type: int\n"
        "    default: 5\n"
        "extends_documentation_fragment: susunola.tencentcloud.tencentcloud",
    )
    fragments, stripped = script.fragments_and_stripped(text_both)
    assert "waiter" in fragments
    assert stripped == ["waiter_delay", "waiter_timeout"]


def test_product_specific_option_stays_inline(tmp_path):
    # A custom description (or a non-fragment default) is a deliberate
    # per-module override.  Because the waiter fragment is all-or-nothing,
    # neither waiter option is stripped when one of them deviates.
    script = _load_script()
    path = tmp_path / "custom.py"
    path.write_text(
        "DOCUMENTATION = r'''\n"
        "options:\n"
        "  waiter_timeout:\n"
        "    description: Longer convergence window for cross-AZ failover.\n"
        "    type: int\n"
        "    default: 900\n"
        "  waiter_delay:\n"
        "    description: Seconds to wait between state-polling attempts.\n"
        "    type: int\n"
        "    default: 5\n"
        "extends_documentation_fragment: susunola.tencentcloud.tencentcloud\n"
        "'''\n"
    )
    changed, stripped = script.migrate_file(str(path))
    assert changed
    assert stripped == []
    text = path.read_text()
    assert "Longer convergence window for cross-AZ failover." in text
    assert "Seconds to wait between state-polling attempts." in text
    assert "susunola.tencentcloud.waiter" not in text
    assert "susunola.tencentcloud.credentials" in text
