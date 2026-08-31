# tc_serverless_application

Deploy an SCF function with environment and VPC settings, aliases, event
triggers and optional API Gateway service publication.

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_serverless_application
      vars:
        tc_serverless_application_function_name: order-webhook
        tc_serverless_application_runtime: Python3.10
        tc_serverless_application_handler: index.main_handler
        tc_serverless_application_zip_file: ./dist/function.zip
        tc_serverless_application_environment: {LOG_LEVEL: INFO}
        tc_serverless_application_triggers:
          - name: every-five-minutes
            trigger_type: timer
            trigger_desc: '0 */5 * * * * *'
        tc_serverless_application_api_gateway_enabled: true
        tc_serverless_application_api_service_name: order-api
        tc_serverless_application_apis:
          - name: order-webhook
            path: /orders
            method: POST
            service_type: SCF
            scf_function_qualifier: production
```

For an API item with `service_type: SCF`, the role defaults the backend
function and namespace to the function managed by the role. A version or alias
can be selected with `scf_function_qualifier`.

When deleting an API-enabled application, pass the explicit
`tc_serverless_application_api_service_id`. The role unreleases the selected
environment, removes managed APIs and deletes the service before removing SCF
triggers, aliases and the function.
