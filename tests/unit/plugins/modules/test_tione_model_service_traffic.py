from ansible_collections.susunola.tencentcloud.plugins.modules.tione_model_service_traffic import (
    authorization_request,
    current_weights,
    normalized_weights,
    validate_weights,
    weights_request,
)


class Object:
    def from_json_string(self, value):
        self.value = value


class Models:
    ModifyModelServiceAuthorizationRequest = ModifyServiceGroupWeightsRequest = WeightEntry = Object


def params():
    return {"service_group_id": "g1", "authorization_enable": True, "weights": [{"ServiceId": "s2", "Weight": 10}, {"ServiceId": "s1", "Weight": 90}]}


def test_requests_map_authorization_and_sorted_weights():
    auth, weights = authorization_request(Models, params()), weights_request(Models, params())
    assert auth.ServiceGroupId == "g1" and auth.AuthorizationEnable is True
    assert '"ServiceId": "s1"' in weights.Weights[0].value


def test_current_weights_ignores_unrelated_service_fields():
    group = {"Services": [{"ServiceId": "s2", "Weight": 10, "Status": "Normal"}, {"ServiceId": "s1", "Weight": 90}]}
    assert current_weights(group) == normalized_weights(params()["weights"])


class Module:
    def fail_json(self, **kwargs):
        raise ValueError(kwargs["msg"])


def test_validate_weights_accepts_exact_distribution():
    validate_weights(Module(), params()["weights"])


def test_validate_weights_rejects_invalid_totals_and_duplicate_ids():
    for value in ([{"ServiceId": "s1", "Weight": 99}], [{"ServiceId": "s1", "Weight": 50}, {"ServiceId": "s1", "Weight": 50}]):
        try:
            validate_weights(Module(), value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid traffic distribution was accepted")
