# tc_cdwpg_analytics_platform

Creates a CDW PostgreSQL instance, reconciles CN/DN parameters, and installs an exact ordered pg_hba access policy. Parameter restart requirements are reported but the role never restarts a production cluster implicitly.

```yaml
- hosts: localhost
  roles:
    - role: susunola.tencentcloud.tc_cdwpg_analytics_platform
      vars:
        tc_cdwpg_analytics_platform_instance:
          name: analytics-pg
          zone: ap-guangzhou-3
          vpc_id: vpc-xxxxxxxx
          subnet_id: subnet-xxxxxxxx
          charge_properties: {ChargeType: POSTPAID_BY_HOUR}
          admin_password: "{{ vault_cdwpg_password }}"
          product_version: 6.3.0
          resources:
            - {SpecName: S_4_16_H, Count: 2, Type: cn}
            - {SpecName: S_8_32_H, Count: 3, Type: dn}
        tc_cdwpg_analytics_platform_parameters:
          - {node_type: cn, name: max_connections, value: '500'}
        tc_cdwpg_analytics_platform_hba_rules:
          - {type: hostssl, database: all, user: analysts, address: 10.0.0.0/16, method: md5}
```

HBA order is preserved because PostgreSQL uses first-match semantics. Set `tc_cdwpg_analytics_platform_allow_destroy: true` only for intentional teardown.
