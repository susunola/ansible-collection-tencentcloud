from ansible_collections.susunola.tencentcloud.plugins.module_utils import lifecycle


class FakeModule:
    def fail_json(self, **kwargs):
        raise RuntimeError(kwargs)


class FakeError(Exception):
    def get_code(self):
        return "InvalidParameter"

    def get_request_id(self):
        return "req-1"


def test_immutable_changes_only_reports_differences():
    assert lifecycle.immutable_changes({"Size": 1, "Name": "a"}, {"Size": 2, "Name": "a"}, ("Size", "Name")) == {
        "Size": {"before": 1, "after": 2}
    }


def test_require_immutable_unchanged_fails_with_replacement_contract():
    try:
        lifecycle.require_immutable_unchanged(FakeModule(), {"Size": 1}, {"Size": 2}, ("Size",), "queue")
    except RuntimeError as exc:
        assert exc.args[0]["replacement_required"] is True
    else:
        raise AssertionError("expected immutable field failure")


def test_sdk_error_payload_preserves_diagnostics():
    payload = lifecycle.sdk_error_payload(FakeError("bad"))
    assert payload["error_code"] == "InvalidParameter"
    assert payload["request_id"] == "req-1"
