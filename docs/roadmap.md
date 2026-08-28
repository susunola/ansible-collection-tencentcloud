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
17. CLB write modules (0.10.0): `clb_load_balancer`, `clb_listener` and
    `clb_listener_target` with async task polling (`wait_for_task`), tag
    reconciliation and exact-set target management. **Done**
18. Write module batch (0.12.0): `cvm_image`, `cfs_file_system` and
    `lighthouse_instance` — the first three of the fifteen planned write
    modules, each with idempotency, check mode, diff and contract tests.
    **Done**
19. TAT connection plugin (0.12.0): `connection/tat.py` runs commands and
    streams files through the TAT agent (no public IP/SSH), reusing
    `module_utils.client` via an option adapter. **Done**
20. EDA event sources (0.12.0): `cls_topic` (rolling-window CLS log polling)
    and `cmq_queue` (long-poll with optional ack) for Event-Driven Ansible.
    **Done**
21. Inventory expansion (0.12.0): `tencentcloud_clb` (load balancers +
    listeners + backends) and `tencentcloud_sg` (security groups + ENIs).
    **Done**
22. Roles (0.12.0): `tc_launch` (CVM pool with `exact_count`) and
    `tc_clb_http` (LB + HTTP listener + targets in one call). **Done**
23. Integration test expansion (0.12.0): `cfs_file_system` and `clb_http`
    targets over a throwaway VPC, sweeper extended to CLB/CFS. **Done**
24. Module tier governance (0.12.0): `check_module_tiers.py` CI gate
    (generated vs core vs unclassified) plus structural validation of every
    generator spec (`validate_specs`). **Done**
25. CVM pool scaling (0.11.0): `cvm_instance` `exact_count`/`count_tag`
    batch create/terminate with oldest-first eviction and PREPAID
    protection. **Done**
26. Write module batches 2-7 (0.12.0): `peering_connection`,
    `vpn_gateway`, `nat_gateway`, `ssm_parameter`, `scf_function`,
    `ckafka_topic`, `cbs_disk`, `dnspod_record`, `clb_rule`,
    `ssl_certificate`, `tag`, `redis_instance`, `cdb_instance`,
    `tke_cluster` — the write-module count grows from 7 to 21, every one
    with idempotency, check mode, diff and contract tests. **Done**
27. COS bucket config face (0.12.0): `cos_bucket` CORS and lifecycle
    configuration management on top of the `qcloud_cos` SDK. **Done**
28. EIP elasticity (0.12.0): bandwidth and charge-type updates on existing
    EIPs. **Done**
29. CI hardening (0.12.0): matrix extended to ansible-core 2.19-2.21 and
    Python 3.13, whole-repo ruff with the ansible-test rule set, coverage
    gate raised to 70%. **Done**
30. Integration target expansion (0.12.0): `cam_user`/`cos_bucket`/
    `key_pair` targets plus opt-in `cvm_image`/`lighthouse` lifecycle
    targets with an extended sweeper. **Done**
31. Generated-module polish (0.12.0): `request_id` on every returned info,
    token-paginated `ids`/`filters` passthrough fix, 5 auto modules
    renamed to drop redundant prefixes, 4 zero-arg single-object modules
    added (196 generated modules). **Done**
32. SDK drift sentinel (0.12.0): `info_specs_auto.py` carries a
    `GENERATED_SDK_VERSION` stamp; `check_sdk_drift.py` fails CI with
    regeneration instructions when the environment SDK drifts. **Done**
33. Failure-path coverage (0.12.0): the real `sdk_call` fail_json contract
    is pinned in unit tests and every generated `_info` test gains a
    `test_run_module_fails_cleanly_on_sdk_error` case. **Done**
34. CVM advanced lifecycle (0.13.0): `cvm_instance` gains `state=rebooted`
    (one-shot `RebootInstances`), `reset_password` (`ResetInstancesPassword`)
    and in-place instance resizing — a drifted `instance_type` on a stopped
    instance is applied with `ResetInstancesType` instead of failing as
    immutable. **Done**

## Next

35. Remaining write modules: `cvm_chc`, `mongodb`, `gaap`, `cdn`, `tcr`
    (the write-module count grows from 21 to 26). **Done** — `mysql` was
    already covered by `cdb_instance` (0.12.0): the new batch adds
    `cvm_chc` (CHC VPC network configuration), `mongodb_instance`
    (create/rename/isolate), `gaap_proxy` (create/open/close/destroy),
    `cdn_domain` (add/start/stop/delete) and `tcr_instance`
    (create/update/delete with idempotent deletion protection).
36. Coverage reporting for unit and integration tests. **Done**: the CI
    SDK contract tests step now collects the module unit tests too (the
    gate only counts what that step measures), and uploads XML + HTML
    coverage reports as artifacts; integration runs collect coverage via
    ``ansible-test --coverage`` and upload it as a report (not a gate,
    since real-cloud coverage fluctuates with account state).
37. Curate auto-generated modules that hide required request parameters
    (e.g. `teo` ZoneId, `mqtt`/`emr` InstanceId, `lcic` SdkAppId): move them
    into curated SPECS with `extra_params` or drop them.
38. Deepen existing write modules: async long-running task polling beyond
    CLB, multi-zone spread for `exact_count`, waiter coverage for database
    instance lifecycles.
39. CVM CHC server lifecycle: rescue mode and network mode switching on
    top of `cvm_chc`. **Done** — the network mode half
    (`ModifyChcNetworkMode`, DEPLOY/BUSINESS) shipped as the
    ``network_mode`` option. The rescue-mode half is NOT API-addressable:
    `EnterRescueMode`/`ExitRescueMode` take an instance `InstanceId` (plain
    CVM, not CHC), and the CHC-specific minios command
    (`ExecuteChcMiniOsCommand`) is absent from the public SDK, so there is
    no supported API surface for it.

Resource modules must be idempotent, support check mode, expose API request
IDs on failure, and use consistent `*_info` naming for read-only operations.
