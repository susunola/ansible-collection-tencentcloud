===============================
Tencent Cloud 1.4 Release Notes
===============================

.. contents:: Topics

v1.4.0
======

Minor Changes
-------------

- module_utils.cos - new ``build_cos_client(region, secret_id, secret_key, ...)`` helper that builds a ``CosS3Client`` without an ``AnsibleModule``, for controller-side callers such as the inventory plugin; ``create_cos_client(module)`` now delegates to it, so the two entry points cannot drift apart. Missing SDK raises the typed ``CosSDKMissing`` error.
- module_utils.cos - new ``list_bucket_entries(client, region)`` helper returning the raw bucket entries of ``list_buckets``. ``list_buckets`` projects three fields for ``cos_bucket_info`` and keeps doing so; callers that want the rest of the entry (``Type``, ``BucketType``, ``AZType``) read it here.
- tc_inventory - CLB and CDB report their run state as an integer; it is now mapped to the same vocabulary the other sources use (``CREATING``, ``RUNNING``, ``ISOLATING``, ``ISOLATED``) and passed through unchanged when the API grows a value this plugin does not know yet, instead of leaving ``keyed_groups`` to group on a bare number.
- tc_inventory - CLB and CDB spell their tags ``TagKey``/``TagValue`` where CVM, Lighthouse, VPC and CBS spell them ``Key``/``Value``. Both dialects are read now, so ``tc_tags`` is populated for every source rather than being empty for half of them.
- tc_inventory - second batch of sources: ``clb`` (CLB load balancers), ``cdb`` (CDB MySQL instances), ``cbs`` (CBS disks) and ``cos`` (COS buckets), alongside the existing ``cvm``, ``tke``, ``lighthouse`` and ``vpc``. CBS and CDB had no inventory plugin before this. Every source keeps the same standardised ``tc_*`` variable set, so grouping and ``compose`` expressions still do not need a per-product branch.
- tc_inventory - the ``cos`` source is the first one that is not an API 3.0 product: it uses its own client builder and collector and therefore needs the ``cos-python-sdk-v5`` distribution on the controller in addition to ``tencentcloud-sdk-python``. It ignores ``filters`` because the COS service call is region-scoped, so narrowing is done with ``regions``; bucket tags are not collected, because they need one extra call per bucket.

v1.3.0
======

Minor Changes
-------------

- tc_inventory - entries that share a resource id are folded into a single host by default (``dedupe``, default ``true``). The overlap is real: a TKE worker node is also a CVM instance and both sources report the same ``i-xxxx``. Merging unions ``tc_sources``, merges list fields and keeps the first configured source's value for scalars, so a host reported by several products joins every matching ``tc_<source>`` group instead of appearing twice.
- tc_inventory - every host carries the same standardised variable set regardless of the product it came from (``tc_source``, ``tc_sources``, ``tc_region``, ``tc_id``, ``tc_name``, ``tc_state``, ``tc_private_ip``, ``tc_public_ip``, ``tc_zone``, ``tc_tags``, ``tc_role``, ``tc_parent_id``, ``tc_parent_name``), so ``keyed_groups`` and ``compose`` do not need a per-product branch. Fields a product has no concept of are ``null`` rather than absent, and the raw API fields are kept alongside, so nothing is lost.
- tc_inventory - new inventory plugin that builds one inventory from several Tencent Cloud products at once, with CVM, TKE (cluster nodes), Lighthouse and VPC as the first batch. The per-product inventory plugins remain available and stay the right choice when a playbook targets a single product; this one is for inventorying an estate, where one source file, one credential block and one cache entry should cover compute and network together. Lighthouse and VPC had no inventory plugin before this.
- tc_inventory - the cache key covers the query configuration (``sources``, ``regions``, ``filters``, ``dedupe``) in addition to the source file path. The inherited ``Cacheable.get_cache_key`` hashes the plugin name and path only, so editing ``regions`` or ``filters`` would otherwise serve a stale inventory until the cache expired.

New Plugins
-----------

Inventory
~~~~~~~~~

- tc_inventory - Unified Tencent Cloud asset inventory across CVM, TKE, Lighthouse and VPC

v1.2.0
======

Minor Changes
-------------

