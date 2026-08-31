# tc_doris_analytics_platform

Builds a CDW Doris analytics platform and reconciles named workload groups after the instance becomes available. Destruction is guarded and removes workload groups before destroying the instance.

```yaml
- hosts: localhost
  roles:
    - role: susunola.tencentcloud.tc_doris_analytics_platform
      vars:
        tc_doris_analytics_platform_instance:
          name: analytics-doris
          zone: ap-guangzhou-3
          fe_spec: {SpecName: S_4_16_H, Count: 3, DiskSize: 100}
          be_spec: {SpecName: S_8_32_H, Count: 3, DiskSize: 500}
          vpc_id: vpc-xxxxxxxx
          subnet_id: subnet-xxxxxxxx
          product_version: "2.1"
          charge_properties: {ChargeType: POSTPAID_BY_HOUR}
          admin_password: "{{ vault_doris_password }}"
        tc_doris_analytics_platform_workload_groups:
          - name: interactive
            cpu_share: 800
            memory_limit: 40
            max_concurrency: 30
            max_queue_size: 15
            queue_timeout: 5000
          - name: batch
            cpu_share: 200
            memory_limit: 60
        tc_doris_analytics_platform_user_bindings:
          - user_name: analyst
            hosts: ['%']
            workload_group: interactive
            teardown_workload_group: normal
```

Set `tc_doris_analytics_platform_allow_destroy: true` only for an intentional teardown. A binding with `teardown_workload_group` is moved there before custom groups are deleted.
