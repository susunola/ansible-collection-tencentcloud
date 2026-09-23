# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Wait for the resources an ``_info`` module reports to reach a state."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: tc_wait
short_description: Wait until Tencent Cloud resources reach a state
version_added: "1.2.0"
description:
  - Runs a C(susunola.tencentcloud) C(_info) module repeatedly until every
    resource it reports carries the requested state, then returns.
  - This is an action plugin because a module cannot invoke another module.
    The observation loop runs on the controller and every poll is a nested
    call to the C(_info) module named in O(module).
  - Use it when the write module that created the resource has no wait option
    of its own, or when the state you need is only visible through a different
    module's read API. When the write module does wait for you, prefer that
    option, because it waits inside one module call instead of re-invoking a
    module on every poll.
  - Waiting is read-only, so the task never reports C(changed). In check mode
    the module is observed once and no polling happens.
  - For a condition the shipped observation table cannot express, use
    O(state_field) with O(list_field), or run the C(_info) module with
    M(ansible.builtin.until) instead of this plugin.
options:
  module:
    description:
      - Name of the C(_info) module to poll.
      - A short name is resolved inside this collection, so C(cvm_instance_info)
        and C(susunola.tencentcloud.cvm_instance_info) are equivalent.
    type: str
    required: true
  args:
    description:
      - Arguments passed to O(module) unchanged on every poll.
      - This plugin reads no credentials itself. Supply them here, or rely on
        the C(TENCENTCLOUD_*) environment variables and the TCCLI profile that
        O(module) already understands.
    type: dict
    default: {}
  state:
    description:
      - State that every reported resource must carry before the task returns.
      - Compared as a string against the field named by O(state_field), so a
        numeric state such as the CLB C(Status) field is written quoted, as in
        C('1').
      - The keyword C(absent) matches a poll that reports no resource at all,
        which is how you wait for a deletion.
      - A poll that reports no resource never matches any other state, so
        waiting for a resource that has just been created keeps polling until
        the read API can see it.
    type: str
    required: true
  state_field:
    description:
      - Dotted path inside each reported resource to the field holding its
        state, for example C(InstanceState).
      - Defaults to the value this collection ships for O(module) when it knows
        the module. Set it explicitly for any module outside that table.
    type: str
  list_field:
    description:
      - Dotted path inside the module result to the list of resources.
      - Defaults to the value this collection ships for O(module) when it knows
        the module. Set it explicitly for any module outside that table.
    type: str
  delay:
    description: Seconds to sleep between polls.
    type: int
    default: 10
  timeout:
    description: Total seconds to keep polling before the task fails.
    type: int
    default: 300
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create an instance and wait until its state is visible
  block:
    - name: Create the instance
      susunola.tencentcloud.cvm_instance:
        region: ap-guangzhou
        instance_name: web-1
        image_id: img-xxxxxxxx
        instance_type: S5.MEDIUM4
      register: created

    - name: Wait for the new instance to report RUNNING
      susunola.tencentcloud.tc_wait:
        module: cvm_instance_info
        args:
          region: ap-guangzhou
          instance_ids:
            - "{{ created.instance.InstanceId }}"
        state: RUNNING
        timeout: 600
        delay: 15

- name: Wait for a cluster and reuse the observation
  susunola.tencentcloud.tc_wait:
    module: tke_cluster_info
    args:
      region: ap-guangzhou
      cluster_ids: ["{{ cluster_id }}"]
    state: Running
    timeout: 900
  register: cluster_wait

- name: Wait until a disk is detached
  susunola.tencentcloud.tc_wait:
    module: cbs_disk_info
    args:
      region: ap-guangzhou
      disk_ids: ["{{ disk_id }}"]
    state: UNATTACHED

- name: Wait for a deletion to be visible
  susunola.tencentcloud.tc_wait:
    module: cdb_instance_info
    args:
      region: ap-guangzhou
      instance_ids: ["{{ doomed_instance_id }}"]
    state: absent
    timeout: 900

- name: Wait on a module outside the shipped observation table
  susunola.tencentcloud.tc_wait:
    module: cls_topic_info
    args:
      region: ap-guangzhou
    state: "1"
    list_field: topics
    state_field: Status
'''

RETURN = r'''
changed:
  description: Always C(false); waiting only reads.
  returned: always
  type: bool
attempts:
  description: How many times the C(_info) module was invoked.
  returned: always
  type: int
waited:
  description: Seconds slept between polls.
  returned: always
  type: int
observed_states:
  description:
    - The state field of every resource in the last poll, in module order.
    - Empty when the last poll reported no resource.
  returned: always
  type: list
  elements: raw
result:
  description: The complete result of the last C(_info) invocation.
  returned: always
  type: dict
msg:
  description: Human-readable summary of what was waited for.
  returned: always
  type: str
