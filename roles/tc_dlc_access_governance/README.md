# tc_dlc_access_governance

Connects DLC engine networks to VPC endpoints, creates compute engines, then
creates metadata databases and exactly reconciles work-group members and
authorization policies. Server-generated policy metadata is ignored when comparing
desired access, so repeated runs remain idempotent.

```yaml
- hosts: localhost
  roles:
    - role: susunola.tencentcloud.tc_dlc_access_governance
      vars:
        tc_dlc_access_governance_vpc_connections:
          - engine_network_id: engine-network-xxxxxxxx
            endpoint_name: analytics-endpoint
            vpc_id: vpc-xxxxxxxx
            subnet_id: subnet-xxxxxxxx
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
        tc_dlc_access_governance_databases:
          - name: sales
            comment: Curated sales datasets
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

The resulting endpoint IDs, engine IDs and database names are published in
`tc_dlc_access_governance_result.vpc_endpoint_ids` and
`tc_dlc_access_governance_result.data_engine_ids` and
`tc_dlc_access_governance_result.database_names`.

Teardown requires `work_group_id` for every group, `endpoint_id` for every VPC
connection and `tc_dlc_access_governance_allow_destroy: true`. It removes policies
and members, deletes empty work groups and databases, then removes engines and VPC
endpoints. Non-empty database deletion additionally requires
`allow_delete_nonempty: true` on that database item.
