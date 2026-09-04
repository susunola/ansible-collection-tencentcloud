===============================
Tencent Cloud 1.0 Release Notes
===============================

.. contents:: Topics

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
