# Tencent Cloud Ansible Collection

[![CI](https://github.com/susunola/ansible-collection-tencentcloud/actions/workflows/ci.yml/badge.svg)](https://github.com/susunola/ansible-collection-tencentcloud/actions/workflows/ci.yml)
[![Ansible Galaxy](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgalaxy.ansible.com%2Fapi%2Fv3%2Fcollections%2Fsusunola%2Ftencentcloud%2F&query=highest_version.version&label=Ansible%20Galaxy&color=blue)](https://galaxy.ansible.com/susunola/tencentcloud)

`susunola.tencentcloud` provides Ansible modules and plugins for managing Tencent
Cloud resources. It is developed as a community collection and is being
reviewed for inclusion in the `ansible` community package (tracked in
[issue #8](https://github.com/susunola/ansible-collection-tencentcloud/issues/8));
the repository stays under the `susunola` namespace.

## Included modules

Resource modules (idempotent, `state: present|absent`, check mode and diff):

| Module | Purpose |
| --- | --- |
| `alb_listener` | Manage Tencent Cloud ALB listeners |
| `alb_load_balancer` | Manage Tencent Cloud Application Load Balancers |
| `alb_target_group` | Manage Tencent Cloud ALB target groups |
| `alb_target_group_targets` | Reconcile Tencent Cloud ALB target group backends |
| `api_gateway_api` | Manage Tencent Cloud API Gateway APIs |
| `api_gateway_api_key` | Manage Tencent Cloud API Gateway API keys |
| `api_gateway_service` | Manage Tencent Cloud API Gateway services |
| `api_gateway_service_release` | Manage Tencent Cloud API Gateway service releases |
| `api_gateway_usage_plan` | Manage Tencent Cloud API Gateway usage plans |
| `api_gateway_usage_plan_binding` | Bind API Gateway usage plans to service environments or APIs |
| `api_gateway_usage_plan_key_binding` | Bind API Gateway keys to usage plans |
| `as_scaling_group` | Manage Tencent Cloud Auto Scaling groups |
| `as_scaling_policy` | Manage Tencent Cloud Auto Scaling policies |
| `as_scheduled_action` | Manage Tencent Cloud Auto Scaling scheduled actions |
| `cam_group` | Manage Tencent Cloud CAM user groups |
| `cam_group_membership` | Manage Tencent Cloud CAM user group membership |
| `cam_oidc_provider` | Manage Tencent Cloud CAM OIDC identity providers |
| `cam_policy` | Manage Tencent Cloud CAM policies |
| `cam_policy_attachment` | Manage a Tencent Cloud CAM policy attachment |
| `cam_role` | Manage Tencent Cloud CAM roles |
| `cam_saml_provider` | Manage Tencent Cloud CAM SAML identity providers |
| `cam_user` | Manage Tencent Cloud CAM sub-users |
| `cbs_auto_snapshot_policy` | Manage Tencent Cloud CBS automatic snapshot policies |
| `cbs_disk` | Manage Tencent Cloud CBS cloud disks |
| `cbs_disk_backup` | Manage Tencent Cloud CBS disk backup points |
| `cbs_snapshot` | Manage Tencent Cloud CBS disk snapshots |
| `cbs_snapshot_share` | Manage Tencent Cloud CBS snapshot sharing permissions |
| `ccn` | Manage Tencent Cloud Cloud Connect Networks |
| `ccn_attachment` | Attach network instances to Tencent Cloud CCN |
| `cdb_account` | Manage TencentDB for MySQL accounts |
| `cdb_account_privilege` | Manage TencentDB for MySQL account privileges |
| `cdb_audit_config` | Manage TencentDB for MySQL audit configuration |
| `cdb_backup_config` | Manage TencentDB for MySQL backup configuration |
| `cdb_database` | Manage databases in TencentDB for MySQL |
| `cdb_instance` | Manage Tencent Cloud CDB MySQL instances |
| `cdb_parameter_template` | Manage Tencent Cloud CDB parameter templates |
| `cdn_cls_log_topic` | Manage Tencent Cloud CDN real-time CLS log topics |
| `cdn_domain` | Manage Tencent Cloud CDN domains |
| `cdwch_instance` | Manage Tencent Cloud TCHouse-C instances |
| `cdwdoris_instance` | Manage Tencent Cloud CDW Doris instances |
| `cdwpg_instance` | Manage Tencent Cloud CDW PostgreSQL instances |
| `cfs_auto_snapshot_policy` | Manage Tencent Cloud CFS automatic snapshot policies |
| `cfs_file_system` | Manage Tencent Cloud CFS file systems |
| `cfs_permission_group` | Manage Tencent Cloud CFS permission groups |
| `cfs_permission_rule` | Manage Tencent Cloud CFS permission rules |
| `cfs_snapshot` | Manage Tencent Cloud CFS snapshots |
| `cfw_address_template` | Manage Tencent Cloud Cloud Firewall address templates |
| `cfw_internet_acl_rule` | Manage Tencent Cloud Cloud Firewall internet border ACL rules |
| `cfw_nat_acl_rule` | Manage Tencent Cloud Cloud Firewall NAT access-control rules |
| `cfw_nat_dnat_rule` | Manage Tencent Cloud Cloud Firewall NAT DNAT rules |
| `cfw_vpc_acl_rule` | Manage Tencent Cloud Cloud Firewall inter-VPC ACL rules |
| `chdfs_access_group` | Manage Tencent Cloud CHDFS access groups |
| `chdfs_access_rules` | Reconcile Tencent Cloud CHDFS access rules |
| `chdfs_file_system` | Manage Tencent Cloud CHDFS file systems |
| `chdfs_mount_access_groups` | Reconcile CHDFS mount point access-group bindings |
| `chdfs_mount_point` | Manage Tencent Cloud CHDFS mount points |
| `ckafka_acl` | Manage Tencent Cloud CKafka ACL entries |
| `ckafka_acl_rule` | Manage Tencent Cloud CKafka ACL rules |
| `ckafka_datahub_connection` | Manage Tencent Cloud CKafka Datahub connection resources |
| `ckafka_datahub_task` | Manage Tencent Cloud CKafka Datahub tasks |
| `ckafka_datahub_topic` | Manage Tencent Cloud CKafka Datahub topics |
| `ckafka_instance` | Manage Tencent Cloud CKafka instances |
| `ckafka_route` | Manage Tencent Cloud CKafka access routes |
| `ckafka_topic` | Manage Tencent Cloud CKafka topics |
| `ckafka_user` | Manage Tencent Cloud CKafka users |
| `clb_listener` | Manage listeners on Tencent Cloud CLB load balancers |
| `clb_listener_target` | Manage backend targets of Tencent Cloud CLB listeners |
| `clb_load_balancer` | Manage Tencent Cloud CLB load balancers |
| `clb_rule` | Manage Tencent Cloud CLB L7 forwarding rules |
| `clb_target_group` | Manage Tencent Cloud CLB target groups and members |
| `cloudaudit_audit` | Manage Tencent Cloud account-level CloudAudit delivery |
| `cloudaudit_track` | Manage Tencent Cloud CloudAudit tracks |
| `cls_config` | Manage Tencent Cloud CLS collection configurations |
| `cls_config_machine_group_binding` | Bind CLS collection configurations to machine groups |
| `cls_index` | Manage Tencent Cloud CLS topic indexes |
| `cls_logset` | Manage Tencent Cloud CLS logsets |
| `cls_machine_group` | Manage Tencent Cloud CLS machine groups |
| `cls_shipper` | Manage Tencent Cloud CLS delivery tasks to COS |
| `cls_topic` | Manage Tencent Cloud CLS topics |
| `cmq_queue` | Manage Tencent Cloud CMQ queues |
| `cmq_subscription` | Manage Tencent Cloud CMQ topic subscriptions |
| `cmq_topic` | Manage Tencent Cloud CMQ topics |
| `config_aggregate_delivery` | Manage Tencent Cloud Config cross-account aggregate delivery |
| `config_aggregator` | Manage creation of Tencent Cloud Config account aggregators |
| `config_alarm_policy` | Manage Tencent Cloud Config alarm policies |
| `config_compliance_pack` | Manage Tencent Cloud Config compliance packs |
| `config_delivery` | Manage Tencent Cloud Config delivery settings |
| `config_recorder` | Manage Tencent Cloud Config resource recorder |
| `config_remediation` | Manage Tencent Cloud Config remediation settings |
| `config_rule` | Manage Tencent Cloud Config compliance rules |
| `cos_bucket` | Manage Tencent Cloud COS buckets |
| `cos_bucket_domain` | Manage Tencent Cloud COS custom domains |
| `cos_bucket_domain_certificate` | Manage Tencent Cloud COS custom-domain certificates |
| `cos_bucket_encryption` | Manage Tencent Cloud COS default bucket encryption |
| `cos_bucket_intelligent_tiering` | Manage Tencent Cloud COS bucket intelligent tiering |
| `cos_bucket_inventory` | Manage Tencent Cloud COS bucket inventory rules |
| `cos_bucket_logging` | Manage Tencent Cloud COS bucket access logging |
| `cos_bucket_object_lock` | Manage Tencent Cloud COS bucket object lock |
| `cos_bucket_origin` | Manage Tencent Cloud COS bucket origin rules |
| `cos_bucket_policy` | Manage Tencent Cloud COS bucket policies |
| `cos_bucket_referer` | Manage Tencent Cloud COS hotlink protection |
| `cos_bucket_replication` | Manage Tencent Cloud COS bucket replication |
| `cos_bucket_response_control` | Manage Tencent Cloud COS response-header controls |
| `cos_bucket_website` | Manage Tencent Cloud COS static website configuration |
| `cos_object` | Manage Tencent Cloud COS objects |
| `cos_object_sync` | Mirror a local directory tree into a Tencent Cloud COS bucket |
| `customer_gateway` | Manage Tencent Cloud VPN customer gateways |
| `cvm_chc` | Manage Tencent Cloud CHC physical server network configuration |
| `cvm_disaster_recover_group` | Manage Tencent Cloud CVM placement groups |
| `cvm_disaster_recover_group_binding` | Bind a Tencent Cloud CVM instance to a placement group |
| `cvm_hpc_cluster` | Manage Tencent Cloud CVM high-performance clusters |
| `cvm_image` | Manage Tencent Cloud CVM custom images |
| `cvm_image_share` | Manage Tencent Cloud CVM image sharing permissions |
| `cvm_instance` | Manage Tencent Cloud CVM instances |
| `cvm_instance_action_timer` | Manage Tencent Cloud CVM instance action timers |
| `cvm_instance_security_group` | Manage the security groups bound to a Tencent Cloud CVM instance |
| `cvm_launch_template` | Manage Tencent Cloud CVM launch templates |
| `cvm_launch_template_version` | Manage Tencent Cloud CVM launch-template versions |
| `cynosdb_account` | Manage Tencent Cloud CynosDB accounts |
| `cynosdb_account_privilege` | Manage Tencent Cloud CynosDB account privileges |
| `cynosdb_backup_config` | Manage Tencent Cloud CynosDB backup configuration |
| `cynosdb_cluster` | Manage Tencent Cloud CynosDB clusters |
| `dbbrain_sql_filter` | Manage Tencent Cloud DBbrain SQL filters |
| `dbdc_db_custom_cluster` | Manage Tencent Cloud DB Custom clusters |
| `dc_direct_connect` | Manage Tencent Cloud physical Direct Connect circuits |
| `dc_direct_connect_tunnel` | Manage Tencent Cloud Direct Connect tunnels |
| `dcdb_instance` | Manage Tencent Cloud DCDB instances |
| `dnspod_custom_line` | Manage DNSPod domain custom lines |
| `dnspod_domain` | Manage Tencent Cloud DNSPod domains |
| `dnspod_line_group` | Manage DNSPod custom line groups |
| `dnspod_record` | Manage Tencent Cloud DNSPod DNS records |
| `dts_consumer_group` | Manage Tencent Cloud DTS consumer groups |
| `dts_migration_job` | Manage Tencent Cloud DTS migration jobs |
| `eb_connection` | Manage Tencent Cloud EventBridge connections |
| `eb_event_bus` | Manage Tencent Cloud EventBridge event buses |
| `eb_rule` | Manage Tencent Cloud EventBridge rules |
| `eb_target` | Manage Tencent Cloud EventBridge rule targets |
| `eip` | Manage Tencent Cloud elastic IP addresses (EIP) |
| `eks_cluster` | Manage Tencent Cloud EKS clusters |
| `eks_container_instance` | Manage Tencent Cloud EKS container instances |
| `elasticsearch_index` | Manage indexes in Tencent Cloud Elasticsearch Service |
| `elasticsearch_instance` | Manage Tencent Cloud Elasticsearch clusters |
| `elasticsearch_snapshot` | Manage Tencent Cloud Elasticsearch cluster snapshots |
| `emr_cluster` | Manage Tencent Cloud EMR clusters |
| `gaap_proxy` | Manage Tencent Cloud GAAP proxies |
| `goosefs_file_system` | Manage Tencent Cloud GooseFS file systems |
| `goosefs_fileset` | Manage Tencent Cloud GooseFS filesets |
| `gwlb_load_balancer` | Manage Tencent Cloud Gateway Load Balancers |
| `gwlb_target_group` | Manage Tencent Cloud GWLB target groups |
| `gwlb_target_group_association` | Manage Tencent Cloud GWLB target group associations |
| `gwlb_target_group_instances` | Reconcile Tencent Cloud GWLB target group instances |
| `havip` | Manage Tencent Cloud VPC high-availability virtual IPs |
| `havip_association` | Manage Tencent Cloud HAVIP drift-scope associations |
| `key_pair` | Manage Tencent Cloud CVM key pairs |
| `kms_key` | Manage a Tencent Cloud KMS key |
| `kms_key_rotation` | Manage automatic rotation for a Tencent Cloud KMS key |
| `lighthouse_disk` | Manage Tencent Cloud Lighthouse data disks |
| `lighthouse_firewall_rules` | Manage Tencent Cloud Lighthouse instance firewall rules |
| `lighthouse_instance` | Manage Tencent Cloud Lighthouse instances |
| `lighthouse_key_pair` | Manage imported Tencent Cloud Lighthouse SSH key pairs |
| `lighthouse_snapshot` | Manage Tencent Cloud Lighthouse instance snapshots |
| `mariadb_account` | Manage TencentDB for MariaDB accounts |
| `mariadb_account_privilege` | Manage a scoped TencentDB for MariaDB account privilege set |
| `mariadb_backup_config` | Manage TencentDB for MariaDB automatic backup configuration |
| `mariadb_instance` | Manage Tencent Cloud MariaDB instances |
| `mongodb_account` | Manage TencentDB for MongoDB accounts |
| `mongodb_backup_config` | Manage TencentDB for MongoDB automatic backup rules |
| `mongodb_instance` | Manage Tencent Cloud MongoDB instances |
| `monitor_alarm_policy` | Manage a Tencent Cloud Monitor alarm policy |
| `monitor_alarm_policy_notice` | Manage notification bindings for a Cloud Monitor alarm policy |
| `monitor_grafana_instance` | Manage Tencent Cloud Managed Grafana instances |
| `monitor_grafana_integration` | Manage Tencent Cloud Managed Grafana integrations |
| `monitor_grafana_internet` | Manage internet access for Tencent Cloud Managed Grafana |
| `monitor_grafana_notification_channel` | Manage Tencent Cloud Managed Grafana notification channels |
| `monitor_grafana_whitelist` | Manage a Tencent Cloud Managed Grafana IP whitelist |
| `monitor_prometheus_alert_group` | Manage Tencent Cloud Managed Prometheus alert groups |
| `monitor_prometheus_alertmanager_config` | Manage Managed Prometheus Alertmanager configuration |
| `monitor_prometheus_cluster_agent` | Manage Managed Prometheus cluster agents |
| `monitor_prometheus_global_notification` | Manage Managed Prometheus global notification settings |
| `monitor_prometheus_grafana_binding` | Bind Managed Prometheus and Grafana instances |
| `monitor_prometheus_instance` | Manage Tencent Cloud pay-as-you-go Managed Prometheus instances |
| `monitor_prometheus_record_rule` | Manage Tencent Cloud Managed Prometheus recording rules |
| `monitor_prometheus_scrape_job` | Manage Tencent Cloud Managed Prometheus scrape jobs |
| `mqtt_authorization_policy` | Manage Tencent Cloud MQTT authorization policies |
| `mqtt_instance` | Manage Tencent Cloud MQTT instances |
| `mqtt_topic` | Manage Tencent Cloud MQTT topics |
| `mqtt_user` | Manage Tencent Cloud MQTT users |
| `nat_gateway` | Manage Tencent Cloud NAT gateways |
| `nat_gateway_rule` | Manage Tencent Cloud NAT gateway DNAT and SNAT rules |
| `network_acl` | Manage Tencent Cloud VPC network ACLs |
| `network_interface` | Manage Tencent Cloud elastic network interfaces |
| `oceanus_job` | Manage Tencent Cloud Oceanus jobs |
| `oceanus_workspace` | Manage Tencent Cloud Oceanus workspaces |
| `organization_member` | Manage Tencent Cloud Organization members |
| `organization_member_identity` | Reconcile Tencent Cloud Organization member identities |
| `organization_member_policy` | Manage Tencent Cloud Organization member access policies |
| `organization_node` | Manage Tencent Cloud Organization nodes |
| `peering_connection` | Manage Tencent Cloud VPC peering connections |
| `postgresql_account` | Manage TencentDB for PostgreSQL accounts |
| `postgresql_backup_plan` | Manage TencentDB for PostgreSQL backup plans |
| `postgresql_instance` | Manage Tencent Cloud PostgreSQL instances |
| `postgresql_parameter_template` | Manage Tencent Cloud PostgreSQL parameter templates |
| `private_dns_record` | Manage a Tencent Cloud Private DNS record |
| `private_dns_zone` | Manage a Tencent Cloud Private DNS zone |
| `privatelink_endpoint` | Manage Tencent Cloud PrivateLink endpoints |
| `privatelink_endpoint_service` | Manage Tencent Cloud PrivateLink endpoint services |
| `redis_account` | Manage TencentDB for Redis accounts |
| `redis_backup_config` | Manage TencentDB for Redis automatic backup configuration |
| `redis_instance` | Manage Tencent Cloud Redis instances |
| `redis_parameter_template` | Manage Tencent Cloud Redis parameter templates |
| `route_table` | Manage Tencent Cloud VPC route tables |
| `scf_alias` | Manage Tencent Cloud SCF function aliases |
| `scf_function` | Manage Tencent Cloud SCF functions |
| `scf_trigger` | Manage Tencent Cloud SCF triggers |
| `scf_version` | Manage Tencent Cloud SCF function versions |
| `security_group` | Manage Tencent Cloud security groups |
| `security_group_rule` | Manage Tencent Cloud security group rules |
| `sms_signature` | Manage Tencent Cloud SMS signatures |
| `sms_template` | Manage Tencent Cloud SMS templates |
| `sqlserver_account` | Manage TencentDB for SQL Server accounts |
| `sqlserver_backup_config` | Manage TencentDB for SQL Server backup configuration |
| `sqlserver_instance` | Manage TencentDB for SQL Server instances |
| `ssl_certificate` | Manage Tencent Cloud SSL certificates |
| `ssm_parameter` | Manage Tencent Cloud SSM secrets (parameters) |
| `ssm_rotation` | Manage Tencent Cloud SSM secret rotation settings |
| `ssm_secret` | Manage Tencent Cloud Secrets Manager custom secrets |
| `ssm_secret_version` | Manage Tencent Cloud SSM secret versions |
| `subnet` | Manage Tencent Cloud VPC subnets |
| `tag` | Manage tags on arbitrary Tencent Cloud resources |
| `tat_command` | Manage Tencent Cloud TAT commands |
| `tat_invoker` | Manage Tencent Cloud TAT scheduled invokers |
| `tcaplusdb_cluster` | Manage Tencent Cloud TcaplusDB clusters |
| `tcb_environment` | Manage Tencent CloudBase environments |
| `tcb_http_service_route` | Manage Tencent CloudBase HTTP service domain routes |
| `tcm_mesh` | Manage Tencent Cloud Mesh instances |
| `tcm_mesh_clusters` | Reconcile Tencent Cloud Mesh cluster links |
| `tcr_instance` | Manage Tencent Cloud TCR enterprise instances |
| `tcr_namespace` | Manage Tencent Cloud TCR namespaces |
| `tcr_replication_instance` | Manage Tencent Cloud TCR replication instances |
| `tcr_replication_rule` | Manage Tencent Cloud TCR replication rules |
| `tcr_repository` | Manage a Tencent Cloud TCR repository |
| `tdcpg_cluster` | Manage Tencent Cloud TDSQL-C PostgreSQL clusters |
| `tdmq_namespace` | Manage Tencent Cloud TDMQ Pulsar namespaces |
| `tdmq_namespace_role` | Manage TDMQ Pulsar namespace role permissions |
| `tdmq_rabbitmq_binding` | Manage TDMQ RabbitMQ bindings |
| `tdmq_rabbitmq_instance` | Manage Tencent Cloud TDMQ RabbitMQ dedicated instances |
| `tdmq_rabbitmq_permission` | Manage TDMQ RabbitMQ virtual host permissions |
| `tdmq_rabbitmq_user` | Manage TDMQ RabbitMQ users |
| `tdmq_rabbitmq_vhost` | Manage TDMQ RabbitMQ virtual hosts |
| `tdmq_rocketmq_cluster` | Manage TDMQ RocketMQ clusters |
| `tdmq_rocketmq_group` | Manage TDMQ RocketMQ consumer groups |
| `tdmq_rocketmq_namespace` | Manage TDMQ RocketMQ namespaces |
| `tdmq_rocketmq_permission` | Manage TDMQ RocketMQ namespace role permissions |
| `tdmq_rocketmq_role` | Manage TDMQ RocketMQ roles |
| `tdmq_rocketmq_topic` | Manage TDMQ RocketMQ topics |
| `tdmq_subscription` | Manage Tencent Cloud TDMQ Pulsar subscriptions |
| `tdmq_topic` | Manage Tencent Cloud TDMQ Pulsar topics |
| `tdmysql_db_instance` | Manage Tencent Cloud TDMysql instances |
| `tem_application` | Manage Tencent Cloud TEM applications |
| `tem_application_deployment` | Deploy Tencent Cloud TEM application versions |
| `tem_application_service` | Manage Tencent Cloud TEM application access services |
| `tem_environment` | Manage Tencent Cloud TEM environments |
| `teo_acceleration_domain` | Manage Tencent Cloud EdgeOne acceleration domains |
| `teo_dns_record` | Manage Tencent Cloud TEO DNS records |
| `teo_origin_group` | Manage Tencent Cloud EdgeOne origin groups |
| `teo_security_bot_lite` | Manage Tencent Cloud EdgeOne basic Bot protection |
| `teo_security_custom_rules` | Manage Tencent Cloud EdgeOne web security custom rules |
| `teo_security_exception_rules` | Manage Tencent Cloud EdgeOne web security exception rules |
| `teo_security_ip_group` | Manage Tencent Cloud EdgeOne security IP groups |
| `teo_security_managed_rules` | Manage Tencent Cloud EdgeOne managed WAF rules |
| `teo_security_rate_limiting_rules` | Manage Tencent Cloud EdgeOne precise rate-limiting rules |
| `teo_security_template_binding` | Manage Tencent Cloud EdgeOne security template bindings |
| `teo_web_security_template` | Manage Tencent Cloud EdgeOne web security templates |
| `teo_zone` | Manage Tencent Cloud EdgeOne zones |
| `thpc_cluster` | Manage Tencent Cloud THPC clusters |
| `tke_addon` | Manage a Tencent Kubernetes Engine addon |
| `tke_backup_storage_location` | Manage Tencent Kubernetes Engine backup storage locations |
| `tke_cluster` | Manage Tencent Cloud TKE clusters |
| `tke_cluster_audit` | Manage Tencent Cloud TKE cluster audit logging |
| `tke_cluster_authentication` | Manage Tencent Cloud TKE cluster authentication options |
| `tke_cluster_autoscaler` | Manage the cluster autoscaler options of a Tencent Cloud TKE cluster |
| `tke_cluster_endpoint` | Manage Tencent Cloud TKE cluster access endpoints |
| `tke_cluster_upgrade` | Upgrade the Kubernetes version of a Tencent Cloud TKE cluster |
| `tke_node_pool` | Manage Tencent Cloud TKE cluster node pools |
| `trabbit_serverless_binding` | Manage Tencent Cloud RabbitMQ Serverless bindings |
| `trabbit_serverless_exchange` | Manage Tencent Cloud RabbitMQ Serverless exchanges |
| `trabbit_serverless_permission` | Manage Tencent Cloud RabbitMQ Serverless permissions |
| `trabbit_serverless_queue` | Manage Tencent Cloud RabbitMQ Serverless queues |
| `trabbit_serverless_user` | Manage Tencent Cloud RabbitMQ Serverless users |
| `trabbit_serverless_vhost` | Manage Tencent Cloud RabbitMQ Serverless virtual hosts |
| `tse_sre_instance` | Manage Tencent Cloud TSE service registry engines |
| `vdb_instance` | Manage Tencent Cloud VectorDB instances |
| `vod_class` | Manage Tencent Cloud VOD media classes |
| `vod_sub_app` | Manage Tencent Cloud VOD sub-applications |
| `vpc` | Manage Tencent Cloud VPCs |
| `vpc_address_template` | Manage Tencent Cloud VPC address templates |
| `vpc_address_template_group` | Manage Tencent Cloud VPC address-template groups |
| `vpc_flow_log` | Manage Tencent Cloud VPC flow logs |
| `vpn_connection` | Manage Tencent Cloud IPsec VPN connections |
| `vpn_gateway` | Manage Tencent Cloud VPN gateways |
| `waf_anti_info_leak_rule` | Manage Tencent Cloud WAF sensitive-information leakage rules |
| `waf_anti_tamper_rule` | Manage Tencent Cloud WAF anti-tamper URL rules |
| `waf_area_ban_rule` | Manage Tencent Cloud WAF geographic blocking |
| `waf_attack_white_rule` | Manage Tencent Cloud WAF attack-signature allow rules |
| `waf_auto_deny` | Manage Tencent Cloud WAF automatic IP blocking |
| `waf_cc_rule` | Manage Tencent Cloud WAF CC protection rules |
| `waf_custom_rule` | Manage Tencent Cloud WAF custom rules |
| `waf_custom_white_rule` | Manage Tencent Cloud WAF precision allowlist rules |
| `waf_host` | Manage Tencent Cloud WAF protected hosts |
| `waf_ip_access_control` | Manage Tencent Cloud WAF IP access-control rules |
| `waf_owasp_white_rule` | Manage Tencent Cloud WAF OWASP allowlist rules |
| `waf_protect_group` | Manage Tencent Cloud WAF protection object groups |
| `waf_threat_intelligence` | Manage Tencent Cloud WAF threat-intelligence blocking |

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
| `cos_object_info` | Gather information about Tencent Cloud COS objects |
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

- ansible-core 2.19 or newer
- Python 3.11 or newer
- `tencentcloud-sdk-python` 3.1.164 or newer
- `tencentcloud-sdk-python-tag` 3.1.164 or newer (only for tag reconciliation)
- `tencentcloud-sdk-python-tat` 3.1.164 or newer (only for the `tat` connection plugin)
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
