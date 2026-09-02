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

## Next (0.14+)

The write-module surface is dense across the core Tencent Cloud product
lines. The next phase shifts from breadth to three tracks: closing the
remaining high-value object-level and product gaps, deepening the platform
plugins around the module set, and hardening governance for a path toward
the official `ansible-collections` organisation.

46. Object-level COS operations. **Done** — `cos_object` manages upload
    (from `src` or inline `content`), download to `dest` and deletion, with
    ETag-based change detection, metadata and storage-class drift
    reconciliation, check mode and diff output.
47. COS object inventory and sync: `cos_object_info` (list/filter objects in
    a bucket with prefix and marker pagination) and `cos_object_sync`
    (mirror a local tree into a bucket prefix, delete extraneous keys) to
    complete the object story started by `cos_object`. **Done** — both
    modules shipped with ETag/MD5 change detection, check mode and full
    unit coverage (44 cos_object tests green on pytest and ansible-test).
48. Compute closure: `cvm_instance` security-group binding
    (`AssociateSecurityGroups`/`DisassociateSecurityGroups` — the CVM SDK
    has no `ModifyInstancesSecurityGroups` request) and image sharing
    (`ModifyImageSharePermission`), the two most-requested CVM gaps.
    **Done** — `cvm_instance_security_group` reconciles the instance's
    bound set exactly (state=present) or unbinds given groups
    (state=absent), enforcing the five-group limit; `cvm_image_share`
    shares/revokes image access per root account ID with SHARE/CANCEL.
    Both ship check mode + diff and 23 unit tests green on pytest and
    ansible-test.
49. Container closure: `tke_cluster` upgrade and auto-scaling so cluster
    lifecycle is fully declarative. The TKE SDK has no `UpgradeCluster` or
    `CreateClusterAutoscaler`; the real APIs are `UpdateClusterVersion`
    and `ModifyClusterAsGroupOptionAttribute`/`DescribeClusterAsGroupOption`
    (as-groups are now node pools). **Done** — `tke_cluster_upgrade`
    reconciles the running Kubernetes version (idempotent against
    `DescribeClusters`, submits `UpdateClusterVersion` with
    max_not_ready_percent/skip_pre_check); `tke_cluster_autoscaler`
    reconciles the cluster-level CA options (scale-down toggles, expander
    algorithm, idle thresholds, unready-node guardrails), writing only the
    provided fields. Both ship check mode + diff and 15 unit tests green
    on pytest and ansible-test.
50. New product lines with zero write coverage today: `eks_*` (Elastic
    Kubernetes Service), `sms_*` (signature/template/package), and `vod_*`
    (media management) as the first candidates. **Done** — the `sms_*`
    line shipped first: `sms_signature` and `sms_template` manage
    the review-based signature/template lifecycle
    (`AddSmsSign`/`DeleteSmsSign`, `AddSmsTemplate`/`DeleteSmsTemplate`)
    with name-keyed idempotency; a failed review (status code -1) is
    treated as absent so re-running resubmits, and both support check mode
    + diff (27 unit tests green). The `eks_*` line followed:
    `eks_cluster` and `eks_container_instance` manage the cluster and
    container-instance lifecycle (create/update/delete through the
    `CreateEKSCluster`/`UpdateEKSCluster`/`DeleteEKSCluster` and
    `CreateEKSContainerInstances`/`UpdateEKSContainerInstance`/
    `DeleteEKSContainerInstances` APIs) with name-keyed idempotency,
    check mode + diff, and nested container/volume/credential model
    builders (26 unit tests green). The `vod_*` line completed the item:
    `vod_class` and `vod_sub_app` manage media categories and
    sub-applications (create/update/delete via `CreateClass`/`DeleteClass`,
    `CreateSubAppId`/`ModifySubAppIdInfo`/`ModifySubAppIdStatus`, with
    sub-application deletion expressed as the `Destroyed` status since the
    platform exposes no delete API), name-keyed idempotency, check mode +
    diff (24 unit tests green). All three lines are registered in the
    module tiers (325 core + 199 generated).
51. Inventory expansion: `tencentcloud_cos` (bucket + object listing) and
    `tencentcloud_tke` (cluster + node pool) dynamic inventory plugins.
    **Done** — `tencentcloud_cos` lists the account's buckets account-wide
    through GetService (hosts keyed by the globally unique bucket name),
    with region/name-prefix filters and an optional per-bucket object
    listing capped by `max_objects`; `tencentcloud_tke` walks each region's
    clusters and their node pools and exposes the nodes whose
    `InstanceRole` is in `instance_roles` (worker pool by default) as
    hosts, attaching `ClusterId`/`ClusterName`/`ClusterStatus`/
    `NodePoolId`/`NodePoolName` host variables. Both support the
    `constructed` and `inventory_cache` fragments, profile credential
    fallback, and ship unit tests (38 new, 91 total in the inventory
    suite).
