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
```

API Gateway APIs currently expose the HTTP/MOCK fields supported by
`api_gateway_api`; SCF backend binding can be represented with an explicit SCF
`apigw` trigger until the API module gains typed SCF backend options.
