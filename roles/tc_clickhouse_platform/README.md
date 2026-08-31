# tc_clickhouse_platform

Creates or scales a TCHouse-C ClickHouse instance, reconciles instance parameters, and configures metadata and table-data backups. Destruction is guarded and disables backup before destroying the instance.

```yaml
- hosts: localhost
  roles:
    - role: susunola.tencentcloud.tc_clickhouse_platform
      vars:
        tc_clickhouse_platform_instance:
          name: analytics-clickhouse
          zone: ap-beijing-2
          vpc_id: vpc-xxxxxxxx
          subnet_id: subnet-xxxxxxxx
          product_version: 23.8.9.1
          data_spec_name: S_16_64_H
          data_node_count: 2
          data_disk_size: 200
          password: "{{ vault_clickhouse_password }}"
        tc_clickhouse_platform_parameters:
          - name: max_concurrent_queries
            value: '200'
            remark: Managed by Ansible
        tc_clickhouse_platform_backup_config:
          enabled: true
          cos_bucket_name: analytics-backup-1250000000
          meta_strategy: {retain_days: 30, week_days: '1,3,5', execute_hour: 2}
          data_strategy: {retain_days: 14, week_days: '0,6', execute_hour: 3}
          backup_tables: [{Database: analytics, Table: events}]
```

The role publishes `tc_clickhouse_platform_result.restart_required` but intentionally does not restart a production cluster implicitly. Set `tc_clickhouse_platform_allow_destroy: true` only for intentional teardown.
