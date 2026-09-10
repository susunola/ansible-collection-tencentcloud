# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Jinja filters for Tencent Cloud tag payloads.

The collection sees tags in three shapes: the ``{key: value}`` mapping a
module parameter takes, the ``{"Key": ..., "Value": ...}`` shape Tencent Cloud
APIs speak, and the list of those an ``*_info`` module returns. Playbooks that
combine tags from several of those places had no way to merge them, because
``ansible.builtin.combine`` only understands mappings.

``tag_merge`` is a thin wrapper over
:func:`ansible_collections.susunola.tencentcloud.plugins.module_utils.tagging.merge_tags`,
imported through ``plugin_utils`` like every other controller-side plugin in
this collection. The reading and normalization semantics stay in
``module_utils`` so the filter and the resource modules agree by construction.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: tag_merge
short_description: Merge Tencent Cloud tag sources into one mapping
version_added: "1.2.0"
description:
  - Merges any number of tag sources into a single mapping of C(key) to
    C(value), with later sources overriding earlier ones.
  - Accepts every tag shape this collection already deals with, so the
    C(tags) parameter of a resource module can be combined with the tags an
    C(*_info) module reported without converting either side first.
  - The result is sorted by key and holds string values, which is what the
    resource modules compute for their C(tags) parameter, so the result can
    be passed straight back into a module or compared against one.
positional: _input, _additional
options:
  _input:
    description:
      - The first tag source.
      - Accepts a C(dict) tag mapping, a single C(Key)/C(Value) tag, a C(list)
        of tags, a C(list) of SDK C(Tag) objects, a nested C(list) of any of
        those, or C(None) for no tags at all.
      - May be omitted, which is how a C(list) of sources is merged without
        naming any of them.
    type: raw
    required: false
  _additional:
    description:
      - Further tag sources, merged left to right after the first. The last
        source that sets a key wins, matching C(dict.update) and
        C(ansible.builtin.combine).
      - A source of an unsupported type (a string, a number) fails the task
        instead of being skipped, so a tag is never dropped silently.
    type: raw
    required: false
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read the tags an instance already carries
  susunola.tencentcloud.cvm_instance_info:
    instance_ids:
      - ins-xxxxxxxx
  register: cvm

- name: Add the environment tags without losing the instance's own tags
  vars:
    env_tags:
      environment: production
      owner: platform-team
  ansible.builtin.set_fact:
    instance_tags: "{{ cvm.instances[0].Tags | susunola.tencentcloud.tag_merge(env_tags) }}"

- name: Merge a list of sources in a single expression
  vars:
    common_tags:
      managed_by: ansible
    local_tags:
      environment: production
  ansible.builtin.debug:
    msg: "{{ [common_tags, cvm.instances[0].Tags, local_tags] | susunola.tencentcloud.tag_merge }}"

- name: A variable that may be unset contributes nothing
  ansible.builtin.debug:
    msg: "{{ extra_tags | default({}) | susunola.tencentcloud.tag_merge({'managed_by': 'ansible'}) }}"
'''

RETURN = r'''
_value:
  description:
    - The merged tags, sorted by key, with every key and value coerced to a
      string.
  type: dict
  returned: success
'''

from ansible.errors import AnsibleFilterError

from ansible_collections.susunola.tencentcloud.plugins.plugin_utils.tags import (
    merge_tags,
)


def tag_merge(*sources):
    """Merge tag sources of any accepted shape into one mapping.

    See the DOCUMENTATION block above and
    ``module_utils.tagging.merge_tags`` for the accepted shapes and the
    override order. The only work done here is turning the helper's
    ``TypeError`` into an ``AnsibleFilterError``, so an unsupported source
    fails the task with the filter named instead of a bare Python traceback.
    """
    try:
        return merge_tags(*sources)
    except TypeError as exc:
        raise AnsibleFilterError("tag_merge: %s" % exc) from exc


class FilterModule(object):
    """Tencent Cloud Jinja filters."""

    def filters(self):
        return {
            "tag_merge": tag_merge,
        }
