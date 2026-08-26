# Roadmap

## Done

1. Foundation: credentials, endpoint overrides, pagination and API errors. **Done**
2. Discovery: CVM instance, VPC and security group facts. **Done**
3. Foundation follow-up (0.3.0): retry policy, unified paginator, tag and
   diff helpers, waiter framework, base module class. **Done**
4. First idempotent resource module: `security_group` with present/absent,
   check mode, diff output and tag management. **Done**
5. Network closure (0.4.0): `vpc`, `subnet`, `route_table`,
   `security_group_rule`, `eip`, `key_pair` write modules plus the matching
   `subnet_info`, `route_table_info`, `eip_info` and `key_pair_info`
   discovery modules. **Done**
6. CVM lifecycle (0.4.0): `cvm_instance` with present/absent/running/stopped
   states and state waiters. **Done**
7. Enterprise reliability (partial, 0.4.0): STS AssumeRole support in every
   module and the `tencentcloud_cvm` dynamic inventory plugin with
   constructed groups and caching. **Done**

## Next

8. Enterprise reliability follow-up: CI version matrix, CAM least-privilege
   policy examples, integration account cost guardrails, Galaxy publishing.
9. Service expansion by real usage: CLB, TKE, COS, CDB, CAM/KMS, Monitor/CLS.
10. Generated API coverage once handwritten conventions are stable.

Resource modules must be idempotent, support check mode, expose API request
IDs on failure, and use consistent `*_info` naming for read-only operations.
