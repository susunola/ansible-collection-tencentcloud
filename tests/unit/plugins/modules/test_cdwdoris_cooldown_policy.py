from ansible_collections.susunola.tencentcloud.plugins.modules.cdwdoris_cooldown_policy import desired


def test_desired_ttl_policy_uses_read_model_field_names():
    assert desired({"name": "archive", "cooldown_ttl": "30 DAY", "cooldown_datetime": None}) == {
        "PolicyName": "archive", "CooldownTtl": "30 DAY",
    }


def test_desired_datetime_policy():
    assert desired({"name": "year-end", "cooldown_ttl": None, "cooldown_datetime": "2026-12-31 00:00:00"}) == {
        "PolicyName": "year-end", "CooldownDatetime": "2026-12-31 00:00:00",
    }
