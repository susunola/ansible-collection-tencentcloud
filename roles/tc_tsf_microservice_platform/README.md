# tc_tsf_microservice_platform

Reconciles foundational TSF namespaces and applications. The role creates
namespaces before applications and removes applications before namespaces.
Destruction requires an explicit safety opt-in.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_tsf_microservice_platform
      vars:
        tc_tsf_microservice_platform_clusters:
          - {name: production, cluster_type: C, vpc_id: vpc-xxxxxxxx, subnet_id: subnet-xxxxxxxx}
        tc_tsf_microservice_platform_namespaces:
          - name: production
            cluster_id: cluster-xxxxxxxx
            resource_type: DEF
            high_availability: true
        tc_tsf_microservice_platform_applications:
          - name: orders
            application_type: C
            microservice_type: N
            description: Order service
            framework_type: SpringCloud
```
