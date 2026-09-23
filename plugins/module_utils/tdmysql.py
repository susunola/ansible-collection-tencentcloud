# -*- coding: utf-8 -*-
"""Shared TDSQL MySQL read-side helpers.

The account, backup-policy and parameter modules need the same describe-side
request builders and response processors from both their write and ``_info``
module. Ansible collection modules must be self-contained (a module may not
import a sibling module), so the shared pure helpers live here and both sides
import them.  Only request-building and response-shaping code lives here; the
``client.<Action>`` SDK calls stay in the module files so the static CAM
action manifest keeps attributing operations to the modules that issue them.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type


def _load():
    from tencentcloud.tdmysql.v20211122 import models, tdmysql_client

    return models, tdmysql_client


def users_request(models, instance_id):
    request = models.DescribeUsersRequest()
    request.InstanceId = instance_id
    return request


def privileges_request(models, p):
    request = models.DescribeUserPrivilegesRequest()
    request.InstanceId, request.UserName, request.Host = p["instance_id"], p["username"], p["host"]
    request.DbName, request.ObjectType, request.Object, request.ColName = "*", "*", "*", "*"
    return request


def account_items(response):
    return [item._serialize(allow_none=True) for item in response.Users or []]


def backup_policy_describe_request(models, instance_id):
    request = models.DescribeDBSBackupPolicyRequest()
    request.InstanceId = instance_id
    return request


def normalize(value):
    result = dict(value or {})
    for key in ("EnableFull", "EnableLog"):
        if result.get(key) is not None:
            result[key] = bool(result[key])
    return result


def parameter_describe_request(models, instance_id):
    request = models.DescribeDBParametersRequest()
    request.InstanceId = instance_id
    return request


def parameter_map(response):
    return {item.Param: item._serialize(allow_none=True) for item in response.Params or []}


def selected(current, names):
    return {name: current[name] for name in sorted(names) if name in current}
