from ansible_collections.susunola.tencentcloud.plugins.modules.oceanus_job_savepoint import matching, find_by_id


def test_matching_reuses_latest_active_or_running_description():
    values=[{"Id":1,"Description":"release","Status":1,"CreateTime":10},{"Id":2,"Description":"release","Status":3,"CreateTime":20},{"Id":3,"Description":"release","Status":4,"CreateTime":30}]
    assert matching(values,"release")["Id"]==2


def test_find_by_id_accepts_serial_or_numeric_identity():
    values=[{"Id":7,"SerialId":"sp-7"}]
    assert find_by_id(values,"sp-7")==values[0]
    assert find_by_id([{"Id":7}],7)=={"Id":7}
