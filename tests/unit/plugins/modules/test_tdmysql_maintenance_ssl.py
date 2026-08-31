from ansible_collections.susunola.tencentcloud.plugins.modules.tdmysql_maintenance_window import expected_range, modify_request as maintenance_request, normalize_start
from ansible_collections.susunola.tencentcloud.plugins.modules.tdmysql_ssl import modify_request as ssl_request


class Object: pass
class Models: ModifyMaintenanceWindowRequest = ModifyInstanceSSLStatusRequest = Object


def test_maintenance_range_normalizes_seconds_and_wraps_midnight():
    assert normalize_start("02:30:00") == "02:30" and expected_range("23:30", 2) == "23:30-01:30"


def test_maintenance_request_sorts_weekdays_chronologically():
    p = {"instance_id": "db1", "start_time": "02:00", "duration_hours": 2, "week_days": ["Saturday", "Tuesday"]}
    request = maintenance_request(Models, p)
    assert request.StartTime == "02:00:00" and request.Duration == 2 and request.WeekDays == ["Tuesday", "Saturday"]


def test_ssl_request_maps_boolean_without_integer_coercion():
    request = ssl_request(Models, "db1", True)
    assert request.InstanceId == "db1" and request.Enabled is True
