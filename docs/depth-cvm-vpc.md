# Depth Plan — CVM & VPC/networking

> Candidates below are derived from the Tencent Cloud *concept surface* teams
> commonly reach for. Names are placeholders to confirm against API Explorer
> / the pinned SDK before scaffolding: the reliable way to get real read
> modules is `python scripts/discover_info_specs.py` + `generate_info_modules.py`
> (pinned SDK) — it only emits actions the SDK actually ships. Resources
> without a list API should stay KNOWN_GAPS rather than get fabricated names.

## CVM — current (20 modules)

instances, images (+share), launch templates (+versions), disaster-recover /
placement groups, CHC, HPC cluster, action timers, instance↔security-group
binding. Read/write pairs are complete for what exists.

### Candidate additions (verify API names, then generate)

| Area | Suggested module (verify) | Kind |
| --- | --- | --- |
| Zones / regions (capacity planning) | `cvm_zone_info` / `cvm_region_info` | _info, generated from DescribeZones / DescribeRegions |
| Instance type catalogue | `cvm_instance_type_info` | _info (DescribeInstanceTypeConfigs) |
| Instance password / attributes | reset/charge sub-actions on `cvm_instance` if gaps | resource |
| Image import/export/rollback | extend `cvm_image` states or add per-action modules | resource |
| Placement group (independent from disaster-recover group) | `cvm_placement_group(_info)` | both |
| Instance state batch ops (stop/start/reboot/term) | convenience `cvm_instance_state` if desired | resource |

Note: key pairs are already their own product (`key_pair*`).

## VPC & networking — current (51 modules across vpc/subnet/route_table/
security_group/network_acl/nat/eip/eni/havip/ccn/direct-connect/vpn/
peering/private-dns/privatelink)

Core plumbing is covered end-to-end. Sub-resource gaps commonly requested:

| Area | Suggested module (verify) | Kind |
| --- | --- | --- |
| EIP association (bind to instance/NAT/LB) | `eip_associate(_info)` (AssociateAddress / DescribeAddresses) | both |
| Network ACL rules | `network_acl_rule(_info)` | both |
| Security group rule sets already exist (`security_group_rule`) — extend if multi rules missing | — | — |
| CCN route table / bandwidth limits / instance attach | `ccn_route_table(_info)`, `ccn_bandwidth_limit`, `ccn_attach_instance` | both |
| Direct Connect gateway / VLAN | `dc_direct_connect_gateway(_info)` | both |
| VPC IPv6 / DHCP option sets | `vpc_ipv6_cidr` / `vpc_dhcp_options(_info)` (if API surface confirms) | both |
| Private DNS zone↔VPC bindings | `private_dns_zone_vpc_binding(_info)` | both |
| VPN client/SSL users | confirm whether part of `vpn_connection` or new | resource |

## Execution

1. Run in an SDK-capable environment:
   ```bash
   python -m pip install "tencentcloud-sdk-python==$(python scripts/check_sdk_drift.py --print-stamp)"
   python scripts/discover_info_specs.py
   python scripts/generate_info_modules.py
   python scripts/audit_info_coverage.py --check
   ```
2. Keep discovered read modules that map to real Describe*/List* actions and
   remove their KNOWN_GAPS entries; add genuine write scaffolds via
   RESOURCE_SPECS only for confirmed APIs.
3. Land CVM and VPC/networking as two separate reviewable PRs.
