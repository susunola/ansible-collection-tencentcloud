from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "generate_product_capabilities.py"


def load_script():
    spec = importlib.util.spec_from_file_location("generate_product_capabilities", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_groups_modules_by_sdk_service(tmp_path):
    script = load_script()
    modules = tmp_path / "plugins" / "modules"
    roles = tmp_path / "roles"
    modules.mkdir(parents=True)
    roles.mkdir()
    (modules / "api_gateway_api.py").write_text(
        "from tencentcloud.apigateway.v20180808 import models\n", encoding="utf-8")
    (modules / "api_gateway_service_info.py").write_text(
        "from tencentcloud.apigateway.v20180808 import models\n", encoding="utf-8")
    (modules / "cos_bucket.py").write_text("import qcloud_cos\n", encoding="utf-8")
    role = roles / "tc_api_gateway"
    role.mkdir()
    (role / "README.md").write_text("API gateway solution\n", encoding="utf-8")

    result = script.inventory(modules, roles)

    assert result["apigateway"]["write"] == ["api_gateway_api"]
    assert result["apigateway"]["info"] == ["api_gateway_service_info"]
    assert result["apigateway"]["roles"] == ["tc_api_gateway"]
    assert result["cos"]["write"] == ["cos_bucket"]


def test_maturity_levels():
    script = load_script()
    assert script.maturity({"write": [], "info": ["a_info"], "roles": []}) == "discovery-only"
    assert script.maturity({"write": ["a"], "info": [], "roles": []}) == "managed"
    assert script.maturity({"write": ["a", "b", "c"], "info": ["a_info"], "roles": []}) == "resource-family"
    assert script.maturity({"write": ["a"], "info": ["a_info"], "roles": ["tc_a"]}) == "solution"


def test_render_is_deterministic_and_has_summary():
    script = load_script()
    products = {
        "vpc": {"write": ["vpc"], "info": ["vpc_info"], "roles": []},
        "cvm": {"write": ["cvm_instance"], "info": [], "roles": ["tc_launch"]},
    }
    rendered = script.render(products)
    assert "Products/services: **2**" in rendered
    assert rendered.index("`cvm`") < rendered.index("`vpc`")
    assert "| `vpc` | managed | 1 | 1 |" in rendered
