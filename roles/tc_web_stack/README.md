# tc_web_stack

Provision a complete Tencent Cloud web stack in one call: a CVM instance pool,
a MySQL CDB instance and a Redis cache, fronted by a CLB with an HTTP listener.
The CVM instances are automatically registered as CLB backends on the web port.

Every component can be skipped by clearing its identity variables; the role
only manages what it is told about.

## Role variables

| Variable | Default | Description |
| --- | --- | --- |
| `tc_web_stack_state` | `present` | `present` provisions the stack, `absent` tears it down in reverse order |
| `tc_web_stack_region` | *(module default)* | Region for all resources; override per run with a play variable |
| `tc_web_stack_enable_cvm` | `true` | Manage the CVM tier |
| `tc_web_stack_instance_id` | `""` | CVM instance id (existing instance) |
| `tc_web_stack_instance_name` | `""` | Match instance by name |
| `tc_web_stack_image_id` / `instance_type` | `""` | Image and model at creation |
| `tc_web_stack_vpc_id` / `subnet_id` | `""` | Networking at creation |
| `tc_web_stack_security_group_ids` | `[]` | Security groups to bind |
| `tc_web_stack_tags` | `{}` | Tags applied to the instances |
| `tc_web_stack_exact_count` / `count_tag` | `null` / `{}` | Exact-count pool management |
| `tc_web_stack_enable_cdb` | `true` | Manage the CDB tier |
| `tc_web_stack_cdb_instance_id` / `cdb_name` | `""` | Identify the CDB instance |
| `tc_web_stack_cdb_engine_version` / `memory` / `volume` | `8.0` / `1000` / `50` | CDB specification at creation |
| `tc_web_stack_cdb_password` | `""` | CDB root password |
| `tc_web_stack_enable_redis` | `true` | Manage the Redis tier |
| `tc_web_stack_redis_instance_id` / `redis_name` | `""` | Identify the Redis instance |
| `tc_web_stack_redis_type_id` / `mem_size` | `2` / `4096` | Redis model and memory at creation |
| `tc_web_stack_enable_clb` | `true` | Manage the CLB tier |
| `tc_web_stack_lb_id` / `lb_name` | `""` | Identify the load balancer |
| `tc_web_stack_lb_type` | `OPEN` | `OPEN` or `INTERNAL` |
| `tc_web_stack_listener_port` | `80` | HTTP listener port |
| `tc_web_stack_listener_name` | `""` | Listener name, defaults to `<lb_name>-http` |
| `tc_web_stack_scheduler` | `WRR` | `WRR`, `LEAST_CONN`, `IP_HASH` ... |
| `tc_web_stack_health_check` | *(see defaults)* | Listener health check configuration |
| `tc_web_stack_targets` | `[]` | Explicit backends `{instance_id\|eni_ip, port, weight}` |
| `tc_web_stack_register_backends` | `true` | Auto-register the created CVM pool on the web port |
| `tc_web_stack_web_port` | `8080` | Port used by auto-derived backends |
| `tc_web_stack_target_weight` | `10` | Weight of auto-derived backends |
| `tc_web_stack_purge` | `true` | Deregister backends not listed on the listener |
| `tc_web_stack_waiter_timeout` / `waiter_delay` | `300` / `5` | Waiter tuning |

Credentials and region follow the collection defaults (`TENCENTCLOUD_*`
environment variables, or `~/.tencentcloud/default.configure`).

## Example

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_web_stack
      vars:
        tc_web_stack_region: ap-guangzhou
        tc_web_stack_instance_name: web-01
        tc_web_stack_image_id: img-xxxxxxxx
        tc_web_stack_instance_type: S5.MEDIUM2
        tc_web_stack_vpc_id: vpc-xxxxxxxx
        tc_web_stack_subnet_id: subnet-xxxxxxxx
        tc_web_stack_security_group_ids: [sg-xxxxxxxx]
        tc_web_stack_cdb_name: prod-mysql
        tc_web_stack_cdb_password: "{{ vault_cdb_password }}"
        tc_web_stack_redis_name: prod-cache
        tc_web_stack_redis_password: "{{ vault_redis_password }}"
        tc_web_stack_lb_name: web-lb
        tc_web_stack_listener_port: 443
```

## Teardown

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_web_stack
      vars:
        tc_web_stack_state: absent
        tc_web_stack_instance_id: ins-xxxxxxxx
        tc_web_stack_cdb_instance_id: cdb-xxxxxxxx
        tc_web_stack_redis_instance_id: crs-xxxxxxxx
        tc_web_stack_lb_id: lb-xxxxxxxx
```

The listener is deleted first (which deregisters its backends), then the load
balancer, Redis, CDB and finally the CVM instances.