'''

from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase

from ansible_collections.susunola.tencentcloud.plugins.plugin_utils.polling import (
    poll_until,
)

COLLECTION_NAME = "susunola.tencentcloud"

DEFAULT_DELAY = 10
DEFAULT_TIMEOUT = 300

#: State keyword that matches a poll reporting no resource at all.
ABSENT = "absent"

#: Observation table for the modules this plugin knows without extra options:
#: module short name -> (list field in the result, state field in a resource).
#: Every entry was read off the installed SDK response model, and
#: ``tests/unit/plugins/action/test_tc_wait.py`` re-checks the field names
#: against the same models so an SDK rename cannot pass silently.
OBSERVATION_SPECS = {
    "cbs_disk_info": ("disks", "DiskState"),
    "cdb_instance_info": ("instances", "Status"),
    "clb_load_balancer_info": ("load_balancers", "Status"),
    "cvm_instance_info": ("instances", "InstanceState"),
    "lighthouse_instance_info": ("instances", "InstanceState"),
    "redis_instance_info": ("instances", "Status"),
    "scf_function_info": ("functions", "Status"),
    "tke_cluster_info": ("clusters", "ClusterStatus"),
}


def fully_qualified(module):
    """Return the FQCN of ``module``, resolving short names in this collection."""
    if "." in module:
        return module
    return "%s.%s" % (COLLECTION_NAME, module)


def short_name(module):
    """Return the last component of a module name, which keys the table."""
    return module.rsplit(".", 1)[-1]


def observation_spec(module, list_field=None, state_field=None):
    """Return the ``(list_field, state_field)`` pair to use for one poll.

    Explicit values win over the shipped table, so any module can be observed
    without editing this plugin.
    """
    default_list, default_state = OBSERVATION_SPECS.get(short_name(module), (None, None))
    return list_field or default_list, state_field or default_state


def lookup_path(value, path):
    """Walk a dotted path through dictionaries; None as soon as it is absent."""
    for step in (path or "").split("."):
        if not step or not isinstance(value, dict):
            return None
        value = value.get(step)
        if value is None:
            return None
    return value


def observed_states(result, list_field, state_field):
    """Return the state of every resource in one module result."""
    resources = lookup_path(result, list_field)
    if not isinstance(resources, list):
        return []
    return [lookup_path(resource, state_field) for resource in resources]


def matches(states, desired):
    """Return True when every observed state equals ``desired``.

    An empty observation matches only the ``absent`` keyword: a resource that
    the read API cannot see yet is not ready, but it is also not present.
    """
    if desired == ABSENT:
        return not states or all(str(state) == ABSENT for state in states)
    return bool(states) and all(str(state) == desired for state in states)


def _fail(message, **extra):
    """Fail the task with a payload that carries ``msg`` on every ansible-core.

    ansible-core 2.21.3 moved action failures onto ``UnifiedTaskResult`` and
    passes the ``result`` dict through untouched, where 2.21.2 and earlier
    merged the message into it as ``msg``. A bare
    ``AnsibleActionFail(message)`` therefore surfaces as an empty payload on
    the newer core, so the plugin supplies ``failed`` and ``msg`` itself and
    the task result is identical on both.
    """
    payload = {"failed": True, "msg": message}
    payload.update(extra)
    raise AnsibleActionFail(message, result=payload)


def positive_int(value, name):
    """Coerce an action-plugin option to a positive int or fail the task."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        _fail("tc_wait '%s' must be an integer, got %r" % (name, value))
    if number <= 0:
        _fail("tc_wait '%s' must be greater than zero, got %r" % (name, value))
    return number


class ActionModule(ActionBase):

    _VALID_ARGS = frozenset(["module", "args", "state", "state_field", "list_field", "delay", "timeout"])

    def run(self, tmp=None, task_vars=None):
        result = super(ActionModule, self).run(tmp, task_vars)
        args = self._task.args

        module = args.get("module")
        if not module:
            _fail("tc_wait requires 'module'")
        module_name = fully_qualified(module)

        module_args = args.get("args") or {}
        if not isinstance(module_args, dict):
            _fail("tc_wait 'args' must be a dictionary of arguments for %s" % module_name)

        desired = args.get("state")
        if desired is None:
            _fail("tc_wait requires 'state'")
        desired = str(desired)

        delay = positive_int(args.get("delay", DEFAULT_DELAY), "delay")
        timeout = positive_int(args.get("timeout", DEFAULT_TIMEOUT), "timeout")

        list_field, state_field = observation_spec(module, args.get("list_field"), args.get("state_field"))
        if not list_field or not state_field:
            _fail(
                "tc_wait has no observation table entry for %r; set list_field and state_field explicitly"
                % module
            )

        def poll():
            observed = self._execute_module(module_name=module_name, module_args=module_args, task_vars=task_vars)
            if not isinstance(observed, dict):
                _fail("tc_wait: %s returned no result" % module_name)
            if observed.get("failed"):
                _fail(
                    "%s failed while tc_wait was observing it: %s" % (module_name, observed.get("msg", "no message")),
                    module=module_name,
                    last_result=observed,
                )
            return observed

        def is_done(observed):
            return matches(observed_states(observed, list_field, state_field), desired)

        if self._task.check_mode:
            # Waiting is pointless without writes, but one read is cheap and
            # tells the operator what the state would have been.
            observed = poll()
            self._display.vvv("tc_wait: check mode, observed %s without waiting" % module_name)
            result.update(
                changed=False,
                attempts=1,
                waited=0,
                observed_states=observed_states(observed, list_field, state_field),
                result=observed,
                msg="check mode: observed %s once and did not wait for state %s" % (module_name, desired),
            )
            return result

        outcome = poll_until(poll, is_done, timeout, delay)
        states = observed_states(outcome.value, list_field, state_field)
        if not outcome.matched:
            _fail(
                "Timed out after %ss waiting for %s to report %s=%s (%s polls); last observed states: %s"
                % (outcome.waited, module_name, state_field, desired, outcome.attempts, states),
                module=module_name,
                state=desired,
                state_field=state_field,
                list_field=list_field,
                attempts=outcome.attempts,
                waited=outcome.waited,
                observed_states=states,
                last_result=outcome.value,
            )
        self._display.vvv(
            "tc_wait: %s reached %s=%s after %s polls" % (module_name, state_field, desired, outcome.attempts)
        )
        result.update(
            changed=False,
            attempts=outcome.attempts,
            waited=outcome.waited,
            observed_states=states,
            result=outcome.value,
            msg="%s reported %s=%s after %s polls" % (module_name, state_field, desired, outcome.attempts),
        )
        return result
