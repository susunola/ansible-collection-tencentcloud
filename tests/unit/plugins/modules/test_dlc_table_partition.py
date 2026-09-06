from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_table_partition import (
    add_request,
    alter_request,
    drop_request,
    drift,
    kv,
    list_request,
    normalize,
    storage,
)


class Model:
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class Models:
    AddDMSPartitionsRequest = AlterDMSPartitionRequest = DropDMSPartitionsRequest = DescribeDMSPartitionsRequest = DMSPartition = Model


def params():
    return {
        "database_name": "analytics",
        "table_name": "sales",
        "values": ["2026-08-31"],
        "schema_name": None,
        "name": "date=2026-08-31",
        "datasource_connection_name": "DataLakeCatalog",
        "params": {"b": "2", "a": "1"},
        "storage": {"location": "cosn://bucket/date=2026-08-31", "serde_params": {"z": "9", "a": "1"}},
        "delete_data": False,
    }


def test_normalization_and_drift_are_semantic():
    p = params()
    current = normalize(
        {
            "DatabaseName": "analytics",
            "TableName": "sales",
            "Values": ["2026-08-31"],
            "Name": p["name"],
            "DatasourceConnectionName": "DataLakeCatalog",
            "Params": [{"Key": "a", "Value": "1"}, {"Key": "b", "Value": "2"}],
            "Sds": {"Location": p["storage"]["location"], "SerdeParams": [{"Key": "a", "Value": "1"}, {"Key": "z", "Value": "9"}]},
        }
    )
    assert kv(p["params"])[0]["Key"] == "a" and storage(p["storage"])["SerdeParams"][0]["Key"] == "a"
    assert drift(p, current) == {}


def test_requests_preserve_exact_identity_and_delete_data_choice():
    p = params()
    add = add_request(Models, p)
    alter = alter_request(Models, p, {"Name": p["name"]})
    drop = drop_request(Models, p)
    listing = list_request(Models, p, 100)
    assert add.Partitions[0].Values == p["values"]
    assert alter.CurrentValues == p["name"] and alter.Partition.Values == p["values"]
    assert drop.Values == p["values"] and drop.DeleteData is False
    assert listing.Values == p["values"] and listing.Offset == 100