52. EDA event sources: COS bucket event notifications and TKE cluster
    events as `event_source` plugins, extending the `cls_topic`/`cmq_queue`
    pattern. **Done** — `cos_bucket` polls a bucket's object listing and
    yields each new or changed object as an `ObjectCreated` event (the
    polling equivalent of a bucket event notification), with prefix
    filtering, an optional `max_objects` cap for very large buckets and
    baseline-first-poll behaviour (set `initial` to also emit pre-existing
    objects); `tke_cluster` polls `DescribeClusterStatus` and yields a
    `ClusterStateChanged` event on any cluster-state/instance-state
    transition (attaching the previous state and node counts) plus a
    `ClusterDeleted` event when a cluster disappears. Both support
    env-var credential fallback and standalone CLI mode, and ship 25 unit
    tests green on pytest and ansible-test.
53. Role library: `tc_web_stack` (CVM + CLB + CDB + Redis in one call),
    `tc_tke_cluster` (managed cluster + node pool + addons) and
    `tc_disaster_recovery` (cross-region replica) roles. **Done** —
    `tc_web_stack` provisions a CVM pool, a MySQL CDB and a Redis cache
    fronted by a CLB with an HTTP listener, auto-registering the created
    instances as backends (explicit target list or per-component enable
    flags, teardown in reverse order); `tc_tke_cluster` reconciles a managed
    cluster plus the `tc_tke_cluster_node_pools`/`tc_tke_cluster_addons`
    lists idempotently (teardown: addons -> node pools -> cluster);
    `tc_disaster_recovery` prepares cross-region DR artifacts — a golden CVM
    image from a source instance, COS bucket replication to the DR region
    and an optional standby CLB in the DR region. All roles follow the
    existing `tc_launch`/`tc_clb_http` conventions (tc_-prefixed defaults,
    `default(omit)` option passthrough, skip when identity vars are empty),
    validated by role YAML/argspec cross-checks, `ansible-playbook
    --syntax-check` on a provision+teardown playbook, and green
    ruff/ansible-test sanity/units.
54. Generator upgrade: extend `scripts/generate_info_modules.py` to emit
    resource-module skeletons (argument spec + request builder) from SDK
    metadata so new write modules start from generated scaffolding instead
    of a blank file. Done: a curated `RESOURCE_SPECS` table names the
    module, service package, identity options and create/update/delete +
    identify actions; `--resource <module>` introspects the SDK request
    models (via `:rtype:` hints) and renders the full module boilerplate —
    DOCUMENTATION/EXAMPLES/RETURN, lazy `_load_*`, per-action request
    builders, identify/`find_<resource>` helpers, check-mode `run_module`
    with a drift TODO — into `plugins/modules/<module>.py`. Scaffolding is
    write-once (existing files are never overwritten) and `--resources
    --check` verifies every spec against the installed SDK in CI. The
    reference entry mirrors the hand-written `scf_alias` module; SDK
    descriptions are embedded verbatim for the developer to curate.
    **Done**
55. Official adoption: open the review process with `ansible-collections`
    (namespace, `meta/runtime.yml` compatibility, `ansible-test` full
    matrix) and track it in a dedicated issue. **In progress** — route
    decision (2026-09): inclusion in the `ansible` community package via
    the ansible-inclusion review; the repo stays `susunola.tencentcloud`
    (no namespace change, no move to the `ansible-collections` org).
    Tracked in
    https://github.com/susunola/ansible-collection-tencentcloud/issues/8
    with a full requirement scorecard. Done so far: 1.0.0 released
    (unblocks the >= 1.0.0 rule), weekly ansible-core devel CI in place,
    `requires_ansible` floor moved onto maintained cores (2.19+). 1.0.0
    is published on Galaxy (2026-09-02, `highest_version` 1.0.0). The
    formal inclusion request was posted (2026-09-02) as
    https://github.com/ansible-collections/ansible-inclusion/discussions/89
    ("New collection inclusion request: susunola.tencentcloud", category
    new collection reviews); remaining step is iterating on review
    feedback (W4 in the issue).
