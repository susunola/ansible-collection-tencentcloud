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
57. P1-01 plugin_utils shared library (2026-09-10): added
    `plugins/plugin_utils/` for the two helpers controller-side plugins were
    already reaching into `module_utils` for: `profile.load_profile` (TCCLI
    credential-profile reader, imported by the `resource_id` /
    `ssm_parameter` / `sts_caller_identity` lookups, the CVM / CLB / COS / SG /
    TKE inventory plugins and the `tat` connection plugin) and
    `paging.Paginator` (the offset/limit loop, used by the inventory plugins
    as well as the generated `_info` modules). The first cut treated
    `plugin_utils` as the layer *below* `module_utils` and moved the
    implementations into it, with `module_utils.client` / `module_utils.paging`
    importing back up. That direction is not allowed and the layer map was
    wrong; entry 58 corrects it. New tests live in
    `tests/unit/plugins/plugin_utils/`, and `plugins/plugin_utils/README.md`
    documents the boundary. Commit `f9f92c1`. The same window cleared
    `ruff check .`, which was red on main with 50 pre-existing findings
    (43× F841, 7× F401) in `tests/unit/plugins/modules` (`3fec907`). **Done**
58. P1-02 first action plugin (2026-09-10): added `plugins/action/tc_wait.py`,
    plus `plugins/module_utils/polling.py` and the re-export shims.
    `tc_wait` waits for an existing resource to reach a state by polling a
    `*_info` module through `_execute_module` — the one operation no module can
    express, since a module cannot invoke a module, so "wait until this disk is
    attached" was previously only reachable via `until`/`retries` against a raw
    API call. Its observation table (module → result list key → state field) is
    not guessed: `tests/unit/plugins/action/test_tc_wait.py` asserts every
    `state_field` still exists on the corresponding installed SDK model, so an
    SDK rename fails a test instead of making the plugin wait forever.

    The sanity run for this item also exposed a real defect that P1-01 had
    shipped to main: ansible-test's `import` test permits module-side code to
    import only `plugins.module_utils`, so `module_utils/client.py:29` and
    `module_utils/paging.py:23` importing `plugin_utils` failed it **881
    times** on `origin/main` (traced through `module_utils.base` / `cos` /
    `lifecycle` / `tencentcloud` and every generated `_info` module). The fix
    inverts the layering rather than patching symptoms: implementations live in
    `module_utils` (`client.load_profile`, `paging.Paginator`, the new
    `polling.poll_until`), and `plugin_utils/{profile,paging,polling}.py`
    re-export them for the controller side. The direction
    `module_utils` → `plugin_utils` → non-module plugins is enforced by
    `ansible-test sanity --test import`, which now reports **0** errors.
    `module_utils.paging` keeps `Paginator` at the path the write-once
    generator emits into every generated `_info` module;
    `PROFILE_FILE` / `DEFAULT_PROFILE_NAME` are deliberately not re-exported
    (a re-exported constant is a separate binding, so rebinding it through the
    shim silently did nothing — the reader tests patch
    `module_utils.client.PROFILE_FILE` instead).

    `wait_for_state` delegates to `poll_until` with a byte-identical
    module-side failure payload. 25 action tests + 7 polling-mechanics tests +
    3 shim-identity tests. Also fixed a latent pytest collection failure:
    `tests/` had no `__init__.py`, so the `module_utils` / `plugin_utils`
    `test_paging.py` / `test_profile.py` pairs collided under the default
    `prepend` import mode and aborted the CI coverage step — 12 package markers
    added, all zero-byte because the `empty-init` sanity test requires it.
    Full tree: 12,984 passed / 31 skipped / 5 xfailed in the measured scope;
    `ruff check .` clean; sanity ignore budget 2289/2350; the remaining sanity
    failures are the three pre-existing ones (`ignores` 102, `pep8` 1,
    `pylint` 46). **Done**
