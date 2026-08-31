# tc_tse_api_gateway

Provisions a TSE cloud-native API gateway, upstream services, routes,
consumers, consumer groups, credentials, AI model services and APIs, TLS certificates, WAF protection, public networks with access control, and service- or route-scoped
rate limits, canary traffic rules, CORS and IP restrictions. Policy entries use concrete service or route IDs. Routes
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
        tc_tse_api_gateway_consumer_group_memberships:
          - consumer_group_name: trusted-clients
            consumer_names: [mobile-application]
        tc_tse_api_gateway_model_api_group_auths:
          - model_api_name: chat-completions
            consumer_group_names: [trusted-clients]
        tc_tse_api_gateway_secret_keys:
          - name: mobile-api-key
            secret_type: ApiKey
            generate_type: System
            resource_type: Consumer
        tc_tse_api_gateway_model_services:
          - name: openai-primary
            secret_key_names: [mobile-api-key]
            config:
              ServiceType: LLMService
              ModelProvider: OpenAI
              ModelProtocol: OpenAI/v1
              ModelSelector: Specify
              DefaultModel: gpt-4.1
        tc_tse_api_gateway_model_apis:
          - name: chat-completions
            model_service_names: [openai-primary]
            config:
              SceneType: Chat
              RequestProtocol: OpenAI
              BasePath: /v1
        tc_tse_api_gateway_certificates:
          - name: public-api
            cert_source: ssl
            ssl_certificate_id: jDZJ5jSa
            bind_domains: [api.example.com]
            cert_type: SVR
            cert_usage: SERVER
        tc_tse_api_gateway_waf_domains: [api.example.com]
        tc_tse_api_gateway_waf_protections:
          - {scope: Global, enabled: true}
          - {scope: Route, resource_ids: [route-xxxxxxxx], enabled: true}
        tc_tse_api_gateway_canary_rules:
          - service_id: service-xxxxxxxx
            priority: 90
            config:
              Enabled: true
              ConditionList: [{Type: header, Key: X-Canary, Operator: exact, Value: beta}]
              BalancedServiceList: [{ServiceID: service-xxxxxxxx, Percent: 100}]
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

`secret_key_names` and `model_service_names` are role-only convenience fields.
They are resolved from resources created in the same role run. Direct
`config.SecretKeyIds` and `config.ListModelServiceId` remain supported.
Memberships and Model API authorizations similarly accept name-based references;
their direct ID fields remain supported for externally managed resources.
