#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: teo_security_bot_lite
short_description: Manage Tencent Cloud EdgeOne basic Bot protection
version_added: "0.14.0"
description: Manages CAPTCHA page and AI crawler detection without modifying other EdgeOne security policy modules.
options:
  zone_id: {type: str, required: true, description: EdgeOne zone ID.}
  scope: {type: str, choices: [zone, template, host], default: zone, description: Security policy scope.}
  template_id: {type: str, description: Web security template ID required for template scope.}
  host: {type: str, description: Acceleration domain required for host scope.}
  captcha_page_enabled: {type: bool, default: false, description: Enable the human-verification page.}
  ai_crawler_enabled: {type: bool, default: false, description: Enable AI crawler detection.}
  ai_crawler_action: {type: str, choices: [Deny, Monitor, Allow, Challenge], default: Monitor, description: Action applied to detected AI crawlers.}
  challenge_option: {type: str, choices: [JSChallenge, ManagedChallenge], default: ManagedChallenge, description: Challenge type when AI crawler action is Challenge.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Challenge AI crawlers on a security template
  susunola.tencentcloud.teo_security_bot_lite:
    region: ap-guangzhou
    zone_id: zone-xxxxxxxx
    scope: template
    template_id: temp-xxxxxxxx
    captcha_page_enabled: true
    ai_crawler_enabled: true
    ai_crawler_action: Challenge
    challenge_option: ManagedChallenge
'''

RETURN = r'''bot_lite: {description: Current normalized basic Bot protection configuration., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.teo.v20220901 import models, teo_client
    return models, teo_client


def _scope(request, p):
    request.ZoneId = p["zone_id"]; request.Entity = {"zone": "ZoneDefaultPolicy", "template": "Template", "host": "Host"}[p["scope"]]
    if p["scope"] == "template": request.TemplateId = p["template_id"]
    if p["scope"] == "host": request.Host = p["host"]
    return request


def describe_request(models, p): return _scope(models.DescribeSecurityPolicyRequest(), p)


def update_request(models, p):
    captcha = models.CAPTCHAPageChallenge(); captcha.Enabled = "on" if p["captcha_page_enabled"] else "off"
    crawler = models.AICrawlerDetection(); crawler.Enabled = "on" if p["ai_crawler_enabled"] else "off"
    if p["ai_crawler_enabled"]:
        action = models.SecurityAction(); action.Name = p["ai_crawler_action"]
        if p["ai_crawler_action"] == "Challenge":
            params = models.ChallengeActionParameters(); params.ChallengeOption = p["challenge_option"]; action.ChallengeActionParameters = params
        crawler.Action = action
    bot = models.BotManagementLite(); bot.CAPTCHAPageChallenge, bot.AICrawlerDetection = captcha, crawler
    policy = models.SecurityPolicy(); policy.BotManagementLite = bot
    request = _scope(models.ModifySecurityPolicyRequest(), p); request.SecurityPolicy = policy; return request


def desired(p): return {"captcha_page_enabled": p["captcha_page_enabled"], "ai_crawler_enabled": p["ai_crawler_enabled"], "ai_crawler_action": p["ai_crawler_action"], "challenge_option": p["challenge_option"]}


def normalize(raw):
    captcha = raw.get("CAPTCHAPageChallenge") or {}; crawler = raw.get("AICrawlerDetection") or {}; action = crawler.get("Action") or {}
    return {"captcha_page_enabled": captcha.get("Enabled") == "on", "ai_crawler_enabled": crawler.get("Enabled") == "on", "ai_crawler_action": action.get("Name") or "Monitor", "challenge_option": (action.get("ChallengeActionParameters") or {}).get("ChallengeOption") or "ManagedChallenge"}


def run_module():
    module = TencentCloudModule(argument_spec={"zone_id": {"required": True}, "scope": {"choices": ["zone", "template", "host"], "default": "zone"}, "template_id": {}, "host": {}, "captcha_page_enabled": {"type": "bool", "default": False}, "ai_crawler_enabled": {"type": "bool", "default": False}, "ai_crawler_action": {"choices": ["Deny", "Monitor", "Allow", "Challenge"], "default": "Monitor"}, "challenge_option": {"choices": ["JSChallenge", "ManagedChallenge"], "default": "ManagedChallenge"}}, supports_check_mode=True)
    p = module.params
    if p["scope"] == "template" and not p.get("template_id"): module.fail_json(msg="template_id is required for template scope")
    if p["scope"] == "host" and not p.get("host"): module.fail_json(msg="host is required for host scope")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TeoClient, "teo.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeSecurityPolicy, describe_request(models, p)); raw = response.SecurityPolicy.BotManagementLite._serialize(allow_none=True) if response.SecurityPolicy and response.SecurityPolicy.BotManagementLite else {}
        before, target = normalize(raw), desired(p)
        if before == target: module.exit_json(changed=False, bot_lite=before)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifySecurityPolicy, update_request(models, p)); response = module.sdk_call(client.DescribeSecurityPolicy, describe_request(models, p)); before = normalize(response.SecurityPolicy.BotManagementLite._serialize(allow_none=True))
        module.exit_json(changed=True, **(diff or {}), bot_lite=before if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