59. P1-03 first filter plugin (2026-09-10): added `plugins/filter/tags.py`
    exposing `tag_merge`, plus `module_utils.tagging.merge_tags` and the
    `plugin_utils.tags` re-export. The filter closes a gap no existing filter
    covered: `ansible.builtin.combine` only understands mappings, so a playbook
    that had the `tags` mapping a module parameter takes *and* the
    `Key`/`Value` list an `*_info` module returns had no way to combine them —
    the API-shaped side had to be re-typed by hand. `tag_merge` accepts a tag
    mapping, a single `Key`/`Value` tag, a list of tags, a list of SDK `Tag`
    objects or a nested list of any of those, merges left to right (last source
    wins, like `combine`), and returns a key-sorted string-valued mapping —
    the same normalization the resource modules apply, so the result can be fed
    straight back into a module.

    Two decisions are worth recording. The implementation sits in
    `module_utils.tagging` rather than in the filter even though the filter is
    its only consumer today: tag reading and tag comparison are one body of
    semantics, and the layering rule is one-directional, so a module that later
    needs the merge would force the implementation back down anyway. And an
    unsupported source raises `AnsibleFilterError` instead of being skipped —
    for a merge, silently dropping a source is a permanent tag loss, so the
    filter names itself in the failure (`tag_merge: unsupported tag source
    'oops': expected a mapping, a list of tags or an SDK Tag object`).

    `filter` is in ansible-test's `DOCUMENTABLE_PLUGINS` (unlike `action`), so
    no sanity ignore entry is needed and `ansible-doc -t filter
    susunola.tencentcloud.tag_merge` renders the inline DOCUMENTATION —
    verified locally against the materialized collection layout, together with
    an end-to-end playbook run through the templar (merge, nested-list
    flattening, unset-variable tolerance, and the failure path). 46 tests cover
    the helper, the Jinja surface and the shim identity. This item also
    completed the hand-maintained "Included plugins" table in `README.md`,
    which was missing the action, callback, filter, TKE/COS inventory and
    COS/TKE event-source rows. **Done**
60. P1-04 collection docsite (2026-09-10): `docs/docsite/` adds an
    `antsibull-docs` + Sphinx build that renders the `DOCUMENTATION` /
    `RETURN` / `EXAMPLES` blocks of all 875 modules and every other plugin
    into an `ansible-doc`-style HTML site — `docs/docsite/build/html/`, ~900
    pages, about eight minutes end to end. `docs/docsite/build.sh` is the
    entry point and `docs/docsite/README.md` documents it. Two flags are
    deliberate: `antsibull-docs --fail-on-error` and `sphinx-build -W`.
    Without the first, a module whose documentation cannot be parsed becomes a
    page that reads "Did not return correct DOCUMENTATION"; without the
    second, a dangling `O(option)` reference ships as a broken link. Both are
    the reason the docsite is a gate rather than a snapshot.

    Building it is what surfaced a defect that had been invisible since the
    modules were written: **141 findings across 70 modules**, and all of them
    one mistake. An option documented as
    `{type: int, description: Maximum retained versions, from 1 to 24.}` puts
    a comma inside an unquoted YAML flow mapping, so `from 1 to 24.` parses as
    a second option key. `ansible-doc` rendered it as a real parameter —
    `dlc_model_version` documented a `from 1 to 24.: null` line under
    `max_reserved_models`, and 82 such keys across the collection are English
    sentence fragments (`'from 1 to 1000'` fourteen times, `'immutable after
    creation'` twelve). 115 lines in 68 modules were repaired: 88 option and
    return-value descriptions are now quoted, 18 nested `options:` blocks
    became the `suboptions:` the schema requires, and 9 `no_log` keys were
    dropped from `DOCUMENTATION` (it is not part of the doc schema — it
    belongs in `argument_spec`).

    The reason CI never saw any of it is the second half of this item:
    `tests/sanity/ignore-2.21.txt` carried 66 blanket
    `validate-modules:invalid-documentation` entries, one per affected file.
    That suppression was worse than it looked, because a module whose
    documentation cannot be parsed is not validated *at all*: those 66 entries
    were also hiding `doc-missing-type`, `doc-required-mismatch`,
    `missing-suboption-docs`, `undocumented-parameter` and five more codes on
    the same files. With the documentation fixed, 73 entries per version file
    were provably obsolete. Removing them and the 11 `no-log-needed` entries
    they covered took the ignore total from **2289 to 1869** and made
    `validate-modules` pass for the first time; `dlc_ray_job_list_info` also
    gained a real fix, since `O(fetched_count)` pointed at a return value.
    The 11 files where `no_log` is a genuine name-based false positive —
    `key` inside `tags`, `primary_keys`, `keyword`, `output_cos_key_prefix`,
    `kms_key_version` — keep a targeted `validate-modules:no-log-needed`
    entry instead of the blanket ones. Sanity is back to exactly its three
    pre-existing failures (`ignores` 100, down from 102; `pep8` 1;
    `pylint` 46). **Done**
