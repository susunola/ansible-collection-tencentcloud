#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: clb_listener
short_description: Manage listeners on Tencent Cloud CLB load balancers
version_added: "0.10.0"
description:
  - Create, update, and delete listeners on a Tencent Cloud CLB (Cloud Load
    Balancer) instance through the C(clb.v20180317) API.
  - A listener is identified by the combination of O(load_balancer_id),
    O(port) and O(protocol); O(listener_id) selects a listener directly when
    known.
  - This module is idempotent. Running it twice leaves the listener unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the listener with V(CreateListener) when it does
        not exist, and updates the mutable attributes with V(ModifyListener)
        when it does.
      - C(absent) deletes the listener with V(DeleteListener).
    type: str
    choices: [present, absent]
    default: present
  load_balancer_id:
    description: ID of the CLB instance owning the listener, e.g. C(lb-xxxxxxxx).
    type: str
    required: true
  listener_id:
    description:
      - ID of an existing listener, e.g. C(lbl-xxxxxxxx).
      - When given, the module operates on that listener; otherwise the
        listener is matched by O(port) and O(protocol).
    type: str
  port:
    description:
      - Listener port, range 1-65535.
      - Part of the listener identity; changing it recreates the listener.
    type: int
    required: true
  protocol:
    description:
      - Listener protocol.
      - Part of the listener identity; changing it recreates the listener.
    type: str
    choices: [TCP, UDP, HTTP, HTTPS, TCP_SSL, QUIC]
    required: true
  name:
    description: Name of the listener. Enforced on existing listeners.
    type: str
  scheduler:
    description:
      - Balancing method, only meaningful for TCP, UDP, TCP_SSL and QUIC
        listeners.
    type: str
    choices: [WRR, LEAST_CONN, IP_HASH]
  session_expire_time:
    description:
      - Session persistence duration in seconds, 30-3600; C(0) disables
        session persistence. Only meaningful for TCP and UDP listeners.
    type: int
  health_check:
    description:
      - Health check configuration, only meaningful for TCP, UDP, TCP_SSL and
        QUIC listeners (layer-7 listeners carry the health check on their
        forwarding rules).
      - Only the keys listed are compared for idempotency; keys not given are
        left at the API default on creation and untouched on update.
    type: dict
    suboptions:
      health_switch:
        description: Whether the health check is enabled.
        type: bool
      interval_time:
        description: Probe interval in seconds, 2-300 (5-300 for some legacy IPv4 instances).
        type: int
      health_num:
        description: Healthy threshold in consecutive probes, 2-10.
        type: int
      un_health_num:
        description: Unhealthy threshold in consecutive probes, 2-10.
        type: int
      time_out:
        description: Probe response timeout in seconds, 2-60; must be lower than O(health_check.interval_time).
        type: int
      check_type:
        description: Probe protocol.
        type: str
        choices: [TCP, HTTP, HTTPS, GRPC, PING, CUSTOM]
      check_port:
        description: Custom probe port; defaults to the backend port when omitted.
        type: int
      http_check_path:
        description: Probe path for HTTP probes.
        type: str
      http_check_domain:
        description: Probe domain carried in the HTTP Host header.
        type: str
      http_check_method:
        description: Probe HTTP method.
        type: str
        choices: [HEAD, GET]
      http_code:
        description: Bitmask of HTTP status codes considered healthy, 1-31.
        type: int
      http_version:
        description: Backend HTTP version for HTTP probes on TCP listeners.
        type: str
        choices: [HTTP/1.0, HTTP/1.1]
  certificate:
    description:
      - Server certificate for HTTPS and TCP_SSL listeners, written to
        V(CertificateInput). One of O(certificate.cert_id) or inline content
        must be resolvable by the API when the protocol requires it.
    type: dict
    suboptions:
      ssl_mode:
        description: Authentication mode.
        type: str
        choices: [UNIDIRECTIONAL, MUTUAL]
      cert_id:
        description: Server certificate ID from the SSL certificate service.
        type: str
      cert_ca_id:
        description: Client CA certificate ID, required when O(certificate.ssl_mode=MUTUAL).
        type: str
  sni_switch:
    description:
      - Whether SNI is enabled, only meaningful for HTTPS listeners.
      - An SNI-enabled listener cannot be switched back off; the API rejects
        the change.
    type: bool
  keepalive_enable:
    description: Whether keep-alive is enabled, only meaningful for HTTP and HTTPS listeners.
    type: bool
  retries:
    description:
      - Maximum number of retry attempts for throttled or transient API
        failures, using exponential backoff with jitter.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Maximum time in seconds to wait for an asynchronous listener task to
        finish.
    type: int
    default: 120
  waiter_delay:
    description: Interval in seconds between state polls while waiting.
    type: int
    default: 5
  user_agent:
    description:
      - User-Agent string sent with API requests.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-clb) package on the controller.
  - Uses the C(clb.tencentcloudapi.com) endpoint by default.
  - Listener operations are asynchronous; V(CreateListener),
    V(ModifyListener) and V(DeleteListener) return a request ID the module
    polls through V(DescribeTaskStatus) until the task succeeds.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a TCP listener with a custom health check
  susunola.tencentcloud.clb_listener:
    region: ap-guangzhou
    load_balancer_id: lb-xxxxxxxx
    protocol: TCP
    port: 8080
    name: tcp-8080
    scheduler: WRR
    session_expire_time: 0
    health_check:
      health_switch: true
      interval_time: 5
      health_num: 3
      un_health_num: 3
      time_out: 2

