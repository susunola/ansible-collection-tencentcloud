"""Unit tests for scripts/check_extensions_metadata.py.

The guard keeps ``meta/extensions.yml`` honest in both directions: every
declaration must point at a populated plugin directory, and every non-core
plugin directory on disk must be declared. Both directions are exercised
here against throwaway trees so the failures do not depend on the shape of
the real collection, plus one test that pins the real manifest.
"""

from __future__ import absolute_import, division, print_function

import importlib.util
import io
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_extensions_metadata.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "check_extensions_metadata", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return _load_script()


def _write_manifest(root, text):
    meta = root / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    path = meta / "extensions.yml"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def _add_plugin(root, *parts):
    """Create plugins/<parts...>/<last>_demo.py and return the directory."""
    directory = root.joinpath("plugins", *parts)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "demo.py").write_text("# plugin\n", encoding="utf-8")
    return directory


def _manifest(*ext_dirs):
    lines = ["extensions:"]
    for ext_dir in ext_dirs:
        lines.append("  - args:")
        lines.append("      ext_dir: %s" % ext_dir)
    return "\n".join(lines) + "\n"


def test_repo_manifest_is_valid(guard):
    data, error = guard._load()
    assert error is None
    assert guard.validate(data) == []


def test_repo_manifest_declares_the_event_source_extension(guard):
    data, error = guard._load()
    assert error is None
    assert [d for d, _p in guard._iter_declarations(data) if d] == [
        "plugins/event_source"]


def test_missing_file_is_reported(guard, tmp_path):
    data, error = guard._load(tmp_path / "meta" / "extensions.yml")
    assert data is None
    assert error == "meta/extensions.yml is missing"


def test_invalid_yaml_is_reported(guard, tmp_path):
    path = _write_manifest(tmp_path, "extensions: [unclosed\n")
    data, error = guard._load(path)
    assert data is None
    assert "not valid YAML" in error


def test_empty_file_is_reported(guard, tmp_path):
    path = _write_manifest(tmp_path, "# only a comment\n")
    data, error = guard._load(path)
    assert data is None
    assert error == "meta/extensions.yml is empty"


def test_non_mapping_top_level_is_reported(guard, tmp_path):
    path = _write_manifest(tmp_path, "- args:\n    ext_dir: plugins/x\n")
    data, error = guard._load(path)
    assert data is None
    assert "must be a mapping at the top level" in error


def test_missing_extensions_key_is_reported(guard, tmp_path):
    path = _write_manifest(tmp_path, "something_else: 1\n")
    data, error = guard._load(path)
    assert data is None
    assert "no 'extensions' key" in error


def test_extensions_must_be_a_list(guard, tmp_path):
    path = _write_manifest(tmp_path, "extensions: plugins/event_source\n")
    data, error = guard._load(path)
    assert data is None
    assert "'extensions' must be a list" in error


def test_entry_without_args_is_reported(guard, tmp_path):
    data = {"extensions": [{"ext_dir": "plugins/x"}]}
    assert guard.validate(data, root=tmp_path) == [
        "extensions[0] must carry an 'args' mapping"]


def test_entry_without_ext_dir_is_reported(guard, tmp_path):
    data = {"extensions": [{"args": {}}]}
    assert guard.validate(data, root=tmp_path) == [
        "extensions[0].args.ext_dir must be a non-empty string"]


def test_non_mapping_entry_is_reported(guard, tmp_path):
    data = {"extensions": ["plugins/event_source"]}
    assert guard.validate(data, root=tmp_path) == [
        "extensions[0] must be a mapping"]


def test_declaration_pointing_at_a_missing_directory(guard, tmp_path):
    data = {"extensions": [{"args": {"ext_dir": "plugins/gone"}}]}
    assert guard.validate(data, root=tmp_path) == [
        "declares 'plugins/gone' but that directory does not exist"]


def test_declaration_pointing_at_an_empty_directory(guard, tmp_path):
    (tmp_path / "plugins" / "event_source").mkdir(parents=True)
    data = {"extensions": [{"args": {"ext_dir": "plugins/event_source"}}]}
    assert guard.validate(data, root=tmp_path) == [
        "declares 'plugins/event_source' but it holds no Python plugin files"]


