# tc_redis_stack

Provisions a TencentDB for Redis instance together with application accounts,
automatic backup policy and an optional reusable parameter template. Existing
instances can be adopted by ID, and teardown can resolve an exact instance name
before removing declared accounts and the instance.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_redis_stack
      vars:
        tc_redis_stack_region: ap-guangzhou
        tc_redis_stack_name: production-cache
        tc_redis_stack_zone_name: ap-guangzhou-3
        tc_redis_stack_type_id: 2
        tc_redis_stack_mem_size: 4096
        tc_redis_stack_password: "{{ vault_redis_password }}"
        tc_redis_stack_accounts:
          - name: application
            password: "{{ vault_application_password }}"
            privilege: rw
        tc_redis_stack_backup_storage_days: 30
        tc_redis_stack_parameter_template:
          name: production-cache
          product_type: 2
          parameters:
            timeout: "300"
```

Set `tc_redis_stack_instance_id` to adopt an existing instance. Passwords are
only required when creating an account; set `rotate_password: true` to request
an explicit rotation. Parameter templates are reusable and are retained during
stack teardown unless `remove_on_absent: true` is set.
