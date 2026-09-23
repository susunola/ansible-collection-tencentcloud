# tc_tke_platform

Provision a TKE cluster together with node pools, API endpoints, addons,
authentication, audit delivery, optional CLS log collection, and cluster
autoscaler settings. An existing Managed Prometheus instance may be bound to
the cluster without taking ownership of that instance.

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_tke_platform
      vars:
        tc_tke_platform_name: production
        tc_tke_platform_vpc_id: vpc-xxxxxxxx
        tc_tke_platform_subnet_id: subnet-xxxxxxxx
        tc_tke_platform_cluster_cidr: 172.20.0.0/16
        tc_tke_platform_service_cidr: 172.21.0.0/16
        tc_tke_platform_node_pools:
          - name: general
            launch_configuration_json: >-
              {"InstanceType":"S5.MEDIUM4","SystemDisk":{"DiskType":"CLOUD_PREMIUM","DiskSize":50}}
            autoscaling_group_json: >-
              {"MinSize":2,"MaxSize":10,"VpcId":"vpc-xxxxxxxx","SubnetIds":["subnet-xxxxxxxx"]}
            enable_autoscale: true
            min_nodes_num: 2
            max_nodes_num: 10
            labels: {workload: general}
        tc_tke_platform_endpoints:
          - {access: private, subnet_id: subnet-xxxxxxxx}
        tc_tke_platform_addons:
          - {name: cbs, update_strategy: merge}
        tc_tke_platform_autoscaler:
          is_scale_down_enabled: true
          expander: least-waste
          scale_down_unneeded_time: 15
        tc_tke_platform_prometheus_instance_id: prom-xxxxxxxx
        tc_tke_platform_cls_log_configs:
          - name: container-stdout
            logset_id: xxxxxx-xx-xx-xx-xxxxxxxx
            log_config:
              name: container-stdout
              logType: container_stdout
              clsDetail: {region: ap-guangzhou}
```

The role publishes `tc_tke_platform_result`. During check mode, child resources
are skipped if a newly planned cluster has no real cluster ID. For safe
teardown, deletion requires `tc_tke_platform_cluster_id` and removes addons,
endpoints and node pools before the cluster.
CLS log configurations are removed first. Their raw payloads are not updated
in place: if a configuration changes, remove the named configuration and
recreate it deliberately. The referenced CLS logset must already exist.
On teardown, the Prometheus cluster binding is removed before deleting the
cluster; the Prometheus instance itself is never deleted by this role.
