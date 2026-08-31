# tc_api_gateway_platform

Provisions or adopts an API Gateway service with APIs, environment releases,
API keys, usage plans and service/API/key bindings. Key secrets remain redacted
by modules and secret-bearing role tasks use `no_log`.

Teardown removes both binding types before plans, unreleases environments,
removes APIs and keys, and deletes the service last. Declared plans require
`usage_plan_id` during teardown.
