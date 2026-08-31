# tc_tem_application

Provision a TEM environment and application, optionally deploy an image or
package version, and reconcile its access-service mappings as one unit.

## Required variables

For creation, set `tc_tem_application_environment_name` and
`tc_tem_application_name` (or pass their existing IDs). To deploy a version,
also set `tc_tem_application_deploy_version` and
`tc_tem_application_deployment`.

Deletion deliberately requires explicit environment and application IDs. Set
`tc_tem_application_destroy_environment: true` only when the environment belongs
exclusively to this application and should also be destroyed.

## Example

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_tem_application
      vars:
        tc_tem_application_environment_name: production
        tc_tem_application_vpc_id: vpc-xxxxxxxx
        tc_tem_application_subnet_ids: [subnet-xxxxxxxx]
        tc_tem_application_name: order-api
        tc_tem_application_deploy_version: v2026.08.31
        tc_tem_application_deployment:
          InitPodNum: 2
          CpuSpec: 1
          MemorySpec: 2
          DeployMode: IMAGE
          ImgRepo: ccr.ccs.tencentyun.com/example/order:v2026.08.31
          SecurityGroupIds: [sg-xxxxxxxx]
        tc_tem_application_services:
          - name: order-api
            access_type: CLUSTER
            service:
              Ports: [8080]
              PortMappingItemList:
                - {Port: 80, TargetPort: 8080, Protocol: TCP}
```

The role publishes `tc_tem_application_result` with the resolved environment
and application IDs and the effective resource payloads.
