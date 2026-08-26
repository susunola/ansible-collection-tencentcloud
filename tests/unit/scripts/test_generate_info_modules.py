from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_info_modules.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_info_modules", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator():
    return _load_generator()


def _doc_blocks(rendered):
    blocks = {}
    for name in ("DOCUMENTATION", "EXAMPLES", "RETURN"):
        marker = "%s = r'''" % name
        start = rendered.index(marker) + len(marker)
        end = rendered.index("'''", start)
        blocks[name] = rendered[start:end]
    return blocks


def test_generator_path_exists():
    assert GENERATOR_PATH.exists()


def test_every_spec_renders_valid_documentation_yaml(generator):
    for spec in generator.SPECS:
        rendered = generator.render_module(spec)
        blocks = _doc_blocks(rendered)
        doc = yaml.safe_load(blocks["DOCUMENTATION"])
        assert doc["module"] == spec["module"]
        assert doc["version_added"] == "0.4.0"
        assert doc["extends_documentation_fragment"] == "tencentcloud.cloud.tencentcloud"

        expected_options = {param["name"] for param in spec["extra_params"]}
        if spec["ids"]:
            expected_options.add(spec["ids"]["param"])
        if spec["filters"]:
            expected_options.add("filters")
        expected_options.add("page_size")
        assert set(doc["options"]) == expected_options

        assert yaml.safe_load(blocks["EXAMPLES"])
        returned = yaml.safe_load(blocks["RETURN"])
        assert set(returned) == {spec["result_key"], "total_count"}


def test_generated_files_are_up_to_date(generator):
    for spec in generator.SPECS:
        path = generator.module_path(spec)
        assert path.exists(), "run scripts/generate_info_modules.py"
        content = path.read_text()
        assert content.startswith("#!/usr/bin/python")
        assert generator.MARKER in content
        assert content == generator.render_module(spec)