- name: Create an HTTPS listener with a certificate
  susunola.tencentcloud.clb_listener:
    region: ap-guangzhou
    load_balancer_id: lb-xxxxxxxx
    protocol: HTTPS
    port: 443
    name: https-443
    certificate:
      ssl_mode: UNIDIRECTIONAL
      cert_id: abcdefgh
    sni_switch: false

- name: Preview the listener changes (no changes applied)
  susunola.tencentcloud.clb_listener:
    region: ap-guangzhou
    load_balancer_id: lb-xxxxxxxx
    protocol: TCP
    port: 8080
    scheduler: LEAST_CONN
  check_mode: true

- name: Delete a listener
  susunola.tencentcloud.clb_listener:
    region: ap-guangzhou
    state: absent
    load_balancer_id: lb-xxxxxxxx
    protocol: TCP
    port: 8080
'''

RETURN = r'''
listener:
  description: The listener as reported by V(DescribeListeners) after the operation.
  returned: success
  type: dict
  sample:
    ListenerId: lbl-xxxxxxxx
    ListenerName: tcp-8080
    Protocol: TCP
    Port: 8080
    Scheduler: WRR
    SessionExpireTime: 0
listener_id:
  description: ID of the managed listener.
  returned: success
  type: str
  sample: lbl-xxxxxxxx
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import (
    is_idempotent_success,
)
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import (
    wait_for_task,
)

# Maps the health_check suboption names to the HealthCheck model attributes.
HEALTH_CHECK_FIELDS = {
    "health_switch": "HealthSwitch",
    "interval_time": "IntervalTime",
    "health_num": "HealthNum",
    "un_health_num": "UnHealthNum",
    "time_out": "TimeOut",
    "check_type": "CheckType",
    "check_port": "CheckPort",
    "http_check_path": "HttpCheckPath",
    "http_check_domain": "HttpCheckDomain",
    "http_check_method": "HttpCheckMethod",
    "http_code": "HttpCode",
    "http_version": "HttpVersion",
}

# Maps the certificate suboption names to the CertificateInput model attributes.
CERTIFICATE_FIELDS = {
    "ssl_mode": "SSLMode",
    "cert_id": "CertId",
    "cert_ca_id": "CertCaId",
}


def _load_clb():
    from tencentcloud.clb.v20180317 import models, clb_client
    return models, clb_client


def build_describe_request(models, load_balancer_id, listener_id, port, protocol):
    request = models.DescribeListenersRequest()
    request.LoadBalancerId = load_balancer_id
    if listener_id:
        request.ListenerIds = [listener_id]
    else:
        request.Port = port
        request.Protocol = protocol
    return request


def find_listener(module, client, models, load_balancer_id, listener_id, port, protocol):
    """Return the matching listener dict or None."""
    request = build_describe_request(models, load_balancer_id, listener_id, port, protocol)
    response = module.sdk_call(client.DescribeListeners, request)
    for candidate in response.Listeners or []:
        current = candidate._serialize(allow_none=True)
        if listener_id and current.get("ListenerId") != listener_id:
            continue
        if not listener_id and (current.get("Port") != port or current.get("Protocol") != protocol):
            continue
        return current
    return None


def build_health_check(models, health_check):
    """Build a HealthCheck model from the module's health_check dict."""
    if not health_check:
        return None
    model = models.HealthCheck()
    for option, attribute in sorted(HEALTH_CHECK_FIELDS.items()):
        value = health_check.get(option)
        if value is None:
            continue
        # HealthSwitch is an int on the wire; the module exposes a bool.
        if isinstance(value, bool):
            value = int(value)
        setattr(model, attribute, value)
    return model


