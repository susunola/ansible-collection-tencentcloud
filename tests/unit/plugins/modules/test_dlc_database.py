from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_database import (
    create_request,
    delete_request,
    describe_request,
    immutable_drift,
    table_count_request,
)


class Object:
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class Models:
    DescribeDatabaseRequest = Object
    DescribeTablesRequest = Object
    CreateMetaDatabaseRequest = Object
    DeleteMetaDatabaseRequest = Object
    MetaDatabaseInfo = Object
    DataGovernPolicy = Object
    SmartPolicy = Object


def params():
    return {
        "name": "analytics",
        "datasource_connection_name": "DataLakeCatalog",
        "comment": "curated",
        "govern_policy": {"RuleType": "STANDARD"},
        "smart_policy": None,
    }


def test_requests_keep_catalog_identity_consistent():
    p = params()
    assert describe_request(Models, p).DatasourceConnectionName == "DataLakeCatalog"
    assert delete_request(Models, p).DatabaseName == "analytics"
    count = table_count_request(Models, p)
    assert count.DatabaseName == "analytics" and count.Limit == 1


def test_create_maps_metadata_and_governance():
    request = create_request(Models, params())
    assert request.MetaDatabaseInfo.DatabaseName == "analytics"
    assert request.MetaDatabaseInfo.Comment == "curated"
    assert request.GovernPolicy.RuleType == "STANDARD"


def test_immutable_drift_is_normalized():
    assert immutable_drift(params(), {"Comment": "curated", "GovernPolicy": {"RuleType": "STANDARD", "Extra": None}}) == {}
    assert "Comment" in immutable_drift(params(), {"Comment": "old", "GovernPolicy": {"RuleType": "STANDARD"}})
