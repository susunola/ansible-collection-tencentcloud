from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_cluster_group import canonical, cluster_request, delete_request, drift, list_request, make_request, normalize


class Request:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items():
            setattr(self, key, item)


class Models:
    ListClusterGroupsRequest = Request
    CreateClusterGroupRequest = Request
    UpdateClusterGroupRequest = Request
    DeleteClusterGroupRequest = Request
    DescribeClusterGroupClustersRequest = Request


def test_json_normalization_and_drift_are_semantic():
    current = normalize({"Name": "compute", "Description": "old", "Config": '{"b":2,"a":1}'})
    params = {"name": "compute", "description": "new", "config": '{"a":1,"b":2}'}
    assert canonical(params["config"]) == '{"a":1,"b":2}'
    assert drift(params, current) == {"Description": ("old", "new")}


def test_requests_preserve_stable_identity_and_force_guard():
    create = make_request(Models, {"name": "compute", "description": None, "config": '{"z":1,"a":2}'})
    update = make_request(Models, {"name": "compute", "description": "managed", "config": None}, update=True, group_id="cg-1")
    delete = delete_request(Models, "cg-1", True)
    listing = list_request(Models, 3)
    clusters = cluster_request(Models, "cg-1")
    assert create.Config == '{"a":2,"z":1}'
    assert update.Id == "cg-1" and update.Description == "managed"
    assert delete.Id == "cg-1" and delete.Force is True
    assert listing.Page == 3 and listing.PageSize == 200
    assert clusters.Id == "cg-1" and clusters.SampleLimit == 20
