# Roadmap

1. Foundation: credentials, endpoint overrides, pagination and API errors. **Done**
2. Discovery: CVM instance, VPC and security group facts. **Done**
3. Foundation follow-up: retry policy, integration harness and tagging helpers.
4. VPC: subnet, route table, NAT gateway and elastic IP.
5. CVM lifecycle: instance create/update/delete, image and key pair.
6. CLB: load balancer, listener and backend registration.
7. COS, CDB and TKE modules, plus dynamic inventory.
8. Generated API coverage after stable handwritten module conventions.

Resource modules should be idempotent, support check mode, expose API request
IDs on failure, and use consistent `*_info` naming for read-only operations.
