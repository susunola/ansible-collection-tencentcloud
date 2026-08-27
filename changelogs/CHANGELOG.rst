===============================
Tencent Cloud 0.6 Release Notes
===============================

.. contents:: Topics

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
- meta - add the ``tencentcloud.cloud.all`` action group so ``module_defaults`` can set shared options (region, credentials, ``role_arn``) once per play.
- meta - register all new modules in the ``tencentcloud.cloud.all`` action group and add an (empty) ``plugin_routing`` section documenting the deprecation process.
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
