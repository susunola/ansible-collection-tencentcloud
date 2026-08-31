# tc_oceanus_streaming_platform

Builds an Oceanus workspace, an optional dedicated Flink cluster, and its jobs. Teardown stops and deletes jobs before deleting the cluster and workspace.

```yaml
- hosts: localhost
  roles:
    - role: susunola.tencentcloud.tc_oceanus_streaming_platform
      vars:
        tc_oceanus_streaming_platform_workspace:
          name: production-streaming
          description: Production Flink workloads
        tc_oceanus_streaming_platform_cluster:
          name: production-flink
          region_id: 1
          zone_id: 100001
          login_password: "{{ vault_flink_ui_password }}"
          vpc_descriptions: [{VpcId: vpc-xxxxxxxx, SubnetId: subnet-xxxxxxxx}]
          default_cos_bucket: flink-artifacts-1250000000
          cu: 19
        tc_oceanus_streaming_platform_folders:
          - {name: production-jobs, folder_type: 0, parent_id: root}
          - {name: production-artifacts, folder_type: 1, parent_id: root}
        tc_oceanus_streaming_platform_resources:
          - resource:
              name: orders-processor
              resource_location:
                StorageType: 1
                Param: {Bucket: flink-artifacts-1250000000, Path: jars/orders-1.0.jar, Region: ap-guangzhou}
            config:
              resource_location:
                StorageType: 1
                Param: {Bucket: flink-artifacts-1250000000, Path: jars/orders-1.1.jar, Region: ap-guangzhou}
              remark: desired-release
        tc_oceanus_streaming_platform_meta_tables:
          - table_name: orders
            database_name: production
            database_id: 12
            flink_version: Flink-1.17
            ddl: |
              CREATE TABLE orders (id BIGINT, amount DECIMAL(18, 2))
              WITH ('connector' = 'kafka')
        tc_oceanus_streaming_platform_jobs:
          - job:
              name: orders-stream
              job_type: 1
              cluster_type: 2
              flink_version: Flink-1.17
            config:
              program_args: SELECT * FROM orders
              default_parallelism: 4
              checkpoint_interval: 60
              auto_recover: true
            desired_status: stopped
            # For a running job, add a stable description to create one reusable savepoint:
            # savepoint: {description: before-release-2026-08-31}
```

Folders are created before contained resources and jobs. Resources and their desired latest immutable artifact version are reconciled before jobs. Each structured job is reconciled in three phases: definition, immutable configuration publication, then runtime state using the new version. Flat job dictionaries remain supported when no configuration publication is needed. Teardown reverses the dependency order by deleting jobs, resources and then folders; nested folders should be declared parent-first because teardown reverses the list.

An optional `savepoint` is triggered only after the job has converged to `running`. Its description acts as an idempotency key; change it for each intentional release checkpoint or set `force: true` for an explicitly repeated snapshot.

Metadata tables require the dedicated cluster input and are reconciled before jobs. Oceanus exposes DDL lookup and update but no metadata-table deletion API, so workspace teardown remains the service-level cleanup boundary for these tables.

Set `tc_oceanus_streaming_platform_allow_destroy: true` only for intentional teardown. CU scale-down also requires `allow_scale_down: true` in the cluster input.
