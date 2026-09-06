# tc_disaster_recovery

Prepare cross-region disaster recovery artifacts for a workload in one call:

1. **Golden image** (primary region) — a CVM image of a source instance used
   as the recovery point to rebuild the fleet in the DR region.
2. **COS replication** — cross-region bucket replication from the primary
   bucket to the DR region, keeping the data plane continuously replicated.
3. **Standby CLB** (DR region, optional) — a pre-wired load balancer and
   listener that becomes the failover entry point; backends are attached once
   the replica fleet has been rebuilt.

## Role variables

| Variable | Default | Description |
| --- | --- | --- |
| `tc_dr_state` | `present` | `present` prepares the artifacts, `absent` removes them in reverse order |
| `tc_dr_region` | *(module default)* | Primary region |
| `tc_dr_dr_region` | *(module default)* | DR region (used for the standby CLB) |
| `tc_dr_enable_image` | `true` | Manage the golden image |
| `tc_dr_image_id` / `image_name` | `""` | Identify the image |
| `tc_dr_image_instance_id` | `""` | Source instance the image is created from |
| `tc_dr_image_description` | `""` | Image description |
| `tc_dr_image_force_poweroff` / `sysprep` | `false` / `false` | Image creation options |
| `tc_dr_enable_cos` | `true` | Manage the COS replication configuration |
| `tc_dr_bucket_name` / `bucket_appid` | `""` | Source bucket (short or full name) |
| `tc_dr_replication_role` | `""` | CAM role QCS used by replication |
| `tc_dr_replication_rules` | `[]` | COS replication rules (DR destination buckets) |
| `tc_dr_enable_clb` | `false` | Manage the standby CLB in the DR region |
| `tc_dr_clb_id` / `clb_name` | `""` | Identify the standby load balancer |
| `tc_dr_clb_type` | `OPEN` | `OPEN` or `INTERNAL` |
| `tc_dr_clb_vpc_id` / `subnet_id` | `""` | DR-region networking |
| `tc_dr_listener_port` | `80` | Standby listener port |
| `tc_dr_listener_protocol` | `TCP` | Standby listener protocol |
| `tc_dr_scheduler` | `WRR` | Load balancing algorithm |
| `tc_dr_health_check` | *(see defaults)* | Listener health check |
| `tc_dr_targets` | `[]` | DR-region backends `{instance_id\|eni_ip, port, weight}` |
| `tc_dr_purge` | `true` | Deregister backends not listed |
| `tc_dr_waiter_timeout` / `waiter_delay` | `300` / `5` | Waiter tuning |

Credentials and region follow the collection defaults (`TENCENTCLOUD_*`
environment variables, or `~/.tencentcloud/default.configure`).

## Example

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_disaster_recovery
      vars:
        tc_dr_region: ap-guangzhou
        tc_dr_dr_region: ap-singapore
        # Golden image of the production database server
        tc_dr_image_name: prod-db-golden
        tc_dr_image_instance_id: ins-xxxxxxxx
        # Replicate the data bucket to the DR region
        tc_dr_bucket_name: prod-data
        tc_dr_replication_role: qcs::cam::uin/100000000001:roleName/COSReplicationRole
        tc_dr_replication_rules:
          - ID: replica
            Status: Enabled
            Prefix: ""
            Destination:
              Bucket: qcs::cos:ap-singapore::dr-data-1250000000
              StorageClass: STANDARD
        # Standby entry point in the DR region
        tc_dr_enable_clb: true
        tc_dr_clb_name: prod-standby
        tc_dr_clb_vpc_id: vpc-xxxxxxxx
        tc_dr_clb_subnet_id: subnet-xxxxxxxx
```

## Failover

After a disaster, rebuild the fleet in the DR region from the golden image
(e.g. with `tc_launch` or `tc_web_stack` in the DR region), then populate
`tc_dr_targets` and re-run the role to attach the rebuilt backends to the
standby CLB. The golden image is created on the first run and only updates
name/description afterwards; to re-baseline it, remove it (`state=absent`)
and run the role again.

## Teardown

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_disaster_recovery
      vars:
        tc_dr_state: absent
        tc_dr_image_id: img-xxxxxxxx
        tc_dr_bucket_name: prod-data
        tc_dr_clb_id: lb-xxxxxxxx
```

The standby CLB (listener then load balancer) is removed first, then the
replication configuration, then the golden image.
