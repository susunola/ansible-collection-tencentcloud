"""Unit tests for the tag write module (``run_module`` flows).

``tag`` reconciles one key/value pair across a set of resources.  The helper
tests in ``test_tag.py`` cover the request builders in isolation; this file
covers the path a user actually takes, because the ``idempotent`` attribute
this module documents is a claim about ``run_module``, not about its helpers.

The fake client is the tag store itself: every mutating call updates it, so
the ``DescribeResourcesByTags`` read the module performs at the start of the
next run sees what the previous run wrote.  That is what makes "run it twice
and the second run reports changed=false" testable in-process.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tag as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    module_args,
    run,
)


class FakeRequest(object):
    pass


class FakeTagFilter(object):
    def __init__(self):
        self.TagKey = None
        self.TagValue = None


class FakeTag(object):
    def __init__(self, key, value):
        self.Key = key
        self.Value = value


class TagModels(FakeModels):
    DescribeResourcesByTagsRequest = FakeRequest
    AttachResourcesTagRequest = FakeRequest
    ModifyResourcesTagValueRequest = FakeRequest
    DetachResourcesTagRequest = FakeRequest
    TagFilter = FakeTagFilter


class FakeResourceTag(object):
    def __init__(self, resource_id, tags):
        self.ResourceId = resource_id
        self.Tags = tags


class FakeDescribeResponse(object):
    def __init__(self, resource_tags):
        self.ResourceTags = resource_tags


class FakeTagStore(object):
    """The tag store, used as the SDK client.

    ``tagged`` is ``{resource_id: value or None}``.  Reads answer from it and
    writes update it, which is what makes a second ``run_module`` observe the
    first one's effect.
    """

    def __init__(self, tagged):
        self.tagged = dict(tagged)
        self.calls = []

    def DescribeResourcesByTags(self, request):
        self.calls.append("DescribeResourcesByTags")
        filters = request.TagFilters or []
        wanted = None
        if filters and filters[0].TagValue:
            wanted = filters[0].TagValue[0]
        out = []
        for resource_id, value in self.tagged.items():
            if value is None:
                continue
            if wanted is not None and value != wanted:
                continue
            out.append(FakeResourceTag(resource_id, [FakeTag(filters[0].TagKey, value)]))
        return FakeDescribeResponse(out)

    def AttachResourcesTag(self, request):
        self.calls.append("AttachResourcesTag")
        for resource_id in request.ResourceIds:
            self.tagged[resource_id] = request.TagValue

    def ModifyResourcesTagValue(self, request):
        self.calls.append("ModifyResourcesTagValue")
        for resource_id in request.ResourceIds:
            self.tagged[resource_id] = request.TagValue

    def DetachResourcesTag(self, request):
        self.calls.append("DetachResourcesTag")
        for resource_id in request.ResourceIds:
            self.tagged[resource_id] = None


def _make_module(monkeypatch, store):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_tag", lambda: (TagModels(), type("C", (), {"TagClient": object})))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: store)
    return store


def _args(**extra):
    base = {
        "tag_key": "env",
        "tag_value": "prod",
        "service_type": "cvm",
        "resource_prefix": "instance",
        "resource_region": "ap-guangzhou",
    }
    base.update(extra)
    module_args(**base)


# ---------------------------------------------------------------------------
# idempotence
# ---------------------------------------------------------------------------


def test_present_then_present_is_idempotent(monkeypatch):
    """The claim the attribute makes: the second run reports changed=false."""
    store = FakeTagStore({"ins-1": None, "ins-2": None})
    _make_module(monkeypatch, store)

    _args(resource_ids=["ins-1", "ins-2"])
    first = run(mod.run_module)
    assert first["changed"] is True
    assert store.tagged == {"ins-1": "prod", "ins-2": "prod"}

    store.calls = []
    _args(resource_ids=["ins-1", "ins-2"])
    second = run(mod.run_module)
    assert second["changed"] is False
    assert second["msg"] == "Tag is up to date"
    # Nothing was written the second time.
    assert store.calls == ["DescribeResourcesByTags", "DescribeResourcesByTags"]


def test_present_updates_a_drifted_value_once(monkeypatch):
    store = FakeTagStore({"ins-1": "dev"})
    _make_module(monkeypatch, store)

    _args(resource_ids=["ins-1"])
    first = run(mod.run_module)
    assert first["changed"] is True
    assert "ModifyResourcesTagValue" in store.calls
    assert store.tagged == {"ins-1": "prod"}

    store.calls = []
    _args(resource_ids=["ins-1"])
    second = run(mod.run_module)
    assert second["changed"] is False
    assert store.calls == ["DescribeResourcesByTags", "DescribeResourcesByTags"]


def test_absent_then_absent_is_idempotent(monkeypatch):
    store = FakeTagStore({"ins-1": "prod"})
    _make_module(monkeypatch, store)

    _args(state="absent", resource_ids=["ins-1"])
    first = run(mod.run_module)
    assert first["changed"] is True
    assert store.tagged == {"ins-1": None}

    store.calls = []
    _args(state="absent", resource_ids=["ins-1"])
    second = run(mod.run_module)
    assert second["changed"] is False
    assert second["msg"] == "Tag already absent"
    assert "DetachResourcesTag" not in store.calls


def test_check_mode_writes_nothing(monkeypatch):
    store = FakeTagStore({"ins-1": None})
    _make_module(monkeypatch, store)

    _args(resource_ids=["ins-1"], _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_ids"] == {"ins-1": "would_attach"}
    assert store.tagged == {"ins-1": None}
