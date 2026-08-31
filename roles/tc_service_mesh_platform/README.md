# tc_service_mesh_platform

Provisions a Tencent Cloud Mesh and reconciles its exact cluster membership,
access logging, distributed tracing and Prometheus integration. Teardown is
guarded by `tc_service_mesh_platform_allow_destroy: true`, requires a stable
mesh ID, and unlinks dependent integrations before deleting the mesh.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_service_mesh_platform
      vars:
        tc_service_mesh_platform_mesh:
          name: production-mesh
          mesh_version: 1.20.5
          mesh_type: HOSTED
        tc_service_mesh_platform_clusters:
          - ClusterId: cls-xxxxxxxx
            Region: ap-guangzhou
            Role: MASTER
        tc_service_mesh_platform_access_log:
          enabled: true
          encoding: JSON
        tc_service_mesh_platform_tracing:
          enabled: true
          sampling: 10
          apm:
            Enable: true
        tc_service_mesh_platform_prometheus:
          config:
            Region: ap-guangzhou
            InstanceId: prom-xxxxxxxx
```
