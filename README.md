# Tencent Cloud Ansible Collection

[![CI](https://github.com/susunola/ansible-collection-tencentcloud/actions/workflows/ci.yml/badge.svg)](https://github.com/susunola/ansible-collection-tencentcloud/actions/workflows/ci.yml)
[![Ansible Galaxy](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgalaxy.ansible.com%2Fapi%2Fv3%2Fcollections%2Fsusunola%2Ftencentcloud%2F&query=highest_version.version&label=Ansible%20Galaxy&color=blue)](https://galaxy.ansible.com/susunola/tencentcloud)

`susunola.tencentcloud` provides Ansible modules and plugins for managing Tencent
Cloud resources. It is developed as a community collection targeting inclusion
in the `ansible-collections` GitHub organization.

## Included modules

Resource modules (idempotent, `state: present|absent`, check mode and diff):

| Module | Purpose |
| --- | --- |
| `api_gateway_service` | Manage Tencent Cloud API Gateway services |
| `cam_group_membership` | Manage Tencent Cloud CAM user group membership |
| `cam_policy` | Manage Tencent Cloud CAM policies |
| `cam_policy_attachment` | Manage a Tencent Cloud CAM policy attachment |
| `cam_role` | Manage Tencent Cloud CAM roles |
| `cam_user` | Manage Tencent Cloud CAM sub-users |
| `cbs_disk` | Manage Tencent Cloud CBS cloud disks |
| `cbs_snapshot` | Manage Tencent Cloud CBS disk snapshots |
| `ccn` | Manage Tencent Cloud Cloud Connect Networks |
| `ccn_attachment` | Attach network instances to Tencent Cloud CCN |
| `cdb_instance` | Manage Tencent Cloud CDB MySQL instances |
| `cdn_domain` | Manage Tencent Cloud CDN domains |
| `cfs_file_system` | Manage Tencent Cloud CFS file systems |
| `ckafka_topic` | Manage Tencent Cloud CKafka topics |
| `clb_listener` | Manage listeners on Tencent Cloud CLB load balancers |
| `clb_listener_target` | Manage backend targets of Tencent Cloud CLB listeners |
| `clb_load_balancer` | Manage Tencent Cloud CLB load balancers |
| `clb_rule` | Manage Tencent Cloud CLB L7 forwarding rules |
| `clb_target_group` | Manage Tencent Cloud CLB target groups and members |
| `cls_logset` | Manage Tencent Cloud CLS logsets |
| `cls_topic` | Manage Tencent Cloud CLS topics |
| `cos_bucket` | Manage Tencent Cloud COS buckets |
| `customer_gateway` | Manage Tencent Cloud VPN customer gateways |
| `cvm_chc` | Manage Tencent Cloud CHC physical server network configuration |
| `cvm_image` | Manage Tencent Cloud CVM custom images |
| `cvm_instance` | Manage Tencent Cloud CVM instances |
| `cynosdb_account` | Manage Tencent Cloud CynosDB accounts |
| `dnspod_record` | Manage Tencent Cloud DNSPod DNS records |
| `eip` | Manage Tencent Cloud elastic IP addresses (EIP) |
| `elasticsearch_instance` | Manage Tencent Cloud Elasticsearch clusters |
| `gaap_proxy` | Manage Tencent Cloud GAAP proxies |
| `key_pair` | Manage Tencent Cloud CVM key pairs |
| `kms_key` | Manage a Tencent Cloud KMS key |
| `kms_key_rotation` | Manage automatic rotation for a Tencent Cloud KMS key |
| `lighthouse_instance` | Manage Tencent Cloud Lighthouse instances |
| `mongodb_instance` | Manage Tencent Cloud MongoDB instances |
| `monitor_alarm_policy` | Manage a Tencent Cloud Monitor alarm policy |
| `monitor_alarm_policy_notice` | Manage notification bindings for a Cloud Monitor alarm policy |
| `nat_gateway` | Manage Tencent Cloud NAT gateways |
| `nat_gateway_rule` | Manage Tencent Cloud NAT gateway DNAT and SNAT rules |
| `network_acl` | Manage Tencent Cloud VPC network ACLs |
| `network_interface` | Manage Tencent Cloud elastic network interfaces |
| `peering_connection` | Manage Tencent Cloud VPC peering connections |
| `postgresql_account` | Manage TencentDB for PostgreSQL accounts |
| `private_dns_record` | Manage a Tencent Cloud Private DNS record |
| `private_dns_zone` | Manage a Tencent Cloud Private DNS zone |
| `privatelink_endpoint` | Manage Tencent Cloud PrivateLink endpoints |
| `privatelink_endpoint_service` | Manage Tencent Cloud PrivateLink endpoint services |
| `redis_instance` | Manage Tencent Cloud Redis instances |
| `route_table` | Manage Tencent Cloud VPC route tables |
| `scf_alias` | Manage Tencent Cloud SCF function aliases |
| `scf_function` | Manage Tencent Cloud SCF functions |
| `scf_version` | Manage Tencent Cloud SCF function versions |
| `security_group` | Manage Tencent Cloud security groups |
| `security_group_rule` | Manage Tencent Cloud security group rules |
| `ssl_certificate` | Manage Tencent Cloud SSL certificates |
| `ssm_parameter` | Manage Tencent Cloud SSM secrets (parameters) |
| `subnet` | Manage Tencent Cloud VPC subnets |
| `tag` | Manage tags on arbitrary Tencent Cloud resources |
| `tcr_instance` | Manage Tencent Cloud TCR enterprise instances |
| `tcr_namespace` | Manage Tencent Cloud TCR namespaces |
| `tcr_repository` | Manage a Tencent Cloud TCR repository |
| `tke_addon` | Manage a Tencent Kubernetes Engine addon |
| `tke_cluster` | Manage Tencent Cloud TKE clusters |
| `tke_node_pool` | Manage Tencent Cloud TKE cluster node pools |
| `vpc` | Manage Tencent Cloud VPCs |
| `vpc_flow_log` | Manage Tencent Cloud VPC flow logs |
| `vpn_connection` | Manage Tencent Cloud IPsec VPN connections |
| `vpn_gateway` | Manage Tencent Cloud VPN gateways |

Read-only `_info` modules (return `changed=false`):

| Module | Purpose |
| --- | --- |
| `acp_scan_task_info` | Gather information about Tencent Cloud ACP scan tasks |
| `adp_agent_release_preview_info` | Gather information about Tencent Cloud ADP agent release previews |
| `advisor_strategy_info` | Gather information about Tencent Cloud ADVISOR strategies |
| `ags_sandbox_instance_info` | Gather information about Tencent Cloud AGS sandbox instances |
| `alb_security_policy_info` | Gather information about Tencent Cloud ALB security policies |
| `ame_ktv_robot_info` | Gather information about Tencent Cloud AME ktv robots |
| `ams_task_info` | Gather information about Tencent Cloud AMS tasks |
| `anicloud_resource_info` | Gather information about Tencent Cloud ANICLOUD resources |
| `antiddos_ddos_block_record_info` | Gather information about Tencent Cloud ANTIDDOS DDoS block records |
| `ape_auth_user_info` | Gather information about Tencent Cloud APE auth users |
| `api_product_info` | Gather information about Tencent Cloud API products |
| `apigateway_service_info` | Gather information about Tencent Cloud API Gateway services |
| `apis_agent_app_mcp_server_info` | Gather information about Tencent Cloud APIS agent app mcp servers |
| `apm_general_span_info` | Gather information about Tencent Cloud APM general spans |
| `as_scaling_group_info` | Gather information about Tencent Cloud auto scaling groups |
| `asr_async_recognition_task_info` | Gather information about Tencent Cloud ASR async recognition tasks |
| `asw_flow_service_info` | Gather information about Tencent Cloud ASW flow services |
| `ba_auth_info` | Gather information about Tencent Cloud BA auth |
| `batch_compute_env_create_info` | Gather information about Tencent Cloud BATCH compute env creates |
| `bdrc_backup_vault_info` | Gather information about Tencent Cloud BDRC backup vaults |
| `bh_device_group_member_info` | Gather information about Tencent Cloud BH device group members |
| `bi_auth_api_key_info` | Gather information about Tencent Cloud BI auth api keys |
| `billing_balance_info` | Gather information about the Tencent Cloud account balance |
| `bizlive_worker_info` | Gather information about Tencent Cloud BIZLIVE workers |
| `bm_device_info` | Gather information about Tencent Cloud BM devices |
| `bma_bp_fake_app_info` | Gather information about Tencent Cloud BMA bp fake apps |
| `bmeip_eip_acl_info` | Gather information about Tencent Cloud BMEIP eip acls |
| `bmlb_load_balancer_info` | Gather information about Tencent Cloud BMLB load balancers |
| `bmvpc_customer_gateway_info` | Gather information about Tencent Cloud BMVPC customer gateways |
| `bsca_kb_component_info` | Gather information about Tencent Cloud BSCA kb components |
| `cam_policy_info` | Gather information about Tencent Cloud CAM policies |
| `cam_role_info` | Gather information about Tencent Cloud CAM roles |
| `cam_user_info` | Gather information about Tencent Cloud CAM sub-users |
| `captcha_user_all_app_id_info` | Gather information about Tencent Cloud CAPTCHA user all app ids |
| `cat_probe_task_info` | Gather information about Tencent Cloud CAT probe tasks |
| `cbs_disk_info` | Gather information about Tencent Cloud CBS disks |
| `ccc_extension_info` | Gather information about Tencent Cloud CCC extensions |
| `cdb_instance_info` | Gather information about TencentDB for MySQL instances |
| `cdc_dedicated_cluster_order_info` | Gather information about Tencent Cloud CDC dedicated cluster orders |
| `cdn_domain_info` | Gather information about Tencent Cloud CDN domains |
| `cds_asset_info` | Gather information about Tencent Cloud CDS assets |
| `cdwch_cn_instance_info` | Gather information about Tencent Cloud CDWCH cn instances |
| `cdwdoris_cluster_configs_history_info` | Gather information about Tencent Cloud CDWDORIS cluster configs histories |
| `cdwpg_account_info` | Gather information about Tencent Cloud CDWPG accounts |
| `cdz_cloud_dedicated_zone_host_info` | Gather information about Tencent Cloud CDZ cloud dedicated zone hosts |
| `cetcd_etcd_instance_info` | Gather information about Tencent Cloud CETCD etcd instances |
| `cfg_action_library_info` | Gather information about Tencent Cloud CFG action libraries |
| `cfs_file_system_info` | Gather information about Tencent Cloud CFS file systems |
| `cfw_cluster_nat_ccn_fw_switch_info` | Gather information about Tencent Cloud CFW cluster nat ccn fw switches |
| `chc_device_info` | Gather information about Tencent Cloud CHC devices |
| `chdfs_file_system_info` | Gather information about Tencent Cloud CHDFS file systems |
| `ciam_user_store_info` | Gather information about Tencent Cloud CIAM user stores |
| `ckafka_instance_info` | Gather information about Tencent Cloud CKafka instances |
| `clb_load_balancer_info` | Gather information about Tencent Cloud CLB load balancers |
| `cloudaudit_event_info` | Gather information about Tencent Cloud CloudAudit events |
| `cloudhsm_vsm_info` | Gather information about Tencent Cloud CLOUDHSM vsms |
| `cloudrc_resource_info` | Gather information about Tencent Cloud CLOUDRC resources |
| `cloudstudio_image_info` | Gather information about Tencent Cloud CLOUDSTUDIO images |
| `cls_topic_info` | Gather information about Tencent Cloud CLS log topics |
| `cme_platform_info` | Gather information about Tencent Cloud CME platforms |
| `cmq_queue_info` | Gather information about Tencent Cloud CMQ queues |
| `cms_lib_sample_info` | Gather information about Tencent Cloud CMS lib samples |
| `cngw_cloud_native_api_gateway_llm_model_api_info` | Gather information about Tencent Cloud CNGW cloud native api gateway llm model apis |
| `config_aggregate_compliance_pack_info` | Gather information about Tencent Cloud CONFIG aggregate compliance packs |
| `controlcenter_account_factory_baseline_item_info` | Gather information about Tencent Cloud CONTROLCENTER account factory baseline items |
| `cos_bucket_info` | Gather information about Tencent Cloud COS buckets |
| `cpdp_merchant_info_for_management_info` | Gather information about Tencent Cloud CPDP merchant info for managements |
| `csip_asset_process_info` | Gather information about Tencent Cloud CSIP asset processes |
| `ctem_api_sec_info` | Gather information about Tencent Cloud CTEM api secs |
| `ctsdb_cluster_info` | Gather information about Tencent Cloud CTSDB clusters |
| `cvm_instance_info` | Gather information about Tencent Cloud CVM instances |
| `cwp_machine_info` | Gather information about Tencent Cloud CWP machines |
| `cws_monitor_info` | Gather information about Tencent Cloud CWS monitors |
| `cynosdb_cluster_info` | Gather information about TencentDB for CynosDB clusters |
| `dasb_device_info` | Gather information about Tencent Cloud DASB devices |
| `dataagent_chunk_info` | Gather information about Tencent Cloud DATAAGENT chunks |
| `dayu_resource_info` | Gather information about Tencent Cloud DAYU resources |
| `dbbrain_db_diag_event_info` | Gather information about Tencent Cloud DBBRAIN db diag events |
| `dbdc_db_custom_cluster_info` | Gather information about Tencent Cloud DBDC db custom clusters |
| `dbs_backup_plan_info` | Gather information about Tencent Cloud DBS backup plans |
| `dc_direct_connect_tunnel_info` | Gather information about Tencent Cloud DC direct connect tunnels |
| `dcdb_instance_info` | Gather information about Tencent Cloud DCDB instances |
| `dlc_task_info` | Gather information about Tencent Cloud DLC tasks |
| `dnspod_record_info` | Gather information about DNSPod records |
| `domain_batch_operation_log_info` | Gather information about Tencent Cloud DOMAIN batch operation logs |
| `dsgc_dspa_assessment_risk_info` | Gather information about Tencent Cloud DSGC dspa assessment risks |
| `dts_subscribe_job_info` | Gather information about Tencent Cloud DTS subscribe jobs |
| `eb_event_bus_info` | Gather information about Tencent Cloud EB event buses |
| `ecdn_domain_info` | Gather information about Tencent Cloud ECDN domains |
| `ecm_address_info` | Gather information about Tencent Cloud ECM addresses |
| `eiam_application_info` | Gather information about Tencent Cloud EIAM applications |
| `eip_info` | Gather information about Tencent Cloud elastic IP addresses (EIP) |
| `eis_runtime_deployed_instances_mc_info` | Gather information about Tencent Cloud EIS runtime deployed instances mcs |
| `emr_node_data_disk_info` | Gather information about Tencent Cloud EMR node data disks |
| `es_cluster_info` | Gather information about Tencent Cloud Elasticsearch clusters |
| `ess_file_url_info` | Gather information about Tencent Cloud ESS file urls |
| `essbasic_template_info` | Gather information about Tencent Cloud ESSBASIC templates |
| `facefusion_material_info` | Gather information about Tencent Cloud FACEFUSION materials |
| `faceid_we_chat_bill_info` | Gather information about Tencent Cloud FACEID we chat bills |
| `fmu_model_info` | Gather information about Tencent Cloud FMU models |
| `fwm_edge_acl_rule_info` | Gather information about Tencent Cloud FWM edge acl rules |
| `ga2_accelerate_area_info` | Gather information about Tencent Cloud GA2 accelerate areas |
| `gaap_proxy_info` | Gather information about Tencent Cloud GAAP proxies |
| `gme_voice_print_info` | Gather information about Tencent Cloud GME voice prints |
| `goosefs_file_system_info` | Gather information about Tencent Cloud GOOSEFS file systems |
| `gs_android_app_info` | Gather information about Tencent Cloud GS android apps |
| `gwlb_gateway_load_balancer_info` | Gather information about Tencent Cloud GWLB gateway load balancers |
| `hai_application_info` | Gather information about Tencent Cloud HAI applications |
| `hasim_link_info` | Gather information about Tencent Cloud HASIM links |
| `hunyuan_glossary_info` | Gather information about Tencent Cloud HUNYUAN glossaries |
| `iai_group_info` | Gather information about Tencent Cloud IAI groups |
| `iap_login_session_duration_info` | Gather information about Tencent Cloud IAP login session duration |
| `ic_sms_info` | Gather information about Tencent Cloud IC smses |
| `igtm_address_pool_info` | Gather information about Tencent Cloud IGTM address pools |
| `ioa_device_info` | Gather information about Tencent Cloud IOA devices |
| `iot_product_info` | Gather information about Tencent Cloud IOT products |
| `iotcloud_device_resource_info` | Gather information about Tencent Cloud IOTCLOUD device resources |
| `iotexplorer_device_position_info` | Gather information about Tencent Cloud IOTEXPLORER device positions |
| `iotvideo_ai_model_application_info` | Gather information about Tencent Cloud IOTVIDEO ai model applications |
| `iotvideoindustry_all_device_info` | Gather information about Tencent Cloud IOTVIDEOINDUSTRY all devices |
| `iss_device_snapshot_info` | Gather information about Tencent Cloud ISS device snapshots |
| `ivld_custom_person_info` | Gather information about Tencent Cloud IVLD custom persons |
| `keewidb_instance_backup_info` | Gather information about Tencent Cloud KEEWIDB instance backups |
| `key_pair_info` | Gather information about Tencent Cloud CVM key pairs |
| `kms_key_info` | Gather information about Tencent Cloud KMS keys |
| `lcic_answer_info` | Gather information about Tencent Cloud LCIC answers |
| `lighthouse_instance_info` | Gather information about Tencent Cloud Lighthouse instances |
| `live_audit_keyword_info` | Gather information about Tencent Cloud LIVE audit keywords |
| `lke_app_knowledge_info` | Gather information about Tencent Cloud LKE app knowledges |
| `lkeap_character_usage_info` | Gather information about Tencent Cloud LKEAP character usage |
| `lowcode_knowledge_set_info` | Gather information about Tencent Cloud LOWCODE knowledge sets |
| `mall_draw_resource_info` | Gather information about Tencent Cloud MALL draw resources |
| `mariadb_instance_info` | Gather information about TencentDB for MariaDB instances |
| `memcached_instance_info` | Gather information about Tencent Cloud MEMCACHED instances |
| `mmps_resource_usage_info` | Gather information about Tencent Cloud MMPS resource usages |
| `mna_access_region_info` | Gather information about Tencent Cloud MNA access regions |
| `mongodb_instance_info` | Gather information about TencentDB for MongoDB instances |
| `monitor_alarm_policy_info` | Gather information about Tencent Cloud Monitor alarm policies |
| `mps_person_sample_info` | Gather information about Tencent Cloud MPS person samples |
| `mqtt_device_certificate_info` | Gather information about Tencent Cloud MQTT device certificates |
| `ms_shield_instance_info` | Gather information about Tencent Cloud MS shield instances |
| `msp_migration_project_info` | Gather information about Tencent Cloud MSP migration projects |
| `nat_gateway_info` | Gather information about Tencent Cloud NAT gateways |
| `oceanus_cluster_info` | Gather information about Tencent Cloud OCEANUS clusters |
| `omics_application_info` | Gather information about Tencent Cloud OMICS applications |
| `organization_member_info` | Gather information about Tencent Cloud Organization members |
| `partners_agent_deals_by_cache_info` | Gather information about Tencent Cloud PARTNERS agent deals by caches |
| `portal_document_info` | Gather information about Tencent Cloud PORTAL documents |
| `postgres_instance_info` | Gather information about TencentDB for PostgreSQL instances |
| `privatedns_account_vpc_info` | Gather information about Tencent Cloud PRIVATEDNS account vpcs |
| `pts_cron_job_info` | Gather information about Tencent Cloud PTS cron jobs |
| `redis_instance_info` | Gather information about TencentDB for Redis instances |
| `region_product_info` | Gather information about Tencent Cloud REGION products |
| `route_table_info` | Gather information about Tencent Cloud VPC route tables |
| `rum_project_info` | Gather information about Tencent Cloud RUM projects |
| `scf_function_info` | Gather information about Tencent Cloud SCF functions |
| `security_group_info` | Gather information about Tencent Cloud security groups |
| `securitylake_security_alarm_table_info` | Gather information about Tencent Cloud SECURITYLAKE security alarm tables |
| `ses_black_email_address_info` | Gather information about Tencent Cloud SES black email addresses |
| `smh_library_info` | Gather information about Tencent Cloud SMH libraries |
| `sms_sign_info` | Gather information about Tencent Cloud SMS signs |
| `sqlserver_instance_info` | Gather information about TencentDB for SQL Server instances |
| `ssa_check_config_asset_info` | Gather information about Tencent Cloud SSA check config assets |
| `ssl_certificate_info` | Gather information about Tencent Cloud SSL certificates |
| `sslpod_domain_info` | Gather information about Tencent Cloud SSLPOD domains |
| `subnet_info` | Gather information about Tencent Cloud subnets |
| `svp_saving_plan_coverage_info` | Gather information about Tencent Cloud SVP saving plan coverages |
| `tat_command_info` | Gather information about Tencent Cloud TAT commands |
| `tbaas_block_info` | Gather information about Tencent Cloud TBAAS blocks |
| `tcaplusdb_cluster_info` | Gather information about Tencent Cloud TCAPLUSDB clusters |
| `tcb_billing_info` | Gather information about Tencent Cloud TCB billings |
| `tcbr_cloud_run_pod_info` | Gather information about Tencent Cloud TCBR cloud run pods |
| `tcm_mesh_info` | Gather information about Tencent Cloud TCM meshes |
| `tcr_instance_info` | Gather information about Tencent Cloud TCR registries |
| `tcss_abnormal_process_event_info` | Gather information about Tencent Cloud TCSS abnormal process events |
| `tdai_agent_duty_task_info` | Gather information about Tencent Cloud TDAI agent duty tasks |
| `tdcpg_cluster_instance_info` | Gather information about Tencent Cloud TDCPG cluster instances |
| `tdid_over_summary_info` | Gather information about Tencent Cloud TDID over summary |
| `tdmq_amqp_cluster_info` | Gather information about Tencent Cloud TDMQ amqp clusters |
| `tdmysql_db_instance_info` | Gather information about Tencent Cloud TDMYSQL db instances |
| `tem_application_info` | Gather information about Tencent Cloud TEM applications |
| `teo_function_info` | Gather information about Tencent Cloud TEO functions |
| `thpc_cluster_info` | Gather information about Tencent Cloud THPC clusters |
| `tia_job_info` | Gather information about Tencent Cloud TIA jobs |
| `tiia_group_info` | Gather information about Tencent Cloud TIIA groups |
| `tione_dataset_info` | Gather information about Tencent Cloud TIONE datasets |
| `tiw_running_task_info` | Gather information about Tencent Cloud TIW running tasks |
| `tke_cluster_info` | Gather information about Tencent Cloud TKE clusters |
| `tokenhub_model_info` | Gather information about Tencent Cloud TOKENHUB models |
| `tourism_draw_resource_info` | Gather information about Tencent Cloud TOURISM draw resources |
| `trabbit_rabbit_mq_serverless_instance_info` | Gather information about Tencent Cloud TRABBIT rabbit mq serverless instances |
| `trocket_consumer_client_info` | Gather information about Tencent Cloud TROCKET consumer clients |
| `trp_code_batch_info` | Gather information about Tencent Cloud TRP code batches |
| `trro_device_info` | Gather information about Tencent Cloud TRRO devices |
| `trtc_call_info` | Gather information about Tencent Cloud TRTC calls |
| `tse_sre_instance_info` | Gather information about Tencent Cloud TSE sre instances |
| `tsf_application_info` | Gather information about Tencent Cloud TSF applications |
| `vcube_resource_info` | Gather information about Tencent Cloud VCUBE resources |
| `vdb_instance_info` | Gather information about Tencent Cloud VDB instances |
| `vm_task_info` | Gather information about Tencent Cloud VM tasks |
| `vod_incremental_migration_strategy_info` | Gather information about Tencent Cloud VOD incremental migration strategies |
| `vpc_info` | Gather information about Tencent Cloud VPCs |
| `vpn_gateway_info` | Gather information about Tencent Cloud VPN gateways |
| `waf_instance_info` | Gather information about Tencent Cloud WAF instances |
| `wav_activity_info` | Gather information about Tencent Cloud WAV activities |
| `wedata_project_info` | Gather information about Tencent Cloud WEDATA projects |
| `weilingwith_element_profile_page_info` | Gather information about Tencent Cloud WEILINGWITH element profile pages |
| `wss_cert_info` | Gather information about Tencent Cloud WSS certs |
| `yinsuda_ktv_robot_info` | Gather information about Tencent Cloud YINSUDA ktv robots |
| `yunjing_account_statistic_info` | Gather information about Tencent Cloud YUNJING account statistics |

Most `_info` modules are generated from SDK metadata by
`scripts/generate_info_modules.py` (marked with a `# Generated by` comment;
run with `--check` to verify they are up to date). The module tables and the
`action_groups` registry are kept in sync with `scripts/sync_registry.py`
(`--check` runs in CI).

## Included plugins

| Plugin | Type | Purpose |
| --- | --- | --- |
| `tencentcloud_cvm` | inventory | Dynamic inventory of CVM instances with constructed groups and caching |
| `tencentcloud_clb` | inventory | Dynamic inventory of CLB load balancers, listeners and backend targets |
| `tencentcloud_sg` | inventory | Dynamic inventory of security groups and their associated network interfaces |
| `tat` | connection | Run commands and transfer files over the TAT agent (no SSH or public IP required) |
| `cls_topic` | event_source | Stream new log records from a CLS log topic (Event-Driven Ansible) |
| `cmq_queue` | event_source | Long-poll a CMQ queue and stream messages (Event-Driven Ansible) |
| `sts_caller_identity` | lookup | Return the current caller identity (Uin, AccountId, Arn) |
| `ssm_parameter` | lookup | Read secrets from Tencent Cloud Secrets Manager (SSM) |

## Included roles

| Role | Purpose |
| --- | --- |
| `tc_launch` | Launch CVM instances with sensible defaults over `cvm_instance` (`exact_count` / `count_tag` supported) |
| `tc_clb_http` | Create a CLB load balancer with HTTP listeners and backend targets in one call |

## Requirements

- ansible-core 2.16 or newer
- Python 3.10 or newer
- `tencentcloud-sdk-python` 3.0.1000 or newer
- `tencentcloud-sdk-python-tag` 3.0.1000 or newer (only for tag reconciliation)
- `tencentcloud-sdk-python-tat` 3.0.1000 or newer (only for the `tat` connection plugin)
- `cos-python-sdk-v5` 1.9.0 or newer (only for the `cos_*` modules)

Install from Ansible Galaxy:

```bash
ansible-galaxy collection install susunola.tencentcloud
```

Or install from source:

```bash
python -m pip install -r requirements.txt
ansible-galaxy collection build
ansible-galaxy collection install susunola-tencentcloud-*.tar.gz
```

## Authentication

Use environment variables (recommended):

```bash
export TENCENTCLOUD_SECRET_ID='...'
export TENCENTCLOUD_SECRET_KEY='...'
export TENCENTCLOUD_REGION='ap-guangzhou'
```

Temporary credentials can also set `TENCENTCLOUD_TOKEN`. Never commit keys.
Use `endpoint` for a private API endpoint or test double, and `timeout` to
control the SDK request timeout.

Credentials and region can also come from a TCCLI-style profile file at
`~/.tencentcloud/default.configure`; select a section with `profile` (or
`TENCENTCLOUD_PROFILE`, default `[default]`). Precedence is: module
parameter > environment variable > profile file.

```ini
# ~/.tencentcloud/default.configure
[default]
secret_id = ...
secret_key = ...
region = ap-guangzhou
```

To operate through a CAM role instead of long-lived keys, set `role_arn`
(or `TENCENTCLOUD_ROLE_ARN`); the modules exchange the base credentials for
temporary ones via STS AssumeRole before calling any other API:

```yaml
- susunola.tencentcloud.vpc:
    region: ap-guangzhou
    role_arn: qcs::cam::uin/1000000000:roleName/AnsibleDeploy
    state: present
    name: app-vpc
    cidr_block: 10.0.0.0/16
```

The `tencentcloud_cvm` inventory plugin reads the same environment variables:

```yaml
# inventory.tencentcloud_cvm.yml
plugin: susunola.tencentcloud.tencentcloud_cvm
regions:
  - ap-guangzhou
keyed_groups:
  - key: Placement.Zone
    prefix: zone
```

Run commands on instances without a public IP or reachable SSH port via the
TAT agent (requires the TAT agent on the target and
`tencentcloud-sdk-python-tat` on the controller):

```yaml
- hosts: all
  connection: susunola.tencentcloud.tat
  vars:
    ansible_tat_instance_id: "{{ inventory_hostname }}"
  tasks:
    - ansible.builtin.shell: uptime && df -h / | tail -1
```

Use the event sources from Event-Driven Ansible (ansible-rulebook) to react
to CLS logs or CMQ messages:

```yaml
# rulebook.yml
- name: react to error logs
  hosts: all
  sources:
    - susunola.tencentcloud.cls_topic:
        region: ap-guangzhou
        topic_id: "{{ topic_id }}"
        query: 'level:ERROR'
  rules:
    - name: page on error
      condition: event.cls.level == "ERROR"
      action:
        run_playbook:
          name: playbooks/on_error.yml
```

## Example

```yaml
- hosts: localhost
  gather_facts: false
  module_defaults:
    group/susunola.tencentcloud.all:
      region: ap-guangzhou
  tasks:
    - name: Ensure a security group exists
      susunola.tencentcloud.security_group:
        state: present
        name: web-sg
        description: Web tier security group
        tags:
          env: prod
```

All modules accept the shared options (`region`, `endpoint`, `timeout`,
credentials and `role_arn`); `module_defaults` with the
`group/susunola.tencentcloud.all` action group applies them once per play.

See [`docs/roadmap.md`](docs/roadmap.md) for the suggested implementation order.
Contributor conventions are in [`docs/development.md`](docs/development.md).

## Development

```bash
python -m pip install -r requirements-dev.txt
ansible-test sanity --python 3.13
ansible-test units --python 3.13
ansible-galaxy collection build
```

Integration tests require Tencent Cloud credentials and run only when
`TENCENTCLOUD_SECRET_ID` / `TENCENTCLOUD_SECRET_KEY` are set (see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Code of Conduct

This collection follows the [Ansible Community Code of Conduct](https://docs.ansible.com/ansible/latest/community/code_of_conduct.html).
See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for details.

## License

GNU General Public License v3.0 or later. See [`COPYING`](COPYING).
