from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_notebook_session import (
    create_request, delete_request, describe_request, desired, immutable_drift, list_request, normalize,
)


class Object:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items(): setattr(self, key, item)


class Models:
    CreateNotebookSessionRequest = DeleteNotebookSessionRequest = DescribeNotebookSessionRequest = DescribeNotebookSessionsRequest = Filter = Object


def params():
    return {"name": "analyst", "kind": "pyspark", "data_engine_name": "spark-prod", "dependent_files": ["cosn://b/z", "cosn://b/a"],
            "dependent_jars": None, "dependent_python": None, "archives": None, "driver_size": "medium", "executor_size": "large",
            "executor_numbers": 2, "executor_max_numbers": 8, "arguments": [{"key": "z", "value": "2"}, {"key": "a", "value": "1"}],
            "proxy_user": "root", "timeout": 7200}


def test_identity_requests_are_exact_and_paginated():
    assert describe_request(Models, "session-1").SessionId == "session-1"
    request = list_request(Models, params(), 100)
    assert request.DataEngineName == "spark-prod" and request.Offset == 100 and request.Limit == 100
    assert request.Filters[0].Name == "notebook-keyword" and request.Filters[0].Values == ["analyst"]
    assert delete_request(Models, "session-1").SessionId == "session-1"


def test_create_maps_and_normalizes_immutable_contract():
    request = create_request(Models, params())
    assert request.Name == "analyst" and request.Kind == "pyspark" and request.DataEngineName == "spark-prod"
    assert request.ProgramDependentFiles == ["cosn://b/a", "cosn://b/z"]
    assert [x["Key"] for x in request.Arguments] == ["a", "z"]


def test_normalize_and_drift_ignore_list_order():
    p = params(); current = desired(p); current.update({"SessionId": "session-1", "State": "idle"})
    current["ProgramDependentFiles"].reverse(); current["Arguments"].reverse()
    normalized = normalize(current)
    assert immutable_drift(p, normalized) == {}
    p["driver_size"] = "xlarge"
    assert immutable_drift(p, normalized)["DriverSize"] == ("medium", "xlarge")
