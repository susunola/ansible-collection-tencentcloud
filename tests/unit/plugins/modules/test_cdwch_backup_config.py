from ansible_collections.susunola.tencentcloud.plugins.modules.cdwch_backup_config import normalize_strategy,normalize_tables
def test_normalize_strategy_uses_api_fields(): assert normalize_strategy({"retain_days":30,"week_days":"1,3","execute_hour":2})=={"RetainDays":30,"WeekDays":"1,3","ExecuteHour":2}
def test_normalize_tables_is_stable(): assert normalize_tables([{"Database":"b","Table":"t"},{"Database":"a","Table":"z"}])==[{"Database":"a","Table":"z"},{"Database":"b","Table":"t"}]
def test_normalize_tables_drops_server_computed_fields(): assert normalize_tables([{"Database":"a","Table":"t","TotalBytes":42,"BackupStatus":1}])==[{"Database":"a","Table":"t"}]
