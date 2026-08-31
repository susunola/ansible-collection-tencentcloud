from ansible_collections.susunola.tencentcloud.plugins.modules.tdmysql_account_privilege import describe_request, modify_request, result
from ansible_collections.susunola.tencentcloud.plugins.modules.tdmysql_database_object_info import database_request, object_request, read_databases, read_objects


class Object:
    def _serialize(self, allow_none=True): return self.value
class Models: DescribeUserPrivilegesRequest = ModifyUserPrivilegesRequest = User = DatabasePrivileges = TablePrivileges = DescribeDatabasesRequest = DescribeDatabaseObjectsRequest = Object


def p(scope="table"): return {"instance_id": "db1", "username": "u1", "host": "%", "scope": scope, "database": "app", "table": "orders", "privileges": ["UPDATE", "SELECT"], "page_size": 2, "max_pages": 5, "database_regexp": None, "table_regexp": None}


def test_scoped_privilege_requests_map_database_and_table():
    describe, modify = describe_request(Models, p()), modify_request(Models, p())
    assert (describe.DbName, describe.ObjectType, describe.Object) == ("app", "table", "orders")
    assert modify.TablePrivileges[0].Privileges == ["SELECT", "UPDATE"]
    assert result(p(), ["SELECT"])["Table"] == "orders"


def test_database_and_object_requests_map_pagination():
    db, obj = database_request(Models, p(), 2), object_request(Models, p(), 4)
    assert (db.Offset, db.Limit) == (2, 2) and (obj.DbName, obj.Offset) == ("app", 4)


class Item:
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=True): return self.value
class Response:
    def __init__(self, databases=None, total=0, tables=None, request_id="r"):
        self.Databases, self.TotalCount, self.RequestId = databases, total, request_id
        self.Tables, self.Views, self.Procs, self.Funcs = tables, [], [], []
class Client:
    def __init__(self): self.db = [Response([Item({"DbName": "a"}), Item({"DbName": "b"})], 3, request_id="r1"), Response([Item({"DbName": "c"})], 3, request_id="r2")]
    def DescribeDatabases(self, request): return self.db.pop(0)
    def DescribeDatabaseObjects(self, request): return Response(tables=[Item({"Table": "orders"})], request_id="ro")
class Module:
    def sdk_call(self, fn, request): return fn(request)


def test_readers_collect_pages_and_object_categories():
    databases, total, truncated, request_id = read_databases(Module(), Client(), Models, p())
    assert len(databases) == 3 and total == 3 and not truncated and request_id == "r2"
    objects, truncated, request_id = read_objects(Module(), Client(), Models, p())
    assert objects["Tables"] == [{"Table": "orders"}] and not truncated and request_id == "ro"
