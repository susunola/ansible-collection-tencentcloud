from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_model_artifact_info import build_request, read


class Request: pass


def params():
    return {"model_uid": "model-1", "model_version": "v2", "include_config": True, "include_files": True, "include_readme": True}


def test_request_uses_strong_model_version_identity():
    request = build_request(Request, params())
    assert request.ModelUid == "model-1" and request.ModelVersion == "v2"


class Models:
    GetModelConfigRequest = GetModelFilesRequest = GetModelReadmeRequest = Request
class Response:
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=True): return dict(self.value)
class Client:
    def __init__(self): self.calls = []
    def GetModelConfig(self, request): self.calls.append(("config", request.ModelUid, request.ModelVersion)); return Response({"ModelName": "m", "ConfigJson": '{"layers": 12}', "RequestId": "rc"})
    def GetModelFiles(self, request): self.calls.append(("files", request.ModelUid, request.ModelVersion)); return Response({"Files": [{"Name": "weights"}], "RequestId": "rf"})
    def GetModelReadme(self, request): self.calls.append(("readme", request.ModelUid, request.ModelVersion)); return Response({"Readme": "# Model", "RequestId": "rr"})
class Module:
    def sdk_call(self, fn, request): return fn(request)


def test_read_combines_artifacts_and_parses_valid_config_json():
    client = Client(); values, request_ids = read(Module(), client, Models, params())
    assert values["config"]["Config"] == {"layers": 12}
    assert values["files"]["Files"] == [{"Name": "weights"}] and values["readme"]["Readme"] == "# Model"
    assert request_ids == {"config": "rc", "files": "rf", "readme": "rr"}
    assert all(call[1:] == ("model-1", "v2") for call in client.calls)


def test_read_honours_independent_artifact_selection_and_invalid_json():
    p = params(); p.update(include_files=False, include_readme=False)
    client = Client()
    client.GetModelConfig = lambda request: Response({"ConfigJson": "not-json", "RequestId": "rc"})
    values, request_ids = read(Module(), client, Models, p)
    assert values == {"config": {"ConfigJson": "not-json", "Config": None}}
    assert request_ids == {"config": "rc"}