61. P2-03 co-maintainer path (2026-09-10): `CONTRIBUTING.md` now spells out
    how a second maintainer actually takes authority, rather than pointing at
    `MAINTAINERS.md` and hoping. Three roles — contributor, reviewer
    (co-maintainer), maintainer — with an explicit table of what each may
    decide, and the **protected surfaces** a reviewer may not merge alone:
    `.github/workflows/` and `CODEOWNERS`, `BASELINE_TOTAL` in
    `scripts/check_sanity_ignore.py`, `GENERATED_SDK_VERSION` in
    `scripts/check_sdk_drift.py`, `CORE_MODULES` / `scripts/SPECS.py`, and
    `version` in `galaxy.yml`. The reasoning is that each of those is a gate
    someone will want to loosen to get a PR green, and a gate that is easy to
    loosen is not a gate: the doc also lists the CI gates a merge must never
    weaken (`audit_info_coverage`, `check_module_tiers`, `check_sdk_drift`,
    `generate_info_modules --check`, `check_sanity_ignore`, `ruff check .`,
    sanity, and `--cov-fail-under=80`). Module naming is the maintainer's call
    because a published FQCN is public API and a rename is a deprecation, not
    an edit. Commitment is stated as a number — 2-4h/week, 48h first response,
    60 days of silence means stepping down — so that the expectation is not
    left to mind-reading.

    Tightening the sanity-ignore budget came with it: after the docsite work
    removed 420 blanket lines the 2350 ceiling left 481 lines of slack, so
    `check_sanity_ignore.py` could not have fired at all.     `BASELINE_TOTAL` is
    now 1900 against a committed total of 1869, and the figures quoted in
    `panorama.html`, `capability-map.html` and this roadmap were corrected.
    **Done**
62. Restore red `main` (2026-09-10): `main` had been failing CI since
    2026-09-09T16:27 — sixteen hours and six commits — and nothing caught
    it, because the only verification being run was local sanity, whose
    output was being read as "the three pre-existing failures" rather than
    as three things that fail CI. What was actually broken:

    - **302 sanity-ignore entries named test files that no longer exist** (37
      distinct files, deleted during the P0-07/P0-09 unit-test rewrites). An
      ignore entry for a deleted file is *itself* an `ignores` failure, and
      302 lines of "File ... does not exist" are easy to file under noise.
    - 10 entries (2.19/2.20 only) that ansible-test reports as unnecessary.
    - **44 pylint `repeated-keyword`** in the dlc/tione deep-harness tests:
      `dict(params(), page_size=0)` is inferred as passing `page_size` twice
      whenever the overridden key already exists in the base dict, which is
      exactly the override case. The `params()` helpers now take overrides
      directly (`params(page_size=0)`).
    - 2 `unnecessary-comprehension` and 1 pep8 `E128`.

    `scripts/check_sanity_ignore.py` now rejects any entry whose file is
    missing, so the next dangling entry fails as one obvious line instead of
    three hundred. With this, `ansible-test sanity` is **EXIT=0 for the first
    time** — 24 tests, zero failures — and the ignore total is 1557. The
    lesson to keep: a green local run is not a green CI run, and a
    "pre-existing failure" is only pre-existing until somebody checks whether
    it is failing the build. **Done**
63. P2-05 triage SLA and label flow (2026-09-10): `CONTRIBUTING.md` had
    promised a first response on issues and pull requests within 48 hours
    since the P2-03 maintainer-path section landed, and nothing measured it.
    At the time this shipped, three items were open and unanswered, the
    oldest 194 hours old.

    - `docs/triage.md` defines what a response *is* (a human comment or a
      submitted review; never a bot comment, which would make every number
      look perfect) and the label set used to triage.
    - `scripts/triage_sla.py` computes first-response times from the GitHub
      API. Four statuses, and only one is an alarm: `OK`, `LATE` (answered
      past the deadline — history), `WAITING` (unanswered, inside the
      window), `BREACH` (unanswered and overdue). Lumping `LATE` in with
      `BREACH`, as the first version did, leaves `--check` red on an item
      that has already been answered and can only be cleared by closing it.
    - `--exclude-author` drops a maintainer's own tracking issues, which can
      never receive a first response by definition.

    The three breaches were answered as part of landing this: #8 (adoption
    tracking) got a refreshed inclusion scorecard, and #9/#10 turned out to
    be red on a `generate_cam_actions.py --check` gate that was already
    broken on `main` at their base commit, not on their own content. The
    nightly triage job is parked on a local branch — the OAuth token in use
    cannot push `.github/workflows/`. **Done**
