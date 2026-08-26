# Roadmap

## Done

1. Foundation: credentials, endpoint overrides, pagination and API errors. **Done**
2. Discovery: CVM instance, VPC and security group facts. **Done**
3. Foundation follow-up (0.3.0): retry policy, unified paginator, tag and
   diff helpers, waiter framework, base module class. **Done**
4. First idempotent resource module: `security_group` with present/absent,
   check mode, diff output and tag management. **Done**

## Next

5. Network closure: `vpc`, `subnet`, `route_table`, `security_group_rule`,
   `eip`, `key_pair` write modules reusing the `security_group` template.
6. Enterprise reliability: STS AssumeRole, inventory cache, CI version
   matrix, CAM least-privilege policy, integration account cost guardrails,
   Galaxy publishing.
7. Service expansion by real usage: CVM lifecycle, CLB, TKE, COS, CDB,
   CAM/KMS, Monitor/CLS.
8. Dynamic inventory plugin, then generated API coverage once handwritten
   conventions are stable.

Resource modules must be idempotent, support check mode, expose API request
IDs on failure, and use consistent `*_info` naming for read-only operations.
