"""Tests for DCDB backup configuration normalization."""
from ansible_collections.susunola.tencentcloud.plugins.modules.dcdb_backup_config import desired, normalize


def test_normalize_orders_weekdays():
    value = normalize({"Days": 30, "StartBackupTime": "02:00", "EndBackupTime": "03:00",
                       "WeekDays": ["Friday", "Monday"], "ArchiveDays": -1})
    assert value["weekdays"] == ["Monday", "Friday"]


def test_desired_deduplicates_weekdays():
    value = desired({"retention_days": 30, "start_time": "02:00", "end_time": "03:00",
                     "weekdays": ["Monday", "Monday", "Friday"], "archive_after_days": 90})
    assert value["weekdays"] == ["Monday", "Friday"]
    assert value["archive_after_days"] == 90
