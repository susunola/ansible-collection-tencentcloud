# tc_launch

Launch Tencent Cloud CVM instances (idempotently) with security groups,
tags and optional exact-count pool management.

## Role variables

| Variable | Default | Description |
| --- | --- | --- |
| `tc_launch_state` | `present` | `present`, `absent`, `running` or `stopped` |
| `tc_launch_instance_id` | `""` | Operate on this instance id |
| `tc_launch_instance_name` | `""` | Match instance by name |
| `tc_launch_image_id` | `""` | Image id at creation |
| `tc_launch_instance_type` | `""` | Instance model at creation |
| `tc_launch_vpc_id` | `""` | VPC id at creation |
| `tc_launch_subnet_id` | `""` | Subnet id at creation |
| `tc_launch_security_group_ids` | `[]` | Security groups to bind |
| `tc_launch_tags` | `{}` | Tags applied to the instance |
| `tc_launch_exact_count` | `null` | Desired pool size, requires `tc_launch_count_tag` |
| `tc_launch_count_tag` | `{}` | Tag pairs identifying the pool |
| `tc_launch_waiter_timeout` | `300` | Seconds to wait for state changes |

Credentials and region follow the collection defaults (`TENCENTCLOUD_*`
environment variables, or `~/.tencentcloud/default.configure`).

## Example

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_launch
      vars:
        tc_launch_instance_name: web-01
        tc_launch_image_id: img-xxxxxxxx
        tc_launch_instance_type: S5.MEDIUM2
        tc_launch_vpc_id: vpc-xxxxxxxx
        tc_launch_subnet_id: subnet-xxxxxxxx
        tc_launch_security_group_ids: [sg-xxxxxxxx]
        tc_launch_tags:
          env: prod
          tier: web
```
