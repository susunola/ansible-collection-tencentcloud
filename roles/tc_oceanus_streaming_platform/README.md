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
        tc_oceanus_streaming_platform_jobs:
          - name: orders-stream
            job_type: 1
            cluster_type: 2
            flink_version: Flink-1.17
            desired_status: stopped
```

Set `tc_oceanus_streaming_platform_allow_destroy: true` only for intentional teardown. CU scale-down also requires `allow_scale_down: true` in the cluster input.