def build_certificate(models, certificate):
    """Build a CertificateInput model from the module's certificate dict."""
    if not certificate:
        return None
    model = models.CertificateInput()
    for option, attribute in sorted(CERTIFICATE_FIELDS.items()):
        value = certificate.get(option)
        if value is not None:
            setattr(model, attribute, value)
    return model


def build_create_request(models, params):
    request = models.CreateListenerRequest()
    request.LoadBalancerId = params["load_balancer_id"]
    request.Ports = [params["port"]]
    request.Protocol = params["protocol"]
    if params["name"]:
        request.ListenerNames = [params["name"]]
    if params["scheduler"]:
        request.Scheduler = params["scheduler"]
    if params["session_expire_time"] is not None:
        request.SessionExpireTime = params["session_expire_time"]
    if params["health_check"]:
        request.HealthCheck = build_health_check(models, params["health_check"])
    if params["certificate"]:
        request.Certificate = build_certificate(models, params["certificate"])
    if params["sni_switch"] is not None:
        request.SniSwitch = int(params["sni_switch"])
    if params["keepalive_enable"] is not None:
        request.KeepaliveEnable = int(params["keepalive_enable"])
    return request


def _create(module, client, models, params):
    """Create the listener and return (listener_id, task_request_id)."""
    request = build_create_request(models, params)
    response = module.sdk_call(client.CreateListener, request)
    listener_ids = response.ListenerIds or []
    return (listener_ids[0] if listener_ids else None), response.RequestId


def _delete(module, client, models, load_balancer_id, listener_id):
    """Delete the listener; returns the async task request ID."""
    request = models.DeleteListenerRequest()
    request.LoadBalancerId = load_balancer_id
    request.ListenerId = listener_id
    response = module.sdk_call(client.DeleteListener, request)
    return response.RequestId


def _update(module, client, models, load_balancer_id, listener_id, params, changes):
    """Update the changed attributes; returns the async task request ID."""
    request = models.ModifyListenerRequest()
    request.LoadBalancerId = load_balancer_id
    request.ListenerId = listener_id
    if "name" in changes:
        request.ListenerName = params["name"]
    if "scheduler" in changes:
        request.Scheduler = params["scheduler"]
    if "session_expire_time" in changes:
        request.SessionExpireTime = params["session_expire_time"]
    if "health_check" in changes:
        request.HealthCheck = build_health_check(models, params["health_check"])
    if "certificate" in changes:
        request.Certificate = build_certificate(models, params["certificate"])
    if "sni_switch" in changes:
        request.SniSwitch = int(params["sni_switch"])
    if "keepalive_enable" in changes:
        request.KeepaliveEnable = int(params["keepalive_enable"])
    response = module.sdk_call(client.ModifyListener, request)
    return response.RequestId


