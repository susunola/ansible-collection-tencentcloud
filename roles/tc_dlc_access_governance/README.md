# tc_dlc_access_governance

Creates DLC compute engines before their work groups, then exactly reconciles
members and authorization policies. Server-generated policy metadata is ignored
when comparing desired access, so repeated runs remain idempotent.

```yaml
- hosts: localhost
  roles:
    - role: susunola.tencentcloud.tc_dlc_access_governance
      vars:
        tc_dlc_access_governance_data_engines:
          - name: production-spark
            engine_type: spark
            cluster_type: spark_cu
            mode: 1
            size: 16
            min_clusters: 1
            max_clusters: 4
            auto_suspend: true
            state: running
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

The resulting engine IDs are published in
`tc_dlc_access_governance_result.data_engine_ids` for later engine-scoped grants.

Teardown requires `work_group_id` for every group and
`tc_dlc_access_governance_allow_destroy: true`. It removes policies and members,
deletes empty work groups, and only then deletes compute engines.
