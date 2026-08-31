from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_ray_job_info import event_read, event_request, history_request, id_request, page_number_read, pods_request


class Object: pass
class Models:
    GetRayJobRequest = GetRayJobHistoryRequest = GetRayJobPodsRequest = GetRayJobEventRequest = Object


def params(): return {"ray_job_id": "job-1", "page_size": 2, "max_pages": 3, "start_time": 10, "end_time": 20, "event_type": "Warning"}


def test_requests_keep_job_identity_and_diagnostic_bounds():
    assert id_request(Models.GetRayJobRequest, "job-1").Id == "job-1"
    assert history_request(Models, params(), 2).Page == 2
    pods = pods_request(Models, params(), 3); assert pods.Page == 3 and pods.StartTime == 10
    event = event_request(Models, params(), "ctx"); assert event.Context == "ctx" and event.EventType == "Warning"


class Item:
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=True): return {"Value": self.value}


class Response:
    def __init__(self, values, pages): self.Items, self.TotalPages = [Item(x) for x in values], pages


class Module:
    def sdk_call(self, fn, request): return fn(request)
    def fail_json(self, **kwargs): raise AssertionError(kwargs)


def test_page_number_diagnostics_follow_total_pages():
    responses = [Response(["a", "b"], 2), Response(["c"], 2)]
    values, truncated = page_number_read(Module(), lambda request: responses.pop(0), lambda page: history_request(Models, params(), page), "Items", params())
    assert values == [{"Value": "a"}, {"Value": "b"}, {"Value": "c"}] and truncated is False


class EventResponse:
    def __init__(self, values, context, over): self.Events, self.Context, self.ListOver = [Item(x) for x in values], context, over


class Client:
    def __init__(self): self.responses = [EventResponse(["a"], "c2", False), EventResponse(["b"], None, True)]
    def GetRayJobEvent(self, request): return self.responses.pop(0)


def test_event_diagnostics_follow_context_until_list_over():
    values, truncated = event_read(Module(), Client(), Models, params())
    assert values == [{"Value": "a"}, {"Value": "b"}] and truncated is False
