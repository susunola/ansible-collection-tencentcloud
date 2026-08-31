# tc_vpc_foundation

Build a reusable network foundation from one declaration: VPC, multi-zone
subnets, NAT gateways, route tables, security groups and exact-set rules.

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_vpc_foundation
      vars:
        tc_vpc_foundation_name: production
        tc_vpc_foundation_cidr_block: 10.20.0.0/16
        tc_vpc_foundation_tags: {environment: production}
        tc_vpc_foundation_subnets:
          - {name: app-a, cidr_block: 10.20.1.0/24, zone: ap-guangzhou-3}
          - {name: app-b, cidr_block: 10.20.2.0/24, zone: ap-guangzhou-4}
        tc_vpc_foundation_security_groups:
          - name: application
            rules:
              - {direction: ingress, protocol: TCP, port: '443', cidr_block: 10.20.0.0/16}
```

The role publishes `tc_vpc_foundation_result`. During check mode, dependent
resources are skipped when a new VPC has no real ID yet. For deletion, list
dependent resources and prefer explicit IDs; the role removes them before the
VPC.
