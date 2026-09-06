from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_resource_config import (
    delete_request,
    drift,
    list_request,
    make_request,
    node,
    normalize,
    scale_down,
    workers,
)


class Object:
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class Models:
    ListResourceConfigsRequest = Object
    ListRayClustersRequest = Object
    CreateResourceConfigRequest = Object
    UpdateResourceConfigRequest = Object
    DeleteResourceConfigRequest = Object


def params():
    return {
        "name": "ray-small",
        "template_type": "Ray",
        "description": "shared",
        "head": {"name": "head", "pod_cpu": 4, "pod_mem": 16, "pod_num": 1, "envs": [{"name": "B", "value": "2"}, {"name": "A", "value": "1"}]},
        "workers": [
            {"name": "worker-b", "pod_cpu": 4, "min_pod_num": 1, "max_pod_num": 8},
            {"name": "worker-a", "pod_cpu": 2, "min_pod_num": 1, "max_pod_num": 4},
        ],
    }


def test_list_request_is_paginated_for_both_resource_types():
    assert list_request(Models, 2).Page == 2 and list_request(Models, 3, ray=True).Page == 3


def test_node_and_worker_normalization_is_order_insensitive():
    assert [x["Name"] for x in node(params()["head"])["Envs"]] == ["A", "B"]
    assert [x["Name"] for x in workers(params()["workers"])] == ["worker-a", "worker-b"]


def test_create_and_update_map_stable_contract():
    assert make_request(Models, params()).Head["PodCpu"] == 4
    assert make_request(Models, params(), update=True, config_id="rc-1").Id == "rc-1"


def test_normalized_readback_is_idempotent():
    current = normalize({"Description": "shared", "Type": "Ray", "Head": node(params()["head"]), "Worker": workers(params()["workers"])})
    assert drift(params(), current) == {}


def test_scale_down_detects_reduced_or_removed_workers():
    old = workers(params()["workers"])
    lower = workers([params()["workers"][0]])
    assert scale_down(node(params()["head"]), node(params()["head"]), old, lower) is True
    assert scale_down({"PodCpu": 4}, {"PodCpu": 2}, [], []) is True


def test_delete_uses_stable_template_id():
    assert delete_request(Models, "rc-1").Id == "rc-1"
