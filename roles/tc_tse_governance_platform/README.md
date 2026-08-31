# tc_tse_governance_platform

Provisions a TSE registry engine with governance namespaces, services, aliases,
configuration groups, draft configuration files and versioned releases. Destruction requires an
explicit engine ID and removes dependent resources in reverse order.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_tse_governance_platform
      vars:
        tc_tse_governance_platform_engine:
          name: production-nacos
          engine_type: nacos
          engine_version: '2.4.3'
          product_version: STANDARD
        tc_tse_governance_platform_namespaces:
          - name: production
        tc_tse_governance_platform_services:
          - {namespace: production, name: orders}
        tc_tse_governance_platform_instances:
          - {namespace: production, service: orders, host: 10.0.0.30, port: 8080, protocol: http, weight: 100}
        tc_tse_governance_platform_aliases:
          - {alias_namespace: shared, alias: orders-api, namespace: production, service: orders}
        tc_tse_governance_platform_lane_groups:
          - name: orders-gray
            traffic_entries: [{Namespace: production, Service: edge-gateway}]
            destinations: [{Namespace: production, Service: orders}]
            rules: [{Name: canary, Enable: true}]
        tc_tse_governance_platform_config_groups:
          - {namespace: production, name: application}
        tc_tse_governance_platform_config_files:
          - namespace: production
            group: application
            name: orders.yaml
            format: YAML
            content: "server:\n  port: 8080\n"
        tc_tse_governance_platform_config_releases:
          - namespace: production
            group: application
            name: orders.yaml
            release_name: production
            format: YAML
            content: "server:\n  port: 8080\n"
```
