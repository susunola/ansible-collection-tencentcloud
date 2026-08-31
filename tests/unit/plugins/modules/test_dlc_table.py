import base64
from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_table import comment_drift, comment_request, delete_request, generate_request, has_data, immutable_drift, normalize, task_request, task_status_request


class Model:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items(): setattr(self, key, item)


class Models:
    CreateTableRequest = DeleteTableRequest = AlterTableCommentRequest = CreateTasksRequest = DescribeTaskDetailRequest = Model
    TableInfo = TableBaseInfo = TasksInfo = Model


def params():
    return {"name": "sales", "database_name": "analytics", "datasource_connection_name": "DataLakeCatalog", "comment": "daily", "table_type": "TABLE", "table_format": "ICEBERG", "data_format": "Parquet", "location": "cosn://bucket/sales", "primary_keys": ["id"], "columns": [{"name": "id", "type": "bigint", "nullable": False}], "partitions": [], "data_engine_name": "engine", "resource_group_name": None}


def test_generate_and_submit_requests_preserve_schema_and_encode_sql():
    p = params(); generated = generate_request(Models, p); submitted = task_request(Models, p, "CREATE TABLE sales")
    assert generated.TableInfo.TableBaseInfo["TableName"] == "sales"
    assert generated.TableInfo.DataFormat == {"Parquet": {}}
    assert base64.b64decode(submitted.Tasks.SQL).decode() == "CREATE TABLE sales"
    assert submitted.Tasks.TaskType == "SQLTask" and submitted.DataEngineName == "engine"


def test_normalization_drift_and_guards():
    p = params(); current = normalize({"TableBaseInfo": {"DatabaseName": "analytics", "TableName": "sales", "DatasourceConnectionName": "DataLakeCatalog", "TableComment": "daily", "Type": "table", "TableFormat": "iceberg", "PrimaryKeys": ["id"]}, "Columns": [{"Name": "id", "Type": "BIGINT", "Nullable": "false", "Position": 0}], "Partitions": [], "Location": "cosn://bucket/sales", "InputFormatShort": "parquet", "RecordCount": 2})
    assert immutable_drift(p, current) == {}
    assert comment_drift(p, current) == {}
    assert has_data(current) is True
    assert delete_request(Models, p).TableBaseInfo.TableName == "sales"
    assert task_status_request(Models, "task-1").TaskInstanceId == "task-1"


def test_table_comment_has_a_non_destructive_update_request():
    p = params(); p["comment"] = "updated"
    request = comment_request(Models, p)
    assert request.TableBaseInfo.TableComment == "updated"
    assert comment_drift(p, {"TableBaseInfo": {"TableComment": "old"}}) == {"TableComment": ("old", "updated")}
