# tc_dlc_access_governance

Creates DLC work groups and exactly reconciles their members and authorization
policies. Server-generated policy metadata is ignored when comparing desired
access, so repeated runs remain idempotent.

```yaml
- hosts: localhost
  roles:
    - role: susunola.tencentcloud.tc_dlc_access_governance
      vars:
        tc_dlc_access_governance_work_groups:
          - work_group:
              name: analytics-engineers
              description: Production lakehouse users
            members: ['100012345678', '100087654321']
            policies:
              - Catalog: DataLakeCatalog
                Database: sales
                Table: orders
                Operation: SELECT
                PolicyType: TABLE
```

Teardown requires `work_group_id` for every group and
`tc_dlc_access_governance_allow_destroy: true`. It removes policies and members
before deleting the now-empty work group.
