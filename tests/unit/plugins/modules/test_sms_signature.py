"""Unit tests for the sms_signature write module (helpers + run_module).

Covers the apply / delete flows of ``plugins/modules/sms_signature.py``
with an in-memory fake SMS client whose write operations mutate the sign
store, so post-write state converges. Signatures are review-based resources:
the module only ever calls AddSmsSign / DeleteSmsSign and never updates in
place. A matching sign whose review failed (StatusCode == -1) is treated as
absent so re-running the task resubmits the application; otherwise an
existing usable/pending signature reports changed=false.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import sms_signature as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SIGN = {
    "SignId": 1001,
    "SignName": "Tencent Cloud",
    "StatusCode": 0,
    "ReviewReply": "",
}


def _sign(**overrides):
    """API-shaped sign dict isolated from the shared constant."""
    item = copy.deepcopy(SIGN)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "sign_name": "Tencent Cloud",
        "state": "present",
        "international": False,
        "sign_type": 0,
        "document_type": 0,
        "sign_purpose": 0,
        "proof_image": "aW1hZ2U=",
        "commission_image": None,
        "qualification_id": None,
        "remark": None,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeSmsClient(object):
    """In-memory SmsClient stand-in.

    Stores API-shaped sign dicts. DescribeSmsSignList pages over the store
    honouring Offset/Limit so find pagination is exercised; AddSmsSign
    appends with a fresh SignId and DeleteSmsSign removes the entry, so
    post-write refetches converge.
    """

    def __init__(self, signs=None):
        self.signs = [copy.deepcopy(s) for s in (signs or [])]
        self.calls = []
        self.offsets = []  # Offset snapshotted at each describe call time
        self._next_id = 2001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeSmsSignList(self, request):
        self._record("DescribeSmsSignList", request)
        self.offsets.append(request.Offset)
        page = self.signs[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            DescribeSignListStatusSet=[FakeResource(dict(s)) for s in page],
            TotalCount=len(self.signs),
            RequestId="req-fake",
        )

    def AddSmsSign(self, request):
        self._record("AddSmsSign", request)
        sign_id = self._next_id
        self._next_id += 1
        self.signs.append(
            {
                "SignId": sign_id,
                "SignName": request.SignName,
                "StatusCode": 1,  # in review
                "ReviewReply": "",
            }
        )
        return SimpleNamespace(AddSignStatus=SimpleNamespace(SignId=sign_id, RequestId="req-fake"))

    def DeleteSmsSign(self, request):
        self._record("DeleteSmsSign", request)
        self.signs = [s for s in self.signs if s.get("SignId") != request.SignId]
        return SimpleNamespace(DeleteSignStatus=SimpleNamespace(SignId=request.SignId, RequestId="req-fake"))


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_sms",
        lambda: (FakeModels(), SimpleNamespace(SmsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# helper tests
# ---------------------------------------------------------------------------


def test_to_int_maps_bool():
    assert mod._to_int(True) == 1
    assert mod._to_int(False) == 0


def test_find_sign_uses_international_flag(monkeypatch):
    fake = FakeSmsClient([_sign()])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    request = mod.find_sign(module, fake, FakeModels(), "Tencent Cloud", True)
    assert request is not None
    describe = [c for c in fake.calls if c[0] == "DescribeSmsSignList"][0][1]
    assert describe.International == 1


def test_find_sign_no_match_returns_none(monkeypatch):
    fake = FakeSmsClient([_sign(SignName="Other")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find_sign(module, fake, FakeModels(), "Tencent Cloud", False) is None


def test_find_sign_matches_by_name(monkeypatch):
    fake = FakeSmsClient([_sign(SignName="Other"), _sign()])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_sign(module, fake, FakeModels(), "Tencent Cloud", False)
    assert value["SignId"] == 1001
    assert value["StatusCode"] == 0


def test_find_sign_prefers_usable_over_rejected(monkeypatch):
    rejected = _sign(SignId=2001, StatusCode=-1, ReviewReply="bad materials")
    usable = _sign(SignId=1001, StatusCode=0)
    fake = FakeSmsClient([rejected, usable])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_sign(module, fake, FakeModels(), "Tencent Cloud", False)
    assert value["SignId"] == 1001  # usable wins over the earlier rejected entry


def test_find_sign_rejected_only_returns_rejected(monkeypatch):
    fake = FakeSmsClient([_sign(StatusCode=-1, ReviewReply="rejected")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_sign(module, fake, FakeModels(), "Tencent Cloud", False)
    assert value["StatusCode"] == -1
    assert value["ReviewReply"] == "rejected"


def test_find_sign_paginates_until_match(monkeypatch):
    signs = [_sign(SignId=1000 + i, SignName="bulk-%04d" % i, StatusCode=0) for i in range(250)]
    signs.append(_sign())
    fake = FakeSmsClient(signs)
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_sign(module, fake, FakeModels(), "Tencent Cloud", False)
    assert value["SignId"] == 1001
    list_calls = [c for c in fake.calls if c[0] == "DescribeSmsSignList"]
    assert len(list_calls) == 3  # pages of 100
    assert fake.offsets == [0, 100, 200]  # single request object is re-used, snapshot at call time


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_sign_name_required():
    module_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "sign_name" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_sms",
        lambda: (FakeModels(), SimpleNamespace(SmsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_present_existing_usable_is_noop(monkeypatch):
    fake = FakeSmsClient([_sign()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["sign_id"] == 1001
    assert result["status_code"] == 0
    assert result["review_reply"] == ""
    assert "already present" in result["msg"]
    assert not any("AddSmsSign" == c[0] for c in fake.calls)


def test_present_existing_in_review_is_noop(monkeypatch):
    fake = FakeSmsClient([_sign(StatusCode=1)])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["status_code"] == 1
    assert "already present" in result["msg"]


def test_present_rejected_signature_resubmits(monkeypatch):
    fake = FakeSmsClient([_sign(StatusCode=-1, ReviewReply="rejected")])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["sign_id"] == 2001  # fresh application id
    assert "submitted for review" in result["msg"]
    assert len(fake.signs) == 2  # rejected entry still listed, new one appended


def test_present_missing_required_materials_fails(monkeypatch):
    fake = FakeSmsClient()
    _make_module(monkeypatch, fake)
    _run_args(sign_type=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "sign_type" in payload["msg"]
    assert "Parameters required to apply" in payload["msg"]
    assert not any("AddSmsSign" == c[0] for c in fake.calls)


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeSmsClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would apply" in result["msg"]
    assert not any("AddSmsSign" == c[0] for c in fake.calls)


def test_present_check_mode_absent_is_dry_run(monkeypatch):
    fake = FakeSmsClient([_sign()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(state="absent"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would delete signature 1001" in result["msg"]
    assert not any("DeleteSmsSign" == c[0] for c in fake.calls)
    assert len(fake.signs) == 1


def test_present_creates_signature(monkeypatch):
    fake = FakeSmsClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["sign_id"] == 2001
    assert result["sign_name"] == "Tencent Cloud"
    add = [c for c in fake.calls if c[0] == "AddSmsSign"][0][1]
    assert add.SignName == "Tencent Cloud"
    assert add.SignType == 0
    assert add.DocumentType == 0
    assert add.SignPurpose == 0
    assert add.ProofImage == "aW1hZ2U="
    assert add.International == 0
    assert not hasattr(add, "CommissionImage")
    assert not hasattr(add, "QualificationId")
    assert not hasattr(add, "Remark")


def test_present_create_international_and_optional_fields(monkeypatch):
    fake = FakeSmsClient()
    _make_module(monkeypatch, fake)
    _run_args(
        international=True,
        commission_image="YXV0aA==",
        qualification_id="qual-9",
        remark="please approve",
        sign_type=2,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    add = [c for c in fake.calls if c[0] == "AddSmsSign"][0][1]
    assert add.International == 1
    assert add.SignType == 2
    assert add.CommissionImage == "YXV0aA=="
    assert add.QualificationId == "qual-9"
    assert add.Remark == "please approve"


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeSmsClient([_sign(SignName="Other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", sign_name="Ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["sign_name"] == "Ghost"
    assert "not present" in result["msg"]
    assert not any("DeleteSmsSign" == c[0] for c in fake.calls)


def test_absent_deletes_matched_signature(monkeypatch):
    fake = FakeSmsClient([_sign()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Deleted signature 1001" in result["msg"]
    delete = [c for c in fake.calls if c[0] == "DeleteSmsSign"][0][1]
    assert delete.SignId == 1001
    assert fake.signs == []
