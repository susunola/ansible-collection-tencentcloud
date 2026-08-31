from ansible_collections.susunola.tencentcloud.plugins.modules.oceanus_meta_table import encode_ddl, get_request


class Request: pass
class Models: GetMetaTableRequest=Request


def test_encode_ddl_is_stable_utf8_base64():
    assert encode_ddl("CREATE TABLE 流 (id BIGINT)")=="Q1JFQVRFIFRBQkxFIOa1gSAoaWQgQklHSU5UKQ=="


def test_get_request_uses_fully_qualified_table_identity():
    p={"catalog_name":"default_catalog","database_name":"prod","table_name":"orders","workspace_id":"space-1"}
    request=get_request(Models,p)
    assert (request.Catalog,request.Database,request.Table,request.WorkSpaceId)==("default_catalog","prod","orders","space-1")