def _wait_task(module, client, models, task_id):
    """Wait for an asynchronous CLB task; returns the task response."""
    def poll():
        request = models.DescribeTaskStatusRequest()
        request.TaskId = task_id
        response = module.sdk_call(client.DescribeTaskStatus, request)
        return response.Status, response.Message, response

    return wait_for_task(
        module,
        poll,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def _health_check_drift(desired, current):
    """True when a user-provided health_check key differs from the listener."""
    if desired is None:
        return False
    current = current or {}
    for option, attribute in sorted(HEALTH_CHECK_FIELDS.items()):
        value = desired.get(option)
        if value is None:
            continue
        if isinstance(value, bool):
            value = int(value)
        if current.get(attribute) != value:
            return True
    return False


def _certificate_drift(desired, current):
    """True when a user-provided certificate key differs from the listener."""
    if desired is None:
        return False
    current = current or {}
    for option, attribute in sorted(CERTIFICATE_FIELDS.items()):
        value = desired.get(option)
        if value is None:
            continue
        if current.get(attribute) != value:
            return True
    return False


def listener_drift(current, params):
    """Return the mutable attributes whose desired value differs."""
    changes = []
    if params["name"] is not None and current.get("ListenerName") != params["name"]:
        changes.append("name")
    if params["scheduler"] is not None and current.get("Scheduler") != params["scheduler"]:
        changes.append("scheduler")
    if (params["session_expire_time"] is not None
            and current.get("SessionExpireTime") != params["session_expire_time"]):
        changes.append("session_expire_time")
    if _health_check_drift(params["health_check"], current.get("HealthCheck")):
        changes.append("health_check")
    if _certificate_drift(params["certificate"], current.get("Certificate")):
        changes.append("certificate")
    if (params["sni_switch"] is not None
            and current.get("SniSwitch") != int(params["sni_switch"])):
        changes.append("sni_switch")
    if (params["keepalive_enable"] is not None
            and current.get("KeepaliveEnable") != int(params["keepalive_enable"])):
        changes.append("keepalive_enable")
    return changes


def _desired_state(params):
    desired = {
        "LoadBalancerId": params["load_balancer_id"],
        "Port": params["port"],
        "Protocol": params["protocol"],
        "ListenerName": params["name"],
        "Scheduler": params["scheduler"],
        "SessionExpireTime": params["session_expire_time"],
        "HealthCheck": params["health_check"],
        "Certificate": params["certificate"],
    }
    return {key: value for key, value in desired.items() if value is not None}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "load_balancer_id": {"type": "str", "required": True},
            "listener_id": {"type": "str"},
            "port": {"type": "int", "required": True},
            "protocol": {
                "type": "str",
                "choices": ["TCP", "UDP", "HTTP", "HTTPS", "TCP_SSL", "QUIC"],
                "required": True,
            },
            "name": {"type": "str"},
            "scheduler": {"type": "str", "choices": ["WRR", "LEAST_CONN", "IP_HASH"]},
            "session_expire_time": {"type": "int"},
            "health_check": {
                "type": "dict",
                "options": {
                    "health_switch": {"type": "bool"},
                    "interval_time": {"type": "int"},
                    "health_num": {"type": "int"},
                    "un_health_num": {"type": "int"},
                    "time_out": {"type": "int"},
                    "check_type": {"type": "str", "choices": ["TCP", "HTTP", "HTTPS", "GRPC", "PING", "CUSTOM"]},
                    "check_port": {"type": "int"},
                    "http_check_path": {"type": "str"},
                    "http_check_domain": {"type": "str"},
                    "http_check_method": {"type": "str", "choices": ["HEAD", "GET"]},
                    "http_code": {"type": "int"},
                    "http_version": {"type": "str", "choices": ["HTTP/1.0", "HTTP/1.1"]},
                },
            },
            "certificate": {
                "type": "dict",
                "options": {
                    "ssl_mode": {"type": "str", "choices": ["UNIDIRECTIONAL", "MUTUAL"]},
                    "cert_id": {"type": "str"},
                    "cert_ca_id": {"type": "str"},
                },
            },
            "sni_switch": {"type": "bool"},
            "keepalive_enable": {"type": "bool"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    load_balancer_id = module.params["load_balancer_id"]
    listener_id = module.params["listener_id"]
    port = module.params["port"]
    protocol = module.params["protocol"]

    models, clb_client = _load_clb()
    client = module.create_client(clb_client.ClbClient, "clb.tencentcloudapi.com")

    try:
        current = find_listener(module, client, models, load_balancer_id, listener_id, port, protocol)

        if state == "absent":
            if current is None:
                module.exit_json(changed=False, msg="Listener already absent")
            target_id = current["ListenerId"]
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would delete listener")
            try:
                task_id = _delete(module, client, models, load_balancer_id, target_id)
                if task_id:
                    _wait_task(module, client, models, task_id)
            except Exception as exc:
                if is_idempotent_success(exc):
                    module.exit_json(changed=True, **(diff or {}), msg="Listener deleted")
                raise
            module.exit_json(
                changed=True, **(diff or {}),
                listener=None, listener_id=target_id, msg="Listener deleted",
            )

        # state == present
        desired = _desired_state(module.params)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would create listener")
            new_id, task_id = _create(module, client, models, module.params)
            if task_id:
                _wait_task(module, client, models, task_id)
            if new_id:
                created = find_listener(module, client, models, load_balancer_id, new_id, None, None)
            else:
                created = find_listener(module, client, models, load_balancer_id, None, port, protocol)
                new_id = created["ListenerId"] if created else None
            module.exit_json(
                changed=True, **(diff or {}),
                listener=created, listener_id=new_id, msg="Listener created",
            )

        target_id = current["ListenerId"]
        changes = listener_drift(current, module.params)
        if not changes:
            module.exit_json(
                changed=False, listener=current, listener_id=target_id,
                msg="Listener is up to date",
            )

        if module.check_mode:
            module.exit_json(
                changed=True, **(maybe_diff(module, current, desired) or {}),
                msg="Would update listener",
            )

        task_id = _update(module, client, models, load_balancer_id, target_id, module.params, changes)
        if task_id:
            _wait_task(module, client, models, task_id)
        updated = find_listener(module, client, models, load_balancer_id, target_id, None, None)
        module.exit_json(
            changed=True,
            **(maybe_diff(module, current, desired) or {}),
            listener=updated,
            listener_id=target_id,
            msg="Listener updated",
        )
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