- Add DCDB account and exact scoped account privilege management.
- Add DCDB one-way data-at-rest encryption, SSL and exact security-group configuration.
- Add DLC work-group create, describe, description update, guarded deletion and convergence waiting.
- Add GAAP TCP/UDP listener, reusable real-server and exact listener binding modules.
- Add GAAP proxy name resolution to the resource_id lookup.
- Add Oceanus dedicated cluster creation, CU scaling, guarded scale-down and deletion.
- Add Oceanus job and resource folder lifecycle with rename, move and non-empty deletion protection.
- Add Oceanus workspace resource creation and reference-aware guarded deletion.
- Add TSE registry-engine access endpoint discovery and expose it from the governance platform role.
- Add ``dlc_cluster_group`` for exact, reference-aware DLC compute-group lifecycle and semantic configuration reconciliation.
- Add ``dlc_data_engine_config`` to reconcile complete DLC engine configuration sets and Spark session resource templates by engine ID or exact name.
- Add ``dlc_data_engine`` for guarded DLC compute-engine creation, configuration, power-state convergence and deletion.
- Add ``dlc_data_mask_strategy`` with exact discovery, normalized subjects, mutable masking configuration and guarded deletion.
- Add ``dlc_database`` with catalog-aware discovery, asynchronous convergence, immutable governance checks and guarded non-empty deletion.
- Add ``dlc_engine_resource_group`` for guarded DLC standard resource-group lifecycle, capacity, network and exact Spark configuration reconciliation.
- Add ``dlc_inference_engine_info`` for discovering inference runtime compatibility, visibility, enablement and capabilities with bounded pagination.
- Add ``dlc_inference_model_info`` with parameter-size bounds, time bounds, stable filters, ordered sorting and bounded pagination.
- Add ``dlc_inference_model`` for presence-only inference model creation and mutable metadata reconciliation with explicit non-deletion semantics.
- Add ``dlc_inference_service_info`` with bounded pagination, time bounds, stable API filters and ordered multi-field sorting.
- Add ``dlc_inference_service`` for honest Running/Stopped service coordination, deployment failure convergence and immutable creation-field checks.
- Add ``dlc_job_spec`` for reusable DLC job definitions with exact compute-target, JSON, tag and running-job deletion semantics.
- Add ``dlc_lab`` for guarded DLC development-workspace lifecycle, image, scheduling, tag and persistent-directory reconciliation.
- Add ``dlc_model_artifact_info`` to inspect config.json, file trees and README metadata for an exact model UID and version with independent least-privilege selectors.
- Add ``dlc_model_version_info`` with strong parent-model scoping, time bounds, stable filters, ordered sorting and bounded pagination.
- Add ``dlc_model_version`` for append-only inference-model version publication and immutable metadata conflict detection.
- Add ``dlc_network_connection`` to discover existing DLC network configurations and idempotently reconcile their descriptions.
- Add ``dlc_notebook_session_info`` with complete pagination and engine, state, keyword, generation and sort filters.
- Add ``dlc_notebook_session`` with strong session identity, terminal-history handling, immutable drift detection and guarded replacement or deletion.
- Add ``dlc_notebook_statement_info`` for strong-identity statement inspection and continuation-token SQL-result pagination.
- Add ``dlc_partition_queue`` for exact, guarded DLC resource queue lifecycle and capacity reconciliation.
- Add ``dlc_ray_cluster`` for guarded DLC Ray cluster lifecycle with normalized image, template, mount, advanced-option and tag reconciliation.
- Add ``dlc_ray_job_info`` with opt-in status history, context-paginated events, Pod inventory and submitted YAML diagnostics.
- Add ``dlc_ray_job_list_info`` with bounded pagination, stable filters, time bounds and ordered sorting without fabricating a missing API total count.
- Add ``dlc_resource_config`` for guarded DLC Head and Worker template lifecycle, exact nested configuration and reference-aware deletion.
- Add ``dlc_script`` for saved SQL lifecycle with base64-safe comparison and explicitly guarded replacement when immutable content drifts.
- Add ``dlc_spark_job`` for guarded, idempotent DLC Spark batch and streaming job-definition lifecycle management.
- Add ``dlc_store_location`` for immutable base query-result storage initialization and mutable advanced storage reconciliation.
- Add ``dlc_table_partition`` for exact DMS partition lifecycle, mutable storage metadata and explicit underlying-data deletion semantics.
- Add ``dlc_table`` with generated-DDL task execution, schema convergence, immutable replacement and stored-data deletion guards.
- Add ``dlc_udf_policy`` for exact, order-insensitive UDF user and work-group policy reconciliation with guarded full-policy clearing.
- Add ``dlc_user_policy`` for exact direct-user policy reconciliation with metadata normalization and precise ID-based detach.
- Add ``dlc_user_vpc_connection`` with exact discovery, convergence and guarded deletion for DLC engine-network VPC endpoints.
- Add ``dlc_user`` with mutable descriptions and user types, owner protection, exact discovery and guarded bound-user deletion.
- Add ``private_dns_account`` for idempotent Private DNS cross-account authorization relationships.
- Add ``ssm_product_secret`` for asynchronously creating and governing SSM-managed database credentials with scoped privileges and rotation.
- Add ``ssm_secret_info``, ``ssm_secret_version_info`` and ``ssm_rotation_info`` with bounded metadata discovery and opt-in sensitive value retrieval.
- Add ``ssm_ssh_key_pair_secret`` for guarded SSH key-pair creation and SSM storage without returning private key material.
- Add ``ssm_supported_product_info`` to discover region-specific product identifiers accepted by SSM managed credentials.
- Add ``tat_invocation_info`` for bounded, redacted invocation and per-instance task auditing with opt-in task output.
- Add ``tat_invocation`` for immediate reusable-command execution, per-instance convergence, redacted output and explicit cancellation.
- Add ``tc_service_mesh_platform`` to compose a mesh, exact cluster membership and telemetry integrations.
- Add ``tc_tdcpg_platform`` to compose cluster provisioning with account and endpoint governance.
- Add ``tc_tdsql_mysql_platform`` to compose instance, accounts, scoped privileges, parameters, backup, SSL and maintenance.
- Add ``tc_tse_api_gateway`` to compose gateway, upstream service and route lifecycles.
- Add ``tc_tse_governance_platform`` to compose engine, service-governance and configuration-center lifecycles.
- Add ``tcb_auth_domain`` for idempotent CloudBase user authentication-domain lifecycle management.
- Add ``tcb_static_store`` with asynchronous online and destruction convergence for CloudBase static hosting.
- Add ``tcm_access_log`` for idempotent mesh access-log scope, format and destination management.
- Add ``tcm_prometheus`` for secret-safe Prometheus integration lifecycle management.
- Add ``tcm_tracing`` for idempotent mesh sampling and APM or Zipkin destination management.
- Add ``tdcpg_account`` for account description governance and explicit password rotation.
- Add ``tdcpg_endpoint_wan`` for convergent public endpoint access management.
- Add ``tdcpg_instance_state`` for guarded instance isolation, recovery and restart workflows.
- Add ``tdmysql_account`` and ``tdmysql_account_info`` with composite identity, async Flow waiting, global privileges, password rotation and guarded deletion.
- Add ``tdmysql_backup_policy`` and ``tdmysql_backup_policy_info`` with cardinality guards and readable-field reconciliation.
- Add ``tdmysql_database_object_info`` and ``tdmysql_account_privilege`` for bounded object discovery and exact global, database or table privilege reconciliation.
- Add ``tdmysql_maintenance_window`` and ``tdmysql_ssl`` with normalized schedule comparison and async SSL convergence.
- Add ``tdmysql_parameter`` and ``tdmysql_parameter_info`` with partial-map reconciliation, constraints, restart reporting and asynchronous task waiting.
- Add ``tione_data_source_info`` with workspace scoping, stable filters, tag filters, sorting and bounded offset pagination.
- Add ``tione_data_source`` with exact-name discovery, immutable-drift reporting, stable-ID guarded deletion and creation/deletion visibility waiting.
- Add ``tione_dataset`` with immutable-drift reporting, stable-ID guarded deletion, nested dataset sources and creation/deletion visibility waiting.
- Add ``tione_model_service_auth_token`` with stable identity, rate limits, idempotent confirmed rotation and secret-safe output.
- Add ``tione_model_service_diagnostics_info`` for service call endpoints and model-acceleration compatibility preflight.
- Add ``tione_model_service_info`` with exact service-version, exact service-group and filtered bounded inventory modes.
- Add ``tione_model_service_state`` for guarded, wait-aware online service start, stop and deletion by stable service-version ID.
- Add ``tione_model_service_traffic`` for idempotent request authorization and validated multi-version traffic weights.
- Add ``tione_model_service`` with readable configuration reconciliation, explicit create-only drift and guarded deletion.
- Add ``tione_notebook_info`` with workspace, state, identity and tag filters plus bounded offset pagination.
- Add ``tione_notebook`` with create/update/start/stop/delete state reconciliation, stopped-state updates, immutable drift reporting and guarded deletion.
- Add ``tione_training_model_version_info`` with stable version-ID detail and strongly parent-scoped model-version inventory.
- Add ``tione_training_model_version`` with strong parent scoping, immutable import convergence, status waiting and guarded stable-version deletion.
- Add ``tione_training_task_info`` with exact and historical-instance detail lookup plus workspace, state, identity and tag-filtered bounded pagination.
- Add ``tione_training_task`` with immutable definition convergence, guarded lifecycle actions, successful-terminal idempotency and explicit failed-task handling.
- Add ``tse_cloud_native_gateway`` with topology drift protection, mutable policy and node specification reconciliation, and guarded deletion.
- Add ``tse_config_file_group`` and ``tse_config_file`` for configuration-center content and access governance.
- Add ``tse_gateway_consumer`` and scope-aware ``tse_gateway_rate_limit`` governance modules.
- Add ``tse_gateway_public_network`` with asynchronous CLB lifecycle, immutable zone topology and exact access control.
- Add ``tse_gateway_route`` for instance-unique HTTP and layer-4 route lifecycle management.
- Add ``tse_gateway_server_group`` for secondary gateway group creation, resizing, metadata updates and guarded deletion.
- Add ``tse_gateway_service_source`` with write-only credential handling and role-level source-name resolution for gateway services.
- Add ``tse_gateway_service`` for declarative upstream service lifecycle management.
- Add ``tse_governance_namespace`` with exact operator and service-visibility reconciliation.
- Add ``tse_governance_service`` with namespace-scoped lifecycle and exact access-set reconciliation.
- Add a DLC access-governance role that composes work groups, exact memberships and exact authorization policies with dependency-safe teardown.
- Add aggregated gateway network, port, public-address and node runtime discovery.
- Add atomic configuration file and release deployment with deterministic teardown.
- Add batched governance host retirement with conflict validation and convergence waiting.
- Add bounded, offset-paginated ``dlc_notebook_session_log_info`` for Notebook operational diagnostics.
- Add complete ``tse_gateway_model_service`` and ``tse_gateway_model_api`` lifecycles for AI gateway workloads.
- Add configuration release publication, version-aware rollback and deletion lifecycle management.
- Add configuration release, immutable version and publication-history audit discovery.
- Add configuration template discovery and expose templates from the governance platform role.
- Add content-aware Oceanus job configuration resource references so managed artifacts and exact versions can be bound to SQL, JAR and Python jobs.
- Add content-aware Oceanus metadata table creation and DDL updates with automatic Base64 encoding.
- Add credential-safe Konga console network reconciliation with access control and convergence waiting.
- Add declarative Doris user-to-workload-group binding and ordered teardown rebinding.
- Add declarative upstream target drain and restore with state readback and convergence waiting.
- Add dts_migration_job name resolution to the resource_id lookup.
- Add exact DLC work-group membership reconciliation with minimal add/remove calls, empty-set protection and convergence waiting.
- Add exact DLC work-group policy reconciliation with writable-field normalization, deterministic detach IDs, empty-set protection and convergence waiting.
- Add gateway autoscaler strategy lifecycle and read-backed group binding reconciliation.
- Add governance lane-group lifecycle management with authoritative entry, destination and rule sets.
- Add governance service-alias lifecycle management and compose aliases after their target services.
- Add governance service-instance registration, mutable runtime policy reconciliation and deterministic deletion.
- Add guarded ``tse_gateway_certificate`` lifecycle management for native PEM and SSL-platform certificates with private-key redaction and reference-aware deletion.
- Add guarded, read-back-verified management of DLC data-engine standby clusters through ``SwitchDataEngine``.
- Add idempotent CDW ClickHouse backup enablement, metadata and table-data schedule management.
- Add idempotent CDW ClickHouse instance parameter add, update and removal with restart metadata.
- Add idempotent CDW Doris workload-group management, including resource limits and the instance-wide enable switch.
- Add idempotent CN and DN parameter management for CDW PostgreSQL, including default restoration and restart metadata.
- Add idempotent DCDB automatic backup retention, schedule and archive configuration.
- Add idempotent DTS migration configuration, preflight-check and lifecycle-action modules.
- Add idempotent Doris hot and cold tiering policy creation and updates.
- Add idempotent Oceanus immutable job configuration publishing and guarded historical-version deletion.
- Add idempotent Oceanus job savepoint triggering with asynchronous completion and failure handling.
- Add idempotent ``tse_gateway_consumer_group`` lifecycle management and guarded ``tse_gateway_secret_key`` credential rotation with redacted results.
- Add idempotent named EMR load-based and time-based automatic scaling strategy management.
- Add immutable Oceanus resource configuration versions with content-aware publication and referenced-version deletion protection.
- Add ordered, exact CDW PostgreSQL HBA rule management with guarded empty-rule replacement.
- Add paginated Nacos and ZooKeeper replica and server-interface topology discovery.
- Add paginated configuration file catalog discovery with namespace, group, name, ID and tag filters.
- Add paginated gateway service-to-route inventory with optional upstream target discovery.
- Add paginated governance service-contract and contract-version discovery.
- Add priority-addressed ``tse_gateway_canary_rule`` lifecycle management for standard and lane traffic rules.
- Add public-IP-to-gateway reverse lookup for incident and inventory workflows.
- Add read-backed ``tse_gateway_waf_protection`` and exact-set ``tse_gateway_waf_domains`` management.
- Add read-backed, delta-based ``tse_gateway_consumer_group_membership`` reconciliation.
- Add read-backed, delta-based ``tse_gateway_model_api_group_auth`` reconciliation.
- Add service- and route-scoped ``tse_gateway_cors`` and ``tse_gateway_ip_restriction`` policy modules.
- Add shared TSE instance tag discovery and expose tags from both solution roles.
- Add the ``tc_cloudbase_platform`` solution role for environment, static hosting, authentication-domain and HTTP-route composition.
- Add the ``tc_private_dns_zone`` solution role for account authorization, VPC association and record composition.
- Add the ``tc_ssm_secret_governance`` solution role for guarded secret, version and rotation composition.
- Add the ``tc_tat_fleet_automation`` solution role for reusable commands, immediate execution and scheduled invokers.
- Add the ``tc_tione_ml_pipeline`` role to compose data, training, model registry and online inference with guarded reverse-order teardown.
- Add the tc_cdwpg_analytics_platform role for ordered instance, parameter and HBA lifecycle management.
- Add the tc_clickhouse_platform role for ordered instance, parameter and backup lifecycle management.
- Add the tc_dcdb_stack role for instances, automatic backups, accounts and privileges.
- Add the tc_doris_analytics_platform role for ordered Doris instance and workload-governance lifecycle management.
- Add the tc_dts_migration role for guarded purchase, configuration, validation and optional startup.
- Add the tc_emr_platform role with guarded cluster termination.
- Add the tc_gaap_accelerator role for a complete proxy-to-origin delivery chain.
- Add the tc_oceanus_streaming_platform role for ordered workspace, dedicated-cluster and job lifecycle management.
- Added CHDFS exact-name resource lookup and the tc_chdfs_data_lake role for file systems, access controls and mounts.
- Added Elasticsearch exact-name lookup and the tc_elasticsearch_platform role for clusters, indexes and snapshots.
- Added GooseFS exact-name lookup and the tc_goosefs_cache role for file systems, filesets and quota governance.
- Added Organization member exact-name lookup and the tc_organization_governance role for nodes, members, identities and policies.
- Added SQL Server exact-name lookup and the tc_sqlserver_stack role for instances, backup strategy, accounts and two-stage teardown.
- Added exact-name Direct Connect lookups and the tc_direct_connect_fabric role for guarded circuit and tunnel lifecycle.
- Added exact-name GWLB lookups and the tc_gwlb_service_chain role for load balancers, target groups, appliances and associations.
- Added the tc_cdn_delivery role for CDN domains, serving state and real-time CLS access-log delivery.
- Added the tc_cloud_audit_governance role for account audit delivery, scoped tracks and truthful stop-only teardown.
- Added the tc_cloud_firewall_policy role for reusable templates and internet, NAT, VPC and DNAT policy layers.
- Added the tc_config_governance role for Config recording, delivery, compliance, remediation, alerting and aggregation workflows.
- Added the tc_kms_keyring role for multi-key lifecycle, independent rotation and guarded scheduled deletion.
- Allow ``tc_dlc_access_governance`` model versions and inference services to reference managed inference models by name with validated UID resolution.
- CONTRIBUTING.md - replaced the one-paragraph "becoming a maintainer" pointer with an actual path: the three roles (contributor / reviewer / maintainer) and what each may decide, the protected surfaces a reviewer may not merge alone (workflows, CODEOWNERS, the sanity-ignore budget, the SDK stamp, the module tiers and specs, galaxy.yml version), the CI gates a merge must not weaken, who owns module naming and why a rename is a deprecation, the expected commitment (2-4h/week, 48h first response, 60 days of silence means stepping down), and what a nomination issue should contain. MAINTAINERS.md now names the roles and records the same 60-day rule.
- Close the read side of twenty-five more write modules with new generated _info modules: cam_group_info, cam_group_membership_info, cam_saml_provider_info, cam_oidc_provider_info, cdb_parameter_template_info, cdb_audit_config_info, cdb_account_privilege_info, mongodb_backup_config_info, postgresql_backup_plan_info, redis_backup_config_info, cynosdb_backup_config_info, mariadb_backup_config_info, redis_parameter_template_info, postgresql_parameter_template_info, cvm_launch_template_info, cvm_launch_template_version_info, cvm_disaster_recover_group_info, cvm_hpc_cluster_info, cvm_image_info, ccn_attachment_info, vpc_flow_log_info, api_gateway_service_info, api_gateway_api_info, cfs_auto_snapshot_policy_info and cls_config_machine_group_binding_info.
- Expand Oceanus job versions with PyFlink, expert mode, trace, operator graph, per-class logging, Elasticsearch Serverless logging, variable replacement and state bucket controls.
- Extend ``dlc_data_engine`` with readable scheduled resume/suspend, prepaid elasticity and time-based elasticity configuration.
- Extend ``private_dns_zone`` with exact cross-account VPC associations through ``account_vpcs``.
- Extend ``tc_dlc_access_governance`` to create users before membership reconciliation and remove them after access teardown.
- Extend ``tc_dlc_access_governance`` to provision compute engines before access resources and tear them down last.
- Extend ``tc_dlc_access_governance`` with exact direct-user policies and policy-first user teardown.
- Extend ``tc_dlc_access_governance`` with metadata databases created before and removed after access policies.
- Extend ``tc_dlc_access_governance`` with opt-in, parent-aware model artifact checks between version publication and inference-service deployment, and publish their results for release gates.
- Extend ``tc_dlc_access_governance`` with ordered DLC engine-network VPC endpoint provisioning and teardown.
- Extend ``tc_dlc_access_governance`` with ordered engine configuration, network metadata and Notebook session orchestration plus published identities.
- Extend ``tc_dlc_access_governance`` with subject-aware data masking creation and mask-first teardown.
- Extend ``tse_gateway_service`` with authoritative backend target and active/passive health-check reconciliation.
- Extend tc_dcdb_stack with optional security controls.
- Integration runs now fail when a target reports green without ever executing its module (scripts/check_integration_ran.py). A target whose gate variable is unset prints an "Explain skipped" task and exits 0, so a whole run could be green while running nothing - the same failure mode that let the scheduled workflow report success for months without a single test. The checker reads each target's PLAY RECAP and flags any that changed nothing while skipping more tasks than it ran. Targets the account genuinely cannot host are exempt through ``account_blocked: true`` in tests/integration/coverage.yml, so the exemptions live in the registry instead of being hard-coded in the checker, and a new target added to the default list without its gate wired up fails the run.
- Integration targets now register the resources they create with ``scripts/e2e_manifest.py``, so the TTL reaper - the third cleanup line - finally has data to audit. Registered: ``private_dns``, ``cls_alarm``, ``tcr_immutable_tag_rule`` and ``tcr_webhook_trigger``.
- Reconcile Oceanus job and resource folders before contained platform objects and delete them in reverse declaration order during teardown.
- Reconcile Oceanus job folder placement after creation using the workspace job tree and ModifyJob target-folder support.
- Resolve AI gateway secret keys and model services by name inside ``tc_tse_api_gateway``.
- Resolve Oceanus job resource references by unique workspace name with automatic latest-version selection or explicit historical version pinning.
- Resolve consumers, consumer groups and Model APIs by name for role-managed membership and authorization relationships.
- Resolve gateway server groups by name in autoscaler bindings and public-network lifecycle operations.
- Resolve managed compute-group, resource-template and Ray-cluster names inside ``tc_dlc_access_governance`` for Ray clusters, laboratories and job specifications.
- Resolve online DLC image versions by exact name and switch existing data-engine images through ``SwitchDataEngineImage`` with explicit authorization and read-back convergence.
- Resolve relationship resource names inside membership and Model API authorization modules so name-based teardown is independently reliable.
- Update the Oceanus streaming platform role to reconcile job definition, configuration publication and runtime state in order.
- Use the certificate metadata API for name and domain changes so native private keys are only required for material rotation.
- Wait for TSE engine deletion and verify internet-access state convergence instead of returning on a stale running status.
- ``scripts/e2e_manifest.py add`` takes ``--ttl-seconds`` (default 7200) instead of requiring a caller-computed ``--expires-at``. An explicit ``--expires-at`` still overrides it. This keeps the expiry arithmetic in one tested place instead of duplicating Jinja date maths in every target.
- ``scripts/integration_inputs.py`` now also emits ``E2E_SCRIPTS_DIR`` and ``E2E_MANIFEST_PATH`` as absolute paths. ``ansible-test`` copies each target into a temporary work directory and runs it from there, so ``role_path``, ``playbook_dir`` and ``output_dir`` all point into a tree that is deleted when the run ends - a target cannot reach ``scripts/`` or the shared manifest by walking up from its own directory.
- ``scripts/resource_reaper.py`` gained ``--warn-on-empty``. An empty manifest is not "nothing expired", it is "nothing was tracked"; reporting ``0 expired`` there read like a working safeguard while the third cleanup line did no work at all. The workflow now passes the flag.
- api_gateway_api - add typed SCF backend function, namespace, qualifier, function type and integrated-response options, and reconcile MOCK payloads.
- apigateway_api_app - add module to create or delete a Tencent Cloud API Gateway application (present/absent, idempotent on the app name, check-mode safe).
- apigateway_ip_strategy - add module to create/remove a Tencent Cloud API Gateway IP access strategy, idempotent on the (service, strategy name) pair (roadmap
- apigateway_plugin - add module to create/remove a Tencent Cloud API Gateway plugin, idempotent on the plugin name (roadmap
- cdb_audit_rule - add module to create or delete a Tencent Cloud CDB audit rule (present/absent, idempotent on the rule name, check-mode safe).
- cdb_audit_rule_template - add module to create/remove a TencentDB for MySQL audit rule template, idempotent on the template name (roadmap
- cdb_instance, redis_instance, mongodb_instance, elasticsearch_instance, sqlserver_instance, mariadb_instance, dcdb_instance, postgresql_instance, cynosdb_cluster, tdcpg_cluster and tdmysql_db_instance - resolve through ``resolver.resolve_one`` instead of hand-rolled first-match lookups. Every one of these products filters names fuzzily on the server, so a task that said ``name: prod`` could silently manage ``prod-old``; the exact name now wins, and two candidates fail as ambiguous with the candidate list instead of the flat "specify instance_id" message. tdmysql_db_instance collects every page before resolving, so a match beyond the first 100 rows is no longer invisible.
- cfs_file_system - add the ``net_interface`` option (``VPC`` by default, ``CCN`` also accepted) plus ``ccn_id`` and ``cidr_block``; ``CreateCfsFileSystem`` rejects a request body without ``NetInterface``.
- clb_load_balancer, clb_target_group, clb_listener and clb_rule - resolve through ``resolver.resolve_one`` instead of hand-rolled first-match lookups. A listener and a forwarding rule have no name: a listener is addressed by ID or by its endpoint (port + protocol) and a rule by ``LocationId`` or by domain and url, both of which now go through the resolver's ``extra_match``, so two listeners on the same port and protocol fail as ambiguous instead of managing ``Listeners[0]``.
- clb_snat_ip - add module to manage SNAT IPs on a Tencent Cloud CLB instance (present/absent, idempotent on the requested IP set, check-mode safe).
- cls_alarm - add module to create/delete a CLS alarm policy, idempotent on alarm name, raw alarm payload via from_json_string (roadmap
- cls_alarm_notice - add module to create/remove a CLS alarm notice (notification channel group), idempotent on the notice name (roadmap
- cvm_chc_info - new module that gathers CHC host network configuration via DescribeChcHosts (ChcHostSet), closing the flagship write module's read-surface gap.
- cvm_disaster_recover_group_binding - the info-coverage audit now maps the write module to the existing generated cvm_disaster_recover_group_info (DescribeDisasterRecoverGroups returns the InstanceIds bound to each placement group, the exact set the write module reconciles).
- cvm_instance_action_timer_info - new module that gathers CVM instance action timers via DescribeInstancesActionTimer (ActionTimers), closing the flagship write module's read-surface gap.
- docs/examples/06_full_chain.yml is the golden path in one file: network foundation, web stack on the ids the foundation published, a read-back stage, and a tagged teardown play. 01 and 02 remain the split-apart version of the same two stages; 06 needs no copied ids because tc_vpc_foundation publishes tc_vpc_foundation_result. docs/examples/README.md documents the chain, the hand-off facts and the teardown order.
- docs/internal-community-post.md is an internal write-up of the month's collection work, framed as reusable methodology rather than a status report: static "cannot execute, still can check" gates (check_examples / check_porting_map), reading doc facts out of the repository before shipping, layering fast static gates ahead of the slow ansible-test suite, and three sandbox/toolchain traps (tmp_path uid collision, zsh word-split, ansible-test sanity being stricter than ruff on unused imports).
- docs/porting.md maps a tencentcloudstack/tencentcloud Terraform config or a raw Tencent Cloud SDK script onto this collection. It translates every provider resource to a module FQCN (including the names that are not the obvious guess), explains what replaces terraform.tfstate (nothing — each task re-discovers the resource by id or name), and contrasts credential, region and check-mode handling on both sides. The README, docs/scenarios.md and docs/examples/README.md cross-link it.
- docs/scenarios.md no longer claims the region defaults to ap-guangzhou; the modules have no default region, so a play must set region or TENCENTCLOUD_REGION. This was the single most common first-run failure when porting from Terraform and contradicted docs/porting.md.
- docs/triage.md defines a 48-hour first-response SLA on issues and pull requests, the label set used to triage them (triage, needs-info, module, dependencies, sla-breach, good first issue), and what counts as a response (human comments and submitted reviews, never bot comments).
- docsite - the collection now ships an ``antsibull-docs`` documentation build under ``docs/docsite/``. ``docs/docsite/build.sh`` renders every module and plugin into ``ansible-doc``-style RST and hands it to Sphinx, producing a browsable and searchable site in ``docs/docsite/build/html/``. With ~875 modules the only index of the collection was the README table, so this is what makes the ``DOCUMENTATION`` blocks reachable without installing anything. The build runs ``antsibull-docs`` with ``--fail-on-error`` and ``sphinx-build`` with ``-W``: a module whose documentation cannot be parsed, or a reference to an option that does not exist, fails the build instead of shipping a broken page.
- elasticsearch_instance_info - new module that gathers Elasticsearch Service instances via DescribeInstances (InstanceList), closing the flagship write module's read-surface gap.
- governance - generate ``docs/product-capabilities.md`` from modules and roles, enforce freshness in CI, and replace the obsolete 50-module roadmap target with product-family priorities.
- lifecycle governance - add a shared ``fail_sdk_error`` method and a source-level gate requiring every write module to preserve error code and request ID diagnostics.
- lighthouse_disk_info - new module that gathers Lighthouse disks via DescribeDisks (DiskSet), closing the flagship write module's read-surface gap.
- lighthouse_firewall_rules_info - new module that gathers the firewall rules of one Lighthouse instance via DescribeFirewallRules (FirewallRuleSet), closing the flagship write module's read-surface gap.
- lighthouse_key_pair_info - new module that gathers Lighthouse key pairs via DescribeKeyPairs (KeyPairSet), closing the flagship write module's read-surface gap.
- lighthouse_snapshot_info - new module that gathers Lighthouse snapshots via DescribeSnapshots (SnapshotSet), closing the flagship write module's read-surface gap.
- lookup plugins - add ``resource_id`` for exact, ambiguity-safe name-to-ID resolution across VPC, subnet, security group, CVM, CLB, TKE and CDB.
- lookup resource_id - add exact-name ALB resolution with native token pagination.
- lookup resource_id - add exact-name, paginated Auto Scaling group resolution.
- lookup resource_id - add exact-name, paginated CBS cloud-disk resolution.
- lookup resource_id - add exact-name, paginated CFS file-system resolution.
- lookup resource_id - add exact-name, paginated CKafka instance resolution.
- lookup resource_id - add exact-name, paginated CynosDB cluster resolution.
- lookup resource_id - add exact-name, paginated EdgeOne zone resolution.
- lookup resource_id - add exact-name, paginated EventBridge event-bus resolution.
- lookup resource_id - add exact-name, paginated Lighthouse instance resolution.
- lookup resource_id - add exact-name, paginated MQTT instance resolution.
- lookup resource_id - add exact-name, paginated Managed Prometheus instance resolution.
- lookup resource_id - add exact-name, paginated MariaDB instance resolution.
- lookup resource_id - add exact-name, paginated PostgreSQL instance resolution.
- lookup resource_id - add exact-name, paginated TDMQ RabbitMQ instance resolution.
- lookup resource_id - add exact-name, paginated TDMQ RocketMQ cluster resolution.
- module_utils - ``lifecycle`` now owns the shared lifecycle semantics: ``error_envelope``/``fail_from_sdk_error`` emit one redacted failure envelope with an ``error_kind``, ``missing_as_none`` normalises the dozen "not found" spellings, ``delete_resource`` treats an already-absent resource as unchanged, ``soft_delete`` encodes the isolate-then-purge convention, and ``plan_changes`` computes the change set once for both check mode and the real run.
- module_utils - add ``resolver``, a shared resource reference resolver. Tencent Cloud list filters match fuzzily (``vpc-name`` is a substring match), so an ID, a name or a tag set is now re-checked client-side: an exact name wins, a single fuzzy candidate is accepted, and two or more candidates fail with ``ambiguous=true`` and the candidate list instead of silently managing whichever row the API listed first.
- module_utils.client - ``load_profile`` keeps its definition here and is re-exported through ``plugin_utils.profile`` for controller-side callers. ``PROFILE_FILE`` / ``DEFAULT_PROFILE_NAME`` are deliberately not re-exported: a re-exported constant is a separate binding, so rebinding it through the shim silently had no effect on the reader. Tests that redirect the profile file patch ``module_utils.client.PROFILE_FILE``.
- module_utils.paging - ``Paginator`` keeps its definition here, because ``scripts/generate_info_modules.py`` emits ``from ...module_utils.paging import Paginator`` into every generated ``_info`` module and committed generated modules are never rewritten; the class is re-exported through ``plugin_utils.paging`` for the inventory plugins. ``paginate()`` remains a module-only convenience wrapper and is not re-exported.
- module_utils.polling - new ``poll_until`` helper: the bounded poll loop with the budget counted as the delays actually slept. It lives in ``module_utils`` because both callers must reach it, and ``plugin_utils.polling`` re-exports it for the controller side. It is the first shared helper motivated by a controller-side consumer, and ``module_utils.waiters.wait_for_state`` now delegates to it while keeping its exact module-side failure payload (``expected_states``, ``last_state``, ``timeout``). ``wait_until_gone`` and ``wait_for_task`` keep their own terminal conditions and are unchanged.
- module_utils.tagging - new ``merge_tags`` helper implementing that merge on top of the existing ``normalize_tags`` / ``tags_from_sdk`` readers, so the filter and the resource modules cannot drift apart; the ``tag_merge`` filter is a thin wrapper that only translates the helper's ``TypeError`` into an ``AnsibleFilterError``. It lives in ``module_utils`` even though the filter is its only consumer today, because tag reading and tag comparison are one body of semantics and because the layering rule is one-directional: a helper a module may later need has to be born in ``module_utils``. ``plugin_utils.tags`` re-exports it for the controller side.
- plugins/plugin_utils - new controller-side import surface for helpers that non-module plugins need. ``plugin_utils.profile`` re-exports ``module_utils.client.load_profile``, ``plugin_utils.paging`` re-exports ``module_utils.paging.Paginator`` and ``plugin_utils.polling`` re-exports ``module_utils.polling.poll_until`` / ``PollOutcome``; the ``resource_id`` / ``ssm_parameter`` / ``sts_caller_identity`` lookups, the CVM / CLB / COS / SG / TKE inventory plugins and the ``tat`` connection plugin now import those paths, and the ``tc_wait`` action plugin imports ``plugin_utils.polling``.
- plugins/plugin_utils - the implementations stay in ``module_utils`` rather than moving here, because ansible-test's ``import`` test lets module-side code import only ``plugins.module_utils``: putting ``load_profile`` or ``Paginator`` in ``plugin_utils`` makes every module that imports them fail that test (observed: 881 errors). The direction is therefore ``module_utils`` implementations -> ``plugin_utils`` re-exports -> non-module plugins, and it is enforced by ``ansible-test sanity --test import``. ``plugins/plugin_utils/README.md`` documents the rule.
- postgresql_instance - the info-coverage audit now maps the write module to the existing generated postgres_instance_info (DescribeDBInstances is the list surface the write module reconciles against); the historical postgres vs postgresql naming split had kept the pair unregistered.
- redis_replication_group - add module to create/remove a TencentDB for Redis replication group, idempotent on group name, seeds from an instance on create (roadmap
- release workflow - ``ansible-test units`` could fail on a tag while the same suite passed on ``main``: CI installs ``requirements.txt`` (and the pinned SDK) in the same job, so unit tests silently had the SDK importable, while the release workflow installed only ansible-core. The release workflow now installs the same dependency set as CI, so the two agree.
- resource_id lookup - add STS AssumeRole, endpoint override, request timeout and SDK client-identifier options consistent with resource modules.
- resource_id lookup - expand name resolution to Redis, MongoDB, API Gateway services, TCR instances, TEM environments and TEM applications.
- resource_id lookup - paginate name searches and retain ambiguity checks across page boundaries for large accounts.
- roles - add ``tc_container_registry`` for TCR instances, namespaces, repositories, vulnerability policy and cross-region replication.
- roles - add ``tc_database_stack`` for a CDB instance, databases, accounts, exact privilege sets and backup retention.
- roles - add ``tc_observability_baseline`` for CLS indexed topics and Cloud Monitor alarm policies.
- roles - add ``tc_security_baseline`` for CAM identities and policy attachments, CloudAudit delivery and Config compliance rules.
- roles - add ``tc_serverless_application`` for SCF code and configuration, aliases, triggers and optional API Gateway publication.
- roles - add ``tc_tem_application`` to provision a TEM environment, application definition, deployment and access-service mappings as one reusable solution.
- roles - add ``tc_tke_platform`` for clusters, node pools, endpoints, addons, authentication and audit delivery.
- roles - add ``tc_vpc_foundation`` for VPCs, multi-zone subnets, NAT gateways, route tables, security groups and exact-set rules.
- sanity - the 66 blanket ``validate-modules:invalid-documentation`` ignore entries are gone. They were suppressing a real defect (see the bugfix entry) rather than a false positive, and they were also masking every *other* validate-modules code for the same files, because a module whose documentation cannot be parsed is not validated at all. Removing them dropped the ignore total from 2289 to 1869 and made ``validate-modules`` pass for the first time; the 11 files where ``no_log`` is genuinely a name-based false positive (``key`` inside ``tags``, ``primary_keys``, ``keyword``, ``output_cos_key_prefix``) keep a targeted ``validate-modules:no-log-needed`` entry.
- scf_custom_domain - add module to create or delete a Tencent Cloud SCF custom domain (present/absent, idempotent on the domain name, check-mode safe).
- scripts/check_examples.py --check validates the example playbooks in docs/examples/ and playbooks/ in CI. They are the copy-paste entry point to the collection and the only artefacts no job ever ran, so they could rot silently. The check asserts every susunola.tencentcloud module resolves, every option passed to one is declared (doc fragments included), every role exists, every role variable is declared in that role's defaults/main.yml, and every variable a play reads is declared, registered, published by a role, documented as an extra var or guarded with "is defined".
- scripts/check_sanity_ignore.py - lowered the ignore budget from 2350 to 1900 against a committed total of 1869. After the docsite work removed 420 blanket ignore lines the old ceiling left 481 lines of slack, so the guard could not fire; it now binds again. Updated the budget figures quoted in docs/panorama.html, docs/capability-map.html and docs/roadmap.md.
- scripts/check_sanity_ignore.py - the budget guard now also fails when an ignore entry names a file that does not exist, and the committed total dropped from 1869 to 1557 after the dangling entries were removed.
- scripts/release_check.py is a pre-release guard: it reports whether the version in galaxy.yml is publishable before a tag is pushed, checking the version format, that it is ahead of the newest released tag, that the tag is free locally and on origin, that there are changelog fragments to fold, that the version is not already in changelog.yaml, and that the tree is clean. --dry-run additionally builds the tarball in a temporary directory, checks MANIFEST.json against galaxy.yml, asserts nothing from build_ignore leaked in, installs it and lists its documentation, then prints what pushing the tag would do. docs/release.md is the runbook.
- scripts/triage_sla.py measures that SLA from the GitHub API and prints one row per item with its age, response time, and one of four statuses (OK, LATE, WAITING, BREACH). Only BREACH -- unanswered and overdue -- fails --check, because it is the only one that is still actionable; a late answer is history, and failing on it would leave CI red on an item nobody can clear except by closing it. --exclude-author drops items a maintainer opened, which can never receive a first response.
- solution roles - add ``tc_alb_application_entry`` for ALB instances, target groups, exact backend sets and listeners with automatic forwarding, exact-name adoption and dependency-ordered teardown.
- solution roles - add ``tc_api_gateway_platform`` for service adoption, APIs, releases, keys, usage plans and both binding types with secret-safe, dependency-aware teardown.
- solution roles - add ``tc_autoscaling_group`` for exact-name adoption and child-first management of Auto Scaling groups, scaling policies and scheduled capacity actions, with a zero-capacity safe default.
- solution roles - add ``tc_block_storage`` for exact-name CBS disk adoption, attachment, snapshots, sharing, backup points and automatic snapshot policies with dependency-safe teardown.
- solution roles - add ``tc_cmq_messaging`` for CMQ queues, topics and HTTP or queue subscriptions with endpoint-safe teardown ordering.
- solution roles - add ``tc_cynosdb_cluster`` for cloud-native database clusters, accounts, exact privilege sets and automatic backups with exact-name adoption and two-stage isolation and purge semantics.
- solution roles - add ``tc_dns_zone`` for child-first management of DNSPod domains, custom routing lines, line groups and DNS records.
- solution roles - add ``tc_edgeone_application`` covering EdgeOne delivery, DNS and all managed web-security policy modules with exact-name zone adoption and dependency-safe teardown.
- solution roles - add ``tc_eventbridge_router`` for exact-name event-bus adoption and child-first orchestration of source connections, routing rules and delivery targets.
- solution roles - add ``tc_kafka_platform`` for CKafka instances, access routes, users, topics, ACL grants and ACL rules with exact-name adoption, deletion-protection handling and child-first teardown.
- solution roles - add ``tc_lighthouse_stack`` for exact-name instance adoption, SSH keys, firewall rules, data disks and snapshots with child-first teardown and explicit isolation semantics.
- solution roles - add ``tc_mariadb_stack`` for MariaDB instances, accounts, scoped privilege sets and automatic backups with exact-name adoption and explicit two-stage isolation and purge semantics.
- solution roles - add ``tc_mongodb_stack`` for MongoDB instances, exact account roles, explicit password rotation and automatic backup policy, including exact-name adoption and credential-aware child-first teardown.
- solution roles - add ``tc_mqtt_broker`` for MQTT instances, network access, topics, users and ordered authorization policies with exact-name adoption and dependency-ordered teardown.
- solution roles - add ``tc_object_storage_baseline`` for secure COS bucket composition across encryption, lifecycle, access, logging, replication and irreversible retention features, with configuration-first safe teardown.
- solution roles - add ``tc_postgresql_stack`` for PostgreSQL instances, accounts, backup plans and reusable parameter templates with exact-name adoption and explicit two-stage isolation and purge semantics.
- solution roles - add ``tc_prometheus_platform`` for exact-name Managed Prometheus adoption, cluster agents, scrape jobs, rules, alerts, notifications and Grafana bindings with dependency-safe teardown.
- solution roles - add ``tc_rabbitmq_platform`` for exact-name dedicated instance adoption, users, virtual hosts, permissions and bindings with secret-safe tasks and deletion-protection-aware teardown.
- solution roles - add ``tc_rabbitmq_serverless`` for managing users, virtual hosts, permissions, exchanges, queues and bindings inside an explicitly supplied existing Serverless instance.
- solution roles - add ``tc_redis_stack`` for Redis instances, application accounts, explicit password rotation, automatic backups and reusable parameter templates, including exact-name adoption and child-first teardown.
- solution roles - add ``tc_rocketmq_platform`` for exact-name cluster adoption and child-first orchestration of RocketMQ namespaces, roles, permissions, topics and consumer groups.
- solution roles - add ``tc_shared_file_storage`` for CFS file systems, permission groups, exact client rules and automatic snapshot binding with name adoption and dependency-ordered teardown.
- solution roles - add ``tc_waf_application`` covering every WAF write module with existing-instance ownership boundaries and dependency-safe teardown.
- solution roles - resolve exact parent names through ``resource_id`` before validating and executing teardown for VPC, TKE, CDB, TCR, TEM and API Gateway compositions.
- solution-role governance - add source contracts that enforce child-first teardown ordering for stateful and externally reachable resources.
- tag_merge - new filter plugin that merges any number of Tencent Cloud tag sources into one ``{key: value}`` mapping. It is the collection's first filter plugin, and it closes a gap no existing filter could: ``ansible.builtin.combine`` only understands mappings, so combining the ``tags`` mapping a module parameter takes with the ``Key``/``Value`` list an ``*_info`` module returns had no expression. A source may be a tag mapping, a single ``Key``/``Value`` tag, a list of tags, a list of SDK ``Tag`` objects, or a nested list of any of those; later sources win, the result is sorted by key with string values (the same normalization the resource modules apply to ``tags``), and an unsupported source fails the task with the filter named instead of dropping tags silently.
- tc_serverless_application - bind API Gateway routes directly to the SCF function managed by the role.
- tc_wait - new action plugin that waits for an existing Tencent Cloud resource to reach a state by polling one of the ``*_info`` modules. It is the collection's first action plugin and the first plugin that can drive another module: a module cannot call a module, so "wait until this disk is attached" was previously inexpressible without ``until``/``retries`` against a raw API call. Options are ``module`` (the ``*_info`` module to poll, short name or FQCN), ``args`` (its arguments), ``state`` (required; ``absent`` means "no longer listed"), plus optional ``state_field``, ``list_field``, ``delay`` and ``timeout``. Waiting only reads, so the task never reports ``changed``; in check mode it observes once instead of polling.
- tcr_immutable_tag_rule - add module to create/delete a TCR immutable tag rule, idempotent on repository+tag pattern within a namespace (roadmap
- tcr_webhook_trigger - add module to create/delete a TCR webhook trigger, idempotent on trigger name within a namespace (roadmap
- tdcpg_cluster_info - new module that gathers TDSQL-C for PostgreSQL clusters via DescribeClusters (ClusterSet), closing the flagship write module's read-surface gap.
- tests - the COS AppId unit tests no longer import the real ``tencentcloud`` SDK. ``fetch_appid`` only needs a client class and a request object to hand to the module double, so the tests now stub ``tencentcloud.cam`` / ``tencentcloud.sts`` in ``sys.modules`` and run in an SDK-free environment as well as an SDK-provided one.
- tests/integration/smoke_readonly.yml is a manual, credential-gated, read-only smoke test that proves the full runtime chain against the real Tencent Cloud API (credential resolution, SDK client, signed request, live response) without creating any resources. It lists VPCs and CVM instances only and is excluded from ansible-test automation because it needs live credentials.
- tke_cls_log_config is a new idempotent TKE module that creates or deletes a CLS log collection configuration for a cluster. The configuration is the raw TKE log-config object, passed through as JSON to the API; idempotency is keyed on the configuration name within the cluster. It supports check mode.
- tke_cluster, tke_node_pool and tke_cluster_upgrade - resolve through ``resolver.resolve_one`` instead of hand-rolled first-match lookups. ``tke_cluster`` and ``tke_cluster_upgrade`` took ``Clusters[0]`` for an ID lookup without re-checking it, which is the wrong thing to trust in front of a version upgrade; node pools have no server-side name filter, so every pool of the cluster is now listed and resolved client-side.
- tke_cluster_deletion_protection is a new idempotent TKE module that enables or disables deletion protection on a cluster, preventing accidental cluster deletion through the console, CLI or API. It reads the current protection state first and is a no-op when the cluster is already in the desired state; it supports check mode.
- tke_cluster_route is a new idempotent TKE module that creates or deletes a route (destination PodCIDR to next-hop gateway IP) inside a cluster route table. A route is uniquely identified within a table by its destination CIDR block. It supports check mode.
- tke_cluster_route_table is a new idempotent TKE module that creates or deletes a cluster route table (usually named after the cluster ID). Route table CIDR and VPC are immutable once created, so an existing table with the same name is treated as present rather than reconciled. It supports check mode.
- vpc, subnet, security_group, route_table, eip, nat_gateway and cvm_instance - resolve through ``resolver.resolve_one`` and report failures and deletes through ``lifecycle`` instead of hand-rolled first-match lookups.
- vpn_gateway, vpn_connection, peering_connection, network_interface, network_acl, vpc_flow_log, nat_gateway_rule, customer_gateway, dc_direct_connect and dc_direct_connect_tunnel - resolve through ``resolver.resolve_one`` instead of hand-rolled first-match lookups. Each of these took ``XxxSet[0]`` after a substring name filter, so ``name: prod`` could manage ``prod-old``; the shared contract now applies to all of them (an exact name wins, a lone fuzzy candidate is accepted, two or more candidates fail with ``ambiguous=true`` and the candidate list), including the paginated lookups and the product-specific scopes (an ENI's ``SubnetId``, a tunnel's ``DirectConnectId``).

Bugfixes
--------

- Align ``ssm_rotation`` begin-time documentation and frequency validation with the SSM API contract.
- DOCUMENTATION - 65 modules documented an option with a comma inside an unquoted YAML flow mapping, for example ``{type: int, description: Maximum retained versions, from 1 to 24.}``. The comma is the flow separator, so ``from 1 to 24.`` was parsed as a second option key and ``ansible-doc`` rendered it as a parameter (``max_reserved_models`` showed a ``from 1 to 24.: null`` line). 115 option descriptions in 68 modules are now quoted, including the same mistake in five ``RETURN`` blocks. Two related defects were fixed in the same pass: ``no_log`` inside a ``DOCUMENTATION`` option (9 modules - it belongs in ``argument_spec``, not in the docs) and nested ``options:`` where the schema requires ``suboptions:`` (3 modules).
- Make ``ssm_parameter`` genuinely idempotent for unchanged current values, apply creation tags, update descriptions through the supported API, and restore secrets pending deletion.
- Paginate Oceanus job and workspace identity lookups to prevent duplicate creation in environments larger than one API page.
- Route DLC Lab, JobSpec and Ray cluster priority changes through their dedicated priority APIs instead of generic update requests.
- Sanity ignores - dropped 302 entries (100 in ignore-2.21.txt, 101 each in 2.19 and 2.20) that named test files deleted during the P0-07/P0-09 unit test rewrites, plus 10 entries ansible-test reports as unnecessary. An ignore line naming a file that no longer exists is itself a failure of ansible-test's ``ignores`` test, and 302 lines of "File ... does not exist" are easy to mistake for noise: they kept ``main`` red from 2026-09-09T16:27 until now. ``scripts/check_sanity_ignore.py`` now also rejects any entry whose file is missing, so the next one fails as one obvious line instead of three hundred.
- Standardize Private DNS zone and record API failure payloads with the collection lifecycle contract.
- Standardize ``tat_command`` API failures with the collection lifecycle error contract.
- Stop online CDN domains and wait for offline state before deleting them.
- Unit tests - fixed the 44 pylint ``repeated-keyword`` findings and 2 ``unnecessary-comprehension`` findings that were also failing sanity. The ``repeated-keyword`` ones were a pylint false positive: ``dict(params(), page_size=0)`` is inferred as having ``page_size`` twice whenever the overridden key already exists in the base dict. The ``params()`` helpers now take overrides directly (``params(page_size=0)``), which reads better and does not trip the inference.
- Update ``dlc_table`` comments in place through ``AlterTableComment`` instead of requiring destructive table replacement.
- Wait for Oceanus resources and immutable resource/job configuration versions to become visible or disappear before returning.
- Wait for Oceanus workspace create, update and delete convergence and for job deletion before returning, preventing dependent-task races.
- apigateway_ip_strategy - build the DescribeIPStrategysStatus filter with the field the SDK actually declares. The lookup set ``Filter.Key``, but the API Gateway ``Filter`` model only declares ``Name`` and ``Values``, so the attribute was silently dropped: the request went out unfiltered and the strategy was matched client-side only. It also set ``Limit`` and ``Offset``, which ``DescribeIPStrategysStatusRequest`` does not declare - the SDK serialized them into the unknown parameters ``Imit`` and ``Ffset`` and sent those to the API as well.
- cfs_file_system - match an existing file system on ``FsName`` instead of ``Name``. ``DescribeCfsFileSystems`` reports the display name as ``FsName``, so name-based lookups never matched and a rename was reported as drift on every run.
- cfs_file_system - re-read the file system by the ID returned from ``CreateCfsFileSystem`` so the created resource is reported back instead of ``None``.
- cls_alarm - correct the documented alarm body so the example actually creates an alarm. The old payload used ``MonitorObjectType: log`` (the field is a ``uint64``: 0 = one shared monitor object, 1 = one per query), ``MonitorTime: {Type: Relative, TimeGap: 600}`` (``Type`` accepts only ``Period``, ``Fixed`` or ``Cron`` and the period field is ``Time``, not ``TimeGap``), and omitted everything CLS requires - at least one of ``AlarmNoticeIds`` or ``MonitorNotice``, a ``LogsetId`` next to every ``TopicId``, and an ``EndTimeOffset`` greater than its ``StartTimeOffset``. The module forwards the body verbatim, so every one of these was rejected by the API rather than by Ansible; only a real-cloud run surfaced them. The option documentation now spells out the constraints.
- cos_bucket, cos_bucket_info - read CORS and lifecycle rules from the flat shape the SDK actually returns. A ``get_bucket_cors`` / ``get_bucket_lifecycle`` GET answers a CORSRule / Rule list at the top level rather than nesting it under ``CORSConfiguration`` / ``LifecycleConfiguration``, so both sub-configurations always looked empty: the module reported a change on every run and never converged.
- cos_bucket, cos_bucket_info, cos_object, cos_object_info, cos_object_sync - resolve ``secret_id``/``secret_key`` from the TCCLI profile in ``~/.tencentcloud/default.configure`` when no parameter or ``TENCENTCLOUD_*`` variable supplies them, and resolve ``region`` the same way. The COS client previously only looked at parameters and the environment, so every ``cos_*`` module failed with ``Set secret_id and secret_key`` under ``ansible-test integration``, which strips the environment.
- cos_bucket, cos_bucket_info, cos_object, cos_object_info, cos_object_sync - resolve the COS AppId through CAM ``GetUserAppId`` instead of treating the STS ``GetCallerIdentity`` ``AccountId`` as the AppId. On accounts where the UIN and the AppId differ the bucket was addressed under a name the account does not own and every COS call answered ``AccessDenied``.
- dlc_ray_job_list_info - the module description referenced ``O(fetched_count)``, which is a return value and not an option, so the docsite build failed on an unresolved cross-reference. It is now ``RV(fetched_count)``.
- galaxy.yml now excludes generated, gitignored output from the collection build: docs/docsite/build, docs/docsite/rst/collections, .pytest_cache, .ruff_cache, .ansible, .coverage and the coverage reports. ansible-galaxy reads build_ignore but not .gitignore, so building on a machine that had built the docsite shipped roughly 250 MB of Sphinx HTML (36.6 MB and nine minutes instead of 1.9 MB and three), and packaging the tool caches made the tarball's own FILES.json checksums disagree with its contents, which ansible-galaxy collection install rejects. CI never saw either problem because CI builds from a clean checkout.
- playbooks/three_tier_web.yml declares web_instance_password, which it passed to cvm_instance without ever defining; a copy of the playbook failed with "The task includes an option with an undefined variable". docs/examples/05_module_mix.yml prints sg.security_group.SecurityGroupId instead of a top-level sg.security_group_id the security_group module does not return.
- postgresql_instance - align long-running waiter defaults with documentation and correct inline documentation parsing.
- private_dns integration target - use a domain the API actually accepts. The target created ``ansible-<random>.internal``, but a single-label ``.internal`` zone is refused outright with ``InvalidParameter.IllegalDomainTld``. The target had therefore never once completed, which is how the defect survived: it self-skipped on its gate variable for as long as that was unset. It now uses the ``<label>.example.com`` shape the module already documents.
- private_dns_zone - recognise ``InvalidParameter.ZoneNotExists`` as "already gone". Private DNS reports a missing zone as an ``InvalidParameter`` rather than a ``ResourceNotFound``, so ``state=absent`` failed its own post-delete confirmation instead of treating the successful delete as success. The code was added to the shared ``is_not_found`` classification, so every module benefits, not just this one.
- redis_replication_group - document a remark that the API actually accepts. The example used ``remark: Primary HA group for app cache``, but CreateReplicationGroup validates the remark with the instance-name rule and rejects any space with ``InvalidParameterValue.InstanceNameRuleError: Illegal character of replication group remark``. The integration target carried the same defect (``CI integration test``), so the real-cloud run failed on the very first create.
- redis_replication_group integration target - stop failing on an account that is not whitelisted for replication groups. CreateReplicationGroup answers ``UnauthorizedOperation.NoCAMAuthed: user not in replication group whitelist`` even for a freshly created, running Redis instance, which is an account capability gap rather than a regression. The target now recognises that code, explains it and skips the lifecycle, while any other create error still fails the run.
- solution roles - require explicit parent IDs before deleting declared child resources in the VPC, TKE, CDB and observability roles.
- tag - stop treating tag-query authorization, throttling or service errors as an empty remote tag set before a write operation.
- tc_serverless_application - unrelease and remove managed API Gateway APIs and their service during teardown instead of leaving externally reachable resources behind.
- tc_wait - ansible-core 2.21.3 moved action failures onto ``UnifiedTaskResult`` and now passes the ``result`` dict of an ``AnsibleActionFail`` through untouched, where 2.21.2 and earlier merged the message into it as ``msg``. Every failure the plugin raised therefore surfaced as an empty payload: the task still failed, but the operator lost the reason and the timeout payload lost ``attempts``, ``waited``, ``observed_states`` and ``last_result`` along with it. The plugin now puts ``failed`` and ``msg`` into the result it passes, which is version-independent, and a regression test asserts the payload rather than the exception type. One test that covers the ``Invalid options`` failure raised by ``ActionBase.run`` (not by this plugin) accepts either spelling, since the plugin cannot influence a failure it does not raise.
- tc_web_stack and tc_disaster_recovery now publish tc_web_stack_result and tc_disaster_recovery_result as facts. docs/examples/02_web_stack.yml, 03_tke_cluster.yml and 04_disaster_recovery.yml all end by printing a role result; two of the three roles never set one, so the last task of those examples printed "VARIABLE IS NOT DEFINED!".
- tc_web_stack, tc_tke_cluster, tc_disaster_recovery, tc_clb_http and tc_launch declare their region variable in defaults/main.yml and read it with default(omit, true), matching the other 43 roles. They read an undeclared tc_<role>_region, which worked by accident (default(omit) tolerates undefined) but left a variable every example sets out of the role's documented interface.
- tcr_webhook_trigger - stop requiring NamespaceName to match when looking up an existing trigger. DescribeWebhookTrigger returns NamespaceName as null and only populates NamespaceId, so the comparison never matched: the module decided the trigger was absent and a second ``state: present`` run called CreateWebhookTrigger again, which the API rejects with "notification policy named ... already exists". The lookup is already scoped to the namespace by the request, so it now only rejects a trigger whose namespace is present AND different.
- waf_custom_white_rule - mark ``bypass_modules`` as explicitly non-secret so Ansible validation does not reject the public module-name list.

New Plugins
-----------

Filter
~~~~~~

- tag_merge - Merge Tencent Cloud tag sources into one mapping

New Modules
-----------

- api_gateway_api_info - Gather information about Tencent Cloud API Gateway APIs
- api_gateway_service_info - Gather information about Tencent Cloud API Gateway services
- cam_group_info - Gather information about Tencent Cloud CAM groups
- cam_group_membership_info - Gather information about Tencent Cloud CAM group memberships of a user
- cam_oidc_provider_info - Gather information about a Tencent Cloud CAM OIDC identity provider
- cam_saml_provider_info - Gather information about Tencent Cloud CAM SAML identity providers
- ccn_attachment_info - Gather information about Tencent Cloud CCN attachments
- cdb_account_privilege_info - Gather information about Tencent Cloud CDB account privileges
- cdb_audit_config_info - Gather information about a Tencent Cloud CDB audit configuration
- cdb_parameter_template_info - Gather information about Tencent Cloud CDB parameter templates
- cfs_auto_snapshot_policy_info - Gather information about Tencent Cloud CFS automatic snapshot policies
- cls_config_machine_group_binding_info - Gather information about Tencent Cloud CLS machine group config bindings
- cvm_disaster_recover_group_info - Gather information about Tencent Cloud CVM placement groups
- cvm_hpc_cluster_info - Gather information about Tencent Cloud CVM HPC clusters
- cvm_image_info - Gather information about Tencent Cloud CVM images
- cvm_launch_template_info - Gather information about Tencent Cloud CVM launch templates
- cvm_launch_template_version_info - Gather information about Tencent Cloud CVM launch template versions
- cynosdb_backup_config_info - Gather information about a Tencent Cloud CynosDB backup configuration
- mariadb_backup_config_info - Gather information about a Tencent Cloud MariaDB backup configuration
- mongodb_backup_config_info - Gather information about a Tencent Cloud MongoDB backup configuration
- postgresql_backup_plan_info - Gather information about Tencent Cloud PostgreSQL backup plans
- postgresql_parameter_template_info - Gather information about Tencent Cloud PostgreSQL parameter templates
- redis_backup_config_info - Gather information about a Tencent Cloud Redis backup configuration
- redis_parameter_template_info - Gather information about Tencent Cloud Redis parameter templates
- vpc_flow_log_info - Gather information about Tencent Cloud VPC flow logs

v1.1.0
======

Minor Changes
-------------

- Add docs/deprecation-policy.md documenting the deprecation/removal lifecycle (one major release of warning), the runtime.yml plugin_routing entry shape, the DOCUMENTATION deprecated block and the changelog fragment format; meta/runtime.yml keeps a commented plugin_routing template skeleton. No module is deprecated in this release - no real candidates exist.
- Add generated vpn_connection_info, customer_gateway_info, ccn_info, cbs_snapshot_info and cfs_snapshot_info discovery modules closing the read side of the existing write modules.
- Add scripts/audit_info_coverage.py: audits that every write module has a readable query surface (matching _info module, curated KNOWN_COVERAGE mapping, or documented KNOWN_GAPS entry) and gates CI with --check.
- Add the three_tier_web scenario playbook (VPC + subnet + security group + exact_count CVM pool + CLB with listener and registered targets) and docs/scenarios.md indexing all five scenario playbooks with prerequisites and cost notes; README links to the scenario index.
- Add tke_cluster_kubeconfig module fetching a TKE cluster's intranet or extranet kubeconfig via DescribeClusterKubeconfig, returning it in the task result or writing it to dest with 0600 permissions and content-hash idempotency.
- Add tke_kubeconfig and cos_static_site scenario playbooks.
- Close the read side of thirty more write modules with new generated _info modules: network_interface_info, security_group_rule_info, tke_node_pool_info, scf_alias_info, scf_version_info, scf_trigger_info, clb_listener_info, clb_listener_target_info, clb_target_group_info, cam_policy_attachment_info, nat_gateway_dnat_rule_info, nat_gateway_snat_rule_info, tag_info, havip_info, network_acl_info, peering_connection_info, vpc_address_template_info, vpc_address_template_group_info, the ALB API (alb.v20251030) modules alb_load_balancer_info, alb_listener_info, alb_target_group_info and alb_target_group_targets_info, plus eks_cluster_info, eks_container_instance_info, sms_signature_info, sms_template_info, vod_class_info, vod_sub_app_info, tke_cluster_autoscaler_info and cvm_image_share_info for the 1.0.0 write modules.
- Close the read side of twenty-four write modules with new generated _info modules: cdb_account_info, cdb_database_info, cdb_backup_config_info, mariadb_account_info, mongodb_account_info, sqlserver_account_info, postgresql_account_info, cynosdb_account_info, redis_account_info, kms_key_rotation_info, dc_direct_connect_info, cls_logset_info, cls_machine_group_info, cls_config_info, cls_shipper_info, cls_index_info, monitor_prometheus_instance_info, monitor_grafana_instance_info, ckafka_topic_info, ckafka_user_info, cbs_auto_snapshot_policy_info, cfs_permission_group_info, cfs_permission_rule_info and ssm_secret_info.
- Raise the SDK contract coverage gate from 55 to 72 after the write-module unit-test drive lifted the measured total to 74 percent (gate keeps two points of headroom).
- cos_object - add pre-signed URL support: ``presign=true`` returns a URL signed for the ``method`` option (``GET`` download or ``PUT`` upload, validity bounded by ``expires``) without touching the bucket and reports ``changed=false``; a non-default ``method`` without ``presign`` fails the task explicitly.
- requirements.txt - tencentcloud-sdk-python is now a compatibility range (>=3.1.164,<4.0.0) instead of an exact pin; generated _info specs remain vouched for the GENERATED_SDK_VERSION stamp, and CI re-pins the SDK to the stamp (via the new ``check_sdk_drift.py --print-stamp``) before the drift sentinel and contract tests.

Bugfixes
--------

- generate_info_modules.py - the list pagination mode now passes extra_params/ids/filters to build_request (previously rendered a broken build_request(models, 0, 0) call for any list spec with extra params), extra_params support elements and choices in the argument spec and documentation, generated list-mode tests inject sample values for extra params, a string_pagination spec flag covers APIs whose Offset/Limit are declared as strings, and the none pagination mode no longer emits E126-tripping continuation indents.
- sync_registry.py - render_galaxy_yml no longer duplicates the word ``modules`` when refreshing the module count in the galaxy.yml description, and its unit test no longer rewrites the real galaxy.yml from the fake-repo fixture.

New Modules
-----------

- alb_listener_info - Gather information about Tencent Cloud ALB listeners
- alb_load_balancer_info - Gather information about Tencent Cloud ALB instances
- alb_target_group_info - Gather information about Tencent Cloud ALB target groups
- alb_target_group_targets_info - Gather information about Tencent Cloud ALB target group targets
- cam_policy_attachment_info - Gather information about Tencent Cloud CAM policy attachments
- cbs_auto_snapshot_policy_info - Gather information about Tencent Cloud CBS automatic snapshot policies
- cbs_snapshot_info - Gather information about Tencent Cloud CBS snapshots
- ccn_info - Gather information about Tencent Cloud CCN instances
- cdb_account_info - Gather information about Tencent Cloud CDB accounts
- cdb_backup_config_info - Gather information about Tencent Cloud CDB backup configuration
- cdb_database_info - Gather information about Tencent Cloud CDB databases
- cfs_permission_group_info - Gather information about Tencent Cloud CFS permission groups
- cfs_permission_rule_info - Gather information about Tencent Cloud CFS permission group rules
- cfs_snapshot_info - Gather information about Tencent Cloud CFS snapshots
- ckafka_topic_info - Gather information about Tencent Cloud CKafka topics
- ckafka_user_info - Gather information about Tencent Cloud CKafka users
- clb_listener_info - Gather information about Tencent Cloud CLB listeners
- clb_listener_target_info - Gather information about Tencent Cloud CLB listener targets
- clb_target_group_info - Gather information about Tencent Cloud CLB target groups
- cls_config_info - Gather information about Tencent Cloud CLS collection configurations
- cls_index_info - Gather information about a Tencent Cloud CLS topic index
- cls_logset_info - Gather information about Tencent Cloud CLS logsets
- cls_machine_group_info - Gather information about Tencent Cloud CLS machine groups
- cls_shipper_info - Gather information about Tencent Cloud CLS shippers
- customer_gateway_info - Gather information about Tencent Cloud customer gateways
- cvm_image_share_info - Gather information about Tencent Cloud CVM image share permissions
- cynosdb_account_info - Gather information about Tencent Cloud CynosDB accounts
- dc_direct_connect_info - Gather information about Tencent Cloud direct connect connections
- eks_cluster_info - Gather information about Tencent Cloud EKS clusters
- eks_container_instance_info - Gather information about Tencent Cloud EKS container instances
- havip_info - Gather information about Tencent Cloud HAVIPs
- kms_key_rotation_info - Gather information about Tencent Cloud KMS key rotation status
- mariadb_account_info - Gather information about Tencent Cloud MariaDB accounts
- mongodb_account_info - Gather information about Tencent Cloud MongoDB accounts
- monitor_grafana_instance_info - Gather information about Tencent Cloud Grafana instances
- monitor_prometheus_instance_info - Gather information about Tencent Cloud Managed Service for Prometheus instances
- nat_gateway_dnat_rule_info - Gather information about Tencent Cloud NAT gateway DNAT rules
- nat_gateway_snat_rule_info - Gather information about Tencent Cloud NAT gateway SNAT rules
- network_acl_info - Gather information about Tencent Cloud network ACLs
- network_interface_info - Gather information about Tencent Cloud elastic network interfaces
- peering_connection_info - Gather information about Tencent Cloud VPC peering connections
- postgresql_account_info - Gather information about Tencent Cloud PostgreSQL accounts
- redis_account_info - Gather information about Tencent Cloud Redis accounts
- scf_alias_info - Gather information about Tencent Cloud SCF function aliases
- scf_trigger_info - Gather information about Tencent Cloud SCF function triggers
- scf_version_info - Gather information about Tencent Cloud SCF function versions
- security_group_rule_info - Gather information about Tencent Cloud security group rules
- sms_signature_info - Gather information about Tencent Cloud SMS signatures
- sms_template_info - Gather information about Tencent Cloud SMS templates
- sqlserver_account_info - Gather information about Tencent Cloud SQL Server accounts
- ssm_secret_info - Gather information about Tencent Cloud Secrets Manager secrets
- tag_info - Gather information about Tencent Cloud tags
- tke_cluster_autoscaler_info - Gather information about Tencent Cloud TKE cluster autoscaler options
- tke_cluster_kubeconfig - Fetch the kubeconfig of a Tencent Cloud TKE cluster
- tke_node_pool_info - Gather information about Tencent Cloud TKE node pools
- vod_class_info - Gather information about Tencent Cloud VOD classes
- vod_sub_app_info - Gather information about Tencent Cloud VOD subapplications
- vpc_address_template_group_info - Gather information about Tencent Cloud VPC address template groups
- vpc_address_template_info - Gather information about Tencent Cloud VPC address templates
- vpn_connection_info - Gather information about Tencent Cloud VPN connections

v1.0.0
======

Major Changes
-------------

- First stable release (1.0.0). The module and plugin API surface is now covered by semantic versioning: breaking changes will only land in future major releases.

Minor Changes
-------------

- Add ALB instance and listener lifecycle with deletion protection, address conversion, TLS settings, and target-group default actions.
- Add ALB target group lifecycle and exact-set backend target reconciliation.
- Add API Gateway API key and usage-plan key binding modules, COS bucket policy management, and TKE cluster endpoint management.
- Add API Gateway service release, usage plan, and usage plan environment binding modules to complete the publish and traffic-governance resource family.
- Add CAM SAML and OIDC identity provider lifecycle management.
- Add CBS automatic snapshot policy lifecycle with exact-set cloud-disk bindings.
- Add CBS cloud-disk backup point lifecycle with NORMAL-state convergence and safe replacement.
- Add CDB and Redis account lifecycle plus PostgreSQL backup-plan modules.
- Add CDB audit enablement, retention and closure configuration.
- Add CDB database lifecycle management with immutable character-set protection.
- Add CDN real-time CLS log topic lifecycle with exact-set domain and area bindings.
- Add CDW Doris and CDW PostgreSQL instance creation, rename, convergence waiting and destruction lifecycle.
- Add CFS manual snapshots and automatic snapshot policies with exact-set file-system bindings.
- Add CFS permission group and client permission rule lifecycle management.
- Add CHDFS file systems, mount points, access groups, exact access rules and mount bindings.
- Add CKafka Datahub source and sink task lifecycle, capacity tuning, pause and resume management.
- Add CKafka VPC, public and internal access-route lifecycle management.
- Add CKafka prefixed and preset ACL rule lifecycle management.
- Add CKafka user lifecycle and explicit password rotation.
- Add CLS collection configuration and machine-group binding modules to complete the LogListener collection path.
- Add CLS continuous COS shipper lifecycle management.
- Add COS bucket replication plus TKE cluster authentication and audit logging modules.
- Add COS intelligent-tiering, origin-rule and response-control configuration management.
- Add COS object-lock enablement and default governance or compliance retention management with irreversible-state protection.
- Add COS scheduled inventory, hotlink protection, and custom-domain resource modules.
- Add COS static website, default encryption, and access logging resource modules.
- Add CVM HPC cluster lifecycle and declarative per-instance scheduled termination timers.
- Add CVM launch-template lifecycle, immutable configuration versions and safe default-version promotion.
- Add CVM spread and partition placement groups plus per-instance placement bindings.
- Add Cloud Firewall NAT DNAT forwarding rule lifecycle with in-place private-target updates.
- Add Cloud Firewall NAT access-control rule lifecycle with ordering, scope and parameter-template support.
- Add Cloud Firewall inter-VPC ACL lifecycle with edge scope, IPv6 and application-protocol support.
- Add Cloud Firewall internet-border ACL rule lifecycle with templates, ordering and enable-state management.
- Add CloudBase environment and HTTP service route lifecycle management.
- Add Config account aggregator creation with explicit immutable membership semantics.
- Add Config change and resource-inventory delivery management for COS and CLS targets.
- Add Config compliance pack lifecycle with exact rule membership, input parameters and activation state.
- Add Config non-compliance alarm policy lifecycle with account scopes, risk levels and notification schedules.
- Add Config recorder lifecycle with exact monitored resource-type convergence.
- Add Config rule remediation lifecycle for manual and automatic corrective actions.
- Add CynosDB cluster lifecycle with storage, secondary-zone and kernel upgrades.
- Add DB Custom cluster lifecycle with exact node membership, tags and guarded multi-stage destruction.
- Add DNSPod custom line and exact-set line group lifecycle management.
- Add EMR cluster creation, rename, convergence waiting and termination lifecycle.
- Add EdgeOne CAPTCHA page and AI crawler detection lifecycle across all security policy scopes.
- Add EdgeOne acceleration-domain lifecycle with origin, protocol, port, IPv6 and online-state convergence.
- Add EdgeOne managed WAF lifecycle with group overrides, automatic updates and high-frequency scanning protection.
- Add EdgeOne origin-group lifecycle with exact origin-record and weight convergence.
- Add EdgeOne security IP-group lifecycle with complete large-set IP and CIDR convergence.
- Add EdgeOne web security template lifecycle while preserving independently managed policy rules.
- Add EdgeOne zone lifecycle with access-mode configuration and pause-state convergence.
- Add Elasticsearch cluster snapshot lifecycle with explicit safe replacement.
- Add Elasticsearch index lifecycle with service-added metadata tolerance.
- Add EventBridge event bus, rule, target, and connection lifecycle management with explicit immutable delivery and source configuration.
- Add GooseFS file system lifecycle with expansion-only capacity management and fileset quota lifecycle.
- Add Grafana notification channels plus Prometheus global notification and Alertmanager singleton configuration modules.
- Add Lighthouse data disk lifecycle with rename, attachment convergence and guarded replacement.
- Add Lighthouse instance snapshot lifecycle with rename and NORMAL-state convergence.
- Add MQTT instance, topic, secret-safe user, and authorization policy lifecycle management.
- Add Managed Grafana internet-access and complete IP-whitelist configuration modules.
- Add Managed Prometheus instance and cluster-agent modules plus Grafana instance, integration, and binding modules.
- Add Managed Prometheus scrape-job, recording-rule, and alert-group lifecycle modules.
- Add MariaDB account creation, description update, password rotation and deletion.
- Add MariaDB automatic backup retention, window, weekday and archive configuration.
- Add MongoDB account creation, role reconciliation, password rotation and deletion.
- Add MongoDB automatic backup schedule, method, retention and alert configuration.
- Add Oceanus job lifecycle with start, stop, pause and resume controls.
- Add Oceanus workspace lifecycle as the ownership boundary for jobs and resources.
- Add PostgreSQL instance creation, resize, rename, renewal, isolation and guarded permanent destruction.
- Add RabbitMQ Serverless exchange, queue and binding lifecycle management.
- Add RabbitMQ Serverless virtual-host, user and permission lifecycle management.
- Add SQL Server account, database privilege, remark and password lifecycle management.
- Add SQL Server instance lifecycle with specification and high-availability controls.
- Add SSM explicit secret-version lifecycle and automatic rotation configuration.
- Add TCHouse-C instance lifecycle with observable node, specification and disk convergence.
- Add TDMQ Pulsar namespace retention and subscription-policy lifecycle management.
- Add TDMQ Pulsar namespace role permission lifecycle management.
- Add TDMQ RabbitMQ dedicated-instance lifecycle with topology and deletion-protection controls.
- Add TDMQ RabbitMQ queue and exchange binding lifecycle management.
- Add TDMQ RabbitMQ user lifecycle, limits, CAM authentication and password rotation.
- Add TDMQ RabbitMQ virtual host configure, write and read permission lifecycle.
- Add TDMQ RabbitMQ virtual host lifecycle and tracing configuration.
- Add TDMysql instance lifecycle with expansion, specification upgrades, recovery and security-group reconciliation.
- Add TDSQL-C PostgreSQL cluster lifecycle with instance topology and specification reconciliation.
- Add TEM application, environment, access service and declarative deployment resources.
- Add THPC cluster lifecycle with complete node topology and explicit deletion-protection control.
- Add TKE backup storage location lifecycle with explicit safe replacement.
- Add TSE service-registry engine lifecycle with Apollo topology and client internet access.
- Add TcaplusDB cluster lifecycle with storage and proxy topology plus password rotation.
- Add Tencent Cloud Mesh instance lifecycle and exact cluster-link reconciliation.
- Add VPC HAVIP lifecycle and exact CVM or ENI drift-scope associations.
- Add VectorDB instance lifecycle with vertical scaling, replica expansion and security groups.
- Add WAF CC rate-protection rule lifecycle with canonical advanced-condition comparison.
- Add WAF OWASP allowlists, automatic attack-source denial and threat-intelligence blocking management.
- Add WAF anti-tamper URL lifecycle, precision allowlist rules and geographic blocking management.
- Add WAF attack-signature allow-rule lifecycle with exact-set signature and condition reconciliation.
- Add WAF protected-host and custom-rule lifecycle modules.
- Add WAF sensitive-information leakage rule lifecycle with immutable URI protection.
- Add ``cos_object_info`` to list and filter objects in a COS bucket, with prefix, marker and max_keys pagination.
- Add ``cos_object_sync`` to mirror a local directory tree into a COS bucket prefix, uploading new or changed files via MD5/ETag comparison and optionally deleting extraneous remote objects.
- Add ``cos_object`` for idempotent COS object upload, download and deletion, with ETag-based change detection, metadata and storage-class drift reconciliation, check mode and diff output.
- Add ``cvm_image_share`` to manage CVM image sharing permissions. With ``state=present`` it shares an image to the given account IDs via ``ModifyImageSharePermission`` (Permission=SHARE); with ``state=absent`` it revokes sharing (Permission=CANCEL). Reads current shares with ``DescribeImageSharePermission``, deduplicates and sorts account IDs, supports check mode and diff.
- Add ``cvm_instance_security_group`` to reconcile the set of security groups bound to a CVM instance. With ``state=present`` it binds missing groups and unbinds extra ones to converge on exactly the desired set; with ``state=absent`` it unbinds the given groups. Uses ``AssociateSecurityGroups``/``DisassociateSecurityGroups`` (one call per group), enforces the five-group platform limit, supports check mode and diff.
- Add ``sms_signature`` to manage Tencent Cloud SMS signatures (签名) via ``AddSmsSign``/``DeleteSmsSign``/``DescribeSmsSignList``. Signature applications are review-based: content fields are sent only at creation, and a signature whose review failed (status code -1) is treated as absent so re-running the task resubmits. Supports check mode and diff.
- Add ``sms_template`` to manage Tencent Cloud SMS templates (短信模板) via ``AddSmsTemplate``/``DeleteSmsTemplate``/``DescribeSmsTemplateList``. Template applications are review-based: content fields are sent only at creation, and a template whose review failed (status code -1) is treated as absent so re-running the task resubmits. Supports check mode and diff.
- Add ``tke_cluster_autoscaler`` to reconcile the cluster-level autoscaler options of a TKE cluster via ``DescribeClusterAsGroupOption``/``ModifyClusterAsGroupOptionAttribute``. Only explicitly provided options are compared and written (scale-down toggles, expander algorithm, idle thresholds, unready-node guardrails); supports check mode and diff.
- Add ``tke_cluster_upgrade`` to upgrade the Kubernetes version of an existing TKE cluster via ``UpdateClusterVersion``. Idempotent against the running version reported by ``DescribeClusters``; supports check mode and diff, and accepts ``max_not_ready_percent`` and ``skip_pre_check``.
- Add account-level CloudAudit COS delivery, CMQ notification, KMS encryption and logging-state management.
- Add complete GWLB lifecycle coverage for load balancers, target groups, associations, and exact-set backend instances.
- Add complete SSM custom-secret lifecycle with initial material, enablement, recovery and scheduled deletion.
- Add cross-account aggregate Config delivery management for COS and CLS targets.
- Add declarative CDB account privileges and organization member identity reconciliation.
- Add declarative scoped MariaDB account privilege reconciliation.
- Add exact EdgeOne L7 custom security rule reconciliation across zone, template and host scopes.
- Add exact EdgeOne precise rate-limiting rules with composite counters, block/throttle modes and enforcement actions.
- Add exact EdgeOne web security exception rules for modules, managed rules, rule groups and request fields.
- Add exact EdgeOne web security template domain-binding reconciliation with explicit unbind policy.
- Add exact-set CBS snapshot sharing permission management.
- Add exact-set CynosDB global, database and table account privilege management.
- Add exact-set Lighthouse instance firewall rule management with version-aware writes.
- Add exact-set TDMQ RocketMQ namespace role permission management.
- Add exact-set WAF protection object group lifecycle management.
- Add idempotent COS custom-domain certificate binding by Tencent Cloud SSL certificate ID.
- Add idempotent CynosDB backup window and retention management.
- Add idempotent SQL Server regular backup strategy management.
- Add idempotent TDMQ RocketMQ namespace lifecycle management.
- Add idempotent TDMQ RocketMQ topic and consumer group lifecycle management.
- Add idempotent TencentDB for MySQL and Redis automatic backup configuration modules.
- Add imported Lighthouse SSH key pair lifecycle with exact-set instance associations.
- Add multi-engine CKafka Datahub connection lifecycle management with recursive credential scrubbing.
- Add organization member access policy lifecycle management.
- Add organization member creation, update, node movement and deletion lifecycle.
- Add physical Direct Connect and secret-safe Direct Connect tunnel lifecycle management.
- Add prepaid and postpaid CKafka instance lifecycle with runtime controls and prepaid capacity changes.
- Add prepaid and postpaid DCDB instance lifecycle with shard expansion and specification upgrades.
- Add prepaid and postpaid MariaDB instance lifecycle with deployment and specification changes.
- Add reusable VPC address templates and exact address-template group membership.
- Add scheduled TAT invoker lifecycle with secret-safe parameter comparison and enablement control.
- Add secret-safe CKafka Datahub elastic topic lifecycle management.
- Add secret-safe TDMQ RocketMQ role lifecycle management.
- Add standard TDMQ RocketMQ cluster lifecycle management with secret-safe output.
- Reconcile mutable CDN origin, service, project and acceleration-area configuration on existing domains.
- Reformat the generated module and contract-test sources so every file satisfies the ``pep8`` sanity test, clearing 5660 ``E701``/``E702``/``E703`` and 1367 ``E501`` violations that had been failing CI on every push.
- cos_bucket - new event_source plugin for Event-Driven Ansible that polls a COS bucket's object listing and yields each new or changed object as an event, the polling equivalent of a bucket event notification (prefix filter, optional max_objects cap, baseline first poll).
- eks_cluster - new module to manage Tencent Cloud EKS clusters (create/update/delete, idempotent by name).
- eks_container_instance - new module to manage Tencent Cloud EKS container instances (create/update/delete, idempotent by name).
- generate_info_modules.py - extend the generator to scaffold resource (write) modules from a curated RESOURCE_SPECS table. ``--resource <module>`` introspects the SDK request models named in the spec and renders the module boilerplate (argument spec, request builders, identify/find helpers, check-mode run_module with a drift TODO) into plugins/modules/<module>.py. Scaffolding is write-once - existing module files are never overwritten - so scaffolded modules can be finished by hand and stay stable across generator runs. ``--resources --check`` verifies every RESOURCE_SPECS entry against the installed SDK and reports missing scaffolds (wired into CI). scf_alias is the reference entry; new write modules add their own spec and scaffold from it.
- tc_disaster_recovery - new role that prepares cross-region disaster recovery artifacts: a golden CVM image of a source instance in the primary region, COS bucket replication to the DR region, and an optional standby CLB pre-wired in the DR region as the failover entry point.
- tc_tke_cluster - new role that provisions a managed TKE cluster with node pools and addons in one call, reconciling the tc_tke_cluster_node_pools and tc_tke_cluster_addons lists idempotently and tearing down in reverse order (addons -> node pools -> cluster).
- tc_web_stack - new role that provisions a complete Tencent Cloud web stack in one call: a CVM instance pool, a MySQL CDB instance and a Redis cache fronted by a CLB with an HTTP listener, automatically registering the created CVM instances as CLB backends (explicit target list or per-component enable flags supported, teardown in reverse order).
- tencentcloud_cos - new dynamic inventory plugin listing COS buckets (and optionally their objects) as hosts, keyed by bucket name, with region/prefix filters and constructed/cache support.
- tencentcloud_tke - new dynamic inventory plugin exposing TKE cluster nodes as hosts (worker pool by default), walking clusters and node pools per region with cluster/node-pool host variables.
- tke_cluster - new event_source plugin for Event-Driven Ansible that polls TKE cluster status via DescribeClusterStatus and yields cluster state-change events (with previous state and node counts) plus cluster-deleted events.
- vod_class - new module to manage Tencent Cloud VOD media categories (create/delete, idempotent by name and parent).
- vod_sub_app - new module to manage Tencent Cloud VOD sub-applications (create/update/delete, idempotent by name; delete uses the Destroyed status since no delete API exists).

Breaking Changes / Porting Guide
--------------------------------

- susunola.tencentcloud now requires ansible-core 2.19 or newer (meta/runtime.yml requires_ansible >= 2.19.0). ansible-core 2.16, 2.17 and 2.18 reached end-of-life (2025-07, 2025-11 and 2026-05) and are no longer tested. Controllers must run Python 3.11 or newer. Upgrade ansible-core before upgrading the collection.

Bugfixes
--------

- cvm_disaster_recover_group - drop the ``strategy`` and ``partition_count`` options; the CVM placement-group API declares neither on ``CreateDisasterRecoverGroupRequest`` nor on the ``DisasterRecoverGroup`` response, so both values were silently discarded and could never converge.
- cvm_disaster_recover_group_binding - send the singular ``DisasterRecoverGroupId`` string expected by ``ModifyInstancesDisasterRecoverGroupRequest`` instead of a ``DisasterRecoverGroupIds`` list, and drop the ``partition_number`` option that the API does not declare; binding requests previously carried no group at all.
- postgresql_instance - declare ``waiter_delay`` and ``waiter_timeout`` in the argument spec so the documented 10 second and 900 second defaults are the ones actually applied, and quote the ``storage`` and ``auto_renew`` descriptions so their embedded commas no longer break the option documentation.
- waf_custom_white_rule - mark ``bypass_modules`` as ``no_log=False``; it carries WAF module names, not a secret.

v0.13.0
=======

Minor Changes
-------------

- Add API Gateway API lifecycle management with route, method, authentication and backend controls.
- Add Auto Scaling scheduled capacity action lifecycle management.
- Add Auto Scaling simple and target-tracking policy lifecycle management.
- Add CAM group lifecycle management.
- Add CDB and Redis parameter-template lifecycle and exact parameter reconciliation.
- Add CLS full-text index and LogListener machine-group management.
- Add CMQ topic and push-subscription lifecycle management, including retention, tracing, filtering and retry policy controls.
- Add DNSPod domain lifecycle, status, group, remark and creation-tag controls.
- Add DTS migration job purchase, rename, resize and destroy operations.
- Add KMS key creation tags, task-level deletion protection and explicit immutable drift detection for alias, key usage and key origin type.
- Add PostgreSQL parameter-template lifecycle and exact parameter reconciliation.
- Add SCF trigger lifecycle, status control and explicit safe replacement.
- Add TCR Enterprise replication rule lifecycle management with filters and overwrite/deletion controls.
- Add TDMQ Pulsar subscription lifecycle management.
- Add ``as_scaling_group`` for idempotent Auto Scaling group lifecycle and capacity management.
- Add ``cam_group_membership`` for paginated, idempotent CAM sub-user membership management by UIN or UID.
- Add ``cam_policy_attachment`` for idempotent CAM policy attachment and detachment across users, roles and groups.
- Add ``cfw_address_template`` for idempotent Cloud Firewall address and domain template management.
- Add ``cloudaudit_track`` for idempotent CloudAudit event delivery management.
- Add ``cmq_queue`` for idempotent CMQ queue lifecycle and delivery settings.
- Add ``config_rule`` for idempotent Tencent Cloud Config compliance rule management.
- Add ``dbbrain_sql_filter`` for DBbrain SQL concurrency filter lifecycle management.
- Add ``dts_consumer_group`` for idempotent DTS data subscription consumer management.
- Add ``kms_key_rotation`` for independently authorized automatic key rotation management with last and next rotation metadata.
- Add ``kms_key`` for customer-managed key creation, description and enabled state reconciliation, and scheduled deletion with a bounded waiting window.
- Add ``monitor_alarm_policy_notice`` for independently reconciling alarm notification rules, hierarchical notices and content-template bindings.
- Add ``monitor_alarm_policy`` for alarm-policy creation, metadata and status reconciliation, and deletion.
- Add ``organization_node`` for idempotent Tencent Cloud Organization unit management.
- Add ``private_dns_record`` for idempotent private DNS record create, update and delete operations.
- Add ``private_dns_zone`` for private-zone lifecycle, VPC associations and creation tags.
- Add ``tat_command`` for idempotent reusable TAT command lifecycle management.
- Add ``tcr_replication_instance`` for TCR cross-region replication instance lifecycle management.
- Add ``tcr_repository`` with idempotent repository create, description reconciliation, force-aware deletion, check mode and diff output.
- Add ``tdmq_topic`` for idempotent TDMQ Pulsar topic lifecycle management.
- Add ``teo_dns_record`` for idempotent EdgeOne DNS record lifecycle management.
- Add ``tke_addon`` for TKE addon installation, version and values updates, and deletion.
- Add a generated per-module Tencent Cloud API action manifest as the basis for least-privilege CAM policies.
- Add api_gateway_service for idempotent API Gateway service lifecycle.
- Add ccn for Cloud Connect Network lifecycle and mutable routing feature flags, with check mode, diff and convergence polling.
- Add ccn_attachment for idempotent VPC, VPN gateway, direct-connect gateway and BM VPC association with CCN.
- Add clb_target_group with idempotent target-group lifecycle and exact-set reconciliation of backend IP, port and weight.
- Add cls_logset for idempotent CLS logset lifecycle, naming and exact tags.
- Add cls_topic for idempotent topic lifecycle, retention, partitions, storage and tags.
- Add cynosdb_account for account lifecycle, descriptions and explicit password rotation.
- Add exact CKafka ACL grant management.
- Add network_acl for ACL lifecycle, exact ingress/egress rules and exact subnet association reconciliation.
- Add postgresql_account for account lifecycle, remarks and explicit password rotation.
- Add privatelink_endpoint for consumer endpoint lifecycle and security groups.
- Add privatelink_endpoint_service for publishing CLB-backed private services.
- Add risk-aware E2E coverage mapping, resource manifests, TTL reaper planning, reliability policy, registry validation, secret-safe telemetry, and six P0 integration targets.
- Add the customer_gateway module for idempotent VPN remote-peer lifecycle, including BGP ASN updates, creation tags, check mode, diff and waiters.
- Add vpc_flow_log for flow-log lifecycle, CLS topic delivery, mutable metadata and enable/disable state management.
- Add vpn_connection for idempotent IPsec tunnel lifecycle, exact SPD route reconciliation, DPD settings and explicit pre-shared-key rotation.
- Add waf_ip_access_control for idempotent IP allowlist and blocklist rules.
- CI - integration runs collect coverage with ``ansible-test --coverage`` and upload the report as an artifact (reported, not gated, because real-cloud coverage fluctuates with account state).
- CI - the SDK contract tests step now also collects the module unit tests and uploads XML and HTML coverage reports as an artifact, so the numbers behind the 70% gate are inspectable even on failed runs.
- Curate hidden required request parameters for eight more ``*_info`` modules so generated modules expose every field the API requires (``trtc_call_info`` CommId/SdkAppId/StartTime/EndTime, ``ess_file_url_info`` (Operator/BusinessType), ``tiw_running_task_info`` (SdkAppID/TaskType), ``weilingwith_element_profile_page_info`` (WorkspaceId/ApplicationToken/BuildingId), ``bsca_kb_component_info`` (Query), ``svp_saving_plan_coverage_info`` (StartDate/EndDate), ``gme_voice_print_info`` (DescribeMode) and ``ses_black_email_address_info`` (StartDate/EndDate). Curated params are validated against the official Tencent Cloud API documentation.
- Curated ``extra_params`` may carry ``no_log`` (used for ``weilingwith_element_profile_page_info.application_token``) so token-like parameters are masked in module output and pass ``validate-modules``.
- Deepen ``ckafka_topic`` with replica safety, throughput quota and message timestamp controls backed by topic-attribute state reads.
- Extend ``kms_key`` with exact alias-based discovery, cancellation of scheduled deletion when restoring a key, and optional automatic rotation management with a configurable 7-365 day period.
- Extend ``monitor_alarm_policy`` reconciliation to update metric and event conditions plus notification rule bindings, and paginate policy discovery.
- Extend ``monitor_alarm_policy`` with project assignment, dimension filters, group-by dimensions, trigger tasks, hierarchical notices, notification content-template bindings and creation-time alarm-policy tags.
- Harden ``tke_addon`` with bounded install, upgrade and deletion waiters, terminal failure detection, merge/replace update strategies and sensitive values handling.
- Let ``tke_addon`` manage version and values independently, accept JSON or YAML values from inline data or controller-side files, optionally perform API DryRun validation, and block numeric version downgrades by default.
- Register all five modules in SDK request-model contract tests and add unit coverage for request construction and canonical values comparison.
- The ``wait_for_task`` waiter now accepts ``success_statuses`` and ``failure_statuses`` so services whose task-status APIs use a different convention than the CLB 0/1/2 integers (for example the CDB SUCCESS/FAILED/KILLED/REMOVED/PAUSED strings) can reuse it; the default keeps the CLB behaviour unchanged.
- The generator now supports ``page_number_base`` for APIs that number pages from zero (trtc, ccc, bsca), emitting ``offset // limit`` instead of the 1-based ``offset // limit + 1`` so pagination no longer skips the first page; ``REQUIRED_PARAM_OVERRIDES`` entries may carry ``page_number_base`` and it is propagated into the spec.
- cbs_snapshot - new standalone write module for CBS cloud disk snapshots. A snapshot is identified either by ``snapshot_id`` or by the combination of ``disk_id`` and ``snapshot_name``; name lookups return the newest snapshot for that name. ``state=present`` creates the snapshot when it does not exist and, by default, waits until the snapshot becomes available (``SnapshotState=NORMAL``); ``state=absent`` deletes the snapshot. Supports check mode and diff output.
- cdb_instance - add ``state=restarted`` to restart a running CDB instance with ``RestartDBInstances`` and wait for the asynchronous restart task via ``DescribeAsyncRequestInfo`` until it reports SUCCESS (or fails), bounded by ``waiter_timeout``.
- cdb_instance - after creation the module now waits for the instance to be delivered (Status 1 with TaskStatus 0) and after isolation waits for Status 5, both bounded by ``waiter_timeout``; the default ``waiter_timeout`` is raised from 120 to 900 seconds because database creation takes several minutes.
- cdb_instance - state=present now changes the instance specification when ``memory`` or ``volume`` drift from the running instance. The change is applied with UpgradeDBInstance (upgrade and downgrade are both supported; disk capacity can only be expanded) and the module waits for the asynchronous spec-change task to report SUCCESS, bounded by ``waiter_timeout``. When only one dimension is given the current value of the other dimension is used.
- cdn_domain - new module to add, start, stop and delete CDN acceleration domains with the ``cdn.v20180606`` API.
- community governance - add ``CODEOWNERS`` (single maintainer) and ``.github/dependabot.yml`` (weekly pip + github-actions updates); the contributing guide now documents the SDK pin/regeneration workflow that the drift sentinel enforces.
- cvm_chc - add ``network_mode`` option (DEPLOY/BUSINESS) to switch the CHC server business NIC network mode via ModifyChcNetworkMode, applied idempotently when it drifts from the DescribeChcHosts state.
- cvm_chc - new module to manage the VPC network configuration of CHC physical servers, attaching or updating the out-of-band (BMC) and deployment VPCs with ``ConfigureChcAssistVpc``, renaming the server with ``ModifyChcAttribute``, and removing the network configuration with ``RemoveChcAssistVpc``/``RemoveChcDeployVpc``. CHC servers are delivered offline and cannot be created through an API, so a missing server fails instead of being created.
- cvm_instance - a different ``instance_type`` on an existing stopped instance is now applied with ``ResetInstancesType`` (instance resizing) instead of failing; resizing keeps the instance stopped.
- cvm_instance - add ``reset_password`` to reset the login password of an existing instance with ``ResetInstancesPassword``; requires ``password`` and only applies with ``state=present``.
- cvm_instance - add ``state=rebooted`` to reboot a running instance with ``RebootInstances`` (one-shot action, always reports changed).
- cvm_instance - add ``zones`` (and optional parallel ``subnet_ids``) for ``exact_count`` pool creation; the shortfall is spread across the listed availability zones as evenly as possible with one ``RunInstances`` call per zone (``Placement.Zone`` plus the matching subnet), so a pool can be kept available across AZs instead of landing in a single one.
- cvm_instance - updates on a stopped instance no longer wait for the ``RUNNING`` state; the power state is never changed by an update.
- elasticsearch_instance - new module to create, rename and destroy Elasticsearch clusters with the ``es.v20180416`` API. Creation uses ``CreateInstance`` with a ``NodeInfoList`` (Type=hotData) and waits for the cluster to reach Status 1; ``state=absent`` destroys the cluster with ``DeleteInstance`` and waits for it to disappear, bounded by ``waiter_timeout``.
- gaap_proxy - new module to create, rename, open, close and destroy GAAP proxies with the ``gaap.v20180529`` API.
- mongodb_instance - new module to create, rename and isolate MongoDB instances with the ``mongodb.v20190725`` API. Prepaid instances are created with ``CreateDBInstance``, postpaid with ``CreateDBInstanceHour``.
- nat_gateway_rule - new module that reconciles the DNAT and SNAT rule sets of a NAT gateway. The desired rules are compared against the rules currently configured on the gateway, the missing delta is created and, when ``purge=true`` (the default), the surplus is deleted. A DNAT rule is identified by protocol, public IP, public port, private IP and private port; a SNAT rule by resource type, resource ID and private IP, so changing the public IPs or the description of an existing rule replaces it (delete and re-create). Supports check mode and diff output.
- network_interface - new module to create, update and delete VPC elastic network interfaces with the ``vpc.v20170312`` API. An interface is identified by ``network_interface_id`` or by ``name`` + ``subnet_id``; the name, description and bound security groups are reconciled on an existing interface with ``ModifyNetworkInterfaceAttribute``.
- redis_instance - after creation the module now waits for the instance to reach Status 2 (running) and after destruction waits for Status -3 (pending recycle, or the instance disappearing from the describe API), both bounded by ``waiter_timeout``; the default ``waiter_timeout`` is raised from 120 to 900 seconds because database creation takes several minutes.
- requirements.txt - pin the write-module SDK subpackages (cvm/mongodb/gaap/cdn/tcr) so their contract tests run in CI instead of silently skipping; cvm is pinned to 3.1.158 for the ChcHost.NetworkMode field the ``cvm_chc`` drift check reads.
- scf_alias - new module to manage SCF function aliases with the ``scf.v20180416`` API. An alias is identified by ``function_name`` + ``name``; the target ``function_version`` and ``description`` are enforced on an existing alias with ``UpdateAlias``.
- scf_version - new module to publish and delete SCF function versions with the ``scf.v20180416`` API. Versions are published with ``PublishVersion``, listed with ``ListVersionByFunction`` and removed with ``DeleteFunctionVersion``; ``$LATEST`` and ``default`` are rejected as identities.
- scripts/check_hidden_required_params.py now runs as a CI gate (``--check``) alongside the SDK drift sentinel, failing the build when a generated ``*_info`` spec hides a required request field of its SDK model. Unit coverage for the docstring heuristics, pagination coverage logic and the gate's exit behaviour was added under ``tests/unit/scripts/``.
- tcr_instance - new module to create, update and delete TCR enterprise instances with the ``tcr.v20190924`` API; deletion protection is enforced idempotently on existing instances with ``ModifyInstance``.
- tcr_namespace - new module to create, update and delete TCR namespace resources with the ``tcr.v20190924`` API. A namespace is identified by ``registry_id`` + ``name``; public access, auto-scan and vulnerability prevention settings are enforced with ``ModifyNamespace``.
- tke_node_pool - new module to create, update and delete TKE node pools with the ``tke.v20220501`` API. A pool is identified by ``cluster_id`` + ``name``; the autoscaling range, labels, taints and deletion protection are reconciled on an existing pool with ``ModifyClusterNodePool``; ``keep_instance`` controls whether instances survive deletion.

Bugfixes
--------

- Complete inherited retry/waiter documentation and GPL headers for the recent product-depth modules so strict Ansible validation succeeds.
- Fix ``cmq_queue`` to use the supported TDMQ CMQ write APIs and wait for queue convergence.
- Read addons from the ``DescribeAddon`` response list and encode addon values as the Base64 JSON representation required by the TKE API.
- Use the shared Tencent Cloud not-found classifier in SCF, SSM, TKE and Private DNS resource discovery paths for consistent absent idempotency.
- Wait for CAM group membership and KMS key rotation changes to become observable before returning success.
- Wait for Cloud Monitor alarm policy create, update and delete operations to converge, using subset comparison for API-expanded condition objects.
- Wait for DBbrain SQL filters and TCR replication instances to reach their terminal desired state.
- Wait for KMS key creation, enable/disable, deletion cancellation and scheduled deletion operations to reach their observable terminal states.
- Wait for Private DNS zone and record create, update and delete operations to converge, and consistently recognize API not-found responses.

New Modules
-----------

- cam_group_membership - Manage Tencent Cloud CAM user group membership
- cam_policy_attachment - Manage a Tencent Cloud CAM policy attachment
- cdn_domain - Manage Tencent Cloud CDN domains
- cvm_chc - Manage Tencent Cloud CHC physical server network configuration
- elasticsearch_instance - Manage Tencent Cloud Elasticsearch clusters
- gaap_proxy - Manage Tencent Cloud GAAP proxies
- kms_key - Manage a Tencent Cloud KMS key
- kms_key_rotation - Manage automatic rotation for a Tencent Cloud KMS key
- mongodb_instance - Manage Tencent Cloud MongoDB instances
- monitor_alarm_policy - Manage a Tencent Cloud Monitor alarm policy
- monitor_alarm_policy_notice - Manage notification bindings for a Cloud Monitor alarm policy
- network_interface - Manage Tencent Cloud elastic network interfaces
- private_dns_record - Manage a Tencent Cloud Private DNS record
- private_dns_zone - Manage a Tencent Cloud Private DNS zone
- scf_alias - Manage Tencent Cloud SCF function aliases
- scf_version - Manage Tencent Cloud SCF function versions
- tcr_instance - Manage Tencent Cloud TCR enterprise instances
- tcr_namespace - Manage Tencent Cloud TCR namespaces
- tcr_repository - Manage a Tencent Cloud TCR repository
- tke_addon - Manage a Tencent Kubernetes Engine addon
- tke_node_pool - Manage Tencent Cloud TKE cluster node pools

v0.12.0
=======

Minor Changes
-------------

- callback - add the ``tencentcloud_resource_actions`` aggregate callback that summarises every Tencent Cloud API call made during a play (operation, request id, duration, success/failure) and prints a machine-readable JSON trail; every module now records its SDK calls through ``sdk_call`` and attaches them to the result as ``tc_api_calls``.
- cbs_disk - add the ``cbs_disk`` module to manage Tencent Cloud CBS cloud disks (create, rename, grow, attach, detach, terminate) through the ``cbs.v20170312`` API with idempotency, check mode and attachment state waiting.
- cdb_instance - add the ``cdb_instance`` module to create, rename and isolate MySQL instances through the ``cdb.v20170320`` API with idempotency and check mode, including project, VPC, security group and tag placement.
- cfs_file_system - add the ``cfs_file_system`` module to manage Tencent Cloud CFS file systems (create, update name/size limit, delete) through the ``cfs.v20190719`` API with idempotency and check mode.
- ci - extend the sanity matrix to ansible-core 2.19/2.20/2.21 (Python 3.12/3.13) and add a whole-repo ``ruff check`` step so lint violations fail CI instead of only local runs.
- ckafka_topic - add the ``ckafka_topic`` module to manage CKafka topics (create, scale partitions/replicas, update retention and note, delete) through the ``ckafka.v20190819`` API with idempotency and check mode.
- clb_rule - add the ``clb_rule`` module to manage Tencent Cloud CLB L7 forwarding rules (create, update scheduler/session persistence/forward type/health check, delete) through the ``clb.v20180317`` API with idempotency and check mode; the returned ``location_id`` plugs into ``clb_listener_target`` for rule-level target management.
- cls_topic event_source - add the ``cls_topic`` event source for Event-Driven Ansible that polls a CLS log topic and yields each new matching log record as an event (rolling ``from``/``to`` window, context-aware pagination, error events keep the source alive).
- cmq_queue event_source - add the ``cmq_queue`` event source for Event-Driven Ansible that long-polls a CMQ queue and yields each received message as an event, with optional delete-after-yield acknowledgement and idle interval.
- cos_bucket - manage the bucket CORS configuration with the new ``cors`` parameter (replacing rules, empty list removes all) and the lifecycle configuration with the new ``lifecycle`` parameter (prefix-matched rules with day-based expiration, storage-class transitions, noncurrent-version transitions and incomplete-multipart-upload aborts).
- cos_bucket_info - the bucket description now includes the CORS and lifecycle configurations alongside ACL, versioning and tags.
- cvm_image - add the ``cvm_image`` module to manage Tencent Cloud CVM custom images (create, rename, describe, delete) through the ``cvm.v20170312`` API with idempotency and check mode.
- dnspod_record - add the ``dnspod_record`` module to manage Tencent Cloud DNSPod DNS records (create, update value/TTL/weight/MX/remark/status, delete) through the ``dnspod.v20210323`` API with idempotency and check mode.
- eip - support updating ``internet_max_bandwidth_out`` on existing addresses via ``ModifyAddressesBandwidth`` and switching ``internet_charge_type`` between ``BANDWIDTH_PREPAID_BY_MONTH`` and ``TRAFFIC_POSTPAID_BY_HOUR`` via ``ModifyAddressInternetChargeType``; both were previously allocation-only no-ops.
- generate_info_modules - add ``validate_specs`` to the generator — every curated and auto SPECS entry is structurally audited (missing keys, bad pagination types, duplicate module/param names, malformed ids/filters, deep dotted response paths, region collisions) and generation/``--check`` fails on any problem.
- generator - discover and generate zero-argument single-object info modules (pagination_type "none") for products that expose no usable list API; adds ba_auth_info, iap_login_session_duration_info, lkeap_character_usage_info and tdid_over_summary_info.
- generator - scripts/info_specs_auto.py now carries a ``GENERATED_SDK_VERSION`` stamp recording the tencentcloud SDK release the auto specs were discovered against, and a new scripts/check_sdk_drift.py compares CI's installed SDK to that stamp so stale specs are regenerated deliberately instead of shipping silently (wired into the CI sanity job).
- generator - the auto-discovered spec names drop the redundant product-prefix repetition (dcdb_dcdb_instance_info -> dcdb_instance_info) and the mangle of all-caps abbreviations (antiddos_d_do_s_block_record_info -> antiddos_ddos_block_record_info).
- info modules - every generated ``*_info`` module now returns ``request_id`` (the request ID of the last API call) alongside the resource list and ``total_count``, so playbooks can cross-reference cloud audit logs.
- info modules - every generated ``*_info`` module now routes SDK call failures through ``fail_json`` with the error code and request id (pinned by new error-path unit tests for module_utils sdk_call and for every generated module), so a failed API call never surfaces as a traceback.
- integration - add ``cfs_file_system`` and ``clb_http`` integration targets (create/idempotency/check-mode/delete over a throwaway VPC, effectively free — CFS SD storage billed per GiB-hour, internal CLB without bandwidth), extend the ``cleanup`` sweeper to collect and delete leftover CLB load balancers and CFS file systems in reverse dependency order, and include the new targets in the integration workflow default set.
- lighthouse_instance - add the ``lighthouse_instance`` module to manage Tencent Cloud Lighthouse instances (create, start, stop, isolate) through the ``lighthouse.v20200324`` API with idempotency and check mode.
- module tiers - add ``scripts/check_module_tiers.py`` and a CI gate that classify every module as generated (``# Generated by scripts/generate_info_modules.py`` marker) or core (hand-written, listed in ``CORE_MODULES``); an unclassified module fails CI, preventing hand-written modules from being silently overwritten by the generator; see ``docs/module_tiers.md``.
- modules - construct SDK tag models by attribute assignment instead of keyword arguments so every write module works against the real Tencent Cloud SDK classes.
- nat_gateway - add the ``nat_gateway`` module to manage Tencent Cloud NAT gateways (create with EIP allocation, update name/bandwidth/deletion protection, delete with risk override) through the ``vpc.v20170312`` API with idempotency and check mode.
- peering_connection - add the ``peering_connection`` module to manage Tencent Cloud VPC peering connections (create, update name/bandwidth/charge type, accept pending connections, delete) through the ``vpc.v20170312`` API with idempotency and check mode.
- redis_instance - add the ``redis_instance`` module to create, rename and destroy Redis instances (postpaid and prepaid destroy flows) through the ``redis.v20180412`` API with idempotency and check mode.
- scf_function - add the ``scf_function`` module to manage Tencent Cloud SCF functions (create from local zip or COS package, update code/config, delete) through the ``scf.v20180416`` API with idempotency and check mode.
- ssl_certificate - add the ``ssl_certificate`` module to upload, rename, deploy (via ``DeployCertificateInstance``) and delete SSL certificates through the ``ssl.v20191205`` API with idempotency and check mode, closing the loop with the ``cert_id`` of ``clb_listener``/``clb_rule``.
- ssm_parameter - add the ``ssm_parameter`` module to manage Tencent Cloud SSM secrets (create with plain-text or binary values, update value, soft or immediate delete) through the ``ssm.v20190923`` API with idempotency and check mode; secret values are no_log.
- tag - add the generic ``tag`` module to attach, update and detach a tag key on arbitrary QCS resources (any service type and resource prefix) through the ``tag.v20180813`` API with idempotency and check mode, reusing the collection tagging helpers.
- tat connection - add the ``tat`` connection plugin that runs commands and transfers files on Tencent Cloud CVM/Lighthouse instances through the TAT agent (``CreateCommand`` + ``InvokeCommand`` with ``DescribeInvocationTasks`` polling); no public IP or SSH port is required, only the TAT agent and ``tencentcloud-sdk-python-tat`` on the controller.
- tc_clb_http role - add the ``tc_clb_http`` role that provisions a CLB load balancer with an HTTP listener and backend target set in a single call, wrapping ``clb_load_balancer``, ``clb_listener`` and ``clb_listener_target``.
- tc_launch role - add the ``tc_launch`` role that wraps ``cvm_instance`` with sensible defaults for launching CVM instances, including ``exact_count``/``count_tag`` pool management and waiter tuning.
- tencentcloud_clb inventory - add the ``tencentcloud_clb`` inventory plugin that lists CLB load balancers per region with their listeners (protocol/port) and backend targets, supporting custom backend hostname templates and caching.
- tencentcloud_sg inventory - add the ``tencentcloud_sg`` inventory plugin that lists security groups with their associated network interfaces (deduplicated hosts accumulate ``sg_ids``/``sg_names``/``eni_ids``), supporting caching.
- tests - add integration targets for cam_user, cos_bucket and key_pair (cheap, run by default in CI), plus opt-in targets for cvm_image (behind TENCENTCLOUD_CVM_IMAGE_SOURCE_INSTANCE) and lighthouse (behind TENCENTCLOUD_LH_BUNDLE_ID / TENCENTCLOUD_LH_BLUEPRINT_ID) that are skipped when the operator has not supplied billable resource inputs.
- tests - extend the cleanup sweeper to also remove NAT gateways, key pairs, Lighthouse instances and CAM sub-users left behind by failed or cancelled integration runs, in reverse dependency order.
- tests - raise the combined module_utils/modules coverage gate in CI from 50% to 70% now that every write module is exercised by the SDK contract suite (currently 79%).
- tke_cluster - add the ``tke_cluster`` module to create, update and delete Kubernetes clusters through the ``tke.v20180525`` API with idempotency and check mode, including CIDR settings, deletion protection and node termination policy on delete.
- vpn_gateway - add the ``vpn_gateway`` module to manage Tencent Cloud VPN gateways (create IPsec/SSL gateways, update name/connection cap/BGP ASN, delete) through the ``vpc.v20170312`` API with idempotency and check mode.

Breaking Changes / Porting Guide
--------------------------------

- antiddos_d_do_s_block_record_info - renamed to antiddos_ddos_block_record_info; the returned key changed from ``d_do_s_block_records`` to ``ddos_block_records``.
- captcha_captcha_user_all_app_id_info - renamed to captcha_user_all_app_id_info; the returned key changed from ``captcha_user_all_app_ids`` to ``user_all_app_ids``.
- dcdb_dcdb_instance_info - renamed to dcdb_instance_info; the returned key changed from ``dcdb_instances`` to ``instances`` and the ids option from ``dcdb_instance_ids`` to ``instance_ids``.
- sms_sms_sign_info - renamed to sms_sign_info; the returned key changed from ``sms_signs`` to ``signs``.
- vcube_vcube_resource_info - renamed to vcube_resource_info; the returned key changed from ``vcube_resources`` to ``resources``.

Bugfixes
--------

- alb_security_policy_info - pass the documented ``security_policy_ids`` and ``filters`` options through to the SDK request instead of dropping them (token-paginated info modules generated with ids or filters options called ``build_request`` with the wrong signature and raised TypeError at runtime). cloudrc_resource_info gets the same fix for ``filters``.
- ckafka_topic - scale partitions through ``CreatePartitionRequest`` with a delta instead of the nonexistent ``PartitionNum`` attribute on ``ModifyTopicAttributesRequest``; shrinking is now rejected with a clear error.
- scf_function - set ``Publish`` on ``UpdateFunctionCodeRequest`` as the string ``"TRUE"`` the SDK declares, not a boolean.
- ssm_parameter - use ``RecoveryWindowInDays`` for delete instead of the int-typed ``DeleteMode`` attribute.

New Plugins
-----------

Callback
~~~~~~~~

- tencentcloud_resource_actions - summarise Tencent Cloud API calls made during a play

Connection
~~~~~~~~~~

- tat - Execute commands and transfer files on Tencent Cloud instances via TAT

Inventory
~~~~~~~~~

- tencentcloud_clb - Tencent Cloud CLB dynamic inventory source (backend instances)
- tencentcloud_sg - Tencent Cloud security group dynamic inventory source

New Modules
-----------

- cbs_disk - Manage Tencent Cloud CBS cloud disks
- cdb_instance - Manage Tencent Cloud CDB MySQL instances
- cfs_file_system - Manage Tencent Cloud CFS file systems
- ckafka_topic - Manage Tencent Cloud CKafka topics
- clb_rule - Manage Tencent Cloud CLB L7 forwarding rules
- cvm_image - Manage Tencent Cloud CVM custom images
- dnspod_record - Manage Tencent Cloud DNSPod DNS records
- lighthouse_instance - Manage Tencent Cloud Lighthouse instances
- nat_gateway - Manage Tencent Cloud NAT gateways
- peering_connection - Manage Tencent Cloud VPC peering connections
- redis_instance - Manage Tencent Cloud Redis instances
- scf_function - Manage Tencent Cloud SCF functions
- ssl_certificate - Manage Tencent Cloud SSL certificates
- ssm_parameter - Manage Tencent Cloud SSM secrets (parameters)
- tag - Manage tags on arbitrary Tencent Cloud resources
- tke_cluster - Manage Tencent Cloud TKE clusters
- vpn_gateway - Manage Tencent Cloud VPN gateways

v0.11.0
=======

Minor Changes
-------------

- CI - SDK contract tests now measure coverage of module_utils and modules and fail below the 50% threshold, blocking silent coverage regressions.
- cvm_instance - add ``exact_count``/``count_tag`` pool scaling mirroring the AWS ec2 module (the module counts the tag-matched instances and brings the pool to the requested size, creating the shortfall in one RunInstances call or terminating the excess oldest-first; PREPAID instances are never terminated automatically).
- integration - delete the test security group by ``security_group_id`` in the network target cleanup instead of by name, so cleanup survives non-unique or renamed groups.
- integration - move integration tests into a dedicated workflow (integration.yml) with three guardrails (a fixed concurrency group that serialises every run against the shared cloud account, a 40-minute budget cap via timeout-minutes, and an always-on ``cleanup`` sweeper target that removes leftover test resources - VPC/subnet/route table/security group/EIP named ``ansible-*-it-*`` - even after a failed or timed-out run).

Breaking Changes / Porting Guide
--------------------------------

- The collection has been renamed from ``tencentcloud.cloud`` to ``susunola.tencentcloud`` so it can be published to Ansible Galaxy (namespace must match a GitHub account). Update every fully qualified collection name in playbooks and roles, for example ``tencentcloud.cloud.cvm_instance`` becomes ``susunola.tencentcloud.cvm_instance``. This also affects ``ansible-galaxy collection install`` (use ``susunola.tencentcloud``), the built tarball name (``susunola-tencentcloud-<version>.tar.gz``) and any ``ansible_collections.tencentcloud.cloud.*`` Python imports.

Bugfixes
--------

- adp_agent_release_preview_info - require ``app_id``.
- apm_general_span_info - require ``instance_id``, ``start_time`` and ``end_time``.
- ccc_extension_info - require ``sdk_app_id``.
- cdwdoris_cluster_configs_history_info - require ``instance_id``, ``start_time`` and ``end_time``.
- cdwpg_account_info - require ``instance_id``.
- dsgc_dspa_assessment_risk_info - require ``dspa_id`` and ``task_id``.
- emr_node_data_disk_info - require ``instance_id`` and rename the ids parameter to ``cvm_instance_ids`` (the API takes node CVM instance IDs, not data-disk IDs).
- essbasic_template_info - require the nested ``agent`` dict with ``app_id``, ``proxy_organization_open_id`` and ``proxy_operator_open_id``.
- iotvideo_ai_model_application_info - require ``model_id``.
- keewidb_instance_backup_info - require ``instance_id``.
- lowcode_knowledge_set_info - require ``env_id``.
- module_utils - change the default ``user_agent`` value to ``ansible-collection.susunola.tencentcloud`` (dot instead of slash) so it satisfies the SDK ``request_client`` regexp; the previous value was silently dropped by the SDK.
- module_utils - the ``user_agent`` option is now forwarded to the SDK's ``ClientProfile.request_client`` so it actually reaches the ``X-TC-RequestClient`` request header (previously a no-op that never left the profile).
- mqtt_device_certificate_info - require ``instance_id``.
- omics_application_info - require ``project_id``.
- tbaas_block_info - require ``channel_name``, ``group_name`` and ``cluster_id``; default ``module``/``operation``/``channel_id``/``group_id`` to the fixed values the API mandates.
- tcbr_cloud_run_pod_info - require ``env_id`` and ``server_name``.
- tdai_agent_duty_task_info - require ``instance_id``.
- tdcpg_cluster_instance_info - require ``cluster_id``.
- teo_function_info - require ``zone_id`` as the API rejects requests without it.
- trocket_consumer_client_info - require ``instance_id``.
- trro_device_info - require ``project_id``.
- yinsuda_ktv_robot_info - require ``app_name`` and ``user_id``.

v0.10.0
=======

Minor Changes
-------------

- clb_listener - new write module managing CLB listeners (TCP/UDP/HTTP/HTTPS), idempotent on load balancer + port + protocol, with health-check and certificate suboptions, drift-only updates, and async task polling.
- clb_listener_target - new write module registering/deregistering CLB backend targets (CVM instances or ENI IPs) on a listener or L7 rule, with exact-set reconciliation, in-place weight updates and optional purge.
- clb_load_balancer - new write module managing CLB instances (present/absent, check mode, diff, tag reconciliation via the tag service, client-token idempotency, status waiters, and task-status recovery when ``CreateLoadBalancer`` returns no IDs).
- module_utils/errors.py - recognize CLB not-found error codes (``InvalidParameter.LBIdNotFound``, ``InvalidParameter.ListenerIdNotFound``) for delete/absent idempotency.
- module_utils/waiters.py - new ``wait_for_task`` helper implementing the Tencent Cloud ``DescribeTaskStatus`` async-task polling convention.

New Modules
-----------

- clb_listener - Manage listeners on Tencent Cloud CLB load balancers
- clb_listener_target - Manage backend targets of Tencent Cloud CLB listeners
- clb_load_balancer - Manage Tencent Cloud CLB load balancers

v0.9.0
======

Minor Changes
-------------

- coverage batch 5 - add 36 generated read-only ``_info`` modules so that every product on the official API index (https://www.tencentcloud.com/document/api) with a usable list API is now covered. Highlights: chdfs_file_system_info, iai_group_info, faceid_we_chat_bill_info, sms_sms_sign_info, gme_voice_print_info, hunyuan_glossary_info, bi_auth_api_key_info, tbaas_block_info, facefusion_material_info, advisor_strategy_info, cdz_cloud_dedicated_zone_host_info, asr_async_recognition_task_info, lcic_answer_info, captcha_captcha_user_all_app_id_info, mna_access_region_info.
- scripts/discover_info_specs.py - reuses existing auto specs verbatim so previously generated modules cannot drift, recognizes ``Get``/``Query``/``Search`` list actions, page-number aliases (``PageNo``/``PageNum``/``PageIndex``), token continuation without a size field, and penalizes candidates with unmanaged optional inputs.
- scripts/generate_info_modules.py - new pagination modes: pagination without a total-count field (stop at the first short page), custom token field pairs (e.g. ``Cursor``/``NextCursor``, ``FileSystemIdMarker``/``NextFileSystemIdMarker``) with optional ``ListOver``/``IsOver``/``HasMore``/``HasNextPage`` flags, and ``list`` mode for unpaginated actions returning an items list.

New Modules
-----------

- acp_scan_task_info - Gather information about Tencent Cloud ACP scan tasks
- advisor_strategy_info - Gather information about Tencent Cloud ADVISOR strategies
- alb_security_policy_info - Gather information about Tencent Cloud ALB security policies
- ams_task_info - Gather information about Tencent Cloud AMS tasks
- anicloud_resource_info - Gather information about Tencent Cloud ANICLOUD resources
- asr_async_recognition_task_info - Gather information about Tencent Cloud ASR async recognition tasks
- bi_auth_api_key_info - Gather information about Tencent Cloud BI auth api keys
- bizlive_worker_info - Gather information about Tencent Cloud BIZLIVE workers
- bsca_kb_component_info - Gather information about Tencent Cloud BSCA kb components
- captcha_captcha_user_all_app_id_info - Gather information about Tencent Cloud CAPTCHA captcha user all app ids
- cdz_cloud_dedicated_zone_host_info - Gather information about Tencent Cloud CDZ cloud dedicated zone hosts
- chdfs_file_system_info - Gather information about Tencent Cloud CHDFS file systems
- ciam_user_store_info - Gather information about Tencent Cloud CIAM user stores
- cloudrc_resource_info - Gather information about Tencent Cloud CLOUDRC resources
- cloudstudio_image_info - Gather information about Tencent Cloud CLOUDSTUDIO images
- cpdp_merchant_info_for_management_info - Gather information about Tencent Cloud CPDP merchant info for managements
- dataagent_chunk_info - Gather information about Tencent Cloud DATAAGENT chunks
- facefusion_material_info - Gather information about Tencent Cloud FACEFUSION materials
- faceid_we_chat_bill_info - Gather information about Tencent Cloud FACEID we chat bills
- fmu_model_info - Gather information about Tencent Cloud FMU models
- gme_voice_print_info - Gather information about Tencent Cloud GME voice prints
- hunyuan_glossary_info - Gather information about Tencent Cloud HUNYUAN glossaries
- iai_group_info - Gather information about Tencent Cloud IAI groups
- ioa_device_info - Gather information about Tencent Cloud IOA devices
- iot_product_info - Gather information about Tencent Cloud IOT products
- lcic_answer_info - Gather information about Tencent Cloud LCIC answers
- mmps_resource_usage_info - Gather information about Tencent Cloud MMPS resource usages
- mna_access_region_info - Gather information about Tencent Cloud MNA access regions
- portal_document_info - Gather information about Tencent Cloud PORTAL documents
- sms_sms_sign_info - Gather information about Tencent Cloud SMS sms signs
- tbaas_block_info - Gather information about Tencent Cloud TBAAS blocks
- tcbr_cloud_run_pod_info - Gather information about Tencent Cloud TCBR cloud run pods
- tia_job_info - Gather information about Tencent Cloud TIA jobs
- tiia_group_info - Gather information about Tencent Cloud TIIA groups
- vm_task_info - Gather information about Tencent Cloud VM tasks
- wav_activity_info - Gather information about Tencent Cloud WAV activities

v0.8.0
======

Minor Changes
-------------

- coverage batches 3+4 - add 126 generated read-only ``_info`` modules, raising product coverage from 36 to 162 distinct Tencent Cloud services. New modules span compute and batch (batch, bm, bmlb, bmvpc, chc, ecm, thpc), storage and backup (bdrc, cetcd, cds, dbs, goosefs, keewidb, memcached, smh, vdb), databases and big data (cdwch, cdwdoris, cdwpg, ctsdb, dbbrain, dbdc, dcdb, dlc, emr, es-scale-out, oceanus, omics, tcaplusdb, tdcpg, tdmysql, wedata), networking and edge (antiddos, bmeip, dc, ecdn, fwm, ga2, gwlb, igtm, privatedns, teo), security and compliance (cfw, cloudhsm, config, csip, ctem, dasb, dsgc, securitylake, ssa, sslpod, yunjing), messaging and integration (cmq, eb, mqtt, tdmq, trabbit, trocket), AI and serverless (adp, ags, apis, asw, hai, lke, lowcode, tdai, tione, tokenhub), media and communication (ame, ccc, ic, iss, ivld, live, mps, ses, trtc, vcube, vod, wss, yinsuda), IoT and devices (iotcloud, iotexplorer, iotvideo, iotvideoindustry, trro), and management/finops (billing-adjacent tcb, controlcenter, domain, eiam, hasim, mall, msp, partners, pts, region, rum, svp, tourism).
- scripts/discover_info_specs.py - new SDK-introspection tool that nominates ``_info`` generator specs automatically: it finds paginated Describe/List actions (Offset/Limit or PageNumber/PageSize) across all installed ``tencentcloud-sdk-python-<product>`` packages, identifies ids and Filters model shapes, and writes ``scripts/info_specs_auto.py``. Products without a qualifying list API are reported in a skip report.
- scripts/generate_info_modules.py - the generator now merges auto-discovered specs from ``scripts/info_specs_auto.py`` and emits a matching generated unit test for each simple auto spec; curated specs keep their hand-written tests.
- tests/contract - contract tests now cover the auto-discovered specs via the merged spec list (362 contracts checked).

New Modules
-----------

- adp_agent_release_preview_info - Gather information about Tencent Cloud ADP agent release previews
- ags_sandbox_instance_info - Gather information about Tencent Cloud AGS sandbox instances
- ame_ktv_robot_info - Gather information about Tencent Cloud AME ktv robots
- antiddos_d_do_s_block_record_info - Gather information about Tencent Cloud ANTIDDOS d do s block records
- ape_auth_user_info - Gather information about Tencent Cloud APE auth users
- api_product_info - Gather information about Tencent Cloud API products
- apis_agent_app_mcp_server_info - Gather information about Tencent Cloud APIS agent app mcp servers
- apm_general_span_info - Gather information about Tencent Cloud APM general spans
- asw_flow_service_info - Gather information about Tencent Cloud ASW flow services
- batch_compute_env_create_info - Gather information about Tencent Cloud BATCH compute env creates
- bdrc_backup_vault_info - Gather information about Tencent Cloud BDRC backup vaults
- bh_device_group_member_info - Gather information about Tencent Cloud BH device group members
- bm_device_info - Gather information about Tencent Cloud BM devices
- bma_bp_fake_app_info - Gather information about Tencent Cloud BMA bp fake apps
- bmeip_eip_acl_info - Gather information about Tencent Cloud BMEIP eip acls
- bmlb_load_balancer_info - Gather information about Tencent Cloud BMLB load balancers
- bmvpc_customer_gateway_info - Gather information about Tencent Cloud BMVPC customer gateways
- cat_probe_task_info - Gather information about Tencent Cloud CAT probe tasks
- ccc_extension_info - Gather information about Tencent Cloud CCC extensions
- cdc_dedicated_cluster_order_info - Gather information about Tencent Cloud CDC dedicated cluster orders
- cds_asset_info - Gather information about Tencent Cloud CDS assets
- cdwch_cn_instance_info - Gather information about Tencent Cloud CDWCH cn instances
- cdwdoris_cluster_configs_history_info - Gather information about Tencent Cloud CDWDORIS cluster configs histories
- cdwpg_account_info - Gather information about Tencent Cloud CDWPG accounts
- cetcd_etcd_instance_info - Gather information about Tencent Cloud CETCD etcd instances
- cfg_action_library_info - Gather information about Tencent Cloud CFG action libraries
- cfw_cluster_nat_ccn_fw_switch_info - Gather information about Tencent Cloud CFW cluster nat ccn fw switches
- chc_device_info - Gather information about Tencent Cloud CHC devices
- cloudhsm_vsm_info - Gather information about Tencent Cloud CLOUDHSM vsms
- cme_platform_info - Gather information about Tencent Cloud CME platforms
- cmq_queue_info - Gather information about Tencent Cloud CMQ queues
- cms_lib_sample_info - Gather information about Tencent Cloud CMS lib samples
- cngw_cloud_native_api_gateway_llm_model_api_info - Gather information about Tencent Cloud CNGW cloud native api gateway llm model apis
- config_aggregate_compliance_pack_info - Gather information about Tencent Cloud CONFIG aggregate compliance packs
- controlcenter_account_factory_baseline_item_info - Gather information about Tencent Cloud CONTROLCENTER account factory baseline items
- csip_asset_process_info - Gather information about Tencent Cloud CSIP asset processes
- ctem_api_sec_info - Gather information about Tencent Cloud CTEM api secs
- ctsdb_cluster_info - Gather information about Tencent Cloud CTSDB clusters
- cws_monitor_info - Gather information about Tencent Cloud CWS monitors
- dasb_device_info - Gather information about Tencent Cloud DASB devices
- dayu_resource_info - Gather information about Tencent Cloud DAYU resources
- dbbrain_db_diag_event_info - Gather information about Tencent Cloud DBBRAIN db diag events
- dbdc_db_custom_cluster_info - Gather information about Tencent Cloud DBDC db custom clusters
- dbs_backup_plan_info - Gather information about Tencent Cloud DBS backup plans
- dc_direct_connect_tunnel_info - Gather information about Tencent Cloud DC direct connect tunnels
- dcdb_dcdb_instance_info - Gather information about Tencent Cloud DCDB dcdb instances
- dlc_task_info - Gather information about Tencent Cloud DLC tasks
- domain_batch_operation_log_info - Gather information about Tencent Cloud DOMAIN batch operation logs
- dsgc_dspa_assessment_risk_info - Gather information about Tencent Cloud DSGC dspa assessment risks
- dts_subscribe_job_info - Gather information about Tencent Cloud DTS subscribe jobs
- eb_event_bus_info - Gather information about Tencent Cloud EB event buses
- ecdn_domain_info - Gather information about Tencent Cloud ECDN domains
- ecm_address_info - Gather information about Tencent Cloud ECM addresses
- eiam_application_info - Gather information about Tencent Cloud EIAM applications
- eis_runtime_deployed_instances_mc_info - Gather information about Tencent Cloud EIS runtime deployed instances mcs
- emr_node_data_disk_info - Gather information about Tencent Cloud EMR node data disks
- ess_file_url_info - Gather information about Tencent Cloud ESS file urls
- essbasic_template_info - Gather information about Tencent Cloud ESSBASIC templates
- fwm_edge_acl_rule_info - Gather information about Tencent Cloud FWM edge acl rules
- ga2_accelerate_area_info - Gather information about Tencent Cloud GA2 accelerate areas
- goosefs_file_system_info - Gather information about Tencent Cloud GOOSEFS file systems
- gs_android_app_info - Gather information about Tencent Cloud GS android apps
- gwlb_gateway_load_balancer_info - Gather information about Tencent Cloud GWLB gateway load balancers
- hai_application_info - Gather information about Tencent Cloud HAI applications
- hasim_link_info - Gather information about Tencent Cloud HASIM links
- ic_sms_info - Gather information about Tencent Cloud IC smses
- igtm_address_pool_info - Gather information about Tencent Cloud IGTM address pools
- iotcloud_device_resource_info - Gather information about Tencent Cloud IOTCLOUD device resources
- iotexplorer_device_position_info - Gather information about Tencent Cloud IOTEXPLORER device positions
- iotvideo_ai_model_application_info - Gather information about Tencent Cloud IOTVIDEO ai model applications
- iotvideoindustry_all_device_info - Gather information about Tencent Cloud IOTVIDEOINDUSTRY all devices
- iss_device_snapshot_info - Gather information about Tencent Cloud ISS device snapshots
- ivld_custom_person_info - Gather information about Tencent Cloud IVLD custom persons
- keewidb_instance_backup_info - Gather information about Tencent Cloud KEEWIDB instance backups
- live_audit_keyword_info - Gather information about Tencent Cloud LIVE audit keywords
- lke_app_knowledge_info - Gather information about Tencent Cloud LKE app knowledges
- lowcode_knowledge_set_info - Gather information about Tencent Cloud LOWCODE knowledge sets
- mall_draw_resource_info - Gather information about Tencent Cloud MALL draw resources
- memcached_instance_info - Gather information about Tencent Cloud MEMCACHED instances
- mps_person_sample_info - Gather information about Tencent Cloud MPS person samples
- mqtt_device_certificate_info - Gather information about Tencent Cloud MQTT device certificates
- ms_shield_instance_info - Gather information about Tencent Cloud MS shield instances
- msp_migration_project_info - Gather information about Tencent Cloud MSP migration projects
- oceanus_cluster_info - Gather information about Tencent Cloud OCEANUS clusters
- omics_application_info - Gather information about Tencent Cloud OMICS applications
- partners_agent_deals_by_cache_info - Gather information about Tencent Cloud PARTNERS agent deals by caches
- privatedns_account_vpc_info - Gather information about Tencent Cloud PRIVATEDNS account vpcs
- pts_cron_job_info - Gather information about Tencent Cloud PTS cron jobs
- region_product_info - Gather information about Tencent Cloud REGION products
- rum_project_info - Gather information about Tencent Cloud RUM projects
- securitylake_security_alarm_table_info - Gather information about Tencent Cloud SECURITYLAKE security alarm tables
- ses_black_email_address_info - Gather information about Tencent Cloud SES black email addresses
- smh_library_info - Gather information about Tencent Cloud SMH libraries
- ssa_check_config_asset_info - Gather information about Tencent Cloud SSA check config assets
- sslpod_domain_info - Gather information about Tencent Cloud SSLPOD domains
- svp_saving_plan_coverage_info - Gather information about Tencent Cloud SVP saving plan coverages
- tcaplusdb_cluster_info - Gather information about Tencent Cloud TCAPLUSDB clusters
- tcb_billing_info - Gather information about Tencent Cloud TCB billings
- tcm_mesh_info - Gather information about Tencent Cloud TCM meshes
- tcss_abnormal_process_event_info - Gather information about Tencent Cloud TCSS abnormal process events
- tdai_agent_duty_task_info - Gather information about Tencent Cloud TDAI agent duty tasks
- tdcpg_cluster_instance_info - Gather information about Tencent Cloud TDCPG cluster instances
- tdmq_amqp_cluster_info - Gather information about Tencent Cloud TDMQ amqp clusters
- tdmysql_db_instance_info - Gather information about Tencent Cloud TDMYSQL db instances
- tem_application_info - Gather information about Tencent Cloud TEM applications
- teo_function_info - Gather information about Tencent Cloud TEO functions
- thpc_cluster_info - Gather information about Tencent Cloud THPC clusters
- tione_dataset_info - Gather information about Tencent Cloud TIONE datasets
- tiw_running_task_info - Gather information about Tencent Cloud TIW running tasks
- tokenhub_model_info - Gather information about Tencent Cloud TOKENHUB models
- tourism_draw_resource_info - Gather information about Tencent Cloud TOURISM draw resources
- trabbit_rabbit_mq_serverless_instance_info - Gather information about Tencent Cloud TRABBIT rabbit mq serverless instances
- trocket_consumer_client_info - Gather information about Tencent Cloud TROCKET consumer clients
- trp_code_batch_info - Gather information about Tencent Cloud TRP code batches
- trro_device_info - Gather information about Tencent Cloud TRRO devices
- trtc_call_info - Gather information about Tencent Cloud TRTC calls
- tse_sre_instance_info - Gather information about Tencent Cloud TSE sre instances
- tsf_application_info - Gather information about Tencent Cloud TSF applications
- vcube_vcube_resource_info - Gather information about Tencent Cloud VCUBE vcube resources
- vdb_instance_info - Gather information about Tencent Cloud VDB instances
- vod_incremental_migration_strategy_info - Gather information about Tencent Cloud VOD incremental migration strategies
- wedata_project_info - Gather information about Tencent Cloud WEDATA projects
- weilingwith_element_profile_page_info - Gather information about Tencent Cloud WEILINGWITH element profile pages
- wss_cert_info - Gather information about Tencent Cloud WSS certs
- yinsuda_ktv_robot_info - Gather information about Tencent Cloud YINSUDA ktv robots
- yunjing_account_statistic_info - Gather information about Tencent Cloud YUNJING account statistics

v0.7.0
======

Minor Changes
-------------

- billing_balance_info - add a generated read-only module returning the account balance (unpaginated single call).
- cdn_domain_info - add a generated read-only module querying CDN domains.
- cloudaudit_event_info - add a generated read-only module querying CloudAudit events (token-paginated LookUpEvents).
- cls_topic_info - add a generated read-only module querying CLS log topics.
- cwp_machine_info - add a generated read-only module querying Cloud Workload Protection machines.
- gaap_proxy_info - add a generated read-only module querying GAAP proxies.
- monitor_alarm_policy_info - add a generated read-only module querying Cloud Monitor alarm policies (page-number paginated).
- nat_gateway_info - add a generated read-only module querying NAT gateways.
- organization_member_info - add a generated read-only module querying Organization members.
- scripts - the _info generator now supports token-based and page-number-based pagination, unpaginated single-object responses, and per-service filter models, so services with non-standard list APIs can be generated too.
- ssl_certificate_info - add a generated read-only module querying SSL certificates.
- tat_command_info - add a generated read-only module querying TAT commands.
- vpn_gateway_info - add a generated read-only module querying VPN gateways.
- waf_instance_info - add a generated read-only module querying WAF instances.

New Modules
-----------

- billing_balance_info - Gather information about the Tencent Cloud account balance
- cdn_domain_info - Gather information about Tencent Cloud CDN domains
- cloudaudit_event_info - Gather information about Tencent Cloud CloudAudit events
- cls_topic_info - Gather information about Tencent Cloud CLS log topics
- cwp_machine_info - Gather information about Tencent Cloud CWP machines
- gaap_proxy_info - Gather information about Tencent Cloud GAAP proxies
- monitor_alarm_policy_info - Gather information about Tencent Cloud Monitor alarm policies
- nat_gateway_info - Gather information about Tencent Cloud NAT gateways
- organization_member_info - Gather information about Tencent Cloud Organization members
- ssl_certificate_info - Gather information about Tencent Cloud SSL certificates
- tat_command_info - Gather information about Tencent Cloud TAT commands
- vpn_gateway_info - Gather information about Tencent Cloud VPN gateways
- waf_instance_info - Gather information about Tencent Cloud WAF instances

v0.6.0
======

Minor Changes
-------------

- apigateway_service_info - add a generated read-only module querying API Gateway services.
- as_scaling_group_info - add a generated read-only module querying auto scaling groups.
- cfs_file_system_info - add a generated read-only module querying CFS file systems.
- ckafka_instance_info - add a generated read-only module querying CKafka instances.
- cynosdb_cluster_info - add a generated read-only module querying CynosDB clusters.
- es_cluster_info - add a generated read-only module querying Elasticsearch Service clusters.
- lighthouse_instance_info - add a generated read-only module querying Lighthouse instances.
- mariadb_instance_info - add a generated read-only module querying TencentDB for MariaDB instances.
- postgres_instance_info - add a generated read-only module querying TencentDB for PostgreSQL instances.
- scf_function_info - add a generated read-only module querying SCF functions.
- scripts - add sync_registry.py keeping README module tables and the action_groups registry in sync with plugins/modules, with a CI --check.
- sqlserver_instance_info - add a generated read-only module querying TencentDB for SQL Server instances.
- tcr_instance_info - add a generated read-only module querying TCR registries.
- tests - the SDK contract tests now auto-discover every module and derive coverage for generated _info modules from the generator specs, so new modules are audited by default.

Bugfixes
--------

- meta - action_groups.all was missing 20 modules (all generated _info modules), so module_defaults did not apply to them.

New Modules
-----------

- apigateway_service_info - Gather information about Tencent Cloud API Gateway services
- as_scaling_group_info - Gather information about Tencent Cloud auto scaling groups
- cfs_file_system_info - Gather information about Tencent Cloud CFS file systems
- ckafka_instance_info - Gather information about Tencent Cloud CKafka instances
- cynosdb_cluster_info - Gather information about TencentDB for CynosDB clusters
- es_cluster_info - Gather information about Tencent Cloud Elasticsearch clusters
- lighthouse_instance_info - Gather information about Tencent Cloud Lighthouse instances
- mariadb_instance_info - Gather information about TencentDB for MariaDB instances
- postgres_instance_info - Gather information about TencentDB for PostgreSQL instances
- scf_function_info - Gather information about Tencent Cloud SCF functions
- sqlserver_instance_info - Gather information about TencentDB for SQL Server instances
- tcr_instance_info - Gather information about Tencent Cloud TCR registries

v0.5.0
======

Major Changes
-------------

- authentication - support TCCLI-style credential profiles in ``~/.tencentcloud/default.configure`` with a new ``profile`` option (env fallback ``TENCENTCLOUD_PROFILE``); precedence is module parameter > environment variable > profile file, and ``region`` is no longer hard-required when a profile supplies it.
- inventory - add the ``tencentcloud_cvm`` dynamic inventory plugin with constructed groups, composed hostvars and caching support.
- lookup - add the ``ssm_parameter`` lookup reading secrets from Tencent Cloud Secrets Manager (``GetSecretValue``).
- lookup - add the ``sts_caller_identity`` lookup returning the caller's Uin/AccountId/Arn, with optional AssumeRole.
- modules - add STS AssumeRole support to every module via ``role_arn``, ``role_session_name`` and ``role_session_duration`` (env fallback ``TENCENTCLOUD_ROLE_ARN``); credentials are exchanged for temporary ones before any service call.
- modules - all write modules now honor Ansible's diff mode (``--diff``), emitting the before/after diff on real runs as well as in check mode.
- scripts - add ``scripts/generate_info_modules.py``, a re-runnable generator that produces read-only ``*_info`` modules from SDK metadata (``--check`` verifies the generated files are current).

Minor Changes
-------------

- Added VPC and security group information modules.
- Added shared SDK endpoint and timeout configuration.
- cam_policy - add an idempotent module managing CAM custom policies with semantic JSON policy comparison.
- cam_policy_info - add a read-only module querying CAM policies.
- cam_role - add an idempotent module managing CAM roles with trust policy documents and native role tags.
- cam_role_info - add a read-only module querying CAM roles.
- cam_user - add an idempotent module managing CAM sub-users (console login, remark, tags).
- cam_user_info - add a read-only module listing CAM sub-users with client-side name / name_keyword filters.
- cbs_disk_info - add a generated read-only module querying CBS cloud disks with IDs or API filters.
- cdb_instance_info - add a generated read-only module querying TencentDB for MySQL instances with IDs.
- ci - add a release workflow that lints the changelog, verifies the tag matches ``galaxy.yml``, builds the collection, creates a GitHub Release and publishes to Ansible Galaxy on ``v*`` tags.
- ci - the release workflow now folds changelog fragments with ``antsibull-changelog release`` and commits the rendered changelog back to main before building the tarball.
- clb_load_balancer_info - add a generated read-only module querying CLB load balancers with IDs or API filters.
- cos_bucket - add an idempotent module managing COS buckets (ACL, versioning, native COS tagging) via the qcloud_cos SDK; the first module family outside the API 3.0 surface.
- cos_bucket / cos_bucket_info - honor role_arn by exchanging the base credentials for temporary ones before building the COS client.
- cos_bucket_info - add a read-only module describing one COS bucket or listing all buckets in a region.
- cvm_instance - add an idempotent module managing the CVM instance lifecycle (present/absent/running/stopped) with state waiters.
- dnspod_record_info - add a generated read-only module listing DNSPod records for a domain.
- eip - add an idempotent module allocating, releasing and binding elastic IP addresses with check mode and diff.
- eip_info - add a read-only module querying elastic IPs with IDs, IPs or API filters.
- governance - add MAINTAINERS.md, SECURITY.md, issue templates and a PR template, following the Ansible community package requirements.
- integration - add a ``network`` target covering the vpc, subnet, route_table, security_group_rule and eip lifecycle against a real account.
- integration - add a real-account security_group integration test target covering create/idempotency/check-mode/delete.
- key_pair - add an idempotent module creating or importing SSH key pairs; generated private keys are returned once at creation.
- key_pair_info - add a read-only module querying key pairs with IDs or API filters.
- kms_key_info - add a generated read-only module listing KMS keys or describing them by key IDs.
- meta - add the ``susunola.tencentcloud.all`` action group so ``module_defaults`` can set shared options (region, credentials, ``role_arn``) once per play.
- meta - register all new modules in the ``susunola.tencentcloud.all`` action group and add an (empty) ``plugin_routing`` section documenting the deprecation process.
- module_utils - add a unified offset/limit paginator replacing the hand-rolled loops in the discovery modules.
- module_utils - all new modules share a retry policy with exponential backoff and jitter for throttled and transient API failures.
- module_utils - split the single-file helper into focused modules (errors, retries, paging, tagging, comparison, waiters, client, base); the original tencentcloud module remains as a backward-compatible shim.
- mongodb_instance_info - add a generated read-only module querying TencentDB for MongoDB instances with IDs.
- redis_instance_info - add a generated read-only module querying TencentDB for Redis instances with IDs.
- route_table - add an idempotent module managing route tables and their user routes (full route reconciliation) with check mode and diff.
- route_table_info - add a read-only module querying route tables with IDs or API filters.
- security_group - add the first idempotent resource module with present/absent state, check mode, diff output, and tag management.
- security_group_rule - add an idempotent module reconciling the ingress/egress rule set of a security group with optional purge.
- sts_caller_identity / ssm_parameter lookups - support credential profiles with the same param > env > profile precedence.
- subnet - add an idempotent module managing subnets (CIDR, zone, broadcast, tags) with check mode and diff.
- subnet_info - add a read-only module querying subnets with IDs or API filters.
- tencentcloud_cvm inventory - support credential profiles (profile option, env TENCENTCLOUD_PROFILE), matching the modules.
- tests - add run_module-level unit tests for every write module covering create, idempotency, delete, check mode and diff mode through a shared test harness.
- tests - add tests/contract with SDK contract tests that build every module's requests against the real SDK model classes in CI, catching wrong field names and scalar types that fake-based unit tests cannot.
- tke_cluster_info - add a generated read-only module querying TKE clusters with IDs or API filters.
- vpc - add an idempotent module managing VPCs (CIDR, DNS servers, domain name, tags) with check mode and diff.

Bugfixes
--------

- Return Tencent Cloud API error codes and request IDs for troubleshooting.
- security_group - build ``Filter`` objects via attribute assignment; the real SDK ``Filter`` class does not accept constructor kwargs, which broke name-based lookups at runtime.
- security_group - fix name/description updates being silently ignored. ModifySecurityGroupAttributeRequest takes GroupName / GroupDescription, not SecurityGroupName / SecurityGroupDesc. Found by the new SDK contract tests.
- subnet - fix DescribeSubnetsRequest.Limit being sent as an integer. The VPC API requires it as a string.

New Plugins
-----------

Lookup
~~~~~~

- ssm_parameter - Retrieve Tencent Cloud Secrets Manager secret values
- sts_caller_identity - Get information about the Tencent Cloud credentials in use

New Modules
-----------

- cam_policy - Manage Tencent Cloud CAM policies
- cam_policy_info - Gather information about Tencent Cloud CAM policies
- cam_role - Manage Tencent Cloud CAM roles
- cam_role_info - Gather information about Tencent Cloud CAM roles
- cam_user - Manage Tencent Cloud CAM sub\-users
- cam_user_info - Gather information about Tencent Cloud CAM sub\-users
- cos_bucket - Manage Tencent Cloud COS buckets
- cos_bucket_info - Gather information about Tencent Cloud COS buckets
