"""Unit tests for scripts/check_sdk_floor.py (the declared-floor guard)."""

from __future__ import absolute_import, division, print_function

import importlib.util
import io
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_sdk_floor.py"

#: A real product of the installed SDK, used as the "resolves" control.
GOOD_MODULE = """\
from tencentcloud.cvm.v20170312 import models, cvm_client


def run(models_module=cvm_client):
    return cvm_client.CvmClient, models.DescribeInstancesRequest
"""

SPEC = """\
GENERATED_SDK_VERSION = '3.1.180'

SPECS_AUTO = [
    {
        'module': 'cvm_instance_info',
        'service_package': 'tencentcloud.cvm.v20170312',
        'client_module': 'cvm_client',
        'client_class': 'CvmClient',
        'request_class': 'DescribeInstancesRequest',
    },
]
"""


def _load_script():
    spec = importlib.util.spec_from_file_location("check_sdk_floor", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def floor():
    return _load_script()


@pytest.fixture(autouse=True)
def _sdk_installed(floor):
    """Skip when the SDK is absent: every check imports real packages."""
    try:
        floor.installed_version()
    except RuntimeError:
        pytest.skip("tencentcloud-sdk-python is not installed")


def _tree(root, modules=None, specs=SPEC, requirements="tencentcloud-sdk-python>=3.1.100,<4.0.0\n"):
    """Build a throwaway collection tree and return its root."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(exist_ok=True)
    (root / "plugins" / "modules").mkdir(parents=True, exist_ok=True)
    for name, source in (modules or {}).items():
        (root / "plugins" / "modules" / name).write_text(source, encoding="utf-8")
    if specs is not None:
        (root / "scripts" / "info_specs_auto.py").write_text(specs, encoding="utf-8")
    if requirements is not None:
        (root / "requirements.txt").write_text(requirements, encoding="utf-8")
    return root


def test_resolvable_references_produce_no_finding(floor, tmp_path):
    root = _tree(tmp_path / "ok", {"cvm_instance.py": GOOD_MODULE})
    assert floor.module_findings(root) == []
    assert floor.spec_findings(root) == []


def test_missing_product_package_is_reported(floor, tmp_path):
    source = "from tencentcloud.nosuchproduct.v20990101 import models\n"
    root = _tree(tmp_path / "bad", {"ghost.py": source})
    findings = floor.module_findings(root)
    assert len(findings) == 1
    assert "plugins/modules/ghost.py" in findings[0]
    assert "tencentcloud.nosuchproduct.v20990101" in findings[0]


def test_missing_client_module_is_reported(floor, tmp_path):
    source = "from tencentcloud.cvm.v20170312 import nosuch_client\n"
    root = _tree(tmp_path / "badclient", {"ghost.py": source})
    findings = floor.module_findings(root)
    assert len(findings) == 1
    assert "nosuch_client" in findings[0]


def test_renamed_client_class_is_reported(floor, tmp_path):
    source = "from tencentcloud.cvm.v20170312 import models, cvm_client\n" \
             "CLIENT = cvm_client.CvmNewClient\n"
    root = _tree(tmp_path / "renamed", {"ghost.py": source})
    findings = floor.module_findings(root)
    assert len(findings) == 1
    assert "CvmNewClient" in findings[0]


def test_model_class_ending_in_client_is_not_a_client(floor, tmp_path):
    """``models.FileClient`` is a model that merely ends in ``Client``."""
    source = "from tencentcloud.tse.v20201207 import models, tse_client\n" \
             "VALUE = models.ConfigFileSupportedClient\n" \
             "CLIENT = tse_client.TseClient\n"
    root = _tree(tmp_path / "model", {"config.py": source})
    assert floor.module_findings(root) == []


def test_client_named_only_by_a_string_is_not_a_class(floor, tmp_path):
    """An option value such as ``supported_client`` is data, not an SDK class."""
    source = "from tencentcloud.tse.v20201207 import models, tse_client\n" \
             "CHOICES = ['ConfigFileSupportedClient']\n" \
             "CLIENT = tse_client.TseClient\n"
    root = _tree(tmp_path / "stringonly", {"config.py": source})
    assert floor.module_findings(root) == []


def test_service_string_table_is_resolved(floor, tmp_path):
    """RESOURCE_SPECS-style tables name the SDK without importing it."""
    source = 'SPECS = {"vpc": ("vpc.v20170312", "VpcClient")}\n'
    root = _tree(tmp_path / "table", {"resource_id.py": source})
    assert floor.module_findings(root) == []


def test_service_string_table_with_renamed_class_is_reported(floor, tmp_path):
    source = 'SPECS = {"vpc": ("vpc.v20170312", "VpcLegacyClient")}\n'
    root = _tree(tmp_path / "tablebad", {"resource_id.py": source})
    findings = floor.module_findings(root)
    assert len(findings) == 1
    assert "VpcLegacyClient" in findings[0]


def test_spec_with_missing_request_class_is_reported(floor, tmp_path):
    specs = SPEC.replace("DescribeInstancesRequest", "DescribeNonsenseRequest")
    root = _tree(tmp_path / "specbad", {"cvm_instance.py": GOOD_MODULE}, specs=specs)
    findings = floor.spec_findings(root)
    assert len(findings) == 1
    assert "DescribeNonsenseRequest" in findings[0]
    assert "models" in findings[0]


def test_spec_with_missing_client_class_is_reported(floor, tmp_path):
    specs = SPEC.replace("'CvmClient'", "'CvmClientV9'")
    root = _tree(tmp_path / "speccls", {"cvm_instance.py": GOOD_MODULE}, specs=specs)
    findings = floor.spec_findings(root)
    assert len(findings) == 1
    assert "CvmClientV9" in findings[0]


def test_spec_with_unknown_product_is_reported(floor, tmp_path):
    specs = SPEC.replace("tencentcloud.cvm.v20170312",
                         "tencentcloud.nosuchproduct.v20990101")
    root = _tree(tmp_path / "specprod", {"cvm_instance.py": GOOD_MODULE}, specs=specs)
    findings = floor.spec_findings(root)
    assert len(findings) == 1
    assert "nosuchproduct" in findings[0]


def test_empty_specs_are_rejected(floor, tmp_path):
    root = _tree(tmp_path / "emptyspecs", {"cvm_instance.py": GOOD_MODULE},
                 specs="SPECS_AUTO = []\n")
    assert floor.spec_findings(root) == [
        "scripts/info_specs_auto.py must define a non-empty SPECS_AUTO"]


def test_missing_specs_file_is_reported(floor, tmp_path):
    root = _tree(tmp_path / "nospecs", {"cvm_instance.py": GOOD_MODULE}, specs=None)
    assert floor.spec_findings(root) == ["scripts/info_specs_auto.py is missing"]


def test_declared_range_is_read_from_requirements(floor, tmp_path):
    root = _tree(tmp_path / "req", {"cvm_instance.py": GOOD_MODULE},
                 requirements="tencentcloud-sdk-python>=3.1.180,<4.0.0\n")
    assert floor.declared_range(root / "requirements.txt") == ("3.1.180", "4.0.0")


def test_unparsable_requirement_reports_no_floor(floor, tmp_path):
    root = _tree(tmp_path / "reqbad", {"cvm_instance.py": GOOD_MODULE},
                 requirements="tencentcloud-sdk-python\n")
    assert floor.declared_range(root / "requirements.txt") == (None, None)


def test_missing_requirement_file_reports_no_floor(floor, tmp_path):
    assert floor.declared_range(tmp_path / "absent.txt") == (None, None)


def test_floor_that_is_not_installed_is_reported(floor, monkeypatch, tmp_path):
    root = _tree(tmp_path / "floormismatch", {"cvm_instance.py": GOOD_MODULE})
    monkeypatch.setattr(floor, "installed_version", lambda: "3.1.999")
    findings, _notes = floor.collect_findings(root=root)
    assert any("advertised, not verified" in finding for finding in findings)


def test_installed_floor_is_not_reported(floor, monkeypatch, tmp_path):
    root = _tree(tmp_path / "floorok", {"cvm_instance.py": GOOD_MODULE})
    monkeypatch.setattr(floor, "installed_version", lambda: "3.1.100")
    findings, notes = floor.collect_findings(root=root)
    assert findings == []
    assert any("3.1.100" in note for note in notes)


def test_check_exits_non_zero_on_a_finding(floor, monkeypatch, tmp_path):
    source = "from tencentcloud.nosuchproduct.v20990101 import models\n"
    root = _tree(tmp_path / "checkbad", {"ghost.py": source})
    monkeypatch.setattr(floor, "installed_version", lambda: "3.1.100")
    out, err = io.StringIO(), io.StringIO()
    rc = floor.main(["--check", "--root", str(root)], out=out, err=err)
    assert rc == 1
    assert "findings (1)" in out.getvalue()
    assert "must resolve at the declared floor" in err.getvalue()


def test_check_passes_on_a_clean_tree(floor, monkeypatch, tmp_path):
    root = _tree(tmp_path / "checkok", {"cvm_instance.py": GOOD_MODULE})
    monkeypatch.setattr(floor, "installed_version", lambda: "3.1.100")
    out, err = io.StringIO(), io.StringIO()
    rc = floor.main(["--check", "--root", str(root)], out=out, err=err)
    assert rc == 0
    assert "SDK floor check OK" in out.getvalue()
    assert err.getvalue() == ""


def test_committed_tree_is_clean_at_the_declared_floor(floor):
    """The repository must pass its own gate.

    The check is only meaningful when the installed SDK *is* the declared
    floor (that is what CI installs); a developer running a newer release
    locally gets the mismatch finding instead, which this test does not
    assert on.
    """
    floor_version, _cap = floor.declared_range()
    if floor.installed_version() != floor_version:
        pytest.skip("installed SDK is not the declared floor")
    findings, _notes = floor.collect_findings()
    assert findings == []
