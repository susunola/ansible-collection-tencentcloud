#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: route_table
short_description: Manage Tencent Cloud VPC route tables
version_added: "0.4.0"
description:
  - Create, update, and delete Tencent Cloud VPC route tables, including
    their IPv4 route entries.
  - This module is idempotent. Running it twice leaves the resource unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the route table if it does not exist and updates
        its name, routes and tags to match the task.
      - C(absent) deletes the route table if it exists. Deleting a route
        table that is still associated with subnets fails; release those
        associations first. The default (main) route table of a VPC cannot
        be deleted.
    type: str
    choices: [present, absent]
    default: present
  name:
    description:
      - Name of the route table. Required when C(state=present).
      - When C(route_table_id) is not given, the route table is matched by
        the C(vpc-id) and C(route-table-name) API filters.
    type: str
  route_table_id:
    description:
      - ID of an existing route table, e.g. C(rtb-xxxxxxxx).
      - When given, the module operates on that route table and C(name) is
        used as the desired name to enforce.
    type: str
  vpc_id:
    description:
      - ID of the VPC the route table belongs to, e.g. C(vpc-xxxxxxxx).
      - Required when creating a new route table; ignored when the route
        table already exists (a route table cannot move between VPCs).
      - Also used together with C(name) to locate an existing route table
        when C(route_table_id) is not given.
    type: str
  routes:
    description:
      - IPv4 route entries of the route table.
      - Routes are reconciled with full-reconcile semantics when this option
        is given - remote user-created (C(USER)) routes whose
        C(destination_cidr_block) is not listed are removed, and listed
        routes missing remotely are added. A listed route whose
        C(gateway_type), C(gateway_id) or C(description) differs from the
        remote entry is replaced (deleted and re-created).
      - System routes (C(NETD), C(CCN) and other non-C(USER) route types)
        are never modified or removed.
      - When O(routes) is omitted, existing routes are left untouched; pass
        an empty list to remove all user-created routes.
    type: list
    elements: dict
    suboptions:
      destination_cidr_block:
        description:
          - Destination IPv4 CIDR block of the route, e.g. C(10.1.0.0/16).
            Must not overlap with the VPC CIDR.
        type: str
        required: true
      gateway_type:
        description:
          - Next hop type, e.g. C(CVM), C(VPN), C(DIRECTCONNECT),
            C(PEERCONNECTION), C(HAVIP), C(NAT), C(NORMAL_CVM), C(EIP),
            C(LOCAL_GATEWAY), C(INTRANAT), C(USER_CCN), C(GWLB_ENDPOINT).
        type: str
        required: true
      gateway_id:
        description:
          - Next hop gateway ID, e.g. C(nat-xxxxxxxx) for C(NAT).
          - When C(gateway_type=NORMAL_CVM), pass the instance private IP;
            when C(gateway_type=EIP), pass C(0).
        type: str
        required: true
      description:
        description: Description of the route entry.
        type: str
  tags:
    description:
      - Tags to apply to the route table as a dict, for example
        I(env=prod).
      - Existing tags not listed are removed; listed tags with a different
        value are updated. Requires the C(tencentcloud-sdk-python-tag) package
        and the tag service to be enabled for the account.
    type: dict
    default: {}
  retries:
    description:
      - Maximum number of retry attempts for throttled or transient API
        failures, using exponential backoff with jitter.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Maximum time in seconds to wait for an asynchronous resource to reach
        the desired state.
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
    default: ansible-collection/tencentcloud.cloud
notes:
  - Requires the C(tencentcloud-sdk-python-vpc) package on the controller.
  - Tag reconciliation additionally requires C(tencentcloud-sdk-python-tag)
    and addresses route tables through the tag service as service type
    C(vpc) with resource prefix C(rtb).
  - Route reconciliation only manages user-created (C(USER)) routes; system
    routes such as the local route and CCN/NETD routes are left untouched.
  - Uses the C(vpc.tencentcloudapi.com) endpoint by default.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a route table with routes
  tencentcloud.cloud.route_table:
    region: ap-guangzhou
    state: present
    vpc_id: vpc-xxxxxxxx
    name: app-rtb
    routes:
      - destination_cidr_block: 10.1.0.0/16
        gateway_type: NAT
        gateway_id: nat-xxxxxxxx
        description: egress via NAT
    tags:
      env: prod

- name: Ensure a route table exists without touching its routes
  tencentcloud.cloud.route_table:
    region: ap-guangzhou
    state: present
    vpc_id: vpc-xxxxxxxx
    name: app-rtb

- name: Remove all user routes from a route table
  tencentcloud.cloud.route_table:
    region: ap-guangzhou
    state: present
    route_table_id: rtb-xxxxxxxx
    name: app-rtb
    routes: []

- name: Delete a route table
  tencentcloud.cloud.route_table:
    region: ap-guangzhou
    state: absent
    route_table_id: rtb-xxxxxxxx
