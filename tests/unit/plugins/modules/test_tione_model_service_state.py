from ansible_collections.susunola.tencentcloud.plugins.modules.tione_model_service_state import (
    action_request,
    detail_request,
    get,
    service_status,
    wait_service,
)


class Object:
    pass


class Models:
    DescribeModelServiceRequest = ModifyModelServiceRequest = DeleteModelServiceRequest = Object


def params():
    return {"service_id": "ms-1", "project_id": "p-1", "waiter_delay": 1, "waiter_timeout": 2}


def test_requests_keep_service_and_project_identity():
    detail = detail_request(Models, params())
    action = action_request(Models.ModifyModelServiceRequest, params(), "STOP")
    assert (detail.ServiceId, detail.TiProjectId) == ("ms-1", "p-1")
    assert (action.ServiceId, action.TiProjectId, action.ServiceAction) == ("ms-1", "p-1", "STOP")


def test_service_status_normalizes_api_spelling():
    assert service_status({"Status": "Normal"}) == "normal"
    assert service_status(None) == ""


class Value:
    def __init__(self, status):
        self.Status = status

    def _serialize(self, allow_none=True):
        return {"Status": self.Status, "ServiceId": "ms-1"}


class Response:
    def __init__(self, value):
        self.Service = value


class Client:
    def __init__(self, statuses):
        self.statuses = list(statuses)

    def DescribeModelService(self, request):
        return Response(Value(self.statuses.pop(0)))


class Module:
    check_mode = False

    def sdk_call(self, fn, request):
        return fn(request)

    def fail_json(self, **kwargs):
        raise RuntimeError(kwargs["msg"])


def test_get_serializes_service_detail():
    assert get(Module(), Client(["Normal"]), Models, params())["ServiceId"] == "ms-1"


def test_wait_service_accepts_normal_after_transition(monkeypatch):
    monkeypatch.setattr("ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters.time.sleep", lambda _: None)
    assert wait_service(Module(), Client(["Pending", "Normal"]), Models, params(), ["normal"]) == "normal"


def test_wait_service_rejects_failed_terminal_state():
    try:
        wait_service(Module(), Client(["Abnormal"]), Models, params(), ["normal"])
    except RuntimeError as exc:
        assert "failed state" in str(exc)
    else:
        raise AssertionError("failed state was accepted")
