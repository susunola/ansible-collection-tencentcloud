from ansible_collections.susunola.tencentcloud.plugins.modules.tdmysql_backup_policy import desired, modify_request, normalize


class Policy:
    def from_json_string(self, value):
        self.value = value


class Object:
    pass


class Models:
    ModifyDBSBackupPolicyRequest = Object
    BackupPolicyModelInput = Policy


def test_normalize_converts_api_flags_to_booleans():
    assert normalize({"EnableFull": 1, "EnableLog": 0}) == {"EnableFull": True, "EnableLog": False}


def test_desired_overlays_only_supplied_fields():
    p = {"backup_method": "snapshot", "enable_log": None}
    value = desired(p, {"BackupMethod": "physical", "EnableLog": True})
    assert value == {"BackupMethod": "snapshot", "EnableLog": True}


def test_modify_request_derives_snapshot_storage_and_integer_flags():
    p = {"instance_id": "db1"}
    target = {
        "BackupStartTime": "00:00",
        "BackupEndTime": "04:00",
        "BackupMethod": "snapshot",
        "EnableFull": True,
        "EnableLog": False,
        "FullRetentionPeriod": 7,
        "LogRetentionPeriod": 7,
        "PeriodTime": "0,1",
    }
    request = modify_request(Models, p, target)
    assert request.InstanceId == "db1" and '"StorageType": "SNAPSHOT"' in request.BackupPolicy.value
    assert '"EnableFull": 1' in request.BackupPolicy.value and '"EnableLog": 0' in request.BackupPolicy.value
