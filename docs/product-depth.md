# Product module depth

Counts by product family of the modules that remain after the P1 surface
reduction (2026-10-28). The retained set is exactly
[`core-allowlist.yml`](core-allowlist.yml); this page restates it grouped by
product. It is no longer auto-generated.

| Product family | Write modules | `_info` modules | Total |
| --- | ---: | ---: | ---: |
| VPC / network (vpc, subnet, security group, route table, eip, nat) | 8 | 7 | 15 |
| CAM | 6 | 4 | 10 |
| CLB | 5 | 4 | 9 |
| CVM (incl. key pairs) | 4 | 3 | 7 |
| COS | 3 | 3 | 6 |
| TKE | 3 | 2 | 5 |
| CBS | 2 | 2 | 4 |
| CDB | 2 | 2 | 4 |
| Lighthouse | 3 | 1 | 4 |
| TCR | 3 | 1 | 4 |
| SSM | 2 | 1 | 3 |
| Auto Scaling | 1 | 1 | 2 |
| KMS | 1 | 1 | 2 |
| Redis | 1 | 1 | 2 |

## Read-surface gaps inside the allowlist

Eleven retained write modules have no same-named `_info` sibling; they are
read back through the write module's own post-change re-read or through a
sibling reader in the same product family:

`cam_group_membership`, `cam_policy_attachment`, `clb_rule`,
`cvm_instance_security_group`, `lighthouse_firewall_rules`,
`lighthouse_key_pair`, `nat_gateway_rule`, `ssm_parameter`, `tcr_namespace`,
`tcr_repository`, `tke_addon`.

Closing these gaps with hand-written readers is candidate P3/P4 work; adding
any module still requires amending `core-allowlist.yml` under the ratchet in
[`REMEDIATION.md`](REMEDIATION.md).

## How depth is extended now

The pre-reduction generator workflow is gone. Depth on the retained modules
means:

1. human-readable option documentation (P3 of `REMEDIATION.md`),
2. the 8-step real-cloud integration contract per write module (P4), and
3. deliberate, reviewed additions through the allowlist ratchet only.
