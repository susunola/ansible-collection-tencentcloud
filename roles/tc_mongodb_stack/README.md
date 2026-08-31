# tc_mongodb_stack

Provisions a TencentDB for MongoDB replica set or sharded cluster with exact
application-account roles, explicit password rotation and automatic backups.
It can adopt an instance by ID and resolves exact names before safe teardown.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_mongodb_stack
      vars:
        tc_mongodb_stack_region: ap-guangzhou
        tc_mongodb_stack_name: production-mongo
        tc_mongodb_stack_zone: ap-guangzhou-3
        tc_mongodb_stack_version: "5.0"
        tc_mongodb_stack_cluster_type: REPLSET
        tc_mongodb_stack_node_num: 3
        tc_mongodb_stack_memory: 8
        tc_mongodb_stack_volume: 100
        tc_mongodb_stack_password: "{{ vault_mongouser_password }}"
        tc_mongodb_stack_mongo_user_password: "{{ vault_mongouser_password }}"
        tc_mongodb_stack_accounts:
          - username: application
            password: "{{ vault_application_password }}"
            roles:
              - namespace: orders
                access: read_write
```

The built-in `mongouser` password is required by Tencent Cloud when creating or
deleting secondary accounts. Supply it whenever `tc_mongodb_stack_accounts` is
non-empty. Isolation of the instance stops billing and moves it to recycle-bin
retention rather than immediately erasing it.