'''

RETURN = r'''
route_table:
  description: The route table as reported by the API after the operation.
  returned: success
  type: dict
  sample:
    RouteTableId: rtb-xxxxxxxx
    VpcId: vpc-xxxxxxxx
    RouteTableName: app-rtb
    Main: false
    RouteSet: []
    TagSet: []
    CreatedTime: "2026-08-26 12:00:00"
'''

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.comparison import build_diff
from ansible_collections.tencentcloud.cloud.plugins.module_utils.errors import (
    is_idempotent_success,
)
from ansible_collections.tencentcloud.cloud.plugins.module_utils.tagging import (
    build_sdk_tags,
    compare_tags,
)


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def _load_tag():
    from tencentcloud.tag.v20180813 import models as tag_models, tag_client
    return tag_models, tag_client


def build_describe_request(models, route_table_id, vpc_id, name):
    request = models.DescribeRouteTablesRequest()
    request.Limit = "100"
    if route_table_id:
        request.RouteTableIds = [route_table_id]
        return request
    filters = []
    if vpc_id:
        vpc_filter = models.Filter()
        vpc_filter.Name = "vpc-id"
        vpc_filter.Values = [vpc_id]
        filters.append(vpc_filter)
    if name:
        name_filter = models.Filter()
        name_filter.Name = "route-table-name"
        name_filter.Values = [name]
        filters.append(name_filter)
    if filters:
        request.Filters = filters
    return request


def _first(collection):
    return collection[0] if collection else None


def find_route_table(module, client, models, route_table_id, vpc_id, name):
    """Return the matching route table dict or None."""
    request = build_describe_request(models, route_table_id, vpc_id, name)
    response = module.sdk_call(client.DescribeRouteTables, request)
    table = _first(response.RouteTableSet or [])
    if table is None:
        return None
    return table._serialize(allow_none=True)


def diff_routes(desired_routes, current_route_set):
    """Compute route entries to add and delete for full reconciliation.

    Only user-created (``USER``) routes from the remote route set are
    considered; system routes are never touched. Routes are keyed by
    destination CIDR block. A remote route whose gateway type, gateway ID
    or description differs from the desired entry is replaced.

    :param desired_routes: list of user-supplied route dicts (module params).
    :param current_route_set: list of serialized ``Route`` dicts from the API.
    :returns: (to_add, to_delete) where ``to_add`` is a list of desired route
        dicts and ``to_delete`` a list of serialized remote route dicts.
    """
    desired = {}
    for route in desired_routes or []:
        desired[route["destination_cidr_block"]] = {
            "gateway_type": route["gateway_type"],
            "gateway_id": route["gateway_id"],
            "description": route.get("description") or "",
        }
    current = {}
    for route in current_route_set or []:
        if route.get("RouteType") and route["RouteType"] != "USER":
            continue
        cidr = route.get("DestinationCidrBlock")
        if not cidr:
            continue
        current[cidr] = route

    to_add = []
    to_delete = []
    for cidr, route in sorted(desired.items()):
        remote = current.get(cidr)
        entry = dict(destination_cidr_block=cidr, **route)
        if remote is None:
            to_add.append(entry)
        elif (remote.get("GatewayType") != route["gateway_type"]
                or remote.get("GatewayId") != route["gateway_id"]
                or (remote.get("RouteDescription") or "") != route["description"]):
            to_delete.append(remote)
            to_add.append(entry)
    for cidr, remote in sorted(current.items()):
        if cidr not in desired:
            to_delete.append(remote)
    return to_add, to_delete


def _apply_routes(module, client, models, route_table_id, to_add, to_delete):
    """Reconcile route entries via DeleteRoutes and CreateRoutes.

    Deletions run first so a replaced CIDR does not collide with its new
    entry. Deletion only needs the route identity fields (``RouteId`` /
    ``RouteItemId``).
    """
    if to_delete:
        request = models.DeleteRoutesRequest()
        request.RouteTableId = route_table_id
        request.Routes = []
        for route in to_delete:
            entry = models.Route()
            entry.RouteId = route.get("RouteId")
            entry.RouteItemId = route.get("RouteItemId")
            request.Routes.append(entry)
        module.sdk_call(client.DeleteRoutes, request)
    if to_add:
        request = models.CreateRoutesRequest()
        request.RouteTableId = route_table_id
        request.Routes = []
        for route in to_add:
            entry = models.Route()
            entry.DestinationCidrBlock = route["destination_cidr_block"]
            entry.GatewayType = route["gateway_type"]
            entry.GatewayId = route["gateway_id"]
            entry.RouteDescription = route.get("description") or ""
            request.Routes.append(entry)
        module.sdk_call(client.CreateRoutes, request)


def _apply_tags(module, client, tag_models, route_table_id, to_add, to_remove):
    """Reconcile tags through the tag service.

    Route tables are addressed as service type ``vpc`` with resource prefix
    ``rtb``. Each tag key is processed independently.
    """
    for key, value in sorted(to_add.items()):
        request = tag_models.AttachResourcesTagRequest()
        request.ServiceType = "vpc"
        request.ResourceIds = [route_table_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "rtb"
        request.TagKey = key
        request.TagValue = value
        module.sdk_call(client.AttachResourcesTag, request)
    for key in to_remove:
        request = tag_models.DetachResourcesTagRequest()
        request.ServiceType = "vpc"
        request.ResourceIds = [route_table_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "rtb"
        request.TagKey = key
        module.sdk_call(client.DetachResourcesTag, request)


def _create(module, client, models, vpc_id, name, tags):
    request = models.CreateRouteTableRequest()
    request.VpcId = vpc_id
    request.RouteTableName = name
    if tags:
        request.Tags = build_sdk_tags(models, tags)
    response = module.sdk_call(client.CreateRouteTable, request)
    return response.RouteTable._serialize(allow_none=True)


def _update_name(module, client, models, route_table_id, name):
    request = models.ModifyRouteTableAttributeRequest()
    request.RouteTableId = route_table_id
    request.RouteTableName = name
    module.sdk_call(client.ModifyRouteTableAttribute, request)


def _delete(module, client, models, route_table_id):
    request = models.DeleteRouteTableRequest()
    request.RouteTableId = route_table_id
    module.sdk_call(client.DeleteRouteTable, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "name": {"type": "str"},
            "route_table_id": {"type": "str"},
            "vpc_id": {"type": "str"},
            "routes": {
                "type": "list",
                "elements": "dict",
                "options": {
                    "destination_cidr_block": {"type": "str", "required": True},
                    "gateway_type": {"type": "str", "required": True},
                    "gateway_id": {"type": "str", "required": True},
                    "description": {"type": "str"},
                },
            },
            "tags": {"type": "dict", "default": {}},
        },
        required_if=[("state", "present", ["name"])],
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    name = module.params["name"]
    route_table_id = module.params["route_table_id"]
    vpc_id = module.params["vpc_id"]
    routes = module.params["routes"]
    tags = module.params["tags"]

    if state == "absent" and not name and not route_table_id:
        module.fail_json(msg="name or route_table_id is required when state=absent")

    models, vpc_client = _load_vpc()
    client = module.create_client(vpc_client.VpcClient, "vpc.tencentcloudapi.com")

    try:
        current = find_route_table(module, client, models, route_table_id, vpc_id, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Route table already absent")
        diff = build_diff(current, None)
        if module.check_mode:
            module.exit_json(changed=True, diff=diff, msg="Would delete route table")
        try:
            _delete(module, client, models, current["RouteTableId"])
        except Exception as exc:
            if is_idempotent_success(exc):
                module.exit_json(changed=True, diff=diff, msg="Route table deleted")
            raise
        module.exit_json(changed=True, diff=diff, route_table=None, msg="Route table deleted")

    # state == present
    desired = {"name": name, "routes": routes, "tags": tags}
    if current is None:
        if not vpc_id:
            module.fail_json(msg="vpc_id is required when creating a route table")
        diff = build_diff(None, desired)
        if module.check_mode:
            module.exit_json(changed=True, diff=diff, msg="Would create route table")
        created = _create(module, client, models, vpc_id, name, tags)
        if routes:
            to_add, _to_remove = diff_routes(routes, [])
            _apply_routes(module, client, models, created["RouteTableId"], to_add, [])
            created = find_route_table(module, client, models, created["RouteTableId"], None, None)
        module.exit_json(changed=True, diff=diff, route_table=created, msg="Route table created")

    table_id = current["RouteTableId"]
    current_name = current.get("RouteTableName")
    current_tags = current.get("TagSet") or []
    current_routes = current.get("RouteSet") or []

    changes = []
    if current_name != name:
        changes.append("name")
    tags_equal, to_add_tags, to_remove_tags = compare_tags(tags, current_tags)
    if not tags_equal:
        changes.append("tags")
    to_add_routes, to_delete_routes = ([], [])
    if routes is not None:
        to_add_routes, to_delete_routes = diff_routes(routes, current_routes)
        if to_add_routes or to_delete_routes:
            changes.append("routes")

    if not changes:
        module.exit_json(changed=False, route_table=current, msg="Route table is up to date")

    if module.check_mode:
        module.exit_json(changed=True, diff=build_diff(current, desired), msg="Would update route table")

    if "name" in changes:
        _update_name(module, client, models, table_id, name)
    if not tags_equal:
        tag_models, tag_client = _load_tag()
        tag_client_instance = module.create_client(
            tag_client.TagClient, "tag.tencentcloudapi.com"
        )
        _apply_tags(module, tag_client_instance, tag_models, table_id, to_add_tags, to_remove_tags)
    if "routes" in changes:
        _apply_routes(module, client, models, table_id, to_add_routes, to_delete_routes)

    updated = find_route_table(module, client, models, table_id, None, None)
    module.exit_json(
        changed=True,
        diff=build_diff(current, desired),
        route_table=updated,
        msg="Route table updated",
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
