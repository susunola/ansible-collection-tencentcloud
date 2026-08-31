# tc_tdcpg_platform

Provisions a TDSQL-C PostgreSQL cluster and applies account descriptions,
explicit password rotations and endpoint public-access policy. Destruction is
guarded and requires a stable cluster ID. The first absent run isolates a
cluster; permanent deletion additionally requires `purge: true` on an already
isolated cluster.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_tdcpg_platform
      vars:
        tc_tdcpg_platform_cluster:
          name: production-postgres
          zone: ap-guangzhou-3
          vpc_id: vpc-xxxxxxxx
          subnet_id: subnet-xxxxxxxx
          master_password: "{{ vault_tdcpg_password }}"
          cpu: 4
          memory: 8
        tc_tdcpg_platform_accounts:
          - account_name: root
            description: Platform administrator
        tc_tdcpg_platform_endpoint_wan:
          - endpoint_id: tdcpg-ep-xxxxxxxx
            state: closed
```
