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

## Completed expansion (historical)

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
    into curated SPECS with `extra_params` or drop them. **In progress** —
    batch 2 verified every remaining candidate against official API docs
    and curated eight more modules (`trtc_call_info`, `ess_file_url_info`,
    `tiw_running_task_info`, `weilingwith_element_profile_page_info`,
    `bsca_kb_component_info`, `svp_saving_plan_coverage_info`,
    `gme_voice_print_info`, `ses_black_email_address_info`). The docstring
    pass confirmed the rest carry no required parameters (filter-only
    fields), and the generator gained `page_number_base` (0-based paging
    for trtc/ccc/bsca) and `no_log` support for curated params.
38. Deepen existing write modules: async long-running task polling beyond
    CLB, multi-zone spread for `exact_count`, waiter coverage for database
    instance lifecycles. **Done** — the async polling half shipped:
    `wait_for_task` now accepts `success_statuses`/`failure_statuses` so
    services with a different status convention than the CLB 0/1/2 integers
    can reuse it (CDB `DescribeAsyncRequestInfo` reports
    SUCCESS/FAILED/KILLED/REMOVED/PAUSED), and `cdb_instance` gained
    `state=restarted` which restarts via `RestartDBInstances` and blocks on
    the async task (verified against the official
    cloud.tencent.com/document/product/236/17488 doc). The multi-zone half
    also shipped: `cvm_instance` `exact_count` accepts `zones` (plus
    optional parallel `subnet_ids`) and spreads the created shortfall
    across the listed AZs as evenly as possible, one `RunInstances` call
    per zone. The lifecycle-waiter half shipped too: `cdb_instance` waits
    for delivery after creation (Status 1 with TaskStatus 0, per the
    CreateDBInstanceHour doc) and for Status 5 (isolated) after
    `state=absent`; `redis_instance` waits for Status 2 (running) after
    creation and Status -3 (pending recycle, or a vanished instance) after
    `state=absent` — all bounded by `waiter_timeout`, whose default rose
    from 120 to 900 seconds in both database modules because creation takes
    several minutes.
39. CVM CHC server lifecycle: rescue mode and network mode switching on
    top of `cvm_chc`. **Done** — the network mode half
    (`ModifyChcNetworkMode`, DEPLOY/BUSINESS) shipped as the
    ``network_mode`` option. The rescue-mode half is NOT API-addressable:
    `EnterRescueMode`/`ExitRescueMode` take an instance `InstanceId` (plain
    CVM, not CHC), and the CHC-specific minios command
    (`ExecuteChcMiniOsCommand`) is absent from the public SDK, so there is
    no supported API surface for it.
40. Deepen write modules batch 2: CDB specification changes, NAT gateway
    forwarding rules and a standalone CBS snapshot module. **Done** — all
    three halves shipped. The CDB half: `cdb_instance` now detects
    `memory`/`volume` drift on an existing instance and applies it with
    `UpgradeDBInstance` (verified against the official
    cloud.tencent.com/document/api/236/15876 doc, which supports both
    upgrade and downgrade; disk capacity can only be expanded). The change
    is tracked through the same `DescribeAsyncRequestInfo` async-task
    polling as `state=restarted` (SUCCESS/FAILED terminal statuses), and
    when only one dimension is given the current value of the other is
    used. The NAT half: a new `nat_gateway_rule` module reconciles the
    DNAT and SNAT rule sets of a gateway (identity keyed on the DNAT
    five-tuple and the SNAT resource triple, replace = delete and
    re-create, deletes run before creates, output-only `NatGatewaySnatId`
    excluded from comparison). The CBS half: a standalone `cbs_snapshot`
    write module manages cloud disk snapshots identified by
    `snapshot_id` or `disk_id` + `snapshot_name` (name lookups return the
    newest snapshot), with `state=present`/`absent`, an async wait for
    `SnapshotState=NORMAL` bounded by `waiter_timeout`, and check mode +
    diff.
