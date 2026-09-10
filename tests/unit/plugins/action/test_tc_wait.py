"""Unit tests for the ``tc_wait`` action plugin.

The plugin runs the observation loop on the controller, so every poll is a
nested module invocation. These tests drive ``run()`` with a stubbed
``_execute_module`` and assert the loop, the return contract and the timeout
payload; the shared loop mechanics themselves are covered by
``tests/unit/plugins/module_utils/test_polling.py``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib

import pytest

from ansible.errors import AnsibleActionFail
from ansible_collections.susunola.tencentcloud.plugins.action.tc_wait import (
    ABSENT,
    OBSERVATION_SPECS,
    ActionModule,
    fully_qualified,
    lookup_path,
    matches,
    observation_spec,
    observed_states,
    positive_int,
    short_name,
)
from ansible_collections.susunola.tencentcloud.plugins.module_utils import polling

REGION = {"region": "ap-guangzhou"}


class FakeTask(object):
    def __init__(self, args, check_mode=False):
        self.args = args
        self.check_mode = check_mode
        self.async_val = 0
        self.action = "susunola.tencentcloud.tc_wait"
        self.no_log = False


class FakeShell(object):
    tmpdir = None


class FakeConnection(object):
    def __init__(self):
        self._shell = FakeShell()


class FakeDisplay(object):
    def __init__(self):
        self.verbose = []

    def vvv(self, message, *args, **kwargs):
        self.verbose.append(message)


def build_action(args, responses, check_mode=False):
    """Return an action instance whose nested calls replay ``responses``.

    The last response is repeated once the script runs out, which is how the
    timeout cases keep observing the same value.
    """
    calls = []

    def fake_execute(module_name=None, module_args=None, task_vars=None, **kwargs):
        calls.append({"module_name": module_name, "module_args": module_args})
        index = min(len(calls) - 1, len(responses) - 1)
        return responses[index]

    action = ActionModule(
        task=FakeTask(args, check_mode=check_mode),
        connection=FakeConnection(),
        play_context=object(),
        loader=object(),
        templar=object(),
        shared_loader_obj=object(),
    )
    action._execute_module = fake_execute
    action._display = FakeDisplay()
    return action, calls


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    """Stop the shared loop from sleeping: these tests exercise the budget.

    The patch targets ``module_utils.polling``, the module where ``poll_until``
    is defined and therefore where ``time`` is looked up. Patching the
    ``plugin_utils`` shim would be a no-op: it only re-exports the function.
    """
    monkeypatch.setattr(polling.time, "sleep", lambda _seconds: None)


def test_the_plugin_reaches_the_loop_through_the_controller_side_shim():
    """The action plugin is controller-side, so it imports plugin_utils."""
    from ansible_collections.susunola.tencentcloud.plugins.action import tc_wait

    assert tc_wait.poll_until is polling.poll_until


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------


def test_fully_qualified_resolves_short_names_in_this_collection():
    assert fully_qualified("cvm_instance_info") == "susunola.tencentcloud.cvm_instance_info"
    assert fully_qualified("other.collection.thing_info") == "other.collection.thing_info"


def test_short_name_strips_the_namespace():
    assert short_name("susunola.tencentcloud.tke_cluster_info") == "tke_cluster_info"
    assert short_name("cvm_instance_info") == "cvm_instance_info"


def test_observation_spec_prefers_explicit_values_over_the_table():
    assert observation_spec("cvm_instance_info") == ("instances", "InstanceState")
    assert observation_spec("cvm_instance_info", list_field="data", state_field="Phase") == ("data", "Phase")


def test_observation_spec_has_no_defaults_for_unknown_modules():
    assert observation_spec("cls_topic_info") == (None, None)


def test_lookup_path_walks_nested_dictionaries():
    payload = {"data": {"items": [{"Phase": "Ready"}]}}
    assert lookup_path(payload, "data.items") == [{"Phase": "Ready"}]
    assert lookup_path(payload, "data.missing") is None
    assert lookup_path(payload, "") is None
    assert lookup_path("not-a-dict", "data") is None


def test_observed_states_maps_every_resource():
    result = {"instances": [{"InstanceState": "RUNNING"}, {"InstanceState": "PENDING"}]}
    assert observed_states(result, "instances", "InstanceState") == ["RUNNING", "PENDING"]


def test_observed_states_is_empty_when_the_list_field_is_absent():
    assert observed_states({"total_count": 0}, "instances", "InstanceState") == []
    assert observed_states({"instances": None}, "instances", "InstanceState") == []


def test_matches_requires_a_non_empty_observation():
    # An empty list means the read API cannot see the resource yet, which is
    # not the same as the resource being ready.
    assert matches([], "RUNNING") is False
    assert matches(["RUNNING"], "RUNNING") is True
    assert matches(["RUNNING", "RUNNING"], "RUNNING") is True
    assert matches(["RUNNING", "PENDING"], "RUNNING") is False


def test_matches_compares_states_as_strings():
    assert matches([1], "1") is True
    assert matches([None], "RUNNING") is False


def test_matches_absent_accepts_an_empty_observation():
    assert matches([], ABSENT) is True
    assert matches(["absent"], ABSENT) is True
    assert matches(["RUNNING"], ABSENT) is False


def test_positive_int_rejects_zero_negative_and_junk():
    assert positive_int("30", "delay") == 30
    assert positive_int(30, "delay") == 30
    for bad in (0, -1, "abc", None):
        with pytest.raises(AnsibleActionFail):
            positive_int(bad, "delay")


# --------------------------------------------------------------------------
# run(): the happy path
# --------------------------------------------------------------------------


def test_waits_until_the_state_is_reported():
    action, calls = build_action(
        {"module": "cvm_instance_info", "args": REGION, "state": "RUNNING", "delay": 5, "timeout": 60},
        [{"instances": [{"InstanceState": "PENDING"}]}, {"instances": [{"InstanceState": "RUNNING"}]}],
    )
    result = action.run(task_vars={})
    assert result["changed"] is False
    assert result["attempts"] == 2
    assert result["waited"] == 5
    assert result["observed_states"] == ["RUNNING"]
    assert result["result"]["instances"][0]["InstanceState"] == "RUNNING"
    assert "reported InstanceState=RUNNING" in result["msg"]
    assert len(calls) == 2


def test_every_poll_uses_the_fully_qualified_module_name_and_same_args():
    args = {"module": "cbs_disk_info", "args": {"region": "ap-guangzhou", "disk_ids": ["disk-1"]}, "state": "ATTACHED"}
    action, calls = build_action(args, [{"disks": [{"DiskState": "ATTACHED"}]}])
    action.run(task_vars={})
    assert calls[0]["module_name"] == "susunola.tencentcloud.cbs_disk_info"
    assert calls[0]["module_args"] == {"region": "ap-guangzhou", "disk_ids": ["disk-1"]}


def test_an_explicit_fqcn_is_used_as_given():
    action, calls = build_action(
        {"module": "susunola.tencentcloud.tke_cluster_info", "args": REGION, "state": "Running"},
        [{"clusters": [{"ClusterStatus": "Running"}]}],
    )
    action.run(task_vars={})
    assert calls[0]["module_name"] == "susunola.tencentcloud.tke_cluster_info"


def test_an_empty_observation_keeps_polling():
    action, calls = build_action(
        {"module": "cvm_instance_info", "args": REGION, "state": "RUNNING", "delay": 1, "timeout": 30},
        [{"instances": [], "total_count": 0}, {"instances": [{"InstanceState": "RUNNING"}]}],
    )
    result = action.run(task_vars={})
    assert result["attempts"] == 2
    assert len(calls) == 2


def test_all_resources_must_reach_the_state():
    action, calls = build_action(
        {"module": "cvm_instance_info", "args": REGION, "state": "RUNNING", "delay": 1, "timeout": 30},
        [
            {"instances": [{"InstanceState": "RUNNING"}, {"InstanceState": "PENDING"}]},
            {"instances": [{"InstanceState": "RUNNING"}, {"InstanceState": "RUNNING"}]},
        ],
    )
    result = action.run(task_vars={})
    assert result["attempts"] == 2
    assert result["observed_states"] == ["RUNNING", "RUNNING"]


def test_absent_matches_immediately_when_nothing_is_reported():
    action, calls = build_action(
        {"module": "cdb_instance_info", "args": REGION, "state": "absent"},
        [{"instances": [], "total_count": 0}],
    )
    result = action.run(task_vars={})
    assert result["attempts"] == 1
    assert result["observed_states"] == []
    assert len(calls) == 1


def test_numeric_states_are_matched_as_strings():
    # The CLB Status field is an integer; the option is a string.
    action, _calls = build_action(
        {"module": "clb_load_balancer_info", "args": REGION, "state": 1},
        [{"load_balancers": [{"Status": 1}]}],
    )
    result = action.run(task_vars={})
    assert result["observed_states"] == [1]


def test_explicit_fields_override_the_shipped_table():
    action, _calls = build_action(
        {
            "module": "cvm_instance_info",
            "args": REGION,
            "state": "Ready",
            "list_field": "data.items",
            "state_field": "Phase",
        },
        [{"data": {"items": [{"Phase": "Ready"}]}}],
    )
    result = action.run(task_vars={})
    assert result["observed_states"] == ["Ready"]


def test_a_module_outside_the_table_works_with_explicit_fields():
    action, _calls = build_action(
        {
            "module": "cls_topic_info",
            "args": REGION,
            "state": "1",
            "list_field": "topics",
            "state_field": "Status",
        },
        [{"topics": [{"Status": "1"}]}],
    )
    assert action.run(task_vars={})["observed_states"] == ["1"]


# --------------------------------------------------------------------------
# run(): failures
# --------------------------------------------------------------------------


def test_timeout_reports_what_was_observed():
    action, calls = build_action(
        {"module": "cvm_instance_info", "args": REGION, "state": "RUNNING", "delay": 10, "timeout": 20},
        [{"instances": [{"InstanceState": "PENDING"}]}],
    )
    with pytest.raises(AnsibleActionFail) as excinfo:
        action.run(task_vars={})
    payload = excinfo.value.result
    assert payload["failed"] is True
    assert "Timed out after 20s" in payload["msg"]
    assert payload["module"] == "susunola.tencentcloud.cvm_instance_info"
    assert payload["state"] == "RUNNING"
    assert payload["state_field"] == "InstanceState"
    assert payload["list_field"] == "instances"
    assert payload["attempts"] == 2
    assert payload["waited"] == 20
    assert payload["observed_states"] == ["PENDING"]
    assert payload["last_result"]["instances"][0]["InstanceState"] == "PENDING"
    assert len(calls) == 2


def test_a_module_without_a_table_entry_is_rejected_before_polling():
    action, calls = build_action({"module": "cls_topic_info", "args": REGION, "state": "1"}, [{}])
    with pytest.raises(AnsibleActionFail) as excinfo:
        action.run(task_vars={})
    assert "no observation table entry" in excinfo.value.result["msg"]
    assert calls == []


def test_a_failed_observation_fails_the_task():
    action, calls = build_action(
        {"module": "cvm_instance_info", "args": REGION, "state": "RUNNING"},
        [{"failed": True, "msg": "AuthFailure.SignatureFailure"}],
    )
    with pytest.raises(AnsibleActionFail) as excinfo:
        action.run(task_vars={})
    assert "AuthFailure.SignatureFailure" in excinfo.value.result["msg"]
    assert excinfo.value.result["last_result"]["failed"] is True
    assert len(calls) == 1


def test_module_is_required():
    action, _calls = build_action({"state": "RUNNING"}, [{}])
    with pytest.raises(AnsibleActionFail) as excinfo:
        action.run(task_vars={})
    assert "requires 'module'" in excinfo.value.result["msg"]


def test_state_is_required():
    action, _calls = build_action({"module": "cvm_instance_info"}, [{}])
    with pytest.raises(AnsibleActionFail) as excinfo:
        action.run(task_vars={})
    assert "requires 'state'" in excinfo.value.result["msg"]


def test_args_must_be_a_dictionary():
    action, _calls = build_action({"module": "cvm_instance_info", "args": ["region"], "state": "RUNNING"}, [{}])
    with pytest.raises(AnsibleActionFail) as excinfo:
        action.run(task_vars={})
    assert "must be a dictionary" in excinfo.value.result["msg"]


def test_zero_delay_is_rejected():
    action, calls = build_action({"module": "cvm_instance_info", "args": REGION, "state": "RUNNING", "delay": 0}, [{}])
    with pytest.raises(AnsibleActionFail) as excinfo:
        action.run(task_vars={})
    assert "must be greater than zero" in excinfo.value.result["msg"]
    assert calls == []


def test_unknown_options_are_rejected():
    # _VALID_ARGS makes the base class catch typos before any polling.
    action, calls = build_action(
        {"module": "cvm_instance_info", "args": REGION, "state": "RUNNING", "timeouts": 30},
        [{}],
    )
    with pytest.raises(AnsibleActionFail) as excinfo:
        action.run(task_vars={})
    assert "Invalid options" in excinfo.value.result["msg"]
    assert calls == []


# --------------------------------------------------------------------------
# run(): check mode
# --------------------------------------------------------------------------


def test_check_mode_observes_once_without_waiting():
    action, calls = build_action(
        {"module": "cvm_instance_info", "args": REGION, "state": "RUNNING", "delay": 10, "timeout": 600},
        [{"instances": [{"InstanceState": "PENDING"}]}],
        check_mode=True,
    )
    result = action.run(task_vars={})
    assert result["changed"] is False
    assert result["attempts"] == 1
    assert result["waited"] == 0
    assert result["observed_states"] == ["PENDING"]
    assert "check mode" in result["msg"]
    assert len(calls) == 1


# --------------------------------------------------------------------------
# The shipped observation table
# --------------------------------------------------------------------------


def test_table_covers_the_documented_state_fields():
    assert OBSERVATION_SPECS["cvm_instance_info"] == ("instances", "InstanceState")
    assert OBSERVATION_SPECS["tke_cluster_info"] == ("clusters", "ClusterStatus")
    assert OBSERVATION_SPECS["clb_load_balancer_info"] == ("load_balancers", "Status")
    assert OBSERVATION_SPECS["cbs_disk_info"] == ("disks", "DiskState")
    assert OBSERVATION_SPECS["redis_instance_info"] == ("instances", "Status")
    assert OBSERVATION_SPECS["cdb_instance_info"] == ("instances", "Status")
    assert OBSERVATION_SPECS["scf_function_info"] == ("functions", "Status")
    assert OBSERVATION_SPECS["lighthouse_instance_info"] == ("instances", "InstanceState")


#: module -> (SDK package, model of one resource in the module's result list).
#: Derived from the response member each module pages: DescribeDisksResponse
#: DiskSet, DescribeDBInstancesResponse Items, DescribeLoadBalancersResponse
#: LoadBalancerSet, DescribeInstancesResponse InstanceSet (CVM, Lighthouse and
#: Redis), ListFunctionsResponse Functions, DescribeClustersResponse Clusters.
SDK_RESOURCE_MODELS = {
    "cbs_disk_info": ("cbs.v20170312", "Disk"),
    "cdb_instance_info": ("cdb.v20170320", "InstanceInfo"),
    "clb_load_balancer_info": ("clb.v20180317", "LoadBalancer"),
    "cvm_instance_info": ("cvm.v20170312", "Instance"),
    "lighthouse_instance_info": ("lighthouse.v20200324", "Instance"),
    "redis_instance_info": ("redis.v20180412", "InstanceSet"),
    "scf_function_info": ("scf.v20180416", "Function"),
    "tke_cluster_info": ("tke.v20180525", "Cluster"),
}


@pytest.mark.parametrize("module", sorted(SDK_RESOURCE_MODELS))
def test_state_field_still_exists_on_the_sdk_resource_model(module):
    # Guards the table against an SDK rename: the plugin matches on the raw
    # serialized field name, so a rename would silently wait forever.
    pytest.importorskip("tencentcloud")
    package, model_name = SDK_RESOURCE_MODELS[module]
    models = importlib.import_module("tencentcloud.%s.models" % package)
    model = getattr(models, model_name)
    fields = model()._serialize(allow_none=True)
    _list_field, state_field = OBSERVATION_SPECS[module]
    assert state_field in fields, "%s lost %s" % (model_name, state_field)