64. P2-04 release automation (2026-09-10): releases are cut by pushing a
    `v*` tag, which is also the only trigger `release.yml` has — so the
    first thing that can tell you a release is broken is the push that makes
    it unbreakable, by which point the tag is out, a GitHub release object
    exists and Galaxy may already have a copy.

    - `scripts/release_check.py` is the guard that runs *before* the tag:
      version format, version ahead of the newest released tag, tag free
      locally and on origin, fragments present, version not already folded
      into `changelog.yaml`, clean tree. `--dry-run` also builds the tarball
      into a temporary directory, checks `MANIFEST.json` against
      `galaxy.yml`, asserts nothing from `build_ignore` leaked in, installs
      it and lists its documentation, then prints the plan without doing any
      of it. `docs/release.md` is the runbook.
    - Two packaging bugs fell out of writing the dry run, both invisible to
      CI because CI builds from a clean checkout. `ansible-galaxy` reads
      `build_ignore` and not `.gitignore`, so `docs/docsite/build` (252 MB of
      generated Sphinx HTML) and the tool caches (`.pytest_cache`,
      `.ruff_cache`, coverage output) were being packaged on any machine that
      was not pristine: **36.6 MB and nine minutes instead of 1.9 MB and
      three**, and a tarball whose own `FILES.json` checksums disagree with
      its contents, which `ansible-galaxy collection install` rejects.
      Fixed in `build_ignore`, asserted by the dry run.
    - `fragment-lint` is opt-in (`--lint`): it takes ~2 minutes for the
      fragments currently queued and `release.yml` already runs it. A guard
      you run before deciding whether to tag has to answer in under a second.
    - On `release.yml` the guard replaces the inline tag/version shell check
      and moves it ahead of the sanity suite, so a tag that disagrees with
      `galaxy.yml` fails in seconds instead of ten minutes. `tag-free` and
      `version-bumped` are skipped there on purpose — the job runs *because*
      the tag exists, so both would fail by construction. That edit is
      parked on a local branch with the other workflow changes.
    - Operational note learned the hard way: do not edit the working tree
      while `ansible-galaxy collection build` is running. It hashes files
      into `FILES.json` and writes them into the tarball separately, so a
      mid-build edit produces a checksum mismatch that looks exactly like a
      corrupt release.

65. P2-06 end-to-end demo case (2026-09-10): `docs/examples/` and
    `playbooks/` are what a new user copies first, and they were the only
    artefacts in the repository that nothing at all looked at — CI cannot
    run them, because running them creates billable resources. So they rot
    silently: rename a module option, drop a role variable and every test
    stays green while the README's golden path becomes a wall of
    "Unsupported parameters".

    - `scripts/check_examples.py --check` closes that statically, in under a
      second: modules resolve, every option passed to one is declared (doc
      fragments included, so `region` counts), roles exist, role variables
      are declared in `defaults/main.yml`, and every variable a play reads
      is declared, registered, published by a role, documented as
      `-e name=` or guarded with `is defined`. It cannot prove a playbook
      works — only that it does not reference things that are gone.
    - What it found on its first run: `playbooks/three_tier_web.yml` passed
      an undeclared `web_instance_password`; two of the three examples that
      end by printing a role result used a fact no role ever set (so they
      printed `VARIABLE IS NOT DEFINED!`); five roles read a region variable
      they never declared, which worked by accident through
      `default(omit)` and kept the variable out of the role's documented
      interface. All fixed.
    - `docs/examples/06_full_chain.yml` is the golden path in one file:
      network foundation, web stack on the ids the foundation published, a
      read-back stage and a tagged teardown play. `01`/`02` remain the
      split-apart version; `06` needs no copied ids because the hand-off is
      `tc_vpc_foundation_result`. `docs/examples/README.md` documents the
      chain, the hand-off facts and the teardown order.
    - Every example file also passes `ansible-playbook --syntax-check`,
      which is the other half of the verification: the static check proves
      the references resolve, the syntax check proves Ansible agrees.

