#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cynosdb_cluster
short_description: Manage Tencent Cloud CynosDB clusters
version_added: "0.14.0"
description: Creates, renames, expands, upgrades, isolates and permanently removes CynosDB clusters.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  cluster_id:
    description:
      - Existing cluster ID.
    type: str
  name:
    description:
      - Cluster name.
    type: str
  zone:
    description:
      - Primary availability zone; immutable after creation.
    type: str
  slave_zone:
    description:
      - Secondary availability zone.
    type: str
  vpc_id:
    description:
      - VPC ID; immutable after creation.
    type: str
  subnet_id:
    description:
      - Subnet ID; immutable after creation.
    type: str
  db_type:
    description:
      - Database engine.
    type: str
    choices: [MYSQL, POSTGRESQL]
    default: MYSQL
  db_version:
    description:
      - Database-compatible version; immutable after creation.
    type: str
  cynos_version:
    description:
      - Upgradeable Cynos kernel version.
    type: str
  cpu:
    description:
      - Initial instance CPU cores.
    type: int
  memory:
    description:
      - Initial instance memory in GiB.
    type: int
  instance_count:
    description:
      - Initial instance count.
    type: int
    default: 1
  storage:
    description:
      - Expandable storage limit in GiB.
    type: int
  admin_password:
    description:
      - Initial administrator password.
    type: str
  port:
    description:
      - Database port.
    type: int
    default: 3306
  pay_mode:
    description:
      - Postpaid or prepaid billing mode.
    type: int
    choices: [0, 1]
    default: 0
  period_months:
    description:
      - Prepaid purchase period.
    type: int
    default: 1
  auto_renew:
    description:
      - Automatically renew prepaid clusters.
    type: bool
    default: false
  security_group_ids:
    description:
      - Security groups bound during creation.
    type: list
    default: []
    elements: str
  purge:
    description:
      - Permanently remove an already isolated cluster.
    type: bool
    default: false

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.cynosdb_cluster_info
    description: Gather information about TencentDB for CynosDB clusters.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cynosdb_cluster:
    name: production-cynosdb
    zone: ap-guangzhou-3
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    db_version: '8.0'
    cpu: 2
    memory: 4
    storage: 100
    admin_password: "{{ vault_cynosdb_password }}"
"""
RETURN = r"""cluster:
  description:
    - Effective CynosDB cluster metadata.
  returned: always
  type: dict"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils import resolver
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.cynosdb.v20190107 import models, cynosdb_client

    return models, cynosdb_client


def describe_request(models, p, offset=0):
    r = models.DescribeClustersRequest()
    r.Offset, r.Limit = offset, 100
    r.DbType = p.get("db_type")
    if p.get("cluster_id") or p.get("name"):
        f = models.QueryFilter()
        f.Names = ["ClusterId" if p.get("cluster_id") else "ClusterName"]
        f.Values = [p.get("cluster_id") or p.get("name")]
        r.Filters = [f]
    return r


def create_request(models, p):
    r = models.CreateClustersRequest()
    r.Zone, r.SlaveZone, r.VpcId, r.SubnetId = p["zone"], p.get("slave_zone"), p["vpc_id"], p["subnet_id"]
    r.DbType, r.DbVersion, r.CynosVersion, r.ClusterName = p["db_type"], p["db_version"], p.get("cynos_version"), p["name"]
    r.Cpu, r.Memory, r.InstanceCount, r.Storage = p["cpu"], p["memory"], p["instance_count"], p["storage"]
    r.AdminPassword, r.Port, r.PayMode, r.Count = p["admin_password"], p["port"], p["pay_mode"], 1
    r.TimeSpan, r.TimeUnit, r.AutoRenewFlag = p["period_months"], "m", 1 if p["auto_renew"] else 0
    r.SecurityGroupIds = p["security_group_ids"]
    return r


def rename_request(models, cluster_id, name):
    r = models.ModifyClusterNameRequest()
    r.ClusterId, r.ClusterName = cluster_id, name
    return r


def storage_request(models, cluster_id, old, new):
    r = models.ModifyClusterStorageRequest()
    r.ClusterId, r.OldStorageLimit, r.NewStorageLimit = cluster_id, old, new
    return r


def slave_zone_request(models, cluster_id, old, new):
    r = models.ModifyClusterSlaveZoneRequest()
    r.ClusterId, r.OldSlaveZone, r.NewSlaveZone = cluster_id, old or "", new
    return r


def version_request(models, cluster_id, version):
    r = models.UpgradeClusterVersionRequest()
    r.ClusterId, r.CynosVersion, r.UpgradeType = cluster_id, version, "online"
    return r


def isolate_request(models, cluster_id, db_type):
    r = models.IsolateClusterRequest()
    r.ClusterId, r.DbType = cluster_id, db_type
    return r


def offline_request(models, cluster_id):
    r = models.OfflineClusterRequest()
    r.ClusterId = cluster_id
    return r


def find(module, client, models, p):
    """Return the matching cluster dict or None.

    The match is re-checked client-side by the shared resolver, so two
    candidates fail with C(ambiguous=true) plus the candidate list instead of
    a flat "specify cluster_id" message with nothing to choose from.
    """
    def describe(filters):
        response = module.sdk_call(client.DescribeClusters, describe_request(models, p))
        return resolver.records(response.ClusterSet)

    return resolver.resolve_one(
        module, describe, resource="CynosDB cluster",
        id_value=p.get("cluster_id"), name_value=p.get("name"),
        id_keys=("ClusterId",), name_keys=("ClusterName",),
    )


