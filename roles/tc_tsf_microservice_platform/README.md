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
        tc_tsf_microservice_platform_microservices:
          - {namespace_id: namespace-xxxxxxxx, name: orders, description: Order service}
        tc_tsf_microservice_platform_vm_deployment_groups:
          - {name: orders-vm, application_id: application-xxxxxxxx, namespace_id: namespace-xxxxxxxx, cluster_id: cluster-xxxxxxxx}
        tc_tsf_microservice_platform_container_deployment_groups:
          - {name: orders-container, application_id: application-xxxxxxxx, namespace_id: namespace-xxxxxxxx, cluster_id: cluster-xxxxxxxx, replicas: 3}
```
