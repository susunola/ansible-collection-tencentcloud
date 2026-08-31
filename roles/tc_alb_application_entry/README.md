# tc_alb_application_entry

Provisions an Application Load Balancer with target groups, exact backend sets
and HTTP, HTTPS or QUIC listeners. A listener nested under a target group gets a
default `ForwardGroup` action automatically; provide `default_actions` only for
advanced routing.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_alb_application_entry
      vars:
        tc_alb_application_entry_region: ap-guangzhou
        tc_alb_application_entry_name: production-entry
        tc_alb_application_entry_address_type: Internet
        tc_alb_application_entry_vpc_id: vpc-xxxxxxxx
        tc_alb_application_entry_zone_mappings:
          - ZoneId: ap-guangzhou-3
            SubnetId: subnet-xxxxxxxx
        tc_alb_application_entry_target_groups:
          - name: application
            targets:
              - {ip: 10.0.1.10, port: 8080, weight: 100}
            listeners:
              - {name: http, port: 80, protocol: HTTP}
```

For teardown, include each `target_group_id`. The role removes listeners,
purges backends, deletes target groups, authorizes disabling ALB deletion
protection, and finally removes the load balancer.
