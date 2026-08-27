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
8. Lookup plugins (0.5.0): `sts_caller_identity` and `ssm_parameter`. **Done**
9. Credential profiles (0.5.0): TCCLI-style profiles from
   `~/.tencentcloud/default.configure` with param > env > profile precedence
   for credentials and region. **Done**
10. CAM and COS (0.5.0): `cam_user`, `cam_role`, `cam_policy` write modules,
    `cam_role_info`/`cam_policy_info`, and `cos_bucket`/`cos_bucket_info`
    built on the `qcloud_cos` SDK via `module_utils/cos.py`. **Done**
11. Project governance (0.5.0): `MAINTAINERS.md`, `SECURITY.md`, issue and PR
    templates, action groups and plugin routing in `meta/runtime.yml`, and
    automatic changelog-fragment folding in the release workflow. **Done**
12. SDK contract tests (0.5.0): `tests/contract/` audits every module's
    request construction against the real SDK models in CI, catching wrong
    field names and types that fake-based unit tests cannot. **Done**
13. Coverage batch 1 (0.6.0): generated `_info` modules for AS, SCF, CFS,
    Lighthouse, CynosDB, PostgreSQL, SQL Server, MariaDB, Elasticsearch,
    CKafka, TCR and API Gateway; contract tests auto-discover modules and
    `scripts/sync_registry.py` keeps README/action_groups in sync. **Done**
14. Coverage batch 2 (0.7.0): generated `_info` modules for NAT/VPN
    gateways, GAAP, CDN, CloudAudit, CWP, WAF, SSL, Organization, Monitor,
    CLS, TAT and Billing; the generator now supports token and page-number
    pagination and unpaginated responses. **Done**
15. Coverage batches 3+4 (0.8.0): `scripts/discover_info_specs.py`
    introspects the installed SDK and nominates `_info` specs automatically;
    126 generated modules raise product coverage from 36 to 162 distinct
    services, each with a generated unit test and contract coverage. **Done**
16. Coverage batch 5 (0.9.0): every product on the official API index with a
    usable list API is covered — 36 more generated `_info` modules via new
    pagination modes (no-total short-page termination, custom token field
    pairs, unpaginated list calls). **Done**

## Next

17. CLB write modules (`clb_load_balancer`, listeners and attachments) on top
    of the existing `clb_load_balancer_info`.
18. `cvm_instance` scaling: `exact_count`-style batch create/terminate with
    per-zone spread.
19. Integration CI: run the integration targets on a schedule against a real
    account, with cost guardrails (budget caps, automatic teardown of leaked
    resources).
20. Coverage reporting for unit and integration tests.
21. Galaxy namespace and publishing: the release workflow already publishes
    on tags once `GALAXY_API_KEY` is configured.
22. Curate auto-generated modules that hide required request parameters
    (e.g. `teo` ZoneId, `mqtt`/`emr` InstanceId, `lcic` SdkAppId): move them
    into curated SPECS with `extra_params` or drop them.

Resource modules must be idempotent, support check mode, expose API request
IDs on failure, and use consistent `*_info` naming for read-only operations.