41. Write module batch 9: six new write modules growing the count from 39
    to 45. **Done** — `tcr_namespace` (namespaces identified by
    `registry_id` + `name`; public access, auto-scan and vulnerability
    prevention enforced with `ModifyNamespace`), `scf_alias`
    (function aliases identified by `function_name` + `name`, target
    `function_version` enforced with `UpdateAlias`), `scf_version`
    (publish/delete function versions; `$LATEST`/`default` rejected as
    identities), `network_interface` (ENIs identified by
    `network_interface_id` or `name` + `subnet_id`; name, description and
    bound security groups reconciled with
    `ModifyNetworkInterfaceAttribute`), `tke_node_pool` (node pools
    identified by `cluster_id` + `name`, `LaunchConfigurePara` passed as
    raw JSON, autoscale/labels/taints/deletion-protection drift enforced
    with `ModifyClusterNodePool`, `keep_instance` delete option) and
    `elasticsearch_instance` (clusters identified by `instance_id` or
    `name`, creation via `NodeInfoList` with Type=hotData, waits for
    Status 1 on create and disappearance on destroy, bounded by
    `waiter_timeout`). Every module ships idempotent present/absent
    semantics, check mode, diff output and contract + unit tests. The
    count now stands at 45 of the 50-module target.
42. P1 resource closure: five write modules complete the 50-module target.
    **Done** — `tcr_repository` manages Enterprise Edition repositories;
    `cam_policy_attachment` manages policy relationships for users, roles and
    groups; `kms_key` manages key creation, enabled state, descriptions and
    scheduled deletion; `monitor_alarm_policy` manages alarm-policy lifecycle;
    and `tke_addon` manages addon installation, upgrades, values and deletion.
    All five support check mode and diff output and are registered in the SDK
    request-model contract audit.
43. VPN topology and CLB target-group closure. **Done** — `customer_gateway`
    manages remote peer definitions by ID or unique name; `vpn_connection`
    manages IPsec tunnel lifecycle, exact SPD CIDR pairs, negotiation and DPD
    settings, plus explicit pre-shared-key rotation. `clb_target_group` adds
    target-group lifecycle and exact-set backend IP/port/weight reconciliation.
    All three support check mode, diff output and convergence polling.
44. VPC network ACL closure. **Done** — `network_acl` manages ACL lifecycle,
    name changes, exact ingress/egress rule sets and exact subnet associations,
    with check mode, diff output and SDK contract coverage.
45. VPC traffic observability. **Done** — `vpc_flow_log` manages flow-log
    lifecycle for ENI, NAT, CCN and direct-connect resources, CLS topic
    delivery, mutable metadata and enabled state with convergence polling.
46. Unified resource resolver and lifecycle layer. **Done** — two
    `module_utils` modules close the two P0 items of
    [panorama.html](panorama.html). `resolver` is the single
    resource-reference contract: Tencent Cloud list filters match fuzzily,
    so an ID, a name or a tag set is re-checked client-side — an exact name
    wins, a lone fuzzy candidate is accepted, and two or more candidates
    fail with `ambiguous=true` plus the candidate list instead of silently
    managing `XxxSet[0]`. `lifecycle` owns what every module used to
    hand-roll: one redacted failure envelope with an `error_kind`,
    `missing_as_none` for the dozen "not found" spellings,
    `delete_resource` (already-absent reports unchanged), `soft_delete`
    (isolate then purge) and `plan_changes` (one change set for check mode
    and the real run). `vpc`, `subnet`, `security_group`, `route_table`,
    `eip`, `nat_gateway` and `cvm_instance` are the first consumers.
