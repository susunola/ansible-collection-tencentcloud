# tc_database_stack

Provision a TencentDB for MySQL instance and its operational baseline:
databases, accounts, exact privilege sets and backup retention.

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_database_stack
      vars:
        tc_database_stack_name: orders
        tc_database_stack_zone: ap-guangzhou-3
        tc_database_stack_memory: 4000
        tc_database_stack_volume: 100
        tc_database_stack_root_password: "{{ vault_mysql_root_password }}"
        tc_database_stack_vpc_id: vpc-xxxxxxxx
        tc_database_stack_subnet_id: subnet-xxxxxxxx
        tc_database_stack_databases:
          - {name: orders, character_set: utf8mb4}
        tc_database_stack_accounts:
          - username: orders_app
            password: "{{ vault_orders_password }}"
            privileges:
              databases:
                - {database: orders, privileges: [SELECT, INSERT, UPDATE, DELETE]}
```

The role publishes `tc_database_stack_result`. Deletion requires an explicit
instance ID when dependent databases or accounts are listed, and removes them
before isolating the instance.
