from ansible_collections.susunola.tencentcloud.plugins.modules.cdwpg_hba_config import normalize
def test_normalize_preserves_security_rule_order():
    rules=[{"type":"hostssl","database":"all","user":"admins","address":"10.0.0.0/24","method":"cert"},{"type":"host","database":"all","user":"all","address":"0.0.0.0/0","method":"reject"}]
    assert [x["User"] for x in normalize(rules)]==["admins","all"]
def test_normalize_omits_optional_mask(): assert normalize([{"type":"host","database":"db","user":"u","address":"10.0.0.1/32","method":"md5","mask":None}])[0]=={"Type":"host","Database":"db","User":"u","Address":"10.0.0.1/32","Method":"md5"}
def test_normalize_projects_sdk_output_and_drops_nulls(): assert normalize([{"Type":"host","Database":"db","User":"u","Address":"10.0.0.1/32","Method":"md5","Mask":None}])==[{"Type":"host","Database":"db","User":"u","Address":"10.0.0.1/32","Method":"md5"}]
