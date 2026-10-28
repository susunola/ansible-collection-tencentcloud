# Product capability matrix

This matrix covers the collection's surface after the P1 surface reduction
(2026-10-28): the modules listed in [`core-allowlist.yml`](core-allowlist.yml)
and the three reusable roles. Everything not listed here was removed from the
collection; see [`REMEDIATION.md`](REMEDIATION.md) for the binding plan.

The matrix is hand-maintained. The pre-reduction generated matrix covered the
removed long tail and is retired with it.

| Product | Write modules | `_info` modules | Role |
| --- | --- | --- | --- |
| CAM (identity) | `cam_user`, `cam_group`, `cam_group_membership`, `cam_role`, `cam_policy`, `cam_policy_attachment` | `cam_user_info`, `cam_group_info`, `cam_role_info`, `cam_policy_info` | — |
| CVM (compute) | `cvm_instance`, `cvm_instance_security_group`, `cvm_image`, `key_pair` | `cvm_instance_info`, `cvm_image_info`, `key_pair_info` | — |
| Lighthouse | `lighthouse_instance`, `lighthouse_firewall_rules`, `lighthouse_key_pair` | `lighthouse_instance_info` | — |
| VPC / network | `vpc`, `subnet`, `security_group`, `security_group_rule`, `route_table`, `eip`, `nat_gateway`, `nat_gateway_rule` | `vpc_info`, `subnet_info`, `security_group_info`, `security_group_rule_info`, `route_table_info`, `eip_info`, `nat_gateway_info` | `tc_vpc_foundation` |
| CLB (load balancer) | `clb_load_balancer`, `clb_listener`, `clb_listener_target`, `clb_rule`, `clb_target_group` | `clb_load_balancer_info`, `clb_listener_info`, `clb_listener_target_info`, `clb_target_group_info` | `tc_clb_http` |
| COS (object storage) | `cos_bucket`, `cos_bucket_policy`, `cos_object` | `cos_bucket_info`, `cos_bucket_policy_info`, `cos_object_info` | — |
| CBS (block storage) | `cbs_disk`, `cbs_snapshot` | `cbs_disk_info`, `cbs_snapshot_info` | — |
| TKE (Kubernetes) | `tke_cluster`, `tke_node_pool`, `tke_addon` | `tke_cluster_info`, `tke_node_pool_info` | `tc_tke_cluster` |
| TCR (registry) | `tcr_instance`, `tcr_namespace`, `tcr_repository` | `tcr_instance_info` | — |
| CDB (TencentDB for MySQL) | `cdb_instance`, `cdb_account` | `cdb_instance_info`, `cdb_account_info` | — |
| Redis | `redis_instance` | `redis_instance_info` | — |
| KMS | `kms_key` | `kms_key_info` | — |
| SSM (secrets) | `ssm_parameter`, `ssm_secret` | `ssm_secret_info` | — |
| Auto Scaling | `as_scaling_group` | `as_scaling_group_info` | — |

Beyond modules, the collection ships an inventory plugin (`tencentcloud_cvm`
and per-product variants), lookup plugins (`resource_id`, `ssm_parameter`,
`sts_caller_identity`), a `tat` connection plugin, a `tag_merge` filter and
the `tc_wait` action plugin.

## How to read this matrix

Every write module aims to be idempotent, to support check mode, and to read
remote state back after a change. An `_info` module is the read-only half of
its pair. Coverage beyond this list is deliberately out of scope for this
collection: adding a product means amending
[`core-allowlist.yml`](core-allowlist.yml) under the ratchet described in
[`REMEDIATION.md`](REMEDIATION.md).