def _wait(module, client, models, p, states):
    wait_for_state(
        module,
        lambda: str((find(module, client, models, p) or {}).get("Status", "")).lower(),
        states,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "cluster_id": {},
            "name": {},
            "zone": {},
            "slave_zone": {},
            "vpc_id": {},
            "subnet_id": {},
            "db_type": {"choices": ["MYSQL", "POSTGRESQL"], "default": "MYSQL"},
            "db_version": {},
            "cynos_version": {},
            "cpu": {"type": "int"},
            "memory": {"type": "int"},
            "instance_count": {"type": "int", "default": 1},
            "storage": {"type": "int"},
            "admin_password": {"no_log": True},
            "port": {"type": "int", "default": 3306},
            "pay_mode": {"type": "int", "choices": [0, 1], "default": 0},
            "period_months": {"type": "int", "default": 1},
            "auto_renew": {"type": "bool", "default": False},
            "security_group_ids": {"type": "list", "elements": "str", "default": []},
            "purge": {"type": "bool", "default": False},
        },
        required_one_of=[("cluster_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CynosdbClient, "cynosdb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, cluster=None)
            cluster_id, status = current["ClusterId"], str(current.get("Status", "")).lower()
            if p["purge"]:
                if status not in ("isolated", "isolate", "offline"):
                    module.fail_json(msg="purge requires an already isolated CynosDB cluster", current_status=status)
                diff = maybe_diff(module, current, None)
                if not module.check_mode:
                    module.sdk_call(client.OfflineCluster, offline_request(models, cluster_id))
                module.exit_json(changed=True, **(diff or {}), cluster=None)
            if status in ("isolated", "isolate", "offline"):
                module.exit_json(changed=False, cluster=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.IsolateCluster, isolate_request(models, cluster_id, current.get("DbType") or p["db_type"]))
            module.exit_json(changed=True, **(diff or {}), cluster=current)
        if not current:
            missing = [k for k in ("name", "zone", "vpc_id", "subnet_id", "db_version", "cpu", "memory", "storage", "admin_password") if p.get(k) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a new CynosDB cluster", missing=missing)
            target = {
                "ClusterName": p["name"],
                "Zone": p["zone"],
                "VpcId": p["vpc_id"],
                "SubnetId": p["subnet_id"],
                "DbType": p["db_type"],
                "DbVersion": p["db_version"],
                "StorageLimit": p["storage"],
            }
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                response = module.sdk_call(client.CreateClusters, create_request(models, p))
                ids = response.ClusterIds or response.ResourceIds or []
                if ids:
                    p["cluster_id"] = ids[0]
                _wait(module, client, models, p, ["running"])
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), cluster=current if not module.check_mode else target)
        immutable = {
            "Zone": p.get("zone"),
            "VpcId": p.get("vpc_id"),
            "SubnetId": p.get("subnet_id"),
            "DbType": p.get("db_type"),
            "DbVersion": p.get("db_version"),
        }
        drift = {k: (current.get(k), v) for k, v in immutable.items() if v is not None and current.get(k) != v}
        if drift:
            module.fail_json(msg="CynosDB placement, engine and compatible version are immutable", immutable_drift=drift)
        old_slave = (current.get("SlaveZones") or [None])[0]
        desired = {
            "ClusterName": p.get("name") or current.get("ClusterName"),
            "StorageLimit": p.get("storage") if p.get("storage") is not None else current.get("StorageLimit"),
            "CynosVersion": p.get("cynos_version") or current.get("CynosVersion"),
            "SlaveZone": p.get("slave_zone") or old_slave,
        }
        before = {
            "ClusterName": current.get("ClusterName"),
            "StorageLimit": current.get("StorageLimit"),
            "CynosVersion": current.get("CynosVersion"),
            "SlaveZone": old_slave,
        }
        if before == desired:
            module.exit_json(changed=False, cluster=current)
        diff = maybe_diff(module, before, desired)
        cluster_id = current["ClusterId"]
        if not module.check_mode:
            if before["ClusterName"] != desired["ClusterName"]:
                module.sdk_call(client.ModifyClusterName, rename_request(models, cluster_id, desired["ClusterName"]))
            if before["StorageLimit"] != desired["StorageLimit"]:
                if desired["StorageLimit"] < before["StorageLimit"]:
                    module.fail_json(msg="CynosDB storage cannot be reduced")
                module.sdk_call(client.ModifyClusterStorage, storage_request(models, cluster_id, before["StorageLimit"], desired["StorageLimit"]))
            if before["SlaveZone"] != desired["SlaveZone"]:
                module.sdk_call(client.ModifyClusterSlaveZone, slave_zone_request(models, cluster_id, before["SlaveZone"], desired["SlaveZone"]))
            if before["CynosVersion"] != desired["CynosVersion"]:
                module.sdk_call(client.UpgradeClusterVersion, version_request(models, cluster_id, desired["CynosVersion"]))
            p["cluster_id"] = cluster_id
            _wait(module, client, models, p, ["running"])
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), cluster=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
