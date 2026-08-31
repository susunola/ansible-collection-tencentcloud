from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules.ssm_rotation import (
    comparable,
    describe_request,
    result,
    update_request,
)


class Request(object):
    pass


class Models(object):
    DescribeRotationDetailRequest = Request
    UpdateRotationStatusRequest = Request


class Response(object):
    EnableRotation = True
    Frequency = 60
    LatestRotateTime = "2026-08-01 02:00:00"
    NextRotateBeginTime = "2026-09-30 02:00:00"


def test_update_request_preserves_service_time_format():
    request = update_request(Models, {
        "secret_name": "prod-db",
        "enabled": True,
        "frequency": 60,
        "begin_time": "2026-09-01 02:00:00",
    })
    assert request.SecretName == "prod-db"
    assert request.EnableRotation is True
    assert request.Frequency == 60
    assert request.RotationBeginTime == "2026-09-01 02:00:00"


def test_rotation_comparable_and_result_exclude_unstable_schedule_from_diff():
    assert comparable(Response()) == {"EnableRotation": True, "Frequency": 60}
    assert result(Response())["NextRotateBeginTime"] == "2026-09-30 02:00:00"
    assert describe_request(Models, "prod-db").SecretName == "prod-db"
