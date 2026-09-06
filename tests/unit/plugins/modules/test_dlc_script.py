import base64
from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_script import create_request, decode_sql, delete_request, drift, list_request, normalize


class Request:
    pass


class Models:
    DescribeScriptsRequest = Request
    CreateScriptRequest = Request
    DeleteScriptRequest = Request


def test_sql_is_encoded_for_create_and_decoded_for_comparison():
    params = {"name": "daily", "sql_statement": "SELECT 1", "description": "test", "database_name": "analytics"}
    request = create_request(Models, params)
    assert request.SQLStatement == base64.b64encode(b"SELECT 1").decode("ascii")
    current = normalize({"ScriptName": "daily", "SQLStatement": request.SQLStatement, "ScriptDesc": "test", "DatabaseName": "analytics"})
    assert decode_sql(request.SQLStatement) == "SELECT 1"
    assert drift(params, current) == {}


def test_pagination_and_delete_use_exact_ids():
    listing = list_request(Models, 200)
    deletion = delete_request(Models, "script-1")
    assert listing.Offset == 200 and listing.Limit == 100
    assert deletion.ScriptIds == ["script-1"]
