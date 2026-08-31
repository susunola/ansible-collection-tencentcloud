# tc_shared_file_storage

Provisions a CFS file system with a permission group, exact client permission
rules and an optional automatic snapshot policy. Existing file systems can be
adopted by ID; teardown resolves an exact file-system name before unbinding the
snapshot policy and deleting resources in dependency order.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_shared_file_storage
      vars:
        tc_shared_file_storage_region: ap-guangzhou
        tc_shared_file_storage_name: application-data
        tc_shared_file_storage_zone: ap-guangzhou-3
        tc_shared_file_storage_vpc_id: vpc-xxxxxxxx
        tc_shared_file_storage_subnet_id: subnet-xxxxxxxx
        tc_shared_file_storage_permission_group_name: application-nfs
        tc_shared_file_storage_permission_rules:
          - client_ip: 10.0.0.0/16
            access: RW
            user_permission: root_squash
        tc_shared_file_storage_snapshot_policy:
          enabled: true
          name: daily-retention
          hour: "02"
          alive_days: 30
```

When deleting declared permission rules, provide
`tc_shared_file_storage_permission_group_id`; this avoids ambiguous destructive
operations. The snapshot policy is force-unbound before the file system is
deleted.
