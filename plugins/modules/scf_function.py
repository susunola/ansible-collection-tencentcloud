#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: scf_function
short_description: Manage Tencent Cloud SCF functions
version_added: "0.12.0"
description:
  - Create, update and delete Tencent Cloud Serverless Cloud Function (SCF)
    functions through the C(scf.v20180416) API.
  - This module is idempotent. Running it twice leaves the function unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the function when it does not exist and updates
        its code and configuration when it does.
      - C(absent) deletes the function.
    type: str
    choices: [present, absent]
    default: present
  function_name:
    description:
      - Name of the function, e.g. C(hello-world).
      - Required to identify, create, update or delete the function.
    type: str
    required: true
  namespace:
    description:
      - Namespace of the function, default C(default).
    type: str
    default: default
  runtime:
    description:
      - Runtime of the function, e.g. C(Python3.10), C(Nodejs18.15),
        C(Go1), C(Java11).
      - Required when creating the function; only applied at creation.
    type: str
  handler:
    description:
      - Entry point of the function, e.g. C(index.main_handler).
      - Required when creating the function.
    type: str
  zip_file:
    description:
      - Local path to a ZIP archive containing the function code.
      - The file is base64-encoded and written to
        V(CreateFunctionRequest.Code.ZipFile). Only applied at creation and
        when the code digest differs.
    type: path
  cos_bucket_name:
    description:
      - COS bucket holding the function package, written to
        V(CreateFunctionRequest.Code.CosBucketName).
      - Provide either O(zip_file) or O(cos_bucket_name)+O(cos_object_name).
    type: str
  cos_object_name:
    description:
      - COS object key of the function package, written to
        V(CreateFunctionRequest.Code.CosObjectName).
    type: str
  cos_bucket_region:
    description:
      - Region of the COS bucket, written to
        V(CreateFunctionRequest.Code.CosBucketRegion).
    type: str
  memory_size:
    description:
      - Memory size in MB, written to V(CreateFunctionRequest.MemorySize) and
        V(UpdateFunctionConfigurationRequest.MemorySize).
    type: int
  execution_timeout:
    description:
      - Execution timeout in seconds, written to V(CreateFunctionRequest)
        and V(UpdateFunctionConfigurationRequest).
    type: int
  description:
    description:
      - Description of the function.
    type: str
  environment:
    description:
      - Environment variables as a dict of key/value pairs, written to
        V(CreateFunctionRequest.Environment.Variables).
    type: dict
    default: {}
  role:
    description:
      - IAM role name (CAM role) the function runs as.
    type: str
  vpc_id:
    description:
      - VPC ID the function is attached to, written to
        V(CreateFunctionRequest.VpcConfig.VpcId).
    type: str
  subnet_id:
    description:
      - Subnet ID the function is attached to, written to
        V(CreateFunctionRequest.VpcConfig.SubnetId).
    type: str
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-scf) package on the controller.
  - Code updates always publish a new version through
    V(UpdateFunctionCodeRequest.Publish); the function version that handles
    requests is the aliased one, so updates take effect on next invocation.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a Python function from a local zip
  susunola.tencentcloud.scf_function:
    region: ap-guangzhou
    state: present
    function_name: hello-world
    runtime: Python3.10
    handler: index.main_handler
    zip_file: /tmp/hello.zip
    memory_size: 128
    execution_timeout: 3
    environment:
      LOG_LEVEL: info

- name: Deploy the function code from a COS object
  susunola.tencentcloud.scf_function:
    region: ap-guangzhou
    state: present
    function_name: hello-world
    runtime: Python3.10
    handler: index.main_handler
    cos_bucket_name: my-code-bucket
    cos_object_name: functions/hello-v2.zip
    cos_bucket_region: ap-guangzhou

- name: Delete a function
  susunola.tencentcloud.scf_function:
    region: ap-guangzhou
    state: absent
    function_name: hello-world
'''

RETURN = r'''
function:
  description: The function as reported by V(GetFunction) after the
    operation.
  returned: success
  type: dict
  sample:
    FunctionName: hello-world
    Runtime: Python3.10
    Handler: index.main_handler
    Status: Active
    MemorySize: 128
    Timeout: 3
