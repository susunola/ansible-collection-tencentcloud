================================
Tencent Cloud 0.10 Release Notes
================================

.. contents:: Topics

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
