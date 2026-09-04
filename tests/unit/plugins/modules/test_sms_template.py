"""Unit tests for the sms_template write module (helpers + run_module).

Creates and deletes SMS template applications. SMS templates are
review-based: the module is idempotent for existing usable/pending
templates (no write, changed=false) and treats a rejected template
(StatusCode == -1) as absent so re-running resubmits. find_template
pages through DescribeSmsTemplateList and prefers a usable same-name
entry over a rejected one, falling back to the rejected entry only when
nothing else matches. Remark is sent to AddSmsTemplate only when
provided.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import sms_template as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _template(**overrides):
    """API-shaped SMS template dict; fresh copy per call."""
    item = {
        "TemplateId": 88001,
        "TemplateName": "Login verification code",
        "StatusCode": 0,
        "ReviewReply": "",
        "International": 0,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "template_name": "Login verification code",
        "state": "present",
        "international": False,
        "sms_type": None,
        "template_content": None,
        "remark": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
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
    """In-memory SmsClient stand-in storing template dicts.

    DescribeSmsTemplateList paginates with the request's Offset/Limit;
    the module collects same-name matches itself. AddSmsTemplate
    synthesises a numeric TemplateId and mirrors the async-review model
    (the module reads it from AddTemplateStatus, not a refetch).
    """

    def __init__(self, templates=None):
        self.templates = [dict(t) for t in (templates or [])]
        self.calls = []
        self._next_id = 90001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeSmsTemplateList(self, request):
        self._record("DescribeSmsTemplateList", request)
        offset = getattr(request, "Offset", 0)
        limit = getattr(request, "Limit", 100)
        page = self.templates[offset:offset + limit]
        return SimpleNamespace(
            DescribeTemplateStatusSet=[FakeResource(dict(t)) for t in page],
            RequestId="req-fake",
        )

    def AddSmsTemplate(self, request):
        self._record("AddSmsTemplate", request)
        template_id = self._next_id
        self._next_id += 1
        self.templates.append(
            {
                "TemplateId": template_id,
                "TemplateName": request.TemplateName,
                "StatusCode": 0,
                "ReviewReply": "",
                "International": request.International,
            }
        )
        return SimpleNamespace(
            AddTemplateStatus=SimpleNamespace(TemplateId=template_id),
            RequestId="req-fake",
        )

    def DeleteSmsTemplate(self, request):
        self._record("DeleteSmsTemplate", request)
        self.templates = [t for t in self.templates if t.get("TemplateId") != request.TemplateId]
        return SimpleNamespace(RequestId="req-fake")


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


def test_to_int_maps_booleans():
    assert mod._to_int(True) == 1
    assert mod._to_int(False) == 0


def test_find_matches_usable_template(monkeypatch):
    fake = FakeSmsClient([_template(), _template(TemplateId=88002, TemplateName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_template(module, fake, FakeModels(), "Login verification code", False)
    assert value["TemplateId"] == 88001
    assert value["StatusCode"] == 0


def test_find_prefers_usable_over_rejected_same_name(monkeypatch):
    fake = FakeSmsClient([_template(TemplateId=88002, StatusCode=-1, ReviewReply="bad words"), _template(TemplateId=88001, StatusCode=0)])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_template(module, fake, FakeModels(), "Login verification code", False)
    assert value["TemplateId"] == 88001  # usable entry wins over the rejected one


def test_find_returns_rejected_when_only_match(monkeypatch):
    fake = FakeSmsClient([_template(TemplateId=88002, StatusCode=-1, ReviewReply="rejected")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_template(module, fake, FakeModels(), "Login verification code", False)
    assert value["TemplateId"] == 88002  # lets the caller resubmit
    assert value["StatusCode"] == -1


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeSmsClient([_template()])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find_template(module, fake, FakeModels(), "ghost", False) is None


def test_find_paginates_across_pages(monkeypatch):
    templates = [_template(TemplateId=1000 + i, TemplateName="filler-%d" % i) for i in range(150)]
    templates.append(_template(TemplateId=88001))
    fake = FakeSmsClient(templates)
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_template(module, fake, FakeModels(), "Login verification code", False)
    assert value["TemplateId"] == 88001
    assert [c[0] for c in fake.calls].count("DescribeSmsTemplateList") == 2  # page 0 + page 100


def test_find_sets_international_flag_on_request(monkeypatch):
    fake = FakeSmsClient()
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find_template(module, fake, FakeModels(), "x", True) is None
    request = fake.calls[0][1]
    assert request.International == 1


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_existing_usable_is_noop(monkeypatch):
    fake = FakeSmsClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["template_id"] == 88001
    assert result["status_code"] == 0
    assert result["msg"] == "Template already present (status 0)"
    assert not any(c[0] in ("AddSmsTemplate", "DeleteSmsTemplate") for c in fake.calls)


def test_present_existing_usable_ignores_content_drift(monkeypatch):
    # Review-based: content changes need a fresh application, so a usable
    # template never triggers a write even with different content params.
    fake = FakeSmsClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(sms_type=1, template_content="Promo {1}", remark="changed")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert not any(c[0] == "AddSmsTemplate" for c in fake.calls)


def test_present_rejected_template_resubmits(monkeypatch):
    fake = FakeSmsClient([_template(TemplateId=88002, StatusCode=-1)])
    _make_module(monkeypatch, fake)
    _run_args(sms_type=0, template_content="Your code is {1}")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["template_id"] == 90001
    assert "submitted for review" in result["msg"]
    add = [c for c in fake.calls if c[0] == "AddSmsTemplate"][0][1]
    assert add.TemplateName == "Login verification code"
    assert add.TemplateContent == "Your code is {1}"
    assert add.SmsType == 0


def test_present_creation_parameters_missing_fails(monkeypatch):
    fake = FakeSmsClient()
    _make_module(monkeypatch, fake)
    _run_args()  # no sms_type / template_content
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Parameters required to apply for a template are missing" in payload["msg"]
    assert "sms_type" in payload["msg"] and "template_content" in payload["msg"]
    assert not any(c[0] == "AddSmsTemplate" for c in fake.calls)


def test_present_creates_template(monkeypatch):
    fake = FakeSmsClient()
    _make_module(monkeypatch, fake)
    _run_args(sms_type=0, template_content="Your code is {1}", remark="login flow")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["template_id"] == 90001
    assert result["msg"] == "Template application submitted for review"
    add = [c for c in fake.calls if c[0] == "AddSmsTemplate"][0][1]
    assert add.TemplateName == "Login verification code"
    assert add.TemplateContent == "Your code is {1}"
    assert add.SmsType == 0
    assert add.International == 0
    assert add.Remark == "login flow"


def test_present_remark_omitted_when_not_given(monkeypatch):
    fake = FakeSmsClient()
    _make_module(monkeypatch, fake)
    _run_args(sms_type=0, template_content="Your code is {1}")
    result = run(mod.run_module)
    assert result["changed"] is True
    add = [c for c in fake.calls if c[0] == "AddSmsTemplate"][0][1]
    assert not hasattr(add, "Remark")


def test_present_international_flag_maps_to_one(monkeypatch):
    fake = FakeSmsClient()
    _make_module(monkeypatch, fake)
    _run_args(international=True, sms_type=0, template_content="Your code is {1}")
    run(mod.run_module)
    add = [c for c in fake.calls if c[0] == "AddSmsTemplate"][0][1]
    assert add.International == 1


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeSmsClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, sms_type=0, template_content="Your code is {1}")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would apply for template Login verification code"
    assert not any(c[0] == "AddSmsTemplate" for c in fake.calls)
    assert fake.templates == []


def test_absent_not_present_is_noop(monkeypatch):
    fake = FakeSmsClient([_template(TemplateName="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Template not present"
    assert not any(c[0] == "DeleteSmsTemplate" for c in fake.calls)


def test_absent_deletes_template(monkeypatch):
    fake = FakeSmsClient([_template(), _template(TemplateId=88002, TemplateName="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Deleted template 88001"
    delete = [c for c in fake.calls if c[0] == "DeleteSmsTemplate"][0][1]
    assert delete.TemplateId == 88001
    assert [t["TemplateId"] for t in fake.templates] == [88002]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeSmsClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete template 88001"
    assert not any(c[0] == "DeleteSmsTemplate" for c in fake.calls)
    assert len(fake.templates) == 1


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
    _run_args(sms_type=0, template_content="Your code is {1}")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"
