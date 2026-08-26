# Roadmap

1. Foundation: credentials, endpoint overrides, retries, pagination and tagging.
2. CVM: instance, image, security group, key pair and VPC facts.
3. VPC: VPC, subnet, route table, NAT gateway and elastic IP.
4. CLB: load balancer, listener and backend registration.
5. COS, CDB and TKE modules, plus dynamic inventory.
6. Generated API coverage after stable handwritten module conventions.

Resource modules should be idempotent, support check mode, expose API request
IDs on failure, and use consistent `*_info` naming for read-only operations.
