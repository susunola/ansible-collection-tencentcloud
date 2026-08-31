# tc_tdsql_mysql_platform

Provisions and governs a production TDSQL MySQL platform: instance topology,
accounts, scoped access, parameters, backup policy, SSL and maintenance window.
Each list item or dictionary uses the options of its corresponding collection
module, while the role injects the stable instance ID.

Teardown deletes declared accounts before isolating the instance. It requires
`tc_tdsql_mysql_platform_allow_destroy: true` and an explicit
`instance.instance_id`. Permanent destruction remains controlled by the
instance module's `purge` option and therefore requires a prior isolated run.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_tdsql_mysql_platform
      vars:
        tc_tdsql_mysql_platform_instance:
          name: orders-db
          zone: ap-guangzhou-3
          vpc_id: vpc-xxxxxxxx
          subnet_id: subnet-xxxxxxxx
          spec_code: tdsql.mysql.x4.medium
          disk: 200
          storage_node_count: 3
          replications: 3
          storage_node_cpu: 4
          storage_node_memory: 16
          password: '{{ vault_admin_password }}'
        tc_tdsql_mysql_platform_accounts:
          - username: reporting
            host: 10.%
            password: '{{ vault_reporting_password }}'
        tc_tdsql_mysql_platform_privileges:
          - username: reporting
            host: 10.%
            scope: database
            database: analytics
            privileges: [SELECT]
        tc_tdsql_mysql_platform_parameters:
          max_connections: '1000'
        tc_tdsql_mysql_platform_ssl_enabled: true
        tc_tdsql_mysql_platform_maintenance_window:
          start_time: '02:00'
          duration_hours: 2
          week_days: [Tuesday, Saturday]
```
