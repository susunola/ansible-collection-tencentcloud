# tc_dlc_access_governance

Connects DLC engine networks to VPC endpoints, creates compute engines, then
creates metadata databases and exactly reconciles work-group members and
authorization policies for managed DLC users. Server-generated policy metadata is
ignored when comparing desired access, so repeated runs remain idempotent.

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
        tc_dlc_access_governance_engine_resource_groups:
          - name: production-etl
            data_engine_name: production-spark
            driver_cu_spec: medium
            executor_cu_spec: large
            min_executors: 2
            max_executors: 10
            network_config_names: [private-data]
        tc_dlc_access_governance_spark_jobs:
          - name: daily-customer-etl
            app_type: 1
            data_engine: production-spark
            app_file: cosn://analytics/jobs/customer-etl.jar
            role_arn: 100000000001
            driver_size: medium
            executor_size: large
            executor_nums: 2
            package_source: cos
        tc_dlc_access_governance_labs:
          - name: analytics-notebook
            resource_partition_id: rp-xxxxxxxx
            queue: default
            lab_image: ccr.ccs.tencentyun.com/dlc/jupyter:latest
            image_pull_type: BuiltIn
            lab_image_pull_type: BuiltIn
            enable_token: true
        tc_dlc_access_governance_partition_queues:
          - partition_code: rp-xxxxxxxx
            name: default
            queue_type: 1
            description: Interactive analytics capacity
            resource_usages:
              - resource_type: CU
                billing_item: sv_dlc_standard_cu_standard_cu
                spec: '0:1:4:0'
                min: 32
                max: 128
        tc_dlc_access_governance_resource_configs:
          - name: analytics-ray-small
            template_type: Ray
            head: {name: head, pod_cpu: 4, pod_mem: 16, pod_num: 1}
            workers:
              - name: workers
                pod_cpu: 4
                pod_mem: 16
                min_pod_num: 1
                max_pod_num: 8
                enable_auto_scaling: true
        tc_dlc_access_governance_ray_clusters:
          - name: analytics-ray
            resource_partition_id: rp-xxxxxxxx
            queue: default
            image: ccr.ccs.tencentyun.com/dlc/ray:latest
            image_pull_type: BuiltIn
            resource_config_id: rc-xxxxxxxx
            priority: 5
        tc_dlc_access_governance_databases:
          - name: sales
            comment: Curated sales datasets
        tc_dlc_access_governance_users:
          - user:
              user_id: '100012345678'
              alias: analytics-engineer
              description: Analytics engineering account
            policies:
              - Catalog: DataLakeCatalog
                Database: sales
                Operation: SELECT
                PolicyType: DATABASE
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
        tc_dlc_access_governance_data_mask_strategies:
          - name: mask-customer-phone
            strategy_type: MASK_SHOW_LAST_4
            description: Reveal only the final four digits
            groups:
              - {WorkGroupId: 10042, StrategyType: MASK_SHOW_LAST_4}
```

The resulting endpoint IDs, engine IDs, database names and user IDs are published in
`tc_dlc_access_governance_result.vpc_endpoint_ids` and
`tc_dlc_access_governance_result.data_engine_ids`,
`tc_dlc_access_governance_result.engine_resource_group_ids` and
`tc_dlc_access_governance_result.spark_job_ids` and
`tc_dlc_access_governance_result.lab_ids` and
`tc_dlc_access_governance_result.partition_queue_ids` and
`tc_dlc_access_governance_result.resource_config_ids` and
`tc_dlc_access_governance_result.ray_cluster_ids` and
`tc_dlc_access_governance_result.database_names` and
`tc_dlc_access_governance_result.user_ids`. Mask strategy IDs are available in
`tc_dlc_access_governance_result.data_mask_strategy_ids`.

Teardown requires `work_group_id` for every group, `endpoint_id` for every VPC
connection and `tc_dlc_access_governance_allow_destroy: true`. It removes policies
and members, deletes empty work groups and users, then databases, engine resource
groups, engines and VPC endpoints. Bound user deletion requires
`allow_delete_bound: true` on the user;
non-empty database deletion additionally requires
`allow_delete_nonempty: true` on that database item.

Spark job definitions are created after engines and resource groups. Teardown removes
them before compute resources and retains the module's active-task guard; set
`allow_delete_running: true` on an individual job only when interruption is intended.
Laboratories follow the same compute-foundation ordering and publish stable IDs for
downstream automation.
Partition queues are reconciled before laboratories and removed afterwards. A default
queue additionally requires `allow_delete_default: true` on that queue item.
Resource templates are created before laboratories and deleted only after Lab/Ray
references are gone. External references require `allow_delete_in_use: true`.
Ray clusters share the same queue and resource-template foundations as laboratories
and are removed before those foundations during teardown.

Direct-user policies are exact-set managed when `policies` is declared. During
teardown the role removes direct policies before deleting each user. Work-group
membership remains managed from each work group's `members` list.

Masking strategies are created after their user and work-group subjects. Teardown
requires an exact `strategy_id` and removes masking strategies before those subjects.