66. P2-07 porting guide (2026-09-10): `docs/porting.md` is the translation
    manual for anyone arriving with a working `tencentcloudstack/tencentcloud`
    Terraform config or a raw Tencent Cloud SDK script. It maps every resource
    to a module FQCN (with a table of the names that are not the obvious
    guess — `clb_instance` is `clb_load_balancer`, `dns_record` is
    `dnspod_record`, `route_table_entry` is a `routes` option on `route_table`,
    `elasticsearch_instance` is read-only), explains what replaces
    `terraform.tfstate` (nothing — every task re-discovers by id or name),
    contrasts the credential/region handling (no region default here; the
    token variable is `TENCENTCLOUD_TOKEN`, not `TENCENTCLOUD_SECURITY_TOKEN`;
    the profile file is `~/.tencentcloud/default.configure`), shows the
    `--check` / `tc_wait` / `exact_count` equivalents of plan / wait / count,
    and walks a VPC-plus-subnet config end to end. Every name, option and
    helper in it was read out of the repository before it shipped.
    `docs/scenarios.md` and `docs/examples/README.md` now cross-link it, and it
    is linked from the README's "Coming from Terraform" paragraph.

67. P2-08 internal community post (2026-09-10): `docs/internal-community-post.md`
    turns the month of collection work into reusable methodology instead of a
    status report. It leads with the "cannot execute, still can check" lesson
    — the collection is too big to run in CI and cannot bill resources, so
    static gates (`check_examples.py`, `check_porting_map.py`) stand in for
    execution — then documents reading doc facts out of the repository before
    shipping, layering fast static gates ahead of the slow `ansible-test`
    suite, and three sandbox/toolchain traps (`tmp_path` uid collision, zsh
    word-split, `ansible-test sanity` being stricter than ruff on unused
    imports). Every module name, option and path in it points back to the
    collection at commit `2f383da`.

68. P2-09 read-only live smoke playbook (2026-09-11):
    `tests/integration/smoke_readonly.yml` is a manual, credential-gated,
    read-only smoke test that proves the full runtime chain against the real
    Tencent Cloud API — credential resolution, SDK client, signed request,
    live response — without creating any resources (changed=0, no billing).
    It lists VPCs and CVM instances only, and is intentionally excluded from
    `ansible-test` automation because it needs live credentials from
    `~/wbenv`. Running it green validates the collection end to end.

69. TKE deletion-protection module (theme #1, 2026-09-11):
    `plugins/modules/tke_cluster_deletion_protection.py` closes the first TKE
    operational-workflow gap from theme #1 (deepen the highest-use resource
    families). It is an idempotent, check-mode-safe toggle over the SDK's
    Enable/DisableClusterDeletionProtection operations: it reads the live
    `DeletionProtection` flag via DescribeClusters before changing it, so a
    cluster already in the desired state is a no-op. Ship with a unit-test
    matrix (enable / disable / idempotent / check-mode / not-found / SDK
    failure) and the changelog fragment. The next TKE increments are cluster
    routes (CreateClusterRoute / ClusterRouteTable) and CLS log configs.

70. TKE cluster route table module (theme #1, 2026-09-11):
    `plugins/modules/tke_cluster_route_table.py` creates or deletes a TKE
    cluster route table (name usually = cluster ID), idempotent on the table
    name, check-mode safe. CIDR/VPC are immutable post-create, so an existing
    same-named table is a no-op rather than reconciled. Unit-test matrix
    (create / idempotent / absent / delete / check-mode / required_if) plus
    changelog fragment.

71. TKE cluster route module (theme #1, 2026-09-11):
    `plugins/modules/tke_cluster_route.py` creates or deletes a route
    (destination PodCIDR -> next-hop gateway IP) inside a cluster route table,
    uniquely keyed by destination CIDR block, idempotent and check-mode safe.
    Unit-test matrix (create / idempotent / absent / delete / check-mode) plus
    changelog fragment. The CLS log config gap (CLSLogConfig / ModifyLogConfig)
    is the remaining TKE operational-workflow item.

72. TKE CLS log config module (theme #1, 2026-09-11):
    `plugins/modules/tke_cls_log_config.py` creates or deletes a CLS log
    collection configuration for a cluster, passing the raw TKE log-config
    object through as JSON (the SDK exposes LogConfig/LogConfigs only as JSON
    strings, with no typed model). Idempotent on the configuration name within
    the cluster, check-mode safe, defensive JSON parsing of DescribeLogConfigs.
    Unit-test matrix (create / idempotent / absent / delete / check-mode /
    required_if) plus changelog fragment. This closes the TKE operational gap
    set from theme #1; the next family to deepen is CLB / CDB / Redis / TCR /
    SCF / API Gateway / CLS-Monitor.

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
coverage gate (80) and the sanity ignore budget (1557/1900) intact.

Status 2026-09-10: P0-01…P0-12 and P1-01…P1-10 have landed (see the numbered
entries above); the docsite build (P1-04) closed the last open P1 item.

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
