#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: apigateway_plugin
short_description: Create or delete a Tencent Cloud API Gateway plugin
version_added: "1.1.0"
description:
  - Creates or deletes a Tencent Cloud API Gateway (API GW) plugin, identified
    by its plugin name. The module is idempotent; it reads the current plugins
    before changing anything and matches on the plugin name. The plugin data is
    a JSON string whose shape depends on I(plugin_type).
  - All plugin configuration fields (C(PluginType), C(PluginData), C(Description),
    C(Tags)) are set directly on the C(CreatePluginRequest) object, so the
    request is built verbatim from the supplied arguments.
options:
  state:
    description: Desired state of the plugin.
    type: str
    choices: [present, absent]
    default: present
  plugin_name:
    description: User-defined plugin name (2-50 chars, a-z/A-Z/0-9/_).
    type: str
    required: true
  plugin_type:
    description:
      - Plugin type. One of C(IPControl), C(TrafficControl), C(Cors),
        C(CustomReq), C(CustomAuth), C(Routing), C(TrafficControlByParameter),
        C(CircuitBreaker), C(ProxyCache).
    type: str
  plugin_data:
    description: Plugin definition statement (JSON string); shape depends on I(plugin_type).
    type: str
  description:
    description: Plugin description (max 200 chars).
    type: str
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create an API GW IP-control plugin
  susunola.tencentcloud.apigateway_plugin:
    plugin_name: allow-office
    plugin_type: IPControl
    plugin_data: '{"type":"ALLOW","ipList":["10.0.0.0/8"]}'
    description: Allow office CIDR only

- name: Remove the plugin
  susunola.tencentcloud.apigateway_plugin:
    plugin_name: allow-office
    state: absent
'''

RETURN = r'''
plugin_name:
  description: Plugin name the operation targeted.
  returned: always
  type: str
plugin_id:
  description: Server-assigned plugin ID after a create, or the matched plugin ID.
  returned: always
  type: str
exists:
  description: Whether the plugin exists after the operation.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load():
    from tencentcloud.apigateway.v20180808 import apigateway_client, models
    return models, apigateway_client


def find_plugin(module, client, models, name):
    request = models.DescribePluginsRequest()
    request.PluginName = name
    request.Limit = 100
    request.Offset = 0
    response = module.sdk_call(client.DescribePlugins, request)
    summary = getattr(response, "Result", None)
    plugins = list(getattr(summary, "PluginSet", None) or [])
    for item in plugins:
        if getattr(item, "PluginName", None) == name:
            return item
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "plugin_name": {"type": "str", "required": True},
            "plugin_type": {"type": "str"},
            "plugin_data": {"type": "str"},
            "description": {"type": "str"},
        },
        required_if=[("state", "present", ("plugin_type", "plugin_data"))],
        supports_check_mode=True,
    )
    p = module.params
    name = p["plugin_name"]
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, apigateway_client = _load()
    client = module.create_client(apigateway_client.ApigatewayClient, "apigateway.tencentcloudapi.com")
    try:
        current = find_plugin(module, client, models, name)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                plugin_name=name,
                plugin_id=getattr(current, "PluginId", None),
                exists=bool(current),
                msg="API GW plugin already %s" % ("present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                plugin_name=name,
                plugin_id=None,
                exists=desired_present,
                msg="Would %s API GW plugin" % ("create" if desired_present else "delete"),
            )
        if desired_present:
            request = models.CreatePluginRequest()
            request.PluginName = name
            request.PluginType = p["plugin_type"]
            request.PluginData = p["plugin_data"]
            if p["description"] is not None:
                request.Description = p["description"]
            response = module.sdk_call(client.CreatePlugin, request)
            created_id = getattr(getattr(response, "Result", None), "PluginId", None)
        else:
            request = models.DeletePluginRequest()
            request.PluginId = getattr(current, "PluginId", None)
            module.sdk_call(client.DeletePlugin, request)
            created_id = None
        final = find_plugin(module, client, models, name)
        module.exit_json(
            changed=True,
            plugin_name=name,
            plugin_id=created_id if desired_present else (getattr(final, "PluginId", None) if final else None),
            exists=bool(final),
            msg="API GW plugin %s" % ("created" if desired_present else "deleted"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud API GW plugin request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
