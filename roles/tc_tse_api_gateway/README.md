# tc_tse_api_gateway

Provisions a TSE cloud-native API gateway, upstream services, routes,
consumers, consumer groups, credentials, public networks with access control, and service- or route-scoped
rate limits, CORS and IP restrictions. Policy entries use the concrete service or route `resource_id`. Routes
may reference `service_name`; the role resolves the created service ID before
route creation. Guarded teardown removes routes and services before the gateway.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_tse_api_gateway
      vars:
        tc_tse_api_gateway_gateway:
          name: production-gateway
          gateway_version: 2.5.1
          feature_version: STANDARD
          node_config: {Specification: 2c4g, Number: 2}
          vpc_config: {VpcId: vpc-xxxxxxxx, SubnetId: subnet-xxxxxxxx}
        tc_tse_api_gateway_services:
          - name: orders
            protocol: http
            timeout: 30000
            retries_count: 2
            upstream_type: IPList
            upstream_info:
              Targets: [{Host: 10.0.0.10, Port: 8080, Weight: 100}]
        tc_tse_api_gateway_routes:
          - name: orders-api
            service_name: orders
            methods: [GET, POST]
            paths: [/orders]
            protocols: [https]
        tc_tse_api_gateway_consumer_groups:
          - {name: trusted-clients, status: Enable}
        tc_tse_api_gateway_secret_keys:
          - name: mobile-api-key
            secret_type: ApiKey
            generate_type: System
            resource_type: Consumer
        tc_tse_api_gateway_cors_policies:
          - scope: route
            resource_id: route-xxxxxxxx
            origins: ['https://app.example.com']
            methods: [GET, POST]
        tc_tse_api_gateway_ip_restrictions:
          - scope: service
            resource_id: service-xxxxxxxx
            restriction_type: whiteList
            addresses: [10.0.0.0/8]
```
