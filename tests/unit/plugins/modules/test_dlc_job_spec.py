from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_job_spec import delete_request, drift, list_request, make_request, normalize


class Request:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items(): setattr(self, key, item)


class Models:
    ListJobSpecsRequest = Request
    CreateJobSpecRequest = Request
    UpdateJobSpecRequest = Request
    DeleteJobSpecRequest = Request


def test_json_and_tags_compare_semantically():
    current = normalize({"Name": "etl", "RuntimeEnv": '{"b":2,"a":1}', "Tags": [{"TagValue": "prod", "TagKey": "env"}]})
    params = {"name": "etl", "runtime_env": '{"a":1,"b":2}', "tags": [{"key": "env", "value": "prod"}]}
    assert drift(params, current) == {}


def test_requests_use_spec_id_and_normalized_payload():
    params = {"name": "etl", "entrypoint": "python main.py", "runtime_env": '{"z":1,"a":2}', "tags": [{"key": "b", "value": "2"}, {"key": "a", "value": "1"}]}
    create = make_request(Models, params)
    update = make_request(Models, params, update=True, spec_id="spec-1")
    delete = delete_request(Models, "spec-1")
    listing = list_request(Models, 2)
    assert create.RuntimeEnv == '{"a":2,"z":1}' and create.Tags[0]["TagKey"] == "a"
    assert update.SpecId == "spec-1" and delete.SpecId == "spec-1"
    assert listing.Page == 2 and listing.PageSize == 200
