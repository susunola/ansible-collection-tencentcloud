# tc_clb_http

Provision a Tencent Cloud CLB load balancer with one HTTP listener and
reconcile its backend target set (idempotent).

## Role variables

| Variable | Default | Description |
| --- | --- | --- |
| `tc_clb_http_lb_name` | `""` | Load balancer name (required) |
| `tc_clb_http_load_balancer_type` | `OPEN` | `OPEN` (public) or `INTERNAL` |
| `tc_clb_http_vpc_id` | `""` | VPC id (required for `INTERNAL`) |
| `tc_clb_http_subnet_id` | `""` | Subnet id (required for `INTERNAL`) |
| `tc_clb_http_listener_port` | `80` | Listener port |
| `tc_clb_http_health_check` | `{...}` | Health check settings dict |
| `tc_clb_http_targets` | `[]` | List of `{instance_id\|eni_ip, port, weight}` |
| `tc_clb_http_purge` | `true` | Deregister targets not listed |

Credentials and region follow the collection defaults.

## Example

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_clb_http
      vars:
        tc_clb_http_lb_name: web-lb
        tc_clb_http_listener_port: 80
        tc_clb_http_targets:
          - instance_id: ins-xxxxxxxx
            port: 8080
            weight: 100
          - instance_id: ins-yyyyyyyy
            port: 8080
            weight: 100
```