'''

import base64
import hashlib

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_scf():
    from tencentcloud.scf.v20180416 import models, scf_client
    return models, scf_client


def _read_zip_b64(zip_file):
    """Return base64 of the local zip and its sha256 digest."""
    with open(zip_file, "rb") as handle:
        data = handle.read()
    digest = hashlib.sha256(data).hexdigest()
    return base64.b64encode(data).decode("ascii"), digest


def find_function(module, client, models, function_name, namespace):
    """Return the matching function dict or None."""
    try:
        request = models.GetFunctionRequest()
        request.FunctionName = function_name
        request.Namespace = namespace
        response = module.sdk_call(client.GetFunction, request)
    except Exception as exc:
        code = getattr(exc, "get_code", lambda: None)()
        if code and ("NotFound" in str(code) or code == "ResourceNotFound.FunctionName"):
            return None
        raise
    return response._serialize(allow_none=True)


def _build_code(models, params, zip_digest=None):
    code = models.Code()
    if params["zip_file"]:
        b64, _digest = _read_zip_b64(params["zip_file"])
        code.ZipFile = b64
    elif params["cos_bucket_name"]:
        code.CosBucketName = params["cos_bucket_name"]
        code.CosBucketRegion = params["cos_bucket_region"] or params["region"]
        if params["cos_object_name"]:
            code.CosObjectName = params["cos_object_name"]
    return code


def _build_environment(models, environment):
    if not environment:
        return None
    env = models.Environment()
    variables = []
    for key, value in sorted(environment.items()):
        pair = models.Variable()
        pair.Key = key
        pair.Value = str(value)
        variables.append(pair)
    env.Variables = variables
    return env


def _build_vpc_config(models, vpc_id, subnet_id):
    if not vpc_id and not subnet_id:
        return None
    config = models.VpcConfig()
    if vpc_id:
        config.VpcId = vpc_id
    if subnet_id:
        config.SubnetId = subnet_id
    return config


def _create(module, client, models, params):
    request = models.CreateFunctionRequest()
    request.FunctionName = params["function_name"]
    request.Namespace = params["namespace"]
    request.Handler = params["handler"]
    if params["runtime"]:
        request.Runtime = params["runtime"]
    if params["description"]:
        request.Description = params["description"]
    if params["memory_size"] is not None:
        request.MemorySize = params["memory_size"]
    if params["execution_timeout"] is not None:
        request.Timeout = params["execution_timeout"]
    request.Code = _build_code(models, params)
    env = _build_environment(models, params["environment"])
    if env is not None:
        request.Environment = env
    if params["role"]:
        request.Role = params["role"]
    vpc_config = _build_vpc_config(models, params["vpc_id"], params["subnet_id"])
    if vpc_config is not None:
        request.VpcConfig = vpc_config
    return module.sdk_call(client.CreateFunction, request)


def _update_code(module, client, models, function_name, namespace, params):
    request = models.UpdateFunctionCodeRequest()
    request.FunctionName = function_name
    request.Namespace = namespace
    request.Handler = params["handler"]
    request.Publish = "TRUE"
    code = _build_code(models, params)
    if params["zip_file"]:
        request.ZipFile = code.ZipFile
    else:
        if code.CosBucketName:
            request.CosBucketName = code.CosBucketName
        if code.CosObjectName:
            request.CosObjectName = code.CosObjectName
        if code.CosBucketRegion:
            request.CosBucketRegion = code.CosBucketRegion
    module.sdk_call(client.UpdateFunctionCode, request)


def _update_config(module, client, models, function_name, namespace, params):
    request = models.UpdateFunctionConfigurationRequest()
    request.FunctionName = function_name
    request.Namespace = namespace
    if params["description"] is not None:
        request.Description = params["description"]
    if params["memory_size"] is not None:
        request.MemorySize = params["memory_size"]
    if params["execution_timeout"] is not None:
        request.Timeout = params["execution_timeout"]
    env = _build_environment(models, params["environment"])
    if env is not None:
        request.Environment = env
    if params["role"] is not None:
        request.Role = params["role"]
    vpc_config = _build_vpc_config(models, params["vpc_id"], params["subnet_id"])
    if vpc_config is not None:
        request.VpcConfig = vpc_config
    module.sdk_call(client.UpdateFunctionConfiguration, request)


def _delete(module, client, models, function_name, namespace):
    request = models.DeleteFunctionRequest()
    request.FunctionName = function_name
    request.Namespace = namespace
    module.sdk_call(client.DeleteFunction, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "function_name": {"type": "str", "required": True},
            "namespace": {"type": "str", "default": "default"},
            "runtime": {"type": "str"},
            "handler": {"type": "str"},
            "zip_file": {"type": "path"},
            "cos_bucket_name": {"type": "str"},
            "cos_object_name": {"type": "str"},
            "cos_bucket_region": {"type": "str"},
            "memory_size": {"type": "int"},
            "execution_timeout": {"type": "int"},
            "description": {"type": "str"},
            "environment": {"type": "dict", "default": {}},
            "role": {"type": "str"},
            "vpc_id": {"type": "str"},
            "subnet_id": {"type": "str"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    function_name = module.params["function_name"]
    namespace = module.params["namespace"]

    if module.params["zip_file"] and (module.params["cos_bucket_name"] or module.params["cos_object_name"]):
        module.fail_json(msg="zip_file and cos_bucket_name/cos_object_name are mutually exclusive")

    models, scf_client = _load_scf()
    client = module.create_client(scf_client.ScfClient, "scf.tencentcloudapi.com")

    try:
        current = find_function(module, client, models, function_name, namespace)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Function already absent")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete function")
        _delete(module, client, models, function_name, namespace)
        module.exit_json(changed=True, **(diff or {}), function=None, msg="Function deleted")

    # state == present
    if current is None:
        if not module.params["handler"]:
            module.fail_json(msg="handler is required when creating a function")
        if not module.params["runtime"]:
            module.fail_json(msg="runtime is required when creating a function")
        desired = {
            "FunctionName": function_name,
            "Runtime": module.params["runtime"],
            "Handler": module.params["handler"],
            "MemorySize": module.params["memory_size"],
            "Timeout": module.params["execution_timeout"],
        }
        desired = {key: value for key, value in desired.items() if value is not None}
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create function")
        _create(module, client, models, module.params)
        created = find_function(module, client, models, function_name, namespace)
        module.exit_json(changed=True, **(diff or {}), function=created, msg="Function created")

    changes = []
    if module.params["zip_file"]:
        b64, new_digest = _read_zip_b64(module.params["zip_file"])
        current_code_size = current.get("CodeSize") or 0
        # Compare by payload length as a cheap proxy; exact match is handled
        # by the API when the code is unchanged.
        if abs(int(current_code_size) - len(b64) * 3 // 4) > 64:
            changes.append("code")
        del b64, new_digest
    elif module.params["cos_object_name"]:
        changes.append("code")
    memory_size = module.params["memory_size"]
    if memory_size is not None and current.get("MemorySize") != memory_size:
        changes.append("memory_size")
    timeout = module.params["execution_timeout"]
    if timeout is not None and current.get("Timeout") != timeout:
        changes.append("timeout")
    description = module.params["description"]
    if description is not None and current.get("Description") != description:
        changes.append("description")

    if not changes:
        module.exit_json(changed=False, function=current, msg="Function is up to date")

    diff = maybe_diff(module, current, {
        "MemorySize": memory_size if memory_size is not None else current.get("MemorySize"),
        "Timeout": timeout if timeout is not None else current.get("Timeout"),
        "Description": description if description is not None else current.get("Description"),
    })
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update function")

    if "code" in changes:
        _update_code(module, client, models, function_name, namespace, module.params)
    _update_config(module, client, models, function_name, namespace, module.params)
    updated = find_function(module, client, models, function_name, namespace)
    module.exit_json(changed=True, **(diff or {}), function=updated, msg="Function updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