def test_core_plugin_dir_must_not_be_declared(guard, tmp_path):
    _add_plugin(tmp_path, "lookup")
    data = {"extensions": [{"args": {"ext_dir": "plugins/lookup"}}]}
    problems = guard.validate(data, root=tmp_path)
    assert problems == [
        "declares 'plugins/lookup', which ansible-core already resolves "
        "natively -- extensions are only for plugin types it cannot load"]


def test_shared_library_dir_must_not_be_declared(guard, tmp_path):
    _add_plugin(tmp_path, "plugin_utils")
    data = {"extensions": [{"args": {"ext_dir": "plugins/plugin_utils"}}]}
    assert guard.validate(data, root=tmp_path) == [
        "declares 'plugins/plugin_utils', which is a shared-library "
        "directory, not an extension"]


def test_path_escaping_the_collection_is_rejected(guard, tmp_path):
    data = {"extensions": [{"args": {"ext_dir": "../outside"}}]}
    assert guard.validate(data, root=tmp_path) == [
        "declares '../outside', which is not a collection-relative directory"]


def test_undeclared_non_core_directory_is_reported(guard, tmp_path):
    _add_plugin(tmp_path, "event_source")
    _add_plugin(tmp_path, "eda_rulebook")
    data = {"extensions": [{"args": {"ext_dir": "plugins/event_source"}}]}
    assert guard.validate(data, root=tmp_path) == [
        "plugins/eda_rulebook is not an ansible-core plugin type and is not "
        "declared in meta/extensions.yml"]


def test_core_and_shared_dirs_are_never_undeclared(guard, tmp_path):
    for name in ("lookup", "modules", "module_utils", "plugin_utils",
                 "doc_fragments"):
        _add_plugin(tmp_path, name)
    data = {"extensions": []}
    assert guard.validate(data, root=tmp_path) == []


def test_undeclared_check_ignores_files_and_dunder_dirs(guard, tmp_path):
    plugins = tmp_path / "plugins"
    plugins.mkdir(parents=True)
    (plugins / "README.md").write_text("not a directory\n", encoding="utf-8")
    _add_plugin(tmp_path, "__pycache__")
    assert guard.validate({"extensions": []}, root=tmp_path) == []


def test_check_exits_zero_when_consistent(guard, monkeypatch, tmp_path):
    _add_plugin(tmp_path, "event_source")
    data = {"extensions": [{"args": {"ext_dir": "plugins/event_source"}}]}
    monkeypatch.setattr(guard, "_load", lambda: (data, None))
    monkeypatch.setattr(guard, "validate", lambda d: [])
    out, err = io.StringIO(), io.StringIO()
    assert guard.main(["--check"], out=out, err=err) == 0
    assert "declared extensions (1): plugins/event_source" in out.getvalue()
    assert "extensions metadata matches plugins/" in out.getvalue()


def test_check_exits_one_on_problems(guard, monkeypatch):
    monkeypatch.setattr(guard, "_load", lambda: ({"extensions": []}, None))
    monkeypatch.setattr(guard, "validate", lambda d: ["boom"])
    out, err = io.StringIO(), io.StringIO()
    assert guard.main(["--check"], out=out, err=err) == 1
    assert "problems (1):" in out.getvalue()
    assert "boom" in out.getvalue()
    assert "fix meta/extensions.yml" in err.getvalue()


def test_report_mode_does_not_fail_on_problems(guard, monkeypatch):
    monkeypatch.setattr(guard, "_load", lambda: ({"extensions": []}, None))
    monkeypatch.setattr(guard, "validate", lambda d: ["boom"])
    out, err = io.StringIO(), io.StringIO()
    assert guard.main([], out=out, err=err) == 0
    assert err.getvalue() == ""


def test_check_exits_one_when_the_manifest_cannot_load(guard, monkeypatch):
    monkeypatch.setattr(
        guard, "_load", lambda: (None, "meta/extensions.yml is missing"))
    out, err = io.StringIO(), io.StringIO()
    assert guard.main(["--check"], out=out, err=err) == 1
    assert "meta/extensions.yml is missing" in out.getvalue()


def test_report_mode_does_not_fail_when_the_manifest_cannot_load(
        guard, monkeypatch):
    monkeypatch.setattr(
        guard, "_load", lambda: (None, "meta/extensions.yml is missing"))
    out, err = io.StringIO(), io.StringIO()
    assert guard.main([], out=out, err=err) == 0
