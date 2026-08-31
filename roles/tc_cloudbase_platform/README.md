# tc_cloudbase_platform

Provisions a CloudBase environment, static website hosting, authentication
domains and HTTP service routes. Teardown is guarded by
`tc_cloudbase_platform_allow_destroy: true`, requires a stable environment ID,
and removes dependent resources before destroying the environment.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_cloudbase_platform
      vars:
        tc_cloudbase_platform_environment:
          alias: production-app
          package_id: baas_package
          resources: [flexdb, storage, function]
        tc_cloudbase_platform_static_store:
          enable_union: true
        tc_cloudbase_platform_auth_domains:
          - app.example.com
        tc_cloudbase_platform_http_routes:
          - domain: api.example.com
            domain_config:
              Protocol: https
              Routes:
                - Path: /api
                  UpstreamResourceType: cloudrun
                  UpstreamResourceName: backend
```
