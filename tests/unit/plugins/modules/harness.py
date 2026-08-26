# -*- coding: utf-8 -*-
"""Shared harness for module main-path unit tests.

Implements the well-known Ansible community unit-test pattern: module
arguments are injected through ``ansible.module_utils.basic._ANSIBLE_ARGS``
and ``exit_json``/``fail_json`` are monkeypatched to raise, so a module's
``run_module()`` can execute in-process and its result payload asserted on.

The Tencent Cloud SDK is not installed in the test environment. Tests must
monkeypatch ``TencentCloudModule.require_sdk`` (no-op), the module's
``_load_*`` functions (returning the fake models/clients below) and
``TencentCloudModule.create_client`` (returning the fake client) before
calling ``run_module()``. This module is an importable helper, not a test
file.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from unittest.mock import patch

from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes


class AnsibleExitJson(SystemExit):
    """Raised when the module calls ``exit_json``; ``args[0]`` is the payload.

    Inherits ``SystemExit`` so modules that wrap their flow in a blanket
    ``except Exception`` (like the real Ansible ``exit_json``, which exits
    the process) do not accidentally swallow the test exit.
    """


class AnsibleFailJson(SystemExit):
    """Raised when the module calls ``fail_json``; ``args[0]`` is the payload."""


def set_module_args(args):
    """Inject module arguments the way the Ansible controller passes them."""
    basic._ANSIBLE_ARGS = to_bytes(json.dumps({"ANSIBLE_MODULE_ARGS": args}))
    # ansible-core 2.21+ requires a serialization profile next to the args.
    basic._ANSIBLE_PROFILE = "legacy"


BASE_ARGS = {
    "region": "ap-guangzhou",
    "secret_id": "dummy-secret-id",
    "secret_key": "dummy-secret-key",
}


def module_args(**extra):
    """Set module args with the mandatory base arguments pre-filled.

    ``_ansible_check_mode=True`` enables check mode and
    ``_ansible_diff=True`` enables diff mode (``module._diff``); both are
    consumed by ``AnsibleModule`` itself and never reach the module spec.
    """
    args = dict(BASE_ARGS)
    args.update(extra)
    set_module_args(args)
    return args


def _exit_json(self, **kwargs):
    kwargs.setdefault("changed", False)
    raise AnsibleExitJson(kwargs)


def _fail_json(self, *args, **kwargs):
    if args:
        kwargs["msg"] = args[0]
    kwargs["failed"] = True
    raise AnsibleFailJson(kwargs)


def run(fn):
    """Run ``fn`` (a module's ``run_module``) and return the result payload.

    ``exit_json``/``fail_json`` are monkeypatched on ``AnsibleModule`` to
    raise instead of printing and exiting. Returns the ``exit_json``
    payload; raises :class:`AnsibleFailJson` when the module fails.
    """
    with patch.object(basic.AnsibleModule, "exit_json", _exit_json), \
            patch.object(basic.AnsibleModule, "fail_json", _fail_json):
        try:
            fn()
        except AnsibleExitJson as exc:
            return exc.args[0]
    raise AssertionError("module returned without calling exit_json or fail_json")


class FakeRequest(object):
    """Stand-in for SDK request/model objects: attributes freely assignable."""


class FakeModels(object):
    """Stand-in for an SDK ``models`` module.

    Any attribute (``Filter``, ``CreateVpcRequest``, ``Tag``, ...) resolves
    to a fresh :class:`FakeRequest` subclass, so request builders can assign
    arbitrary fields on the instances.
    """

    def __getattr__(self, name):
        return type(name, (FakeRequest,), {})


class FakeResource(object):
    """Stand-in for an SDK resource object.

    Supports both attribute access (``obj.VpcName``) and
    ``_serialize(allow_none=True)`` like the SDK model objects the modules
    inspect.
    """

    def __init__(self, data):
        self.__dict__["_data"] = dict(data)

    def __getattr__(self, name):
        try:
            return self.__dict__["_data"][name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self.__dict__["_data"][name] = value

    def _serialize(self, allow_none=True):
        return dict(self._data)
