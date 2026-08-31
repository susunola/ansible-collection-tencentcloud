from ansible_collections.susunola.tencentcloud.plugins.modules.tione_model_service_auth_token import create_request, delete_request, desired, find, modify_request, normalized_limits, sanitize


class Object:
    def from_json_string(self, value): self.value = value
class Models: CreateModelServiceAuthTokenRequest = ModifyModelServiceAuthTokenRequest = DeleteModelServiceAuthTokenRequest = AuthToken = Object
class Module:
    def fail_json(self, **kwargs): raise ValueError(kwargs["msg"])


TOKENS = [{"Base": {"Id": "t1", "Value": "secret", "Name": "prod", "Description": "old"}, "Limits": [{"Strategy": "PerDay", "Max": 10}]}]
P = {"service_group_id": "g1", "project_id": "p1", "token_id": "t1", "name": "prod", "description": "new", "limits": [{"Strategy": "PerMinute", "Max": 5}]}


def test_find_prefers_stable_id_and_rejects_duplicate_names():
    assert find(Module(), TOKENS, P)["Base"]["Id"] == "t1"
    try: find(Module(), TOKENS * 2, dict(P, token_id=None))
    except ValueError: pass
    else: raise AssertionError("ambiguous token name was accepted")


def test_desired_preserves_identity_and_normalizes_limits():
    value = desired(P, TOKENS[0])
    assert value["Base"]["Id"] == "t1" and value["Base"]["Description"] == "new"
    assert value["Limits"] == normalized_limits(P["limits"])


def test_requests_keep_group_workspace_and_secret_identity():
    create = create_request(Models, P); modify = modify_request(Models, P, TOKENS[0], True); delete = delete_request(Models, P, TOKENS[0])
    assert (create.ServiceGroupId, create.TiProjectId, create.Name) == ("g1", "p1", "prod")
    assert modify.NeedReset is True and '"Id": "t1"' in modify.AuthToken.value
    assert delete.AuthTokenValue == "secret"


def test_sanitize_removes_value_unless_explicitly_requested():
    assert "Value" not in sanitize(TOKENS[0])["Base"]
    assert sanitize(TOKENS[0], True)["Base"]["Value"] == "secret"