47. VPC resource family rollout. **Done** — the resolver is rolled out to the
    rest of the VPC family: `vpn_gateway`, `vpn_connection`,
    `peering_connection`, `network_interface`, `network_acl`, `vpc_flow_log`,
    `nat_gateway_rule`, `customer_gateway`, `dc_direct_connect` and
    `dc_direct_connect_tunnel`. Every one of them used to take `XxxSet[0]`
    after a substring name filter, so `name: prod` could manage `prod-old`;
    the shared contract now applies to all ten, including the paginated
    lookups (customer gateway, network ACL, flow log, VPN connection) and the
    product-specific scopes an ID or a name does not cover (an ENI's
    `SubnetId`, a tunnel's `DirectConnectId`). Each family now has one
    contract test — `tests/unit/plugins/modules/test_resource_family_resolution.py`
    — asserting exact-name-wins, lone-fuzzy-accepted, ambiguous-fails and
    id-ignores-noise across all ten lookup entry points.
48. TKE resource family rollout. **Done** — `tke_cluster`, `tke_node_pool`
    and `tke_cluster_upgrade` join the same contract. `tke_cluster` looked a
    cluster up by ID with `Clusters[0]` and never re-checked it;
    `tke_cluster_upgrade` did the same before submitting a version upgrade,
    which is the wrong place to trust the API's row order. Node pools have no
    server-side name filter at all, so every pool of the cluster is now
    listed and resolved client-side.
49. Load-balancer resource family rollout. **Done** — `clb_load_balancer`,
    `clb_target_group`, `clb_listener` and `clb_rule` join the same contract.
    A listener and a forwarding rule have no name at all: a listener is
    addressed by ID or by its endpoint (port + protocol) and a rule by
    `LocationId` or by (domain, url), both of which go through the
    resolver's `extra_match`. Two listeners on the same port and protocol
    now fail as ambiguous instead of managing `Listeners[0]`.
50. Database resource family rollout. **Done** — `cdb_instance`,
    `redis_instance`, `mongodb_instance`, `elasticsearch_instance`,
    `sqlserver_instance`, `mariadb_instance`, `dcdb_instance`,
    `postgresql_instance`, `cynosdb_cluster`, `tdcpg_cluster` and
    `tdmysql_db_instance` join the same contract. Every one of these
    products filters names **fuzzily** on the server (`InstanceNames`,
    `SearchKey`, `SearchName`, `LoadBalancerName`-style substring matches),
    so `name: prod` could match `prod-old` and the old helper managed
    whichever row the API returned first. `tdmysql_db_instance` now collects
    every page before resolving, so a match beyond the first 100 rows is no
    longer invisible; its ambiguity failure carries the candidate list
    instead of the flat "specify instance_id" message.
51. Database resource family read surface. **Done** — the three flagship
    write modules that still lacked a read surface now have one, closing the
    panorama's "write + info 成对" gap for the whole family.
    `elasticsearch_instance_info` (DescribeInstances / `InstanceList`) and
    `tdcpg_cluster_info` (DescribeClusters / `ClusterSet`) are added as
    curated generator specs after introspecting the SDK request/response
    shapes; `postgresql_instance` is mapped in the coverage audit to the
    existing generated `postgres_instance_info` (DescribeDBInstances is the
    same list surface the write module reconciles against — the historical
    `postgres` vs `postgresql` naming split is why the audit never paired
    them). Info-coverage audit: covered 153→155, mapped 6→7, gap 281→278.
52. Lighthouse resource family read surface. **Done** — the four flagship
    Lighthouse write modules that still lacked a read surface now have one:
    `lighthouse_disk_info` (DescribeDisks / `DiskSet`), `lighthouse_firewall_rules_info`
    (DescribeFirewallRules / `FirewallRuleSet`, scoped by the required
    `instance_id`), `lighthouse_key_pair_info` (DescribeKeyPairs / `KeyPairSet`) and
    `lighthouse_snapshot_info` (DescribeSnapshots / `SnapshotSet`), all added as
    curated generator specs after introspecting the SDK request/response shapes.
    Info-coverage audit: covered 155→159, gap 278→274.
53. CVM residual-family read surface. **Done** — the remaining flagship CVM
    write modules that lacked a read surface now have one:
    `cvm_chc_info` (DescribeChcHosts / `ChcHostSet`, reading the CHC host
    network-configuration surface the write module manages) and
    `cvm_instance_action_timer_info` (DescribeInstancesActionTimer /
    `ActionTimers`, unpaginated list surface with optional `instance_ids` /
    `action_timer_ids` filters); `cvm_disaster_recover_group_binding` is
    mapped in the coverage audit to the existing `cvm_disaster_recover_group_info`
    (DescribeDisasterRecoverGroups returns the `InstanceIds` bound per group,
    the exact set the write module reconciles). Info-coverage audit:
    covered 159→161, mapped 7→8, gap 274→271.
54. Coverage 80% milestone (2026-09-08): the 80% sprint added main-path
    `run_module` unit tests for 73 more write modules (1,102 tests across six
    parallel groups), lifting measured statement coverage to **81.44%** and the
    CI gate from 72 to **80** (`--cov-fail-under 80`). Write modules without a
    dedicated test file fell from 222 (of 313, 2026-08-31) to 111 (of 440).
    Benchmark docs are synchronized to this state — `docs/panorama.html`,
    `docs/capability-map.html` (09-08 figures), `docs/gap-closure.md`
    (G1b milestone marked reached). **Done**
55. P0-05 read-surface wave 1 (2026-09-09): closed the 85 write-module read
    gaps in the tse / dlc / cos / tdmq families — 53 curated generator specs
    added via SDK introspection (`scripts/generate_info_modules.py`), lifting
    the module count 781→**834** (440 write + 394 `_info`). Info-coverage
    audit: covered 165→**189**, mapped 8→**41**, gap 267→**210** (181 backlog +
    29 judged no-list-API). The new `_info` unit tests raised measured
    statement coverage to **81.64%** (10,327 collected / 10,297 passed /
    30 skipped; gate 80 held). Commit `c9b16df`; `docs/capability-map.html`
    synchronized to the 09-09 figures. Wave 2 (waf / teo / tsf / monitor /
    config / oceanus / ckafka ...) is tracked as P0-06. **Done**
56. P0-06 read-surface wave 2 (2026-09-09): closed the 69 write-module read
    gaps in the config / monitor / oceanus / teo / tsf / waf / tke families —
    41 curated generator specs added via SDK introspection (config 5, monitor
    6, oceanus 6, teo 5, tsf 10, waf 9), 2 write modules mapped to an existing
    generated `_info` (`monitor_alarm_policy_notice` / `monitor_grafana_internet`),
    and 26 modules judged to have no usable list API (per-domain singleton
    reads and non-standard paging, each recorded with its reason in
    KNOWN_NO_LIST_API), lifting the module count 834→**875** (440 write +
    435 `_info`). Info-coverage audit: covered 189→**230**, mapped 41→**43**,
    gap 210→**167** (112 backlog + 55 no-list, was 181 backlog + 29 no-list).
    The new `_info` unit tests raised measured statement coverage to **82%**
    (10,601 collected / 10,571 passed / 30 skipped; gate 80 held). Commit
    `b236013`; `docs/capability-map.html` synchronized to the 09-09 figures
    (`e0d531d`). Wave 3 (ckafka / trabbit / api_gateway / cfw / dts backlog)
    folds into the next read-surface wave. **Done**

Resource modules must be idempotent, support check mode, expose API request
IDs on failure, and use consistent `*_info` naming for read-only operations.

## Current priorities

The collection has moved beyond the original 50-write-module target. Current
module and product counts are generated in
[`product-capabilities.md`](product-capabilities.md); they should not be copied
into this roadmap because those numbers change with every coverage batch.

### In flight — P0×12 + P1×10 execution (approved 2026-09-08)

The 30-item urgent list in [`panorama.html`](panorama.html) is now the execution
backlog: P0-01/02 flagship integration-target skeletons and the trusted-run
environment (G1-a/b/c), P0-05/06 read-surface closure (wave 1 tse/dlc/cos/tdmq
85 gaps + wave 2 config/monitor/oceanus/teo/tsf/waf/tke 69 gaps done
2026-09-09 — 154 write gaps closed, audit covered 230 / mapped 43 / gap
167 = 112 backlog + 55 no-list; the next wave chases the ckafka / trabbit /
api_gateway / cfw / dts backlog),
P0-07/08/09 unit-test breadth and shallow
test upgrades (111 → <60 write modules without dedicated tests), P0-10/11 role
task tests and contract coverage for generated modules, and the P1 structural
items — plugin_utils / action / filter plugins, docsite, extensions.yml,
doc_fragments and module_utils grouping, event_source docs, README FQCN index
and example playbooks. Items land as individual commits, each keeping the
coverage gate (80) and the sanity ignore budget (2292/2350) intact.

1. **Deepen the eight highest-use resource families.** Close runtime and
   operational workflows in TEM, TKE, CLB, CDB/Redis/MongoDB, TCR, SCF,
   API Gateway and CLS/Monitor before adding more discovery-only products.
2. **Ship reusable solutions.** Grow from low-level modules into roles for a
   VPC foundation, TKE platform, database stack, serverless application,
   logging baseline, monitoring baseline and security baseline. TEM, VPC, TKE,
   CDB, SCF, observability and security now form the first solution-role waves.
3. **Normalize lifecycle behavior.** Apply the shared SDK error payload,
   request IDs, bounded waiters, deletion protection, immutable-field errors
   and absent-resource idempotency to every write module.
4. **Replace raw SDK dictionaries on common paths.** Expose typed suboptions
   for frequently used deployment, node-pool, listener, database and gateway
   fields while retaining an explicitly advanced raw payload escape hatch.
5. **Improve cross-resource composition.** Add consistent name-to-ID lookups,
   exact-set reconciliation modes and result contracts so playbooks do not
   require chains of ad-hoc query tasks and `set_fact` expressions.
6. **Finish generated-info curation.** Resolve the remaining hidden-required-
   parameter candidates and keep the SDK drift sentinel authoritative.

Each product-family milestone should include a complete resource graph,
one runnable golden-path playbook, least-privilege CAM actions, and a clear
statement of SDK/API limitations.