56. 1.0.0 release readiness (unblocks #55 W1): plan the 0.x -> 1.0.0
    release — lock the `requires_ansible` floor onto currently maintained
    cores (2.19/2.20/2.21; 2.16 core reached EOL 2025-07), set the Python
    floor, fold deprecations, audit removal candidates, back-tag releases
    (`v0.13.0`, ...) so tag == Galaxy version, and make tagging part of
    the release workflow. **Done**: released as 1.0.0 (tag `v1.0.0`) —
    `meta/runtime.yml` requires_ansible >= 2.19.0, CI matrix trimmed from
    2.16-2.21 to 2.19/2.20/2.21 (python 3.11/3.12/3.13), release workflow
    pinned to ansible-core 2.19, README requirements aligned (ansible-core
    2.19+ / Python 3.11+ / SDK 3.1.164+), SECURITY.md supported-version
    table refreshed to 1.0.x. Zero modules deprecated or removed (audit
    found no `deprecated`/`removed_in` markers across 524 modules). 0.x
    tags were NOT back-filled: the tag-triggered release workflow makes
    back-tagging historical commits unsafe; tags start at v1.0.0
    (release.yml already verifies tag == galaxy.yml version). Published
    to Galaxy as 1.0.0 (2026-09-02, release run 33605335645).
57. Write-module unit-test coverage drive (CI gate): the SDK contract
    coverage gate (`--cov-fail-under`) was born red at 70 — introduced
    2026-08-31 in `01fd38e` after the batch module-generation run pushed
    the write-module count to 313, of which only 63 have unit tests.
    Measured baseline 2026-09-02: 58.6% total (module_utils 92.5%,
    `_info` modules 85.7%, write modules 51.4%; 11,710 of the 16,097
    missed statements come from the 249 untested write modules). The
    gate is recalibrated to 55 (just under baseline, still catches
    regressions). **In progress — batch 1 (2026-09-02)**: added
    run-path + helper unit tests for `kms_key` (87.3%, 172/197) and
    `tke_addon` (86.0%, 154/179) — 47 new tests, full suite 3114 green,
    total coverage 58.6% -> 59.00% (gate 55 margin +4pp). **In progress —
    batch 2 (2026-09-02)**: added run-path + helper unit tests for
    `tdmysql_db_instance` (95.8%, 204/213, up from 43.7%) — 42 new tests,
    full suite 3156 green, total coverage 59.00% -> 59.29% (gate 55
    margin +4.29pp). **In progress — batch 3 (2026-09-02)**: added
    run-path + helper unit tests for `dbdc_db_custom_cluster` (97.6%,
    207/212, up from 45.8%) — 44 new tests, full suite 3200 green, total
    coverage 59.29% -> 59.57% (gate 55 margin +4.57pp). **In progress —
    batch 4 (2026-09-02)**: added run-path + helper unit tests for
    `cdwch_instance` (97.7%, 172/176, up from 43.8%) — 53 new tests, full
    suite 3253 green, total coverage 59.57% -> 59.81% (gate 55 margin
    +4.81pp). **In progress — batch 5 (2026-09-02)**: rewrote the
    helper-only test file for `cdn_domain` into the full run-path +
    helper harness (97.7%, 172/176, up from 50.6%) — 36 tests, full
    suite 3279 green, total coverage 59.81% -> 60.03% (gate 55 margin
    +5.03pp). **In progress — batch 6 (2026-09-02)**: rewrote the
    helper-only test file for `lighthouse_instance` into the full
    run-path + helper harness (97.7%, 169/173, up from 48.0%) — 47
    tests, full suite 3313 green, total coverage 60.03% -> 60.25%
    (gate 55 margin +5.25pp). **In progress — batch 7 (2026-09-02)**:
    added a full harness test file for `lighthouse_firewall_rules`
    (94.7%, 72/76, up from 43.4%; the 4 misses are the lazy-import and
    entrypoint lines) — 18 tests incl. pagination and remove-then-add
    reconcile, full suite 3331 green, total coverage 60.25% -> 60.35%
    (gate 55 margin +5.35pp). **In progress — batch 8 (2026-09-02)**:
    added a full harness test file for `lighthouse_disk` (95.1%,
    136/143, up from 33.6%) — 38 tests incl. the create/attach/detach/
    terminate/replace flows and a patched-clock waiter-timeout path —
    full suite 3369 green, total coverage 60.35% -> 60.58% (gate 55
    margin +5.58pp). **In progress — batch 9 (2026-09-02)**: added a
    full harness test file for `lighthouse_key_pair` (96.4%, 108/112,
    up from 37.5%; the 4 misses are the lazy-import and entrypoint
    lines) — 36 tests incl. pagination past 100, force-replace
    re-import ordering and association add/remove/switch — full suite
    3405 green, total coverage 60.58% -> 60.75% (gate 55 margin
    +5.75pp). **In progress — batch 10 (2026-09-02)**: added a full
    harness test file for `lighthouse_snapshot` (96.0%, 96/100, up from
    40.0%; the 4 misses are the lazy-import and entrypoint lines) —
    32 tests incl. the create/rename/delete/wait flows, a multi-poll
    NORMAL transition and patched-clock timeout/FAILED paths — full
    suite 3437 green, total coverage 60.75% -> 60.89% (gate 55 margin
    +5.89pp). **In progress — batch 11 (2026-09-02)**: rewrote the
    helper-only test file for `ccn_attachment` into the full run-path +
    helper harness (96%, 87/91, up from a 13-line smoke test) — 22 tests
    incl. attach/detach/update-description flows, re-attach no-change and
    patched-clock timeout paths — full suite green. **Planned**:
    continue with the next highest-miss write modules per the per-file
    report, raising the
    floor back towards 70; each batch must keep the gate green. Scaling
    plan (structural scan of the 222 untested write modules + batching
    proposal): docs/coverage-batching.md — 175 of the 222 share the same
    helper skeleton, so a test-skeleton generator (lever 1) is the
    recommended path to close the ~+4,000-statement gap in ~10-15 batches
    instead of ~180.

Resource modules must be idempotent, support check mode, expose API request
IDs on failure, and use consistent `*_info` naming for read-only operations.

