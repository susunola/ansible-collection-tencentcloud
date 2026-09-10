# Tencent Cloud Ansible Collection

[![CI](https://github.com/susunola/ansible-collection-tencentcloud/actions/workflows/ci.yml/badge.svg)](https://github.com/susunola/ansible-collection-tencentcloud/actions/workflows/ci.yml)
[![Ansible Galaxy](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgalaxy.ansible.com%2Fapi%2Fv3%2Fcollections%2Fsusunola%2Ftencentcloud%2F&query=highest_version.version&label=Ansible%20Galaxy&color=blue)](https://galaxy.ansible.com/susunola/tencentcloud)

`susunola.tencentcloud` provides Ansible modules and plugins for managing Tencent
Cloud resources. It is developed as a community collection targeting inclusion
in the `ansible-collections` GitHub organization.

## Capability overview

The collection covers **204 Tencent Cloud product domains** through **875 modules**,
including **440 resource modules**, **435 read-only `_info` modules**, and **68
reusable roles**. The README highlights how to navigate the collection instead of
rendering the entire catalog by default.

| Start with | Typical products | Where to explore |
| --- | --- | --- |
| Compute and containers | CVM, Lighthouse, TKE, EKS, TCR, Auto Scaling | [Module index](plugins/modules/) · [Reusable roles](#included-roles) |
| Network and edge | VPC, CLB, ALB, GWLB, CCN, VPN, CDN, EdgeOne, DNSPod | [Product capability matrix](docs/product-capabilities.md) |
| Databases and storage | CDB, CynosDB, Redis, MongoDB, PostgreSQL, COS, CBS, CFS | [Product capability matrix](docs/product-capabilities.md) |
| Security and governance | CAM, KMS, SSM, WAF, Cloud Firewall, Config, CloudAudit | [Solution scenarios](docs/scenarios.md) |
| Data, AI and integration | DLC, Oceanus, EMR, TI-ONE, CKafka, TDMQ, EventBridge | [Capability panorama](docs/panorama.html) |
| Operations | CLS, Monitor, Prometheus, Grafana, TAT, dynamic inventory | [Plugins](#included-plugins) |

For exact module names, maturity, write/read coverage, and role availability, use
the generated [product capability matrix](docs/product-capabilities.md). It is the
canonical catalog and stays synchronized with the collection.

<details>
<summary><strong>Browse all 440 resource modules</strong></summary>

Resource modules are idempotent and support `state: present|absent`, check mode,
and diff unless their individual documentation states otherwise.

| Module (FQCN) | Purpose | Examples |
| --- | --- | --- |
| `susunola.tencentcloud.alb_listener` | Manage Tencent Cloud ALB listeners | [`alb_listener`](plugins/modules/alb_listener.py) |
| `susunola.tencentcloud.alb_load_balancer` | Manage Tencent Cloud Application Load Balancers | [`alb_load_balancer`](plugins/modules/alb_load_balancer.py) |
| `susunola.tencentcloud.alb_target_group` | Manage Tencent Cloud ALB target groups | [`alb_target_group`](plugins/modules/alb_target_group.py) |
| `susunola.tencentcloud.alb_target_group_targets` | Reconcile Tencent Cloud ALB target group backends | [`alb_target_group_targets`](plugins/modules/alb_target_group_targets.py) |
| `susunola.tencentcloud.api_gateway_api` | Manage Tencent Cloud API Gateway APIs | [`api_gateway_api`](plugins/modules/api_gateway_api.py) |
| `susunola.tencentcloud.api_gateway_api_key` | Manage Tencent Cloud API Gateway API keys | [`api_gateway_api_key`](plugins/modules/api_gateway_api_key.py) |
| `susunola.tencentcloud.api_gateway_service` | Manage Tencent Cloud API Gateway services | [`api_gateway_service`](plugins/modules/api_gateway_service.py) |
| `susunola.tencentcloud.api_gateway_service_release` | Manage Tencent Cloud API Gateway service releases | [`api_gateway_service_release`](plugins/modules/api_gateway_service_release.py) |
| `susunola.tencentcloud.api_gateway_usage_plan` | Manage Tencent Cloud API Gateway usage plans | [`api_gateway_usage_plan`](plugins/modules/api_gateway_usage_plan.py) |
| `susunola.tencentcloud.api_gateway_usage_plan_binding` | Bind API Gateway usage plans to service environments or APIs | [`api_gateway_usage_plan_binding`](plugins/modules/api_gateway_usage_plan_binding.py) |
| `susunola.tencentcloud.api_gateway_usage_plan_key_binding` | Bind API Gateway keys to usage plans | [`api_gateway_usage_plan_key_binding`](plugins/modules/api_gateway_usage_plan_key_binding.py) |
| `susunola.tencentcloud.as_scaling_group` | Manage Tencent Cloud Auto Scaling groups | [`as_scaling_group`](plugins/modules/as_scaling_group.py) |
| `susunola.tencentcloud.as_scaling_policy` | Manage Tencent Cloud Auto Scaling policies | [`as_scaling_policy`](plugins/modules/as_scaling_policy.py) |
| `susunola.tencentcloud.as_scheduled_action` | Manage Tencent Cloud Auto Scaling scheduled actions | [`as_scheduled_action`](plugins/modules/as_scheduled_action.py) |
| `susunola.tencentcloud.cam_group` | Manage Tencent Cloud CAM user groups | [`cam_group`](plugins/modules/cam_group.py) |
| `susunola.tencentcloud.cam_group_membership` | Manage Tencent Cloud CAM user group membership | [`cam_group_membership`](plugins/modules/cam_group_membership.py) |
| `susunola.tencentcloud.cam_oidc_provider` | Manage Tencent Cloud CAM OIDC identity providers | [`cam_oidc_provider`](plugins/modules/cam_oidc_provider.py) |
| `susunola.tencentcloud.cam_policy` | Manage Tencent Cloud CAM policies | [`cam_policy`](plugins/modules/cam_policy.py) |
| `susunola.tencentcloud.cam_policy_attachment` | Manage a Tencent Cloud CAM policy attachment | [`cam_policy_attachment`](plugins/modules/cam_policy_attachment.py) |
| `susunola.tencentcloud.cam_role` | Manage Tencent Cloud CAM roles | [`cam_role`](plugins/modules/cam_role.py) |
| `susunola.tencentcloud.cam_saml_provider` | Manage Tencent Cloud CAM SAML identity providers | [`cam_saml_provider`](plugins/modules/cam_saml_provider.py) |
| `susunola.tencentcloud.cam_user` | Manage Tencent Cloud CAM sub-users | [`cam_user`](plugins/modules/cam_user.py) |
| `susunola.tencentcloud.cbs_auto_snapshot_policy` | Manage Tencent Cloud CBS automatic snapshot policies | [`cbs_auto_snapshot_policy`](plugins/modules/cbs_auto_snapshot_policy.py) |
| `susunola.tencentcloud.cbs_disk` | Manage Tencent Cloud CBS cloud disks | [`cbs_disk`](plugins/modules/cbs_disk.py) |
| `susunola.tencentcloud.cbs_disk_backup` | Manage Tencent Cloud CBS disk backup points | [`cbs_disk_backup`](plugins/modules/cbs_disk_backup.py) |
| `susunola.tencentcloud.cbs_snapshot` | Manage Tencent Cloud CBS disk snapshots | [`cbs_snapshot`](plugins/modules/cbs_snapshot.py) |
| `susunola.tencentcloud.cbs_snapshot_share` | Manage Tencent Cloud CBS snapshot sharing permissions | [`cbs_snapshot_share`](plugins/modules/cbs_snapshot_share.py) |
| `susunola.tencentcloud.ccn` | Manage Tencent Cloud Cloud Connect Networks | [`ccn`](plugins/modules/ccn.py) |
| `susunola.tencentcloud.ccn_attachment` | Attach network instances to Tencent Cloud CCN | [`ccn_attachment`](plugins/modules/ccn_attachment.py) |
| `susunola.tencentcloud.cdb_account` | Manage TencentDB for MySQL accounts | [`cdb_account`](plugins/modules/cdb_account.py) |
| `susunola.tencentcloud.cdb_account_privilege` | Manage TencentDB for MySQL account privileges | [`cdb_account_privilege`](plugins/modules/cdb_account_privilege.py) |
| `susunola.tencentcloud.cdb_audit_config` | Manage TencentDB for MySQL audit configuration | [`cdb_audit_config`](plugins/modules/cdb_audit_config.py) |
| `susunola.tencentcloud.cdb_backup_config` | Manage TencentDB for MySQL backup configuration | [`cdb_backup_config`](plugins/modules/cdb_backup_config.py) |
| `susunola.tencentcloud.cdb_database` | Manage databases in TencentDB for MySQL | [`cdb_database`](plugins/modules/cdb_database.py) |
| `susunola.tencentcloud.cdb_instance` | Manage Tencent Cloud CDB MySQL instances | [`cdb_instance`](plugins/modules/cdb_instance.py) |
| `susunola.tencentcloud.cdb_parameter_template` | Manage Tencent Cloud CDB parameter templates | [`cdb_parameter_template`](plugins/modules/cdb_parameter_template.py) |
| `susunola.tencentcloud.cdn_cls_log_topic` | Manage Tencent Cloud CDN real-time CLS log topics | [`cdn_cls_log_topic`](plugins/modules/cdn_cls_log_topic.py) |
| `susunola.tencentcloud.cdn_domain` | Manage Tencent Cloud CDN domains | [`cdn_domain`](plugins/modules/cdn_domain.py) |
| `susunola.tencentcloud.cdwch_backup_config` | Manage Tencent Cloud CDW ClickHouse backup configuration | [`cdwch_backup_config`](plugins/modules/cdwch_backup_config.py) |
| `susunola.tencentcloud.cdwch_instance` | Manage Tencent Cloud TCHouse-C instances | [`cdwch_instance`](plugins/modules/cdwch_instance.py) |
| `susunola.tencentcloud.cdwch_parameter` | Manage a Tencent Cloud CDW ClickHouse instance parameter | [`cdwch_parameter`](plugins/modules/cdwch_parameter.py) |
| `susunola.tencentcloud.cdwdoris_cooldown_policy` | Manage a Tencent Cloud CDW Doris cooldown policy | [`cdwdoris_cooldown_policy`](plugins/modules/cdwdoris_cooldown_policy.py) |
| `susunola.tencentcloud.cdwdoris_instance` | Manage Tencent Cloud CDW Doris instances | [`cdwdoris_instance`](plugins/modules/cdwdoris_instance.py) |
| `susunola.tencentcloud.cdwdoris_user_workload_group` | Bind a Tencent Cloud CDW Doris user to a workload group | [`cdwdoris_user_workload_group`](plugins/modules/cdwdoris_user_workload_group.py) |
| `susunola.tencentcloud.cdwdoris_workload_group` | Manage Tencent Cloud CDW Doris workload groups | [`cdwdoris_workload_group`](plugins/modules/cdwdoris_workload_group.py) |
| `susunola.tencentcloud.cdwpg_hba_config` | Manage Tencent Cloud CDW PostgreSQL HBA rules | [`cdwpg_hba_config`](plugins/modules/cdwpg_hba_config.py) |
| `susunola.tencentcloud.cdwpg_instance` | Manage Tencent Cloud CDW PostgreSQL instances | [`cdwpg_instance`](plugins/modules/cdwpg_instance.py) |
| `susunola.tencentcloud.cdwpg_parameter` | Manage a Tencent Cloud CDW PostgreSQL parameter | [`cdwpg_parameter`](plugins/modules/cdwpg_parameter.py) |
| `susunola.tencentcloud.cfs_auto_snapshot_policy` | Manage Tencent Cloud CFS automatic snapshot policies | [`cfs_auto_snapshot_policy`](plugins/modules/cfs_auto_snapshot_policy.py) |
| `susunola.tencentcloud.cfs_file_system` | Manage Tencent Cloud CFS file systems | [`cfs_file_system`](plugins/modules/cfs_file_system.py) |
| `susunola.tencentcloud.cfs_permission_group` | Manage Tencent Cloud CFS permission groups | [`cfs_permission_group`](plugins/modules/cfs_permission_group.py) |
| `susunola.tencentcloud.cfs_permission_rule` | Manage Tencent Cloud CFS permission rules | [`cfs_permission_rule`](plugins/modules/cfs_permission_rule.py) |
| `susunola.tencentcloud.cfs_snapshot` | Manage Tencent Cloud CFS snapshots | [`cfs_snapshot`](plugins/modules/cfs_snapshot.py) |
| `susunola.tencentcloud.cfw_address_template` | Manage Tencent Cloud Cloud Firewall address templates | [`cfw_address_template`](plugins/modules/cfw_address_template.py) |
| `susunola.tencentcloud.cfw_internet_acl_rule` | Manage Tencent Cloud Cloud Firewall internet border ACL rules | [`cfw_internet_acl_rule`](plugins/modules/cfw_internet_acl_rule.py) |
| `susunola.tencentcloud.cfw_nat_acl_rule` | Manage Tencent Cloud Cloud Firewall NAT access-control rules | [`cfw_nat_acl_rule`](plugins/modules/cfw_nat_acl_rule.py) |
| `susunola.tencentcloud.cfw_nat_dnat_rule` | Manage Tencent Cloud Cloud Firewall NAT DNAT rules | [`cfw_nat_dnat_rule`](plugins/modules/cfw_nat_dnat_rule.py) |
| `susunola.tencentcloud.cfw_vpc_acl_rule` | Manage Tencent Cloud Cloud Firewall inter-VPC ACL rules | [`cfw_vpc_acl_rule`](plugins/modules/cfw_vpc_acl_rule.py) |
| `susunola.tencentcloud.chdfs_access_group` | Manage Tencent Cloud CHDFS access groups | [`chdfs_access_group`](plugins/modules/chdfs_access_group.py) |
| `susunola.tencentcloud.chdfs_access_rules` | Reconcile Tencent Cloud CHDFS access rules | [`chdfs_access_rules`](plugins/modules/chdfs_access_rules.py) |
| `susunola.tencentcloud.chdfs_file_system` | Manage Tencent Cloud CHDFS file systems | [`chdfs_file_system`](plugins/modules/chdfs_file_system.py) |
| `susunola.tencentcloud.chdfs_mount_access_groups` | Reconcile CHDFS mount point access-group bindings | [`chdfs_mount_access_groups`](plugins/modules/chdfs_mount_access_groups.py) |
| `susunola.tencentcloud.chdfs_mount_point` | Manage Tencent Cloud CHDFS mount points | [`chdfs_mount_point`](plugins/modules/chdfs_mount_point.py) |
| `susunola.tencentcloud.ckafka_acl` | Manage Tencent Cloud CKafka ACL entries | [`ckafka_acl`](plugins/modules/ckafka_acl.py) |
| `susunola.tencentcloud.ckafka_acl_rule` | Manage Tencent Cloud CKafka ACL rules | [`ckafka_acl_rule`](plugins/modules/ckafka_acl_rule.py) |
| `susunola.tencentcloud.ckafka_datahub_connection` | Manage Tencent Cloud CKafka Datahub connection resources | [`ckafka_datahub_connection`](plugins/modules/ckafka_datahub_connection.py) |
| `susunola.tencentcloud.ckafka_datahub_task` | Manage Tencent Cloud CKafka Datahub tasks | [`ckafka_datahub_task`](plugins/modules/ckafka_datahub_task.py) |
| `susunola.tencentcloud.ckafka_datahub_topic` | Manage Tencent Cloud CKafka Datahub topics | [`ckafka_datahub_topic`](plugins/modules/ckafka_datahub_topic.py) |
| `susunola.tencentcloud.ckafka_instance` | Manage Tencent Cloud CKafka instances | [`ckafka_instance`](plugins/modules/ckafka_instance.py) |
| `susunola.tencentcloud.ckafka_route` | Manage Tencent Cloud CKafka access routes | [`ckafka_route`](plugins/modules/ckafka_route.py) |
| `susunola.tencentcloud.ckafka_topic` | Manage Tencent Cloud CKafka topics | [`ckafka_topic`](plugins/modules/ckafka_topic.py) |
| `susunola.tencentcloud.ckafka_user` | Manage Tencent Cloud CKafka users | [`ckafka_user`](plugins/modules/ckafka_user.py) |
| `susunola.tencentcloud.clb_listener` | Manage listeners on Tencent Cloud CLB load balancers | [`clb_listener`](plugins/modules/clb_listener.py) |
| `susunola.tencentcloud.clb_listener_target` | Manage backend targets of Tencent Cloud CLB listeners | [`clb_listener_target`](plugins/modules/clb_listener_target.py) |
| `susunola.tencentcloud.clb_load_balancer` | Manage Tencent Cloud CLB load balancers | [`clb_load_balancer`](plugins/modules/clb_load_balancer.py) |
| `susunola.tencentcloud.clb_rule` | Manage Tencent Cloud CLB L7 forwarding rules | [`clb_rule`](plugins/modules/clb_rule.py) |
| `susunola.tencentcloud.clb_target_group` | Manage Tencent Cloud CLB target groups and members | [`clb_target_group`](plugins/modules/clb_target_group.py) |
| `susunola.tencentcloud.cloudaudit_audit` | Manage Tencent Cloud account-level CloudAudit delivery | [`cloudaudit_audit`](plugins/modules/cloudaudit_audit.py) |
| `susunola.tencentcloud.cloudaudit_track` | Manage Tencent Cloud CloudAudit tracks | [`cloudaudit_track`](plugins/modules/cloudaudit_track.py) |
| `susunola.tencentcloud.cls_config` | Manage Tencent Cloud CLS collection configurations | [`cls_config`](plugins/modules/cls_config.py) |
| `susunola.tencentcloud.cls_config_machine_group_binding` | Bind CLS collection configurations to machine groups | [`cls_config_machine_group_binding`](plugins/modules/cls_config_machine_group_binding.py) |
| `susunola.tencentcloud.cls_index` | Manage Tencent Cloud CLS topic indexes | [`cls_index`](plugins/modules/cls_index.py) |
| `susunola.tencentcloud.cls_logset` | Manage Tencent Cloud CLS logsets | [`cls_logset`](plugins/modules/cls_logset.py) |
| `susunola.tencentcloud.cls_machine_group` | Manage Tencent Cloud CLS machine groups | [`cls_machine_group`](plugins/modules/cls_machine_group.py) |
| `susunola.tencentcloud.cls_shipper` | Manage Tencent Cloud CLS delivery tasks to COS | [`cls_shipper`](plugins/modules/cls_shipper.py) |
| `susunola.tencentcloud.cls_topic` | Manage Tencent Cloud CLS topics | [`cls_topic`](plugins/modules/cls_topic.py) |
| `susunola.tencentcloud.cmq_queue` | Manage Tencent Cloud CMQ queues | [`cmq_queue`](plugins/modules/cmq_queue.py) |
| `susunola.tencentcloud.cmq_subscription` | Manage Tencent Cloud CMQ topic subscriptions | [`cmq_subscription`](plugins/modules/cmq_subscription.py) |
| `susunola.tencentcloud.cmq_topic` | Manage Tencent Cloud CMQ topics | [`cmq_topic`](plugins/modules/cmq_topic.py) |
| `susunola.tencentcloud.config_aggregate_delivery` | Manage Tencent Cloud Config cross-account aggregate delivery | [`config_aggregate_delivery`](plugins/modules/config_aggregate_delivery.py) |
| `susunola.tencentcloud.config_aggregator` | Manage creation of Tencent Cloud Config account aggregators | [`config_aggregator`](plugins/modules/config_aggregator.py) |
| `susunola.tencentcloud.config_alarm_policy` | Manage Tencent Cloud Config alarm policies | [`config_alarm_policy`](plugins/modules/config_alarm_policy.py) |
| `susunola.tencentcloud.config_compliance_pack` | Manage Tencent Cloud Config compliance packs | [`config_compliance_pack`](plugins/modules/config_compliance_pack.py) |
| `susunola.tencentcloud.config_delivery` | Manage Tencent Cloud Config delivery settings | [`config_delivery`](plugins/modules/config_delivery.py) |
| `susunola.tencentcloud.config_recorder` | Manage Tencent Cloud Config resource recorder | [`config_recorder`](plugins/modules/config_recorder.py) |
| `susunola.tencentcloud.config_remediation` | Manage Tencent Cloud Config remediation settings | [`config_remediation`](plugins/modules/config_remediation.py) |
| `susunola.tencentcloud.config_rule` | Manage Tencent Cloud Config compliance rules | [`config_rule`](plugins/modules/config_rule.py) |
| `susunola.tencentcloud.cos_bucket` | Manage Tencent Cloud COS buckets | [`cos_bucket`](plugins/modules/cos_bucket.py) |
| `susunola.tencentcloud.cos_bucket_domain` | Manage Tencent Cloud COS custom domains | [`cos_bucket_domain`](plugins/modules/cos_bucket_domain.py) |
| `susunola.tencentcloud.cos_bucket_domain_certificate` | Manage Tencent Cloud COS custom-domain certificates | [`cos_bucket_domain_certificate`](plugins/modules/cos_bucket_domain_certificate.py) |
| `susunola.tencentcloud.cos_bucket_encryption` | Manage Tencent Cloud COS default bucket encryption | [`cos_bucket_encryption`](plugins/modules/cos_bucket_encryption.py) |
| `susunola.tencentcloud.cos_bucket_intelligent_tiering` | Manage Tencent Cloud COS bucket intelligent tiering | [`cos_bucket_intelligent_tiering`](plugins/modules/cos_bucket_intelligent_tiering.py) |
| `susunola.tencentcloud.cos_bucket_inventory` | Manage Tencent Cloud COS bucket inventory rules | [`cos_bucket_inventory`](plugins/modules/cos_bucket_inventory.py) |
| `susunola.tencentcloud.cos_bucket_logging` | Manage Tencent Cloud COS bucket access logging | [`cos_bucket_logging`](plugins/modules/cos_bucket_logging.py) |
| `susunola.tencentcloud.cos_bucket_object_lock` | Manage Tencent Cloud COS bucket object lock | [`cos_bucket_object_lock`](plugins/modules/cos_bucket_object_lock.py) |
| `susunola.tencentcloud.cos_bucket_origin` | Manage Tencent Cloud COS bucket origin rules | [`cos_bucket_origin`](plugins/modules/cos_bucket_origin.py) |
| `susunola.tencentcloud.cos_bucket_policy` | Manage Tencent Cloud COS bucket policies | [`cos_bucket_policy`](plugins/modules/cos_bucket_policy.py) |
| `susunola.tencentcloud.cos_bucket_referer` | Manage Tencent Cloud COS hotlink protection | [`cos_bucket_referer`](plugins/modules/cos_bucket_referer.py) |
| `susunola.tencentcloud.cos_bucket_replication` | Manage Tencent Cloud COS bucket replication | [`cos_bucket_replication`](plugins/modules/cos_bucket_replication.py) |
| `susunola.tencentcloud.cos_bucket_response_control` | Manage Tencent Cloud COS response-header controls | [`cos_bucket_response_control`](plugins/modules/cos_bucket_response_control.py) |
| `susunola.tencentcloud.cos_bucket_website` | Manage Tencent Cloud COS static website configuration | [`cos_bucket_website`](plugins/modules/cos_bucket_website.py) |
| `susunola.tencentcloud.cos_object` | Manage Tencent Cloud COS objects | [`cos_object`](plugins/modules/cos_object.py) |
| `susunola.tencentcloud.cos_object_sync` | Mirror a local directory tree into a Tencent Cloud COS bucket | [`cos_object_sync`](plugins/modules/cos_object_sync.py) |
| `susunola.tencentcloud.customer_gateway` | Manage Tencent Cloud VPN customer gateways | [`customer_gateway`](plugins/modules/customer_gateway.py) |
| `susunola.tencentcloud.cvm_chc` | Manage Tencent Cloud CHC physical server network configuration | [`cvm_chc`](plugins/modules/cvm_chc.py) |
| `susunola.tencentcloud.cvm_disaster_recover_group` | Manage Tencent Cloud CVM placement groups | [`cvm_disaster_recover_group`](plugins/modules/cvm_disaster_recover_group.py) |
| `susunola.tencentcloud.cvm_disaster_recover_group_binding` | Bind a Tencent Cloud CVM instance to a placement group | [`cvm_disaster_recover_group_binding`](plugins/modules/cvm_disaster_recover_group_binding.py) |
| `susunola.tencentcloud.cvm_hpc_cluster` | Manage Tencent Cloud CVM high-performance clusters | [`cvm_hpc_cluster`](plugins/modules/cvm_hpc_cluster.py) |
| `susunola.tencentcloud.cvm_image` | Manage Tencent Cloud CVM custom images | [`cvm_image`](plugins/modules/cvm_image.py) |
| `susunola.tencentcloud.cvm_image_share` | Manage Tencent Cloud CVM image sharing permissions | [`cvm_image_share`](plugins/modules/cvm_image_share.py) |
| `susunola.tencentcloud.cvm_instance` | Manage Tencent Cloud CVM instances | [`cvm_instance`](plugins/modules/cvm_instance.py) |
| `susunola.tencentcloud.cvm_instance_action_timer` | Manage Tencent Cloud CVM instance action timers | [`cvm_instance_action_timer`](plugins/modules/cvm_instance_action_timer.py) |
| `susunola.tencentcloud.cvm_instance_security_group` | Manage the security groups bound to a Tencent Cloud CVM instance | [`cvm_instance_security_group`](plugins/modules/cvm_instance_security_group.py) |
| `susunola.tencentcloud.cvm_launch_template` | Manage Tencent Cloud CVM launch templates | [`cvm_launch_template`](plugins/modules/cvm_launch_template.py) |
| `susunola.tencentcloud.cvm_launch_template_version` | Manage Tencent Cloud CVM launch-template versions | [`cvm_launch_template_version`](plugins/modules/cvm_launch_template_version.py) |
| `susunola.tencentcloud.cynosdb_account` | Manage Tencent Cloud CynosDB accounts | [`cynosdb_account`](plugins/modules/cynosdb_account.py) |
| `susunola.tencentcloud.cynosdb_account_privilege` | Manage Tencent Cloud CynosDB account privileges | [`cynosdb_account_privilege`](plugins/modules/cynosdb_account_privilege.py) |
| `susunola.tencentcloud.cynosdb_backup_config` | Manage Tencent Cloud CynosDB backup configuration | [`cynosdb_backup_config`](plugins/modules/cynosdb_backup_config.py) |
| `susunola.tencentcloud.cynosdb_cluster` | Manage Tencent Cloud CynosDB clusters | [`cynosdb_cluster`](plugins/modules/cynosdb_cluster.py) |
| `susunola.tencentcloud.dbbrain_sql_filter` | Manage Tencent Cloud DBbrain SQL filters | [`dbbrain_sql_filter`](plugins/modules/dbbrain_sql_filter.py) |
| `susunola.tencentcloud.dbdc_db_custom_cluster` | Manage Tencent Cloud DB Custom clusters | [`dbdc_db_custom_cluster`](plugins/modules/dbdc_db_custom_cluster.py) |
| `susunola.tencentcloud.dc_direct_connect` | Manage Tencent Cloud physical Direct Connect circuits | [`dc_direct_connect`](plugins/modules/dc_direct_connect.py) |
| `susunola.tencentcloud.dc_direct_connect_tunnel` | Manage Tencent Cloud Direct Connect tunnels | [`dc_direct_connect_tunnel`](plugins/modules/dc_direct_connect_tunnel.py) |
| `susunola.tencentcloud.dcdb_account` | Manage Tencent Cloud DCDB accounts | [`dcdb_account`](plugins/modules/dcdb_account.py) |
| `susunola.tencentcloud.dcdb_account_privilege` | Manage scoped Tencent Cloud DCDB account privileges | [`dcdb_account_privilege`](plugins/modules/dcdb_account_privilege.py) |
| `susunola.tencentcloud.dcdb_backup_config` | Manage Tencent Cloud DCDB automatic backup configuration | [`dcdb_backup_config`](plugins/modules/dcdb_backup_config.py) |
| `susunola.tencentcloud.dcdb_instance` | Manage Tencent Cloud DCDB instances | [`dcdb_instance`](plugins/modules/dcdb_instance.py) |
| `susunola.tencentcloud.dcdb_security_config` | Manage Tencent Cloud DCDB encryption, SSL and security groups | [`dcdb_security_config`](plugins/modules/dcdb_security_config.py) |
| `susunola.tencentcloud.dlc_cluster_group` | Manage Tencent Cloud DLC compute cluster groups | [`dlc_cluster_group`](plugins/modules/dlc_cluster_group.py) |
| `susunola.tencentcloud.dlc_data_engine` | Manage Tencent Cloud Data Lake Compute engines | [`dlc_data_engine`](plugins/modules/dlc_data_engine.py) |
| `susunola.tencentcloud.dlc_data_engine_config` | Reconcile Tencent Cloud DLC data-engine runtime configuration | [`dlc_data_engine_config`](plugins/modules/dlc_data_engine_config.py) |
| `susunola.tencentcloud.dlc_data_mask_strategy` | Manage Tencent Cloud Data Lake Compute masking strategies | [`dlc_data_mask_strategy`](plugins/modules/dlc_data_mask_strategy.py) |
| `susunola.tencentcloud.dlc_database` | Manage Tencent Cloud Data Lake Compute metadata databases | [`dlc_database`](plugins/modules/dlc_database.py) |
| `susunola.tencentcloud.dlc_engine_resource_group` | Manage Tencent Cloud DLC standard engine resource groups | [`dlc_engine_resource_group`](plugins/modules/dlc_engine_resource_group.py) |
| `susunola.tencentcloud.dlc_inference_model` | Ensure and reconcile Tencent Cloud DLC inference models | [`dlc_inference_model`](plugins/modules/dlc_inference_model.py) |
| `susunola.tencentcloud.dlc_inference_service` | Manage Tencent Cloud DLC inference-service runtime state | [`dlc_inference_service`](plugins/modules/dlc_inference_service.py) |
| `susunola.tencentcloud.dlc_job_spec` | Manage reusable Tencent Cloud DLC job specifications | [`dlc_job_spec`](plugins/modules/dlc_job_spec.py) |
| `susunola.tencentcloud.dlc_lab` | Manage Tencent Cloud DLC data laboratories | [`dlc_lab`](plugins/modules/dlc_lab.py) |
| `susunola.tencentcloud.dlc_model_version` | Publish immutable Tencent Cloud DLC model versions | [`dlc_model_version`](plugins/modules/dlc_model_version.py) |
| `susunola.tencentcloud.dlc_network_connection` | Reconcile Tencent Cloud DLC network-connection metadata | [`dlc_network_connection`](plugins/modules/dlc_network_connection.py) |
| `susunola.tencentcloud.dlc_notebook_session` | Manage Tencent Cloud DLC Notebook sessions | [`dlc_notebook_session`](plugins/modules/dlc_notebook_session.py) |
| `susunola.tencentcloud.dlc_partition_queue` | Manage Tencent Cloud DLC resource partition queues | [`dlc_partition_queue`](plugins/modules/dlc_partition_queue.py) |
| `susunola.tencentcloud.dlc_ray_cluster` | Manage Tencent Cloud DLC Ray clusters | [`dlc_ray_cluster`](plugins/modules/dlc_ray_cluster.py) |
| `susunola.tencentcloud.dlc_resource_config` | Manage Tencent Cloud DLC Ray and Spark resource templates | [`dlc_resource_config`](plugins/modules/dlc_resource_config.py) |
| `susunola.tencentcloud.dlc_script` | Manage Tencent Cloud DLC saved SQL scripts | [`dlc_script`](plugins/modules/dlc_script.py) |
| `susunola.tencentcloud.dlc_spark_job` | Manage Tencent Cloud DLC Spark job definitions | [`dlc_spark_job`](plugins/modules/dlc_spark_job.py) |
| `susunola.tencentcloud.dlc_store_location` | Configure Tencent Cloud DLC query-result storage locations | [`dlc_store_location`](plugins/modules/dlc_store_location.py) |
| `susunola.tencentcloud.dlc_table` | Manage Tencent Cloud DLC metadata tables | [`dlc_table`](plugins/modules/dlc_table.py) |
| `susunola.tencentcloud.dlc_table_partition` | Manage Tencent Cloud DLC table partition entries | [`dlc_table_partition`](plugins/modules/dlc_table_partition.py) |
| `susunola.tencentcloud.dlc_udf_policy` | Reconcile Tencent Cloud DLC UDF access policies | [`dlc_udf_policy`](plugins/modules/dlc_udf_policy.py) |
| `susunola.tencentcloud.dlc_user` | Manage Tencent Cloud Data Lake Compute users | [`dlc_user`](plugins/modules/dlc_user.py) |
| `susunola.tencentcloud.dlc_user_policy` | Manage Tencent Cloud Data Lake Compute user policies | [`dlc_user_policy`](plugins/modules/dlc_user_policy.py) |
| `susunola.tencentcloud.dlc_user_vpc_connection` | Connect DLC engine networks to Tencent Cloud VPCs | [`dlc_user_vpc_connection`](plugins/modules/dlc_user_vpc_connection.py) |
| `susunola.tencentcloud.dlc_work_group` | Manage Tencent Cloud Data Lake Compute work groups | [`dlc_work_group`](plugins/modules/dlc_work_group.py) |
| `susunola.tencentcloud.dlc_work_group_membership` | Manage Tencent Cloud Data Lake Compute work-group members | [`dlc_work_group_membership`](plugins/modules/dlc_work_group_membership.py) |
| `susunola.tencentcloud.dlc_work_group_policy` | Manage Tencent Cloud Data Lake Compute work-group policies | [`dlc_work_group_policy`](plugins/modules/dlc_work_group_policy.py) |
| `susunola.tencentcloud.dnspod_custom_line` | Manage DNSPod domain custom lines | [`dnspod_custom_line`](plugins/modules/dnspod_custom_line.py) |
| `susunola.tencentcloud.dnspod_domain` | Manage Tencent Cloud DNSPod domains | [`dnspod_domain`](plugins/modules/dnspod_domain.py) |
| `susunola.tencentcloud.dnspod_line_group` | Manage DNSPod custom line groups | [`dnspod_line_group`](plugins/modules/dnspod_line_group.py) |
| `susunola.tencentcloud.dnspod_record` | Manage Tencent Cloud DNSPod DNS records | [`dnspod_record`](plugins/modules/dnspod_record.py) |
| `susunola.tencentcloud.dts_consumer_group` | Manage Tencent Cloud DTS consumer groups | [`dts_consumer_group`](plugins/modules/dts_consumer_group.py) |
| `susunola.tencentcloud.dts_migration_action` | Control a Tencent Cloud DTS migration job | [`dts_migration_action`](plugins/modules/dts_migration_action.py) |
| `susunola.tencentcloud.dts_migration_check` | Run and wait for a Tencent Cloud DTS migration check | [`dts_migration_check`](plugins/modules/dts_migration_check.py) |
| `susunola.tencentcloud.dts_migration_job` | Manage Tencent Cloud DTS migration jobs | [`dts_migration_job`](plugins/modules/dts_migration_job.py) |
| `susunola.tencentcloud.dts_migration_job_config` | Configure a Tencent Cloud DTS migration job | [`dts_migration_job_config`](plugins/modules/dts_migration_job_config.py) |
| `susunola.tencentcloud.eb_connection` | Manage Tencent Cloud EventBridge connections | [`eb_connection`](plugins/modules/eb_connection.py) |
| `susunola.tencentcloud.eb_event_bus` | Manage Tencent Cloud EventBridge event buses | [`eb_event_bus`](plugins/modules/eb_event_bus.py) |
| `susunola.tencentcloud.eb_rule` | Manage Tencent Cloud EventBridge rules | [`eb_rule`](plugins/modules/eb_rule.py) |
| `susunola.tencentcloud.eb_target` | Manage Tencent Cloud EventBridge rule targets | [`eb_target`](plugins/modules/eb_target.py) |
| `susunola.tencentcloud.eip` | Manage Tencent Cloud elastic IP addresses (EIP) | [`eip`](plugins/modules/eip.py) |
| `susunola.tencentcloud.eks_cluster` | Manage Tencent Cloud EKS clusters | [`eks_cluster`](plugins/modules/eks_cluster.py) |
| `susunola.tencentcloud.eks_container_instance` | Manage Tencent Cloud EKS container instances | [`eks_container_instance`](plugins/modules/eks_container_instance.py) |
| `susunola.tencentcloud.elasticsearch_index` | Manage indexes in Tencent Cloud Elasticsearch Service | [`elasticsearch_index`](plugins/modules/elasticsearch_index.py) |
| `susunola.tencentcloud.elasticsearch_instance` | Manage Tencent Cloud Elasticsearch clusters | [`elasticsearch_instance`](plugins/modules/elasticsearch_instance.py) |
| `susunola.tencentcloud.elasticsearch_snapshot` | Manage Tencent Cloud Elasticsearch cluster snapshots | [`elasticsearch_snapshot`](plugins/modules/elasticsearch_snapshot.py) |
| `susunola.tencentcloud.emr_auto_scale_strategy` | Manage Tencent Cloud EMR automatic scaling strategies | [`emr_auto_scale_strategy`](plugins/modules/emr_auto_scale_strategy.py) |
| `susunola.tencentcloud.emr_cluster` | Manage Tencent Cloud EMR clusters | [`emr_cluster`](plugins/modules/emr_cluster.py) |
| `susunola.tencentcloud.gaap_layer4_listener` | Manage Tencent Cloud GAAP TCP and UDP listeners | [`gaap_layer4_listener`](plugins/modules/gaap_layer4_listener.py) |
| `susunola.tencentcloud.gaap_listener_real_servers` | Reconcile Tencent Cloud GAAP listener origin bindings | [`gaap_listener_real_servers`](plugins/modules/gaap_listener_real_servers.py) |
| `susunola.tencentcloud.gaap_proxy` | Manage Tencent Cloud GAAP proxies | [`gaap_proxy`](plugins/modules/gaap_proxy.py) |
| `susunola.tencentcloud.gaap_real_server` | Manage Tencent Cloud GAAP real servers | [`gaap_real_server`](plugins/modules/gaap_real_server.py) |
| `susunola.tencentcloud.goosefs_file_system` | Manage Tencent Cloud GooseFS file systems | [`goosefs_file_system`](plugins/modules/goosefs_file_system.py) |
| `susunola.tencentcloud.goosefs_fileset` | Manage Tencent Cloud GooseFS filesets | [`goosefs_fileset`](plugins/modules/goosefs_fileset.py) |
| `susunola.tencentcloud.gwlb_load_balancer` | Manage Tencent Cloud Gateway Load Balancers | [`gwlb_load_balancer`](plugins/modules/gwlb_load_balancer.py) |
| `susunola.tencentcloud.gwlb_target_group` | Manage Tencent Cloud GWLB target groups | [`gwlb_target_group`](plugins/modules/gwlb_target_group.py) |
| `susunola.tencentcloud.gwlb_target_group_association` | Manage Tencent Cloud GWLB target group associations | [`gwlb_target_group_association`](plugins/modules/gwlb_target_group_association.py) |
| `susunola.tencentcloud.gwlb_target_group_instances` | Reconcile Tencent Cloud GWLB target group instances | [`gwlb_target_group_instances`](plugins/modules/gwlb_target_group_instances.py) |
| `susunola.tencentcloud.havip` | Manage Tencent Cloud VPC high-availability virtual IPs | [`havip`](plugins/modules/havip.py) |
| `susunola.tencentcloud.havip_association` | Manage Tencent Cloud HAVIP drift-scope associations | [`havip_association`](plugins/modules/havip_association.py) |
| `susunola.tencentcloud.key_pair` | Manage Tencent Cloud CVM key pairs | [`key_pair`](plugins/modules/key_pair.py) |
| `susunola.tencentcloud.kms_key` | Manage a Tencent Cloud KMS key | [`kms_key`](plugins/modules/kms_key.py) |
| `susunola.tencentcloud.kms_key_rotation` | Manage automatic rotation for a Tencent Cloud KMS key | [`kms_key_rotation`](plugins/modules/kms_key_rotation.py) |
| `susunola.tencentcloud.lighthouse_disk` | Manage Tencent Cloud Lighthouse data disks | [`lighthouse_disk`](plugins/modules/lighthouse_disk.py) |
| `susunola.tencentcloud.lighthouse_firewall_rules` | Manage Tencent Cloud Lighthouse instance firewall rules | [`lighthouse_firewall_rules`](plugins/modules/lighthouse_firewall_rules.py) |
| `susunola.tencentcloud.lighthouse_instance` | Manage Tencent Cloud Lighthouse instances | [`lighthouse_instance`](plugins/modules/lighthouse_instance.py) |
| `susunola.tencentcloud.lighthouse_key_pair` | Manage imported Tencent Cloud Lighthouse SSH key pairs | [`lighthouse_key_pair`](plugins/modules/lighthouse_key_pair.py) |
| `susunola.tencentcloud.lighthouse_snapshot` | Manage Tencent Cloud Lighthouse instance snapshots | [`lighthouse_snapshot`](plugins/modules/lighthouse_snapshot.py) |
| `susunola.tencentcloud.mariadb_account` | Manage TencentDB for MariaDB accounts | [`mariadb_account`](plugins/modules/mariadb_account.py) |
| `susunola.tencentcloud.mariadb_account_privilege` | Manage a scoped TencentDB for MariaDB account privilege set | [`mariadb_account_privilege`](plugins/modules/mariadb_account_privilege.py) |
| `susunola.tencentcloud.mariadb_backup_config` | Manage TencentDB for MariaDB automatic backup configuration | [`mariadb_backup_config`](plugins/modules/mariadb_backup_config.py) |
| `susunola.tencentcloud.mariadb_instance` | Manage Tencent Cloud MariaDB instances | [`mariadb_instance`](plugins/modules/mariadb_instance.py) |
| `susunola.tencentcloud.mongodb_account` | Manage TencentDB for MongoDB accounts | [`mongodb_account`](plugins/modules/mongodb_account.py) |
| `susunola.tencentcloud.mongodb_backup_config` | Manage TencentDB for MongoDB automatic backup rules | [`mongodb_backup_config`](plugins/modules/mongodb_backup_config.py) |
| `susunola.tencentcloud.mongodb_instance` | Manage Tencent Cloud MongoDB instances | [`mongodb_instance`](plugins/modules/mongodb_instance.py) |
| `susunola.tencentcloud.monitor_alarm_policy` | Manage a Tencent Cloud Monitor alarm policy | [`monitor_alarm_policy`](plugins/modules/monitor_alarm_policy.py) |
| `susunola.tencentcloud.monitor_alarm_policy_notice` | Manage notification bindings for a Cloud Monitor alarm policy | [`monitor_alarm_policy_notice`](plugins/modules/monitor_alarm_policy_notice.py) |
| `susunola.tencentcloud.monitor_grafana_instance` | Manage Tencent Cloud Managed Grafana instances | [`monitor_grafana_instance`](plugins/modules/monitor_grafana_instance.py) |
| `susunola.tencentcloud.monitor_grafana_integration` | Manage Tencent Cloud Managed Grafana integrations | [`monitor_grafana_integration`](plugins/modules/monitor_grafana_integration.py) |
| `susunola.tencentcloud.monitor_grafana_internet` | Manage internet access for Tencent Cloud Managed Grafana | [`monitor_grafana_internet`](plugins/modules/monitor_grafana_internet.py) |
| `susunola.tencentcloud.monitor_grafana_notification_channel` | Manage Tencent Cloud Managed Grafana notification channels | [`monitor_grafana_notification_channel`](plugins/modules/monitor_grafana_notification_channel.py) |
| `susunola.tencentcloud.monitor_grafana_whitelist` | Manage a Tencent Cloud Managed Grafana IP whitelist | [`monitor_grafana_whitelist`](plugins/modules/monitor_grafana_whitelist.py) |
| `susunola.tencentcloud.monitor_prometheus_alert_group` | Manage Tencent Cloud Managed Prometheus alert groups | [`monitor_prometheus_alert_group`](plugins/modules/monitor_prometheus_alert_group.py) |
| `susunola.tencentcloud.monitor_prometheus_alertmanager_config` | Manage Managed Prometheus Alertmanager configuration | [`monitor_prometheus_alertmanager_config`](plugins/modules/monitor_prometheus_alertmanager_config.py) |
| `susunola.tencentcloud.monitor_prometheus_cluster_agent` | Manage Managed Prometheus cluster agents | [`monitor_prometheus_cluster_agent`](plugins/modules/monitor_prometheus_cluster_agent.py) |
| `susunola.tencentcloud.monitor_prometheus_global_notification` | Manage Managed Prometheus global notification settings | [`monitor_prometheus_global_notification`](plugins/modules/monitor_prometheus_global_notification.py) |
| `susunola.tencentcloud.monitor_prometheus_grafana_binding` | Bind Managed Prometheus and Grafana instances | [`monitor_prometheus_grafana_binding`](plugins/modules/monitor_prometheus_grafana_binding.py) |
| `susunola.tencentcloud.monitor_prometheus_instance` | Manage Tencent Cloud pay-as-you-go Managed Prometheus instances | [`monitor_prometheus_instance`](plugins/modules/monitor_prometheus_instance.py) |
| `susunola.tencentcloud.monitor_prometheus_record_rule` | Manage Tencent Cloud Managed Prometheus recording rules | [`monitor_prometheus_record_rule`](plugins/modules/monitor_prometheus_record_rule.py) |
| `susunola.tencentcloud.monitor_prometheus_scrape_job` | Manage Tencent Cloud Managed Prometheus scrape jobs | [`monitor_prometheus_scrape_job`](plugins/modules/monitor_prometheus_scrape_job.py) |
| `susunola.tencentcloud.mqtt_authorization_policy` | Manage Tencent Cloud MQTT authorization policies | [`mqtt_authorization_policy`](plugins/modules/mqtt_authorization_policy.py) |
| `susunola.tencentcloud.mqtt_instance` | Manage Tencent Cloud MQTT instances | [`mqtt_instance`](plugins/modules/mqtt_instance.py) |
| `susunola.tencentcloud.mqtt_topic` | Manage Tencent Cloud MQTT topics | [`mqtt_topic`](plugins/modules/mqtt_topic.py) |
| `susunola.tencentcloud.mqtt_user` | Manage Tencent Cloud MQTT users | [`mqtt_user`](plugins/modules/mqtt_user.py) |
| `susunola.tencentcloud.nat_gateway` | Manage Tencent Cloud NAT gateways | [`nat_gateway`](plugins/modules/nat_gateway.py) |
| `susunola.tencentcloud.nat_gateway_rule` | Manage Tencent Cloud NAT gateway DNAT and SNAT rules | [`nat_gateway_rule`](plugins/modules/nat_gateway_rule.py) |
| `susunola.tencentcloud.network_acl` | Manage Tencent Cloud VPC network ACLs | [`network_acl`](plugins/modules/network_acl.py) |
| `susunola.tencentcloud.network_interface` | Manage Tencent Cloud elastic network interfaces | [`network_interface`](plugins/modules/network_interface.py) |
| `susunola.tencentcloud.oceanus_cluster` | Manage Tencent Cloud Oceanus dedicated clusters | [`oceanus_cluster`](plugins/modules/oceanus_cluster.py) |
| `susunola.tencentcloud.oceanus_folder` | Manage Tencent Cloud Oceanus folders | [`oceanus_folder`](plugins/modules/oceanus_folder.py) |
| `susunola.tencentcloud.oceanus_job` | Manage Tencent Cloud Oceanus jobs | [`oceanus_job`](plugins/modules/oceanus_job.py) |
| `susunola.tencentcloud.oceanus_job_config` | Manage Tencent Cloud Oceanus job configuration versions | [`oceanus_job_config`](plugins/modules/oceanus_job_config.py) |
| `susunola.tencentcloud.oceanus_job_savepoint` | Create Tencent Cloud Oceanus job savepoints | [`oceanus_job_savepoint`](plugins/modules/oceanus_job_savepoint.py) |
| `susunola.tencentcloud.oceanus_meta_table` | Manage Tencent Cloud Oceanus metadata tables | [`oceanus_meta_table`](plugins/modules/oceanus_meta_table.py) |
| `susunola.tencentcloud.oceanus_resource` | Manage Tencent Cloud Oceanus resources | [`oceanus_resource`](plugins/modules/oceanus_resource.py) |
| `susunola.tencentcloud.oceanus_resource_config` | Manage Tencent Cloud Oceanus resource versions | [`oceanus_resource_config`](plugins/modules/oceanus_resource_config.py) |
| `susunola.tencentcloud.oceanus_workspace` | Manage Tencent Cloud Oceanus workspaces | [`oceanus_workspace`](plugins/modules/oceanus_workspace.py) |
| `susunola.tencentcloud.organization_member` | Manage Tencent Cloud Organization members | [`organization_member`](plugins/modules/organization_member.py) |
| `susunola.tencentcloud.organization_member_identity` | Reconcile Tencent Cloud Organization member identities | [`organization_member_identity`](plugins/modules/organization_member_identity.py) |
| `susunola.tencentcloud.organization_member_policy` | Manage Tencent Cloud Organization member access policies | [`organization_member_policy`](plugins/modules/organization_member_policy.py) |
| `susunola.tencentcloud.organization_node` | Manage Tencent Cloud Organization nodes | [`organization_node`](plugins/modules/organization_node.py) |
| `susunola.tencentcloud.peering_connection` | Manage Tencent Cloud VPC peering connections | [`peering_connection`](plugins/modules/peering_connection.py) |
| `susunola.tencentcloud.postgresql_account` | Manage TencentDB for PostgreSQL accounts | [`postgresql_account`](plugins/modules/postgresql_account.py) |
| `susunola.tencentcloud.postgresql_backup_plan` | Manage TencentDB for PostgreSQL backup plans | [`postgresql_backup_plan`](plugins/modules/postgresql_backup_plan.py) |
| `susunola.tencentcloud.postgresql_instance` | Manage Tencent Cloud PostgreSQL instances | [`postgresql_instance`](plugins/modules/postgresql_instance.py) |
| `susunola.tencentcloud.postgresql_parameter_template` | Manage Tencent Cloud PostgreSQL parameter templates | [`postgresql_parameter_template`](plugins/modules/postgresql_parameter_template.py) |
| `susunola.tencentcloud.private_dns_account` | Manage Tencent Cloud Private DNS cross-account authorization | [`private_dns_account`](plugins/modules/private_dns_account.py) |
| `susunola.tencentcloud.private_dns_record` | Manage a Tencent Cloud Private DNS record | [`private_dns_record`](plugins/modules/private_dns_record.py) |
| `susunola.tencentcloud.private_dns_zone` | Manage a Tencent Cloud Private DNS zone | [`private_dns_zone`](plugins/modules/private_dns_zone.py) |
| `susunola.tencentcloud.privatelink_endpoint` | Manage Tencent Cloud PrivateLink endpoints | [`privatelink_endpoint`](plugins/modules/privatelink_endpoint.py) |
| `susunola.tencentcloud.privatelink_endpoint_service` | Manage Tencent Cloud PrivateLink endpoint services | [`privatelink_endpoint_service`](plugins/modules/privatelink_endpoint_service.py) |
| `susunola.tencentcloud.redis_account` | Manage TencentDB for Redis accounts | [`redis_account`](plugins/modules/redis_account.py) |
| `susunola.tencentcloud.redis_backup_config` | Manage TencentDB for Redis automatic backup configuration | [`redis_backup_config`](plugins/modules/redis_backup_config.py) |
| `susunola.tencentcloud.redis_instance` | Manage Tencent Cloud Redis instances | [`redis_instance`](plugins/modules/redis_instance.py) |
| `susunola.tencentcloud.redis_parameter_template` | Manage Tencent Cloud Redis parameter templates | [`redis_parameter_template`](plugins/modules/redis_parameter_template.py) |
| `susunola.tencentcloud.route_table` | Manage Tencent Cloud VPC route tables | [`route_table`](plugins/modules/route_table.py) |
| `susunola.tencentcloud.scf_alias` | Manage Tencent Cloud SCF function aliases | [`scf_alias`](plugins/modules/scf_alias.py) |
| `susunola.tencentcloud.scf_function` | Manage Tencent Cloud SCF functions | [`scf_function`](plugins/modules/scf_function.py) |
| `susunola.tencentcloud.scf_trigger` | Manage Tencent Cloud SCF triggers | [`scf_trigger`](plugins/modules/scf_trigger.py) |
| `susunola.tencentcloud.scf_version` | Manage Tencent Cloud SCF function versions | [`scf_version`](plugins/modules/scf_version.py) |
| `susunola.tencentcloud.security_group` | Manage Tencent Cloud security groups | [`security_group`](plugins/modules/security_group.py) |
| `susunola.tencentcloud.security_group_rule` | Manage Tencent Cloud security group rules | [`security_group_rule`](plugins/modules/security_group_rule.py) |
| `susunola.tencentcloud.sms_signature` | Manage Tencent Cloud SMS signatures | [`sms_signature`](plugins/modules/sms_signature.py) |
| `susunola.tencentcloud.sms_template` | Manage Tencent Cloud SMS templates | [`sms_template`](plugins/modules/sms_template.py) |
| `susunola.tencentcloud.sqlserver_account` | Manage TencentDB for SQL Server accounts | [`sqlserver_account`](plugins/modules/sqlserver_account.py) |
| `susunola.tencentcloud.sqlserver_backup_config` | Manage TencentDB for SQL Server backup configuration | [`sqlserver_backup_config`](plugins/modules/sqlserver_backup_config.py) |
| `susunola.tencentcloud.sqlserver_instance` | Manage TencentDB for SQL Server instances | [`sqlserver_instance`](plugins/modules/sqlserver_instance.py) |
| `susunola.tencentcloud.ssl_certificate` | Manage Tencent Cloud SSL certificates | [`ssl_certificate`](plugins/modules/ssl_certificate.py) |
| `susunola.tencentcloud.ssm_parameter` | Manage Tencent Cloud SSM secrets (parameters) | [`ssm_parameter`](plugins/modules/ssm_parameter.py) |
| `susunola.tencentcloud.ssm_product_secret` | Manage Tencent Cloud SSM managed-product secrets | [`ssm_product_secret`](plugins/modules/ssm_product_secret.py) |
| `susunola.tencentcloud.ssm_rotation` | Manage Tencent Cloud SSM secret rotation settings | [`ssm_rotation`](plugins/modules/ssm_rotation.py) |
| `susunola.tencentcloud.ssm_secret` | Manage Tencent Cloud Secrets Manager custom secrets | [`ssm_secret`](plugins/modules/ssm_secret.py) |
| `susunola.tencentcloud.ssm_secret_version` | Manage Tencent Cloud SSM secret versions | [`ssm_secret_version`](plugins/modules/ssm_secret_version.py) |
| `susunola.tencentcloud.ssm_ssh_key_pair_secret` | Manage Tencent Cloud SSM SSH key-pair secrets | [`ssm_ssh_key_pair_secret`](plugins/modules/ssm_ssh_key_pair_secret.py) |
| `susunola.tencentcloud.subnet` | Manage Tencent Cloud VPC subnets | [`subnet`](plugins/modules/subnet.py) |
| `susunola.tencentcloud.tag` | Manage tags on arbitrary Tencent Cloud resources | [`tag`](plugins/modules/tag.py) |
| `susunola.tencentcloud.tat_command` | Manage Tencent Cloud TAT commands | [`tat_command`](plugins/modules/tat_command.py) |
| `susunola.tencentcloud.tat_invocation` | Invoke or cancel a Tencent Cloud TAT command | [`tat_invocation`](plugins/modules/tat_invocation.py) |
| `susunola.tencentcloud.tat_invoker` | Manage Tencent Cloud TAT scheduled invokers | [`tat_invoker`](plugins/modules/tat_invoker.py) |
| `susunola.tencentcloud.tcaplusdb_cluster` | Manage Tencent Cloud TcaplusDB clusters | [`tcaplusdb_cluster`](plugins/modules/tcaplusdb_cluster.py) |
| `susunola.tencentcloud.tcb_auth_domain` | Manage Tencent CloudBase authentication domains | [`tcb_auth_domain`](plugins/modules/tcb_auth_domain.py) |
| `susunola.tencentcloud.tcb_environment` | Manage Tencent CloudBase environments | [`tcb_environment`](plugins/modules/tcb_environment.py) |
| `susunola.tencentcloud.tcb_http_service_route` | Manage Tencent CloudBase HTTP service domain routes | [`tcb_http_service_route`](plugins/modules/tcb_http_service_route.py) |
| `susunola.tencentcloud.tcb_static_store` | Manage Tencent CloudBase static website hosting | [`tcb_static_store`](plugins/modules/tcb_static_store.py) |
| `susunola.tencentcloud.tcm_access_log` | Manage Tencent Cloud Mesh access logging | [`tcm_access_log`](plugins/modules/tcm_access_log.py) |
| `susunola.tencentcloud.tcm_mesh` | Manage Tencent Cloud Mesh instances | [`tcm_mesh`](plugins/modules/tcm_mesh.py) |
| `susunola.tencentcloud.tcm_mesh_clusters` | Reconcile Tencent Cloud Mesh cluster links | [`tcm_mesh_clusters`](plugins/modules/tcm_mesh_clusters.py) |
| `susunola.tencentcloud.tcm_prometheus` | Manage Tencent Cloud Mesh Prometheus integration | [`tcm_prometheus`](plugins/modules/tcm_prometheus.py) |
| `susunola.tencentcloud.tcm_tracing` | Manage Tencent Cloud Mesh tracing | [`tcm_tracing`](plugins/modules/tcm_tracing.py) |
| `susunola.tencentcloud.tcr_instance` | Manage Tencent Cloud TCR enterprise instances | [`tcr_instance`](plugins/modules/tcr_instance.py) |
| `susunola.tencentcloud.tcr_namespace` | Manage Tencent Cloud TCR namespaces | [`tcr_namespace`](plugins/modules/tcr_namespace.py) |
| `susunola.tencentcloud.tcr_replication_instance` | Manage Tencent Cloud TCR replication instances | [`tcr_replication_instance`](plugins/modules/tcr_replication_instance.py) |
| `susunola.tencentcloud.tcr_replication_rule` | Manage Tencent Cloud TCR replication rules | [`tcr_replication_rule`](plugins/modules/tcr_replication_rule.py) |
| `susunola.tencentcloud.tcr_repository` | Manage a Tencent Cloud TCR repository | [`tcr_repository`](plugins/modules/tcr_repository.py) |
| `susunola.tencentcloud.tdcpg_account` | Govern a TDSQL-C PostgreSQL account | [`tdcpg_account`](plugins/modules/tdcpg_account.py) |
| `susunola.tencentcloud.tdcpg_cluster` | Manage Tencent Cloud TDSQL-C PostgreSQL clusters | [`tdcpg_cluster`](plugins/modules/tdcpg_cluster.py) |
| `susunola.tencentcloud.tdcpg_endpoint_wan` | Manage public access for a TDSQL-C PostgreSQL endpoint | [`tdcpg_endpoint_wan`](plugins/modules/tdcpg_endpoint_wan.py) |
| `susunola.tencentcloud.tdcpg_instance_state` | Manage TDSQL-C PostgreSQL instance runtime state | [`tdcpg_instance_state`](plugins/modules/tdcpg_instance_state.py) |
| `susunola.tencentcloud.tdmq_namespace` | Manage Tencent Cloud TDMQ Pulsar namespaces | [`tdmq_namespace`](plugins/modules/tdmq_namespace.py) |
| `susunola.tencentcloud.tdmq_namespace_role` | Manage TDMQ Pulsar namespace role permissions | [`tdmq_namespace_role`](plugins/modules/tdmq_namespace_role.py) |
| `susunola.tencentcloud.tdmq_rabbitmq_binding` | Manage TDMQ RabbitMQ bindings | [`tdmq_rabbitmq_binding`](plugins/modules/tdmq_rabbitmq_binding.py) |
| `susunola.tencentcloud.tdmq_rabbitmq_instance` | Manage Tencent Cloud TDMQ RabbitMQ dedicated instances | [`tdmq_rabbitmq_instance`](plugins/modules/tdmq_rabbitmq_instance.py) |
| `susunola.tencentcloud.tdmq_rabbitmq_permission` | Manage TDMQ RabbitMQ virtual host permissions | [`tdmq_rabbitmq_permission`](plugins/modules/tdmq_rabbitmq_permission.py) |
| `susunola.tencentcloud.tdmq_rabbitmq_user` | Manage TDMQ RabbitMQ users | [`tdmq_rabbitmq_user`](plugins/modules/tdmq_rabbitmq_user.py) |
| `susunola.tencentcloud.tdmq_rabbitmq_vhost` | Manage TDMQ RabbitMQ virtual hosts | [`tdmq_rabbitmq_vhost`](plugins/modules/tdmq_rabbitmq_vhost.py) |
| `susunola.tencentcloud.tdmq_rocketmq_cluster` | Manage TDMQ RocketMQ clusters | [`tdmq_rocketmq_cluster`](plugins/modules/tdmq_rocketmq_cluster.py) |
| `susunola.tencentcloud.tdmq_rocketmq_group` | Manage TDMQ RocketMQ consumer groups | [`tdmq_rocketmq_group`](plugins/modules/tdmq_rocketmq_group.py) |
| `susunola.tencentcloud.tdmq_rocketmq_namespace` | Manage TDMQ RocketMQ namespaces | [`tdmq_rocketmq_namespace`](plugins/modules/tdmq_rocketmq_namespace.py) |
| `susunola.tencentcloud.tdmq_rocketmq_permission` | Manage TDMQ RocketMQ namespace role permissions | [`tdmq_rocketmq_permission`](plugins/modules/tdmq_rocketmq_permission.py) |
| `susunola.tencentcloud.tdmq_rocketmq_role` | Manage TDMQ RocketMQ roles | [`tdmq_rocketmq_role`](plugins/modules/tdmq_rocketmq_role.py) |
| `susunola.tencentcloud.tdmq_rocketmq_topic` | Manage TDMQ RocketMQ topics | [`tdmq_rocketmq_topic`](plugins/modules/tdmq_rocketmq_topic.py) |
| `susunola.tencentcloud.tdmq_subscription` | Manage Tencent Cloud TDMQ Pulsar subscriptions | [`tdmq_subscription`](plugins/modules/tdmq_subscription.py) |
| `susunola.tencentcloud.tdmq_topic` | Manage Tencent Cloud TDMQ Pulsar topics | [`tdmq_topic`](plugins/modules/tdmq_topic.py) |
| `susunola.tencentcloud.tdmysql_account` | Manage Tencent Cloud TDSQL MySQL accounts | [`tdmysql_account`](plugins/modules/tdmysql_account.py) |
| `susunola.tencentcloud.tdmysql_account_privilege` | Manage scoped Tencent Cloud TDSQL MySQL account privileges | [`tdmysql_account_privilege`](plugins/modules/tdmysql_account_privilege.py) |
| `susunola.tencentcloud.tdmysql_backup_policy` | Manage Tencent Cloud TDSQL MySQL backup policy | [`tdmysql_backup_policy`](plugins/modules/tdmysql_backup_policy.py) |
| `susunola.tencentcloud.tdmysql_db_instance` | Manage Tencent Cloud TDMysql instances | [`tdmysql_db_instance`](plugins/modules/tdmysql_db_instance.py) |
| `susunola.tencentcloud.tdmysql_maintenance_window` | Manage Tencent Cloud TDSQL MySQL maintenance windows | [`tdmysql_maintenance_window`](plugins/modules/tdmysql_maintenance_window.py) |
| `susunola.tencentcloud.tdmysql_parameter` | Manage Tencent Cloud TDSQL MySQL instance parameters | [`tdmysql_parameter`](plugins/modules/tdmysql_parameter.py) |
| `susunola.tencentcloud.tdmysql_ssl` | Manage Tencent Cloud TDSQL MySQL SSL state | [`tdmysql_ssl`](plugins/modules/tdmysql_ssl.py) |
| `susunola.tencentcloud.tem_application` | Manage Tencent Cloud TEM applications | [`tem_application`](plugins/modules/tem_application.py) |
| `susunola.tencentcloud.tem_application_deployment` | Deploy Tencent Cloud TEM application versions | [`tem_application_deployment`](plugins/modules/tem_application_deployment.py) |
| `susunola.tencentcloud.tem_application_service` | Manage Tencent Cloud TEM application access services | [`tem_application_service`](plugins/modules/tem_application_service.py) |
| `susunola.tencentcloud.tem_environment` | Manage Tencent Cloud TEM environments | [`tem_environment`](plugins/modules/tem_environment.py) |
| `susunola.tencentcloud.teo_acceleration_domain` | Manage Tencent Cloud EdgeOne acceleration domains | [`teo_acceleration_domain`](plugins/modules/teo_acceleration_domain.py) |
| `susunola.tencentcloud.teo_dns_record` | Manage Tencent Cloud TEO DNS records | [`teo_dns_record`](plugins/modules/teo_dns_record.py) |
| `susunola.tencentcloud.teo_origin_group` | Manage Tencent Cloud EdgeOne origin groups | [`teo_origin_group`](plugins/modules/teo_origin_group.py) |
| `susunola.tencentcloud.teo_security_bot_lite` | Manage Tencent Cloud EdgeOne basic Bot protection | [`teo_security_bot_lite`](plugins/modules/teo_security_bot_lite.py) |
| `susunola.tencentcloud.teo_security_custom_rules` | Manage Tencent Cloud EdgeOne web security custom rules | [`teo_security_custom_rules`](plugins/modules/teo_security_custom_rules.py) |
| `susunola.tencentcloud.teo_security_exception_rules` | Manage Tencent Cloud EdgeOne web security exception rules | [`teo_security_exception_rules`](plugins/modules/teo_security_exception_rules.py) |
| `susunola.tencentcloud.teo_security_ip_group` | Manage Tencent Cloud EdgeOne security IP groups | [`teo_security_ip_group`](plugins/modules/teo_security_ip_group.py) |
| `susunola.tencentcloud.teo_security_managed_rules` | Manage Tencent Cloud EdgeOne managed WAF rules | [`teo_security_managed_rules`](plugins/modules/teo_security_managed_rules.py) |
| `susunola.tencentcloud.teo_security_rate_limiting_rules` | Manage Tencent Cloud EdgeOne precise rate-limiting rules | [`teo_security_rate_limiting_rules`](plugins/modules/teo_security_rate_limiting_rules.py) |
| `susunola.tencentcloud.teo_security_template_binding` | Manage Tencent Cloud EdgeOne security template bindings | [`teo_security_template_binding`](plugins/modules/teo_security_template_binding.py) |
| `susunola.tencentcloud.teo_web_security_template` | Manage Tencent Cloud EdgeOne web security templates | [`teo_web_security_template`](plugins/modules/teo_web_security_template.py) |
| `susunola.tencentcloud.teo_zone` | Manage Tencent Cloud EdgeOne zones | [`teo_zone`](plugins/modules/teo_zone.py) |
| `susunola.tencentcloud.thpc_cluster` | Manage Tencent Cloud THPC clusters | [`thpc_cluster`](plugins/modules/thpc_cluster.py) |
| `susunola.tencentcloud.tione_data_source` | Manage Tencent Cloud TIONE data sources | [`tione_data_source`](plugins/modules/tione_data_source.py) |
| `susunola.tencentcloud.tione_dataset` | Manage Tencent Cloud TIONE datasets | [`tione_dataset`](plugins/modules/tione_dataset.py) |
| `susunola.tencentcloud.tione_model_service` | Manage Tencent Cloud TIONE online model service configuration | [`tione_model_service`](plugins/modules/tione_model_service.py) |
| `susunola.tencentcloud.tione_model_service_auth_token` | Manage Tencent Cloud TIONE model service authentication tokens | [`tione_model_service_auth_token`](plugins/modules/tione_model_service_auth_token.py) |
| `susunola.tencentcloud.tione_model_service_state` | Manage Tencent Cloud TIONE online model service state | [`tione_model_service_state`](plugins/modules/tione_model_service_state.py) |
| `susunola.tencentcloud.tione_model_service_traffic` | Manage Tencent Cloud TIONE service authorization and version traffic | [`tione_model_service_traffic`](plugins/modules/tione_model_service_traffic.py) |
| `susunola.tencentcloud.tione_notebook` | Manage Tencent Cloud TIONE notebooks | [`tione_notebook`](plugins/modules/tione_notebook.py) |
| `susunola.tencentcloud.tione_training_model_version` | Manage versions of an existing Tencent Cloud TIONE training model | [`tione_training_model_version`](plugins/modules/tione_training_model_version.py) |
| `susunola.tencentcloud.tione_training_task` | Manage Tencent Cloud TIONE training tasks | [`tione_training_task`](plugins/modules/tione_training_task.py) |
| `susunola.tencentcloud.tke_addon` | Manage a Tencent Kubernetes Engine addon | [`tke_addon`](plugins/modules/tke_addon.py) |
| `susunola.tencentcloud.tke_backup_storage_location` | Manage Tencent Kubernetes Engine backup storage locations | [`tke_backup_storage_location`](plugins/modules/tke_backup_storage_location.py) |
| `susunola.tencentcloud.tke_cluster` | Manage Tencent Cloud TKE clusters | [`tke_cluster`](plugins/modules/tke_cluster.py) |
| `susunola.tencentcloud.tke_cluster_audit` | Manage Tencent Cloud TKE cluster audit logging | [`tke_cluster_audit`](plugins/modules/tke_cluster_audit.py) |
| `susunola.tencentcloud.tke_cluster_authentication` | Manage Tencent Cloud TKE cluster authentication options | [`tke_cluster_authentication`](plugins/modules/tke_cluster_authentication.py) |
| `susunola.tencentcloud.tke_cluster_autoscaler` | Manage the cluster autoscaler options of a Tencent Cloud TKE cluster | [`tke_cluster_autoscaler`](plugins/modules/tke_cluster_autoscaler.py) |
| `susunola.tencentcloud.tke_cluster_endpoint` | Manage Tencent Cloud TKE cluster access endpoints | [`tke_cluster_endpoint`](plugins/modules/tke_cluster_endpoint.py) |
| `susunola.tencentcloud.tke_cluster_kubeconfig` | Fetch the kubeconfig of a Tencent Cloud TKE cluster | [`tke_cluster_kubeconfig`](plugins/modules/tke_cluster_kubeconfig.py) |
| `susunola.tencentcloud.tke_cluster_upgrade` | Upgrade the Kubernetes version of a Tencent Cloud TKE cluster | [`tke_cluster_upgrade`](plugins/modules/tke_cluster_upgrade.py) |
| `susunola.tencentcloud.tke_node_pool` | Manage Tencent Cloud TKE cluster node pools | [`tke_node_pool`](plugins/modules/tke_node_pool.py) |
| `susunola.tencentcloud.trabbit_serverless_binding` | Manage Tencent Cloud RabbitMQ Serverless bindings | [`trabbit_serverless_binding`](plugins/modules/trabbit_serverless_binding.py) |
| `susunola.tencentcloud.trabbit_serverless_exchange` | Manage Tencent Cloud RabbitMQ Serverless exchanges | [`trabbit_serverless_exchange`](plugins/modules/trabbit_serverless_exchange.py) |
| `susunola.tencentcloud.trabbit_serverless_permission` | Manage Tencent Cloud RabbitMQ Serverless permissions | [`trabbit_serverless_permission`](plugins/modules/trabbit_serverless_permission.py) |
| `susunola.tencentcloud.trabbit_serverless_queue` | Manage Tencent Cloud RabbitMQ Serverless queues | [`trabbit_serverless_queue`](plugins/modules/trabbit_serverless_queue.py) |
| `susunola.tencentcloud.trabbit_serverless_user` | Manage Tencent Cloud RabbitMQ Serverless users | [`trabbit_serverless_user`](plugins/modules/trabbit_serverless_user.py) |
| `susunola.tencentcloud.trabbit_serverless_vhost` | Manage Tencent Cloud RabbitMQ Serverless virtual hosts | [`trabbit_serverless_vhost`](plugins/modules/trabbit_serverless_vhost.py) |
| `susunola.tencentcloud.tse_cloud_native_gateway` | Manage a Tencent Cloud TSE cloud-native API gateway | [`tse_cloud_native_gateway`](plugins/modules/tse_cloud_native_gateway.py) |
| `susunola.tencentcloud.tse_config_file` | Manage a Tencent Cloud TSE configuration file | [`tse_config_file`](plugins/modules/tse_config_file.py) |
| `susunola.tencentcloud.tse_config_file_deployment` | Atomically deploy a Tencent Cloud TSE configuration file and release | [`tse_config_file_deployment`](plugins/modules/tse_config_file_deployment.py) |
| `susunola.tencentcloud.tse_config_file_group` | Manage a Tencent Cloud TSE configuration file group | [`tse_config_file_group`](plugins/modules/tse_config_file_group.py) |
| `susunola.tencentcloud.tse_config_file_release` | Manage a Tencent Cloud TSE configuration file release | [`tse_config_file_release`](plugins/modules/tse_config_file_release.py) |
| `susunola.tencentcloud.tse_gateway_autoscaler_binding` | Bind a TSE gateway autoscaler strategy to gateway groups | [`tse_gateway_autoscaler_binding`](plugins/modules/tse_gateway_autoscaler_binding.py) |
| `susunola.tencentcloud.tse_gateway_autoscaler_strategy` | Manage a Tencent Cloud TSE gateway autoscaler strategy | [`tse_gateway_autoscaler_strategy`](plugins/modules/tse_gateway_autoscaler_strategy.py) |
| `susunola.tencentcloud.tse_gateway_canary_rule` | Manage a Tencent Cloud TSE gateway canary rule | [`tse_gateway_canary_rule`](plugins/modules/tse_gateway_canary_rule.py) |
| `susunola.tencentcloud.tse_gateway_certificate` | Manage a Tencent Cloud TSE gateway certificate | [`tse_gateway_certificate`](plugins/modules/tse_gateway_certificate.py) |
| `susunola.tencentcloud.tse_gateway_console_network` | Manage Tencent Cloud TSE gateway console network access | [`tse_gateway_console_network`](plugins/modules/tse_gateway_console_network.py) |
| `susunola.tencentcloud.tse_gateway_consumer` | Manage a Tencent Cloud TSE API gateway consumer | [`tse_gateway_consumer`](plugins/modules/tse_gateway_consumer.py) |
| `susunola.tencentcloud.tse_gateway_consumer_group` | Manage a Tencent Cloud TSE API gateway consumer group | [`tse_gateway_consumer_group`](plugins/modules/tse_gateway_consumer_group.py) |
| `susunola.tencentcloud.tse_gateway_consumer_group_membership` | Manage TSE API gateway consumer group membership | [`tse_gateway_consumer_group_membership`](plugins/modules/tse_gateway_consumer_group_membership.py) |
| `susunola.tencentcloud.tse_gateway_cors` | Manage CORS policy on a Tencent Cloud TSE gateway resource | [`tse_gateway_cors`](plugins/modules/tse_gateway_cors.py) |
| `susunola.tencentcloud.tse_gateway_ip_restriction` | Manage IP access control on a Tencent Cloud TSE gateway resource | [`tse_gateway_ip_restriction`](plugins/modules/tse_gateway_ip_restriction.py) |
| `susunola.tencentcloud.tse_gateway_model_api` | Manage a Tencent Cloud TSE AI gateway model API | [`tse_gateway_model_api`](plugins/modules/tse_gateway_model_api.py) |
| `susunola.tencentcloud.tse_gateway_model_api_group_auth` | Manage TSE gateway Model API consumer group authorization | [`tse_gateway_model_api_group_auth`](plugins/modules/tse_gateway_model_api_group_auth.py) |
| `susunola.tencentcloud.tse_gateway_model_service` | Manage a Tencent Cloud TSE AI gateway model service | [`tse_gateway_model_service`](plugins/modules/tse_gateway_model_service.py) |
| `susunola.tencentcloud.tse_gateway_public_network` | Manage a Tencent Cloud TSE gateway public network | [`tse_gateway_public_network`](plugins/modules/tse_gateway_public_network.py) |
| `susunola.tencentcloud.tse_gateway_rate_limit` | Manage Tencent Cloud TSE service or route rate limiting | [`tse_gateway_rate_limit`](plugins/modules/tse_gateway_rate_limit.py) |
| `susunola.tencentcloud.tse_gateway_route` | Manage a Tencent Cloud TSE gateway route | [`tse_gateway_route`](plugins/modules/tse_gateway_route.py) |
| `susunola.tencentcloud.tse_gateway_secret_key` | Manage a Tencent Cloud TSE API gateway secret key | [`tse_gateway_secret_key`](plugins/modules/tse_gateway_secret_key.py) |
| `susunola.tencentcloud.tse_gateway_server_group` | Manage a Tencent Cloud TSE gateway server group | [`tse_gateway_server_group`](plugins/modules/tse_gateway_server_group.py) |
| `susunola.tencentcloud.tse_gateway_service` | Manage a Tencent Cloud TSE gateway upstream service | [`tse_gateway_service`](plugins/modules/tse_gateway_service.py) |
| `susunola.tencentcloud.tse_gateway_service_source` | Manage a Tencent Cloud TSE gateway service source | [`tse_gateway_service_source`](plugins/modules/tse_gateway_service_source.py) |
| `susunola.tencentcloud.tse_gateway_upstream_node_status` | Reconcile Tencent Cloud TSE gateway upstream node health state | [`tse_gateway_upstream_node_status`](plugins/modules/tse_gateway_upstream_node_status.py) |
| `susunola.tencentcloud.tse_gateway_waf_domains` | Manage Tencent Cloud TSE gateway WAF domains | [`tse_gateway_waf_domains`](plugins/modules/tse_gateway_waf_domains.py) |
| `susunola.tencentcloud.tse_gateway_waf_protection` | Manage Tencent Cloud TSE gateway WAF protection | [`tse_gateway_waf_protection`](plugins/modules/tse_gateway_waf_protection.py) |
| `susunola.tencentcloud.tse_governance_alias` | Manage a Tencent Cloud TSE governance service alias | [`tse_governance_alias`](plugins/modules/tse_governance_alias.py) |
| `susunola.tencentcloud.tse_governance_host_retirement` | Retire all Tencent Cloud TSE governance instances on a host | [`tse_governance_host_retirement`](plugins/modules/tse_governance_host_retirement.py) |
| `susunola.tencentcloud.tse_governance_instance` | Manage a Tencent Cloud TSE governance service instance | [`tse_governance_instance`](plugins/modules/tse_governance_instance.py) |
| `susunola.tencentcloud.tse_governance_lane_group` | Manage a Tencent Cloud TSE governance lane group | [`tse_governance_lane_group`](plugins/modules/tse_governance_lane_group.py) |
| `susunola.tencentcloud.tse_governance_namespace` | Manage a Tencent Cloud TSE governance namespace | [`tse_governance_namespace`](plugins/modules/tse_governance_namespace.py) |
| `susunola.tencentcloud.tse_governance_service` | Manage a Tencent Cloud TSE governance service | [`tse_governance_service`](plugins/modules/tse_governance_service.py) |
| `susunola.tencentcloud.tse_sre_instance` | Manage Tencent Cloud TSE service registry engines | [`tse_sre_instance`](plugins/modules/tse_sre_instance.py) |
| `susunola.tencentcloud.tsf_application` | Manage a Tencent Cloud TSF application | [`tsf_application`](plugins/modules/tsf_application.py) |
| `susunola.tencentcloud.tsf_application_config` | Manage a versioned Tencent Cloud TSF application configuration | [`tsf_application_config`](plugins/modules/tsf_application_config.py) |
| `susunola.tencentcloud.tsf_application_config_release` | Manage a Tencent Cloud TSF application configuration release | [`tsf_application_config_release`](plugins/modules/tsf_application_config_release.py) |
| `susunola.tencentcloud.tsf_cluster` | Manage a Tencent Cloud TSF cluster | [`tsf_cluster`](plugins/modules/tsf_cluster.py) |
| `susunola.tencentcloud.tsf_container_deployment_group` | Manage a Tencent Cloud TSF container deployment group | [`tsf_container_deployment_group`](plugins/modules/tsf_container_deployment_group.py) |
| `susunola.tencentcloud.tsf_lane` | Manage a Tencent Cloud TSF traffic lane | [`tsf_lane`](plugins/modules/tsf_lane.py) |
| `susunola.tencentcloud.tsf_lane_rule` | Manage a Tencent Cloud TSF traffic lane rule | [`tsf_lane_rule`](plugins/modules/tsf_lane_rule.py) |
| `susunola.tencentcloud.tsf_microservice` | Manage a Tencent Cloud TSF microservice | [`tsf_microservice`](plugins/modules/tsf_microservice.py) |
| `susunola.tencentcloud.tsf_namespace` | Manage a Tencent Cloud TSF namespace | [`tsf_namespace`](plugins/modules/tsf_namespace.py) |
| `susunola.tencentcloud.tsf_public_config` | Manage a versioned Tencent Cloud TSF public configuration | [`tsf_public_config`](plugins/modules/tsf_public_config.py) |
| `susunola.tencentcloud.tsf_repository` | Manage a Tencent Cloud TSF package repository | [`tsf_repository`](plugins/modules/tsf_repository.py) |
| `susunola.tencentcloud.tsf_vm_deployment_group` | Manage a Tencent Cloud TSF virtual-machine deployment group | [`tsf_vm_deployment_group`](plugins/modules/tsf_vm_deployment_group.py) |
| `susunola.tencentcloud.vdb_instance` | Manage Tencent Cloud VectorDB instances | [`vdb_instance`](plugins/modules/vdb_instance.py) |
| `susunola.tencentcloud.vod_class` | Manage Tencent Cloud VOD media classes | [`vod_class`](plugins/modules/vod_class.py) |
| `susunola.tencentcloud.vod_sub_app` | Manage Tencent Cloud VOD sub-applications | [`vod_sub_app`](plugins/modules/vod_sub_app.py) |
| `susunola.tencentcloud.vpc` | Manage Tencent Cloud VPCs | [`vpc`](plugins/modules/vpc.py) |
| `susunola.tencentcloud.vpc_address_template` | Manage Tencent Cloud VPC address templates | [`vpc_address_template`](plugins/modules/vpc_address_template.py) |
| `susunola.tencentcloud.vpc_address_template_group` | Manage Tencent Cloud VPC address-template groups | [`vpc_address_template_group`](plugins/modules/vpc_address_template_group.py) |
| `susunola.tencentcloud.vpc_flow_log` | Manage Tencent Cloud VPC flow logs | [`vpc_flow_log`](plugins/modules/vpc_flow_log.py) |
| `susunola.tencentcloud.vpn_connection` | Manage Tencent Cloud IPsec VPN connections | [`vpn_connection`](plugins/modules/vpn_connection.py) |
| `susunola.tencentcloud.vpn_gateway` | Manage Tencent Cloud VPN gateways | [`vpn_gateway`](plugins/modules/vpn_gateway.py) |
| `susunola.tencentcloud.waf_anti_info_leak_rule` | Manage Tencent Cloud WAF sensitive-information leakage rules | [`waf_anti_info_leak_rule`](plugins/modules/waf_anti_info_leak_rule.py) |
| `susunola.tencentcloud.waf_anti_tamper_rule` | Manage Tencent Cloud WAF anti-tamper URL rules | [`waf_anti_tamper_rule`](plugins/modules/waf_anti_tamper_rule.py) |
| `susunola.tencentcloud.waf_area_ban_rule` | Manage Tencent Cloud WAF geographic blocking | [`waf_area_ban_rule`](plugins/modules/waf_area_ban_rule.py) |
| `susunola.tencentcloud.waf_attack_white_rule` | Manage Tencent Cloud WAF attack-signature allow rules | [`waf_attack_white_rule`](plugins/modules/waf_attack_white_rule.py) |
| `susunola.tencentcloud.waf_auto_deny` | Manage Tencent Cloud WAF automatic IP blocking | [`waf_auto_deny`](plugins/modules/waf_auto_deny.py) |
| `susunola.tencentcloud.waf_cc_rule` | Manage Tencent Cloud WAF CC protection rules | [`waf_cc_rule`](plugins/modules/waf_cc_rule.py) |
| `susunola.tencentcloud.waf_custom_rule` | Manage Tencent Cloud WAF custom rules | [`waf_custom_rule`](plugins/modules/waf_custom_rule.py) |
| `susunola.tencentcloud.waf_custom_white_rule` | Manage Tencent Cloud WAF precision allowlist rules | [`waf_custom_white_rule`](plugins/modules/waf_custom_white_rule.py) |
| `susunola.tencentcloud.waf_host` | Manage Tencent Cloud WAF protected hosts | [`waf_host`](plugins/modules/waf_host.py) |
| `susunola.tencentcloud.waf_ip_access_control` | Manage Tencent Cloud WAF IP access-control rules | [`waf_ip_access_control`](plugins/modules/waf_ip_access_control.py) |
| `susunola.tencentcloud.waf_owasp_white_rule` | Manage Tencent Cloud WAF OWASP allowlist rules | [`waf_owasp_white_rule`](plugins/modules/waf_owasp_white_rule.py) |
| `susunola.tencentcloud.waf_protect_group` | Manage Tencent Cloud WAF protection object groups | [`waf_protect_group`](plugins/modules/waf_protect_group.py) |
| `susunola.tencentcloud.waf_threat_intelligence` | Manage Tencent Cloud WAF threat-intelligence blocking | [`waf_threat_intelligence`](plugins/modules/waf_threat_intelligence.py) |

</details>

<details>
<summary><strong>Browse all 435 read-only <code>_info</code> modules</strong></summary>

Read-only `_info` modules (return `changed=false`):

| Module (FQCN) | Purpose | Examples |
| --- | --- | --- |
| `susunola.tencentcloud.acp_scan_task_info` | Gather information about Tencent Cloud ACP scan tasks | [`acp_scan_task_info`](plugins/modules/acp_scan_task_info.py) |
| `susunola.tencentcloud.adp_agent_release_preview_info` | Gather information about Tencent Cloud ADP agent release previews | [`adp_agent_release_preview_info`](plugins/modules/adp_agent_release_preview_info.py) |
| `susunola.tencentcloud.advisor_strategy_info` | Gather information about Tencent Cloud ADVISOR strategies | [`advisor_strategy_info`](plugins/modules/advisor_strategy_info.py) |
| `susunola.tencentcloud.ags_sandbox_instance_info` | Gather information about Tencent Cloud AGS sandbox instances | [`ags_sandbox_instance_info`](plugins/modules/ags_sandbox_instance_info.py) |
| `susunola.tencentcloud.alb_listener_info` | Gather information about Tencent Cloud ALB listeners | [`alb_listener_info`](plugins/modules/alb_listener_info.py) |
| `susunola.tencentcloud.alb_load_balancer_info` | Gather information about Tencent Cloud ALB instances | [`alb_load_balancer_info`](plugins/modules/alb_load_balancer_info.py) |
| `susunola.tencentcloud.alb_security_policy_info` | Gather information about Tencent Cloud ALB security policies | [`alb_security_policy_info`](plugins/modules/alb_security_policy_info.py) |
| `susunola.tencentcloud.alb_target_group_info` | Gather information about Tencent Cloud ALB target groups | [`alb_target_group_info`](plugins/modules/alb_target_group_info.py) |
| `susunola.tencentcloud.alb_target_group_targets_info` | Gather information about Tencent Cloud ALB target group targets | [`alb_target_group_targets_info`](plugins/modules/alb_target_group_targets_info.py) |
| `susunola.tencentcloud.ame_ktv_robot_info` | Gather information about Tencent Cloud AME ktv robots | [`ame_ktv_robot_info`](plugins/modules/ame_ktv_robot_info.py) |
| `susunola.tencentcloud.ams_task_info` | Gather information about Tencent Cloud AMS tasks | [`ams_task_info`](plugins/modules/ams_task_info.py) |
| `susunola.tencentcloud.anicloud_resource_info` | Gather information about Tencent Cloud ANICLOUD resources | [`anicloud_resource_info`](plugins/modules/anicloud_resource_info.py) |
| `susunola.tencentcloud.antiddos_ddos_block_record_info` | Gather information about Tencent Cloud ANTIDDOS DDoS block records | [`antiddos_ddos_block_record_info`](plugins/modules/antiddos_ddos_block_record_info.py) |
| `susunola.tencentcloud.ape_auth_user_info` | Gather information about Tencent Cloud APE auth users | [`ape_auth_user_info`](plugins/modules/ape_auth_user_info.py) |
| `susunola.tencentcloud.api_gateway_api_info` | Gather information about Tencent Cloud API Gateway APIs | [`api_gateway_api_info`](plugins/modules/api_gateway_api_info.py) |
| `susunola.tencentcloud.api_gateway_service_info` | Gather information about Tencent Cloud API Gateway services | [`api_gateway_service_info`](plugins/modules/api_gateway_service_info.py) |
| `susunola.tencentcloud.api_product_info` | Gather information about Tencent Cloud API products | [`api_product_info`](plugins/modules/api_product_info.py) |
| `susunola.tencentcloud.apigateway_service_info` | Gather information about Tencent Cloud API Gateway services | [`apigateway_service_info`](plugins/modules/apigateway_service_info.py) |
| `susunola.tencentcloud.apis_agent_app_mcp_server_info` | Gather information about Tencent Cloud APIS agent app mcp servers | [`apis_agent_app_mcp_server_info`](plugins/modules/apis_agent_app_mcp_server_info.py) |
| `susunola.tencentcloud.apm_general_span_info` | Gather information about Tencent Cloud APM general spans | [`apm_general_span_info`](plugins/modules/apm_general_span_info.py) |
| `susunola.tencentcloud.as_scaling_group_info` | Gather information about Tencent Cloud auto scaling groups | [`as_scaling_group_info`](plugins/modules/as_scaling_group_info.py) |
| `susunola.tencentcloud.asr_async_recognition_task_info` | Gather information about Tencent Cloud ASR async recognition tasks | [`asr_async_recognition_task_info`](plugins/modules/asr_async_recognition_task_info.py) |
| `susunola.tencentcloud.asw_flow_service_info` | Gather information about Tencent Cloud ASW flow services | [`asw_flow_service_info`](plugins/modules/asw_flow_service_info.py) |
| `susunola.tencentcloud.ba_auth_info` | Gather information about Tencent Cloud BA auth | [`ba_auth_info`](plugins/modules/ba_auth_info.py) |
| `susunola.tencentcloud.batch_compute_env_create_info` | Gather information about Tencent Cloud BATCH compute env creates | [`batch_compute_env_create_info`](plugins/modules/batch_compute_env_create_info.py) |
| `susunola.tencentcloud.bdrc_backup_vault_info` | Gather information about Tencent Cloud BDRC backup vaults | [`bdrc_backup_vault_info`](plugins/modules/bdrc_backup_vault_info.py) |
| `susunola.tencentcloud.bh_device_group_member_info` | Gather information about Tencent Cloud BH device group members | [`bh_device_group_member_info`](plugins/modules/bh_device_group_member_info.py) |
| `susunola.tencentcloud.bi_auth_api_key_info` | Gather information about Tencent Cloud BI auth api keys | [`bi_auth_api_key_info`](plugins/modules/bi_auth_api_key_info.py) |
| `susunola.tencentcloud.billing_balance_info` | Gather information about the Tencent Cloud account balance | [`billing_balance_info`](plugins/modules/billing_balance_info.py) |
| `susunola.tencentcloud.bizlive_worker_info` | Gather information about Tencent Cloud BIZLIVE workers | [`bizlive_worker_info`](plugins/modules/bizlive_worker_info.py) |
| `susunola.tencentcloud.bm_device_info` | Gather information about Tencent Cloud BM devices | [`bm_device_info`](plugins/modules/bm_device_info.py) |
| `susunola.tencentcloud.bma_bp_fake_app_info` | Gather information about Tencent Cloud BMA bp fake apps | [`bma_bp_fake_app_info`](plugins/modules/bma_bp_fake_app_info.py) |
| `susunola.tencentcloud.bmeip_eip_acl_info` | Gather information about Tencent Cloud BMEIP eip acls | [`bmeip_eip_acl_info`](plugins/modules/bmeip_eip_acl_info.py) |
| `susunola.tencentcloud.bmlb_load_balancer_info` | Gather information about Tencent Cloud BMLB load balancers | [`bmlb_load_balancer_info`](plugins/modules/bmlb_load_balancer_info.py) |
| `susunola.tencentcloud.bmvpc_customer_gateway_info` | Gather information about Tencent Cloud BMVPC customer gateways | [`bmvpc_customer_gateway_info`](plugins/modules/bmvpc_customer_gateway_info.py) |
| `susunola.tencentcloud.bsca_kb_component_info` | Gather information about Tencent Cloud BSCA kb components | [`bsca_kb_component_info`](plugins/modules/bsca_kb_component_info.py) |
| `susunola.tencentcloud.cam_group_info` | Gather information about Tencent Cloud CAM groups | [`cam_group_info`](plugins/modules/cam_group_info.py) |
| `susunola.tencentcloud.cam_group_membership_info` | Gather information about Tencent Cloud CAM group memberships of a user | [`cam_group_membership_info`](plugins/modules/cam_group_membership_info.py) |
| `susunola.tencentcloud.cam_oidc_provider_info` | Gather information about a Tencent Cloud CAM OIDC identity provider | [`cam_oidc_provider_info`](plugins/modules/cam_oidc_provider_info.py) |
| `susunola.tencentcloud.cam_policy_attachment_info` | Gather information about Tencent Cloud CAM policy attachments | [`cam_policy_attachment_info`](plugins/modules/cam_policy_attachment_info.py) |
| `susunola.tencentcloud.cam_policy_info` | Gather information about Tencent Cloud CAM policies | [`cam_policy_info`](plugins/modules/cam_policy_info.py) |
| `susunola.tencentcloud.cam_role_info` | Gather information about Tencent Cloud CAM roles | [`cam_role_info`](plugins/modules/cam_role_info.py) |
| `susunola.tencentcloud.cam_saml_provider_info` | Gather information about Tencent Cloud CAM SAML identity providers | [`cam_saml_provider_info`](plugins/modules/cam_saml_provider_info.py) |
| `susunola.tencentcloud.cam_user_info` | Gather information about Tencent Cloud CAM sub-users | [`cam_user_info`](plugins/modules/cam_user_info.py) |
| `susunola.tencentcloud.captcha_user_all_app_id_info` | Gather information about Tencent Cloud CAPTCHA user all app ids | [`captcha_user_all_app_id_info`](plugins/modules/captcha_user_all_app_id_info.py) |
| `susunola.tencentcloud.cat_probe_task_info` | Gather information about Tencent Cloud CAT probe tasks | [`cat_probe_task_info`](plugins/modules/cat_probe_task_info.py) |
| `susunola.tencentcloud.cbs_auto_snapshot_policy_info` | Gather information about Tencent Cloud CBS automatic snapshot policies | [`cbs_auto_snapshot_policy_info`](plugins/modules/cbs_auto_snapshot_policy_info.py) |
| `susunola.tencentcloud.cbs_disk_info` | Gather information about Tencent Cloud CBS disks | [`cbs_disk_info`](plugins/modules/cbs_disk_info.py) |
| `susunola.tencentcloud.cbs_snapshot_info` | Gather information about Tencent Cloud CBS snapshots | [`cbs_snapshot_info`](plugins/modules/cbs_snapshot_info.py) |
| `susunola.tencentcloud.ccc_extension_info` | Gather information about Tencent Cloud CCC extensions | [`ccc_extension_info`](plugins/modules/ccc_extension_info.py) |
| `susunola.tencentcloud.ccn_attachment_info` | Gather information about Tencent Cloud CCN attachments | [`ccn_attachment_info`](plugins/modules/ccn_attachment_info.py) |
| `susunola.tencentcloud.ccn_info` | Gather information about Tencent Cloud CCN instances | [`ccn_info`](plugins/modules/ccn_info.py) |
| `susunola.tencentcloud.cdb_account_info` | Gather information about Tencent Cloud CDB accounts | [`cdb_account_info`](plugins/modules/cdb_account_info.py) |
| `susunola.tencentcloud.cdb_account_privilege_info` | Gather information about Tencent Cloud CDB account privileges | [`cdb_account_privilege_info`](plugins/modules/cdb_account_privilege_info.py) |
| `susunola.tencentcloud.cdb_audit_config_info` | Gather information about a Tencent Cloud CDB audit configuration | [`cdb_audit_config_info`](plugins/modules/cdb_audit_config_info.py) |
| `susunola.tencentcloud.cdb_backup_config_info` | Gather information about Tencent Cloud CDB backup configuration | [`cdb_backup_config_info`](plugins/modules/cdb_backup_config_info.py) |
| `susunola.tencentcloud.cdb_database_info` | Gather information about Tencent Cloud CDB databases | [`cdb_database_info`](plugins/modules/cdb_database_info.py) |
| `susunola.tencentcloud.cdb_instance_info` | Gather information about TencentDB for MySQL instances | [`cdb_instance_info`](plugins/modules/cdb_instance_info.py) |
| `susunola.tencentcloud.cdb_parameter_template_info` | Gather information about Tencent Cloud CDB parameter templates | [`cdb_parameter_template_info`](plugins/modules/cdb_parameter_template_info.py) |
| `susunola.tencentcloud.cdc_dedicated_cluster_order_info` | Gather information about Tencent Cloud CDC dedicated cluster orders | [`cdc_dedicated_cluster_order_info`](plugins/modules/cdc_dedicated_cluster_order_info.py) |
| `susunola.tencentcloud.cdn_domain_info` | Gather information about Tencent Cloud CDN domains | [`cdn_domain_info`](plugins/modules/cdn_domain_info.py) |
| `susunola.tencentcloud.cds_asset_info` | Gather information about Tencent Cloud CDS assets | [`cds_asset_info`](plugins/modules/cds_asset_info.py) |
| `susunola.tencentcloud.cdwch_cn_instance_info` | Gather information about Tencent Cloud CDWCH cn instances | [`cdwch_cn_instance_info`](plugins/modules/cdwch_cn_instance_info.py) |
| `susunola.tencentcloud.cdwdoris_cluster_configs_history_info` | Gather information about Tencent Cloud CDWDORIS cluster configs histories | [`cdwdoris_cluster_configs_history_info`](plugins/modules/cdwdoris_cluster_configs_history_info.py) |
| `susunola.tencentcloud.cdwpg_account_info` | Gather information about Tencent Cloud CDWPG accounts | [`cdwpg_account_info`](plugins/modules/cdwpg_account_info.py) |
| `susunola.tencentcloud.cdz_cloud_dedicated_zone_host_info` | Gather information about Tencent Cloud CDZ cloud dedicated zone hosts | [`cdz_cloud_dedicated_zone_host_info`](plugins/modules/cdz_cloud_dedicated_zone_host_info.py) |
| `susunola.tencentcloud.cetcd_etcd_instance_info` | Gather information about Tencent Cloud CETCD etcd instances | [`cetcd_etcd_instance_info`](plugins/modules/cetcd_etcd_instance_info.py) |
| `susunola.tencentcloud.cfg_action_library_info` | Gather information about Tencent Cloud CFG action libraries | [`cfg_action_library_info`](plugins/modules/cfg_action_library_info.py) |
| `susunola.tencentcloud.cfs_auto_snapshot_policy_info` | Gather information about Tencent Cloud CFS automatic snapshot policies | [`cfs_auto_snapshot_policy_info`](plugins/modules/cfs_auto_snapshot_policy_info.py) |
| `susunola.tencentcloud.cfs_file_system_info` | Gather information about Tencent Cloud CFS file systems | [`cfs_file_system_info`](plugins/modules/cfs_file_system_info.py) |
| `susunola.tencentcloud.cfs_permission_group_info` | Gather information about Tencent Cloud CFS permission groups | [`cfs_permission_group_info`](plugins/modules/cfs_permission_group_info.py) |
| `susunola.tencentcloud.cfs_permission_rule_info` | Gather information about Tencent Cloud CFS permission group rules | [`cfs_permission_rule_info`](plugins/modules/cfs_permission_rule_info.py) |
| `susunola.tencentcloud.cfs_snapshot_info` | Gather information about Tencent Cloud CFS snapshots | [`cfs_snapshot_info`](plugins/modules/cfs_snapshot_info.py) |
| `susunola.tencentcloud.cfw_cluster_nat_ccn_fw_switch_info` | Gather information about Tencent Cloud CFW cluster nat ccn fw switches | [`cfw_cluster_nat_ccn_fw_switch_info`](plugins/modules/cfw_cluster_nat_ccn_fw_switch_info.py) |
| `susunola.tencentcloud.chc_device_info` | Gather information about Tencent Cloud CHC devices | [`chc_device_info`](plugins/modules/chc_device_info.py) |
| `susunola.tencentcloud.chdfs_file_system_info` | Gather information about Tencent Cloud CHDFS file systems | [`chdfs_file_system_info`](plugins/modules/chdfs_file_system_info.py) |
| `susunola.tencentcloud.ciam_user_store_info` | Gather information about Tencent Cloud CIAM user stores | [`ciam_user_store_info`](plugins/modules/ciam_user_store_info.py) |
| `susunola.tencentcloud.ckafka_instance_info` | Gather information about Tencent Cloud CKafka instances | [`ckafka_instance_info`](plugins/modules/ckafka_instance_info.py) |
| `susunola.tencentcloud.ckafka_topic_info` | Gather information about Tencent Cloud CKafka topics | [`ckafka_topic_info`](plugins/modules/ckafka_topic_info.py) |
| `susunola.tencentcloud.ckafka_user_info` | Gather information about Tencent Cloud CKafka users | [`ckafka_user_info`](plugins/modules/ckafka_user_info.py) |
| `susunola.tencentcloud.clb_listener_info` | Gather information about Tencent Cloud CLB listeners | [`clb_listener_info`](plugins/modules/clb_listener_info.py) |
| `susunola.tencentcloud.clb_listener_target_info` | Gather information about Tencent Cloud CLB listener targets | [`clb_listener_target_info`](plugins/modules/clb_listener_target_info.py) |
| `susunola.tencentcloud.clb_load_balancer_info` | Gather information about Tencent Cloud CLB load balancers | [`clb_load_balancer_info`](plugins/modules/clb_load_balancer_info.py) |
| `susunola.tencentcloud.clb_target_group_info` | Gather information about Tencent Cloud CLB target groups | [`clb_target_group_info`](plugins/modules/clb_target_group_info.py) |
| `susunola.tencentcloud.cloudaudit_event_info` | Gather information about Tencent Cloud CloudAudit events | [`cloudaudit_event_info`](plugins/modules/cloudaudit_event_info.py) |
| `susunola.tencentcloud.cloudhsm_vsm_info` | Gather information about Tencent Cloud CLOUDHSM vsms | [`cloudhsm_vsm_info`](plugins/modules/cloudhsm_vsm_info.py) |
| `susunola.tencentcloud.cloudrc_resource_info` | Gather information about Tencent Cloud CLOUDRC resources | [`cloudrc_resource_info`](plugins/modules/cloudrc_resource_info.py) |
| `susunola.tencentcloud.cloudstudio_image_info` | Gather information about Tencent Cloud CLOUDSTUDIO images | [`cloudstudio_image_info`](plugins/modules/cloudstudio_image_info.py) |
| `susunola.tencentcloud.cls_config_info` | Gather information about Tencent Cloud CLS collection configurations | [`cls_config_info`](plugins/modules/cls_config_info.py) |
| `susunola.tencentcloud.cls_config_machine_group_binding_info` | Gather information about Tencent Cloud CLS machine group config bindings | [`cls_config_machine_group_binding_info`](plugins/modules/cls_config_machine_group_binding_info.py) |
| `susunola.tencentcloud.cls_index_info` | Gather information about a Tencent Cloud CLS topic index | [`cls_index_info`](plugins/modules/cls_index_info.py) |
| `susunola.tencentcloud.cls_logset_info` | Gather information about Tencent Cloud CLS logsets | [`cls_logset_info`](plugins/modules/cls_logset_info.py) |
| `susunola.tencentcloud.cls_machine_group_info` | Gather information about Tencent Cloud CLS machine groups | [`cls_machine_group_info`](plugins/modules/cls_machine_group_info.py) |
| `susunola.tencentcloud.cls_shipper_info` | Gather information about Tencent Cloud CLS shippers | [`cls_shipper_info`](plugins/modules/cls_shipper_info.py) |
| `susunola.tencentcloud.cls_topic_info` | Gather information about Tencent Cloud CLS log topics | [`cls_topic_info`](plugins/modules/cls_topic_info.py) |
| `susunola.tencentcloud.cme_platform_info` | Gather information about Tencent Cloud CME platforms | [`cme_platform_info`](plugins/modules/cme_platform_info.py) |
| `susunola.tencentcloud.cmq_queue_info` | Gather information about Tencent Cloud CMQ queues | [`cmq_queue_info`](plugins/modules/cmq_queue_info.py) |
| `susunola.tencentcloud.cms_lib_sample_info` | Gather information about Tencent Cloud CMS lib samples | [`cms_lib_sample_info`](plugins/modules/cms_lib_sample_info.py) |
| `susunola.tencentcloud.cngw_cloud_native_api_gateway_llm_model_api_info` | Gather information about Tencent Cloud CNGW cloud native api gateway llm model apis | [`cngw_cloud_native_api_gateway_llm_model_api_info`](plugins/modules/cngw_cloud_native_api_gateway_llm_model_api_info.py) |
| `susunola.tencentcloud.config_aggregate_compliance_pack_info` | Gather information about Tencent Cloud CONFIG aggregate compliance packs | [`config_aggregate_compliance_pack_info`](plugins/modules/config_aggregate_compliance_pack_info.py) |
| `susunola.tencentcloud.config_aggregator_info` | Gather information about Tencent Cloud Config aggregators | [`config_aggregator_info`](plugins/modules/config_aggregator_info.py) |
| `susunola.tencentcloud.config_alarm_policy_info` | Gather information about Tencent Cloud Config alarm policies | [`config_alarm_policy_info`](plugins/modules/config_alarm_policy_info.py) |
| `susunola.tencentcloud.config_compliance_pack_info` | Gather information about Tencent Cloud Config compliance packs | [`config_compliance_pack_info`](plugins/modules/config_compliance_pack_info.py) |
| `susunola.tencentcloud.config_remediation_info` | Gather information about Tencent Cloud Config remediations | [`config_remediation_info`](plugins/modules/config_remediation_info.py) |
| `susunola.tencentcloud.config_rule_info` | Gather information about Tencent Cloud Config Config rules | [`config_rule_info`](plugins/modules/config_rule_info.py) |
| `susunola.tencentcloud.controlcenter_account_factory_baseline_item_info` | Gather information about Tencent Cloud CONTROLCENTER account factory baseline items | [`controlcenter_account_factory_baseline_item_info`](plugins/modules/controlcenter_account_factory_baseline_item_info.py) |
| `susunola.tencentcloud.cos_bucket_info` | Gather information about Tencent Cloud COS buckets | [`cos_bucket_info`](plugins/modules/cos_bucket_info.py) |
| `susunola.tencentcloud.cos_object_info` | Gather information about Tencent Cloud COS objects | [`cos_object_info`](plugins/modules/cos_object_info.py) |
| `susunola.tencentcloud.cpdp_merchant_info_for_management_info` | Gather information about Tencent Cloud CPDP merchant info for managements | [`cpdp_merchant_info_for_management_info`](plugins/modules/cpdp_merchant_info_for_management_info.py) |
| `susunola.tencentcloud.csip_asset_process_info` | Gather information about Tencent Cloud CSIP asset processes | [`csip_asset_process_info`](plugins/modules/csip_asset_process_info.py) |
| `susunola.tencentcloud.ctem_api_sec_info` | Gather information about Tencent Cloud CTEM api secs | [`ctem_api_sec_info`](plugins/modules/ctem_api_sec_info.py) |
| `susunola.tencentcloud.ctsdb_cluster_info` | Gather information about Tencent Cloud CTSDB clusters | [`ctsdb_cluster_info`](plugins/modules/ctsdb_cluster_info.py) |
| `susunola.tencentcloud.customer_gateway_info` | Gather information about Tencent Cloud customer gateways | [`customer_gateway_info`](plugins/modules/customer_gateway_info.py) |
| `susunola.tencentcloud.cvm_chc_info` | Gather information about Tencent Cloud CHC host network configuration | [`cvm_chc_info`](plugins/modules/cvm_chc_info.py) |
| `susunola.tencentcloud.cvm_disaster_recover_group_info` | Gather information about Tencent Cloud CVM placement groups | [`cvm_disaster_recover_group_info`](plugins/modules/cvm_disaster_recover_group_info.py) |
| `susunola.tencentcloud.cvm_hpc_cluster_info` | Gather information about Tencent Cloud CVM HPC clusters | [`cvm_hpc_cluster_info`](plugins/modules/cvm_hpc_cluster_info.py) |
| `susunola.tencentcloud.cvm_image_info` | Gather information about Tencent Cloud CVM images | [`cvm_image_info`](plugins/modules/cvm_image_info.py) |
| `susunola.tencentcloud.cvm_image_share_info` | Gather information about Tencent Cloud CVM image share permissions | [`cvm_image_share_info`](plugins/modules/cvm_image_share_info.py) |
| `susunola.tencentcloud.cvm_instance_action_timer_info` | Gather information about Tencent Cloud CVM instance action timers | [`cvm_instance_action_timer_info`](plugins/modules/cvm_instance_action_timer_info.py) |
| `susunola.tencentcloud.cvm_instance_info` | Gather information about Tencent Cloud CVM instances | [`cvm_instance_info`](plugins/modules/cvm_instance_info.py) |
| `susunola.tencentcloud.cvm_launch_template_info` | Gather information about Tencent Cloud CVM launch templates | [`cvm_launch_template_info`](plugins/modules/cvm_launch_template_info.py) |
| `susunola.tencentcloud.cvm_launch_template_version_info` | Gather information about Tencent Cloud CVM launch template versions | [`cvm_launch_template_version_info`](plugins/modules/cvm_launch_template_version_info.py) |
| `susunola.tencentcloud.cwp_machine_info` | Gather information about Tencent Cloud CWP machines | [`cwp_machine_info`](plugins/modules/cwp_machine_info.py) |
| `susunola.tencentcloud.cws_monitor_info` | Gather information about Tencent Cloud CWS monitors | [`cws_monitor_info`](plugins/modules/cws_monitor_info.py) |
| `susunola.tencentcloud.cynosdb_account_info` | Gather information about Tencent Cloud CynosDB accounts | [`cynosdb_account_info`](plugins/modules/cynosdb_account_info.py) |
| `susunola.tencentcloud.cynosdb_backup_config_info` | Gather information about a Tencent Cloud CynosDB backup configuration | [`cynosdb_backup_config_info`](plugins/modules/cynosdb_backup_config_info.py) |
| `susunola.tencentcloud.cynosdb_cluster_info` | Gather information about TencentDB for CynosDB clusters | [`cynosdb_cluster_info`](plugins/modules/cynosdb_cluster_info.py) |
| `susunola.tencentcloud.dasb_device_info` | Gather information about Tencent Cloud DASB devices | [`dasb_device_info`](plugins/modules/dasb_device_info.py) |
| `susunola.tencentcloud.dataagent_chunk_info` | Gather information about Tencent Cloud DATAAGENT chunks | [`dataagent_chunk_info`](plugins/modules/dataagent_chunk_info.py) |
| `susunola.tencentcloud.dayu_resource_info` | Gather information about Tencent Cloud DAYU resources | [`dayu_resource_info`](plugins/modules/dayu_resource_info.py) |
| `susunola.tencentcloud.dbbrain_db_diag_event_info` | Gather information about Tencent Cloud DBBRAIN db diag events | [`dbbrain_db_diag_event_info`](plugins/modules/dbbrain_db_diag_event_info.py) |
| `susunola.tencentcloud.dbdc_db_custom_cluster_info` | Gather information about Tencent Cloud DBDC db custom clusters | [`dbdc_db_custom_cluster_info`](plugins/modules/dbdc_db_custom_cluster_info.py) |
| `susunola.tencentcloud.dbs_backup_plan_info` | Gather information about Tencent Cloud DBS backup plans | [`dbs_backup_plan_info`](plugins/modules/dbs_backup_plan_info.py) |
| `susunola.tencentcloud.dc_direct_connect_info` | Gather information about Tencent Cloud direct connect connections | [`dc_direct_connect_info`](plugins/modules/dc_direct_connect_info.py) |
| `susunola.tencentcloud.dc_direct_connect_tunnel_info` | Gather information about Tencent Cloud DC direct connect tunnels | [`dc_direct_connect_tunnel_info`](plugins/modules/dc_direct_connect_tunnel_info.py) |
| `susunola.tencentcloud.dcdb_instance_info` | Gather information about Tencent Cloud DCDB instances | [`dcdb_instance_info`](plugins/modules/dcdb_instance_info.py) |
| `susunola.tencentcloud.dlc_cluster_group_info` | Gather information about Tencent Cloud DLC cluster groups | [`dlc_cluster_group_info`](plugins/modules/dlc_cluster_group_info.py) |
| `susunola.tencentcloud.dlc_data_engine_info` | Gather information about Tencent Cloud DLC data engines | [`dlc_data_engine_info`](plugins/modules/dlc_data_engine_info.py) |
| `susunola.tencentcloud.dlc_data_mask_strategy_info` | Gather information about Tencent Cloud DLC data mask strategies | [`dlc_data_mask_strategy_info`](plugins/modules/dlc_data_mask_strategy_info.py) |
| `susunola.tencentcloud.dlc_database_info` | Gather information about Tencent Cloud DLC databases | [`dlc_database_info`](plugins/modules/dlc_database_info.py) |
| `susunola.tencentcloud.dlc_inference_engine_info` | Gather Tencent Cloud DLC inference engines | [`dlc_inference_engine_info`](plugins/modules/dlc_inference_engine_info.py) |
| `susunola.tencentcloud.dlc_inference_model_info` | Gather Tencent Cloud DLC inference models | [`dlc_inference_model_info`](plugins/modules/dlc_inference_model_info.py) |
| `susunola.tencentcloud.dlc_inference_service_info` | Gather Tencent Cloud DLC inference services | [`dlc_inference_service_info`](plugins/modules/dlc_inference_service_info.py) |
| `susunola.tencentcloud.dlc_job_spec_info` | Gather information about Tencent Cloud DLC job specs | [`dlc_job_spec_info`](plugins/modules/dlc_job_spec_info.py) |
| `susunola.tencentcloud.dlc_lab_info` | Gather information about Tencent Cloud DLC labs | [`dlc_lab_info`](plugins/modules/dlc_lab_info.py) |
| `susunola.tencentcloud.dlc_model_artifact_info` | Inspect Tencent Cloud DLC model-version artifacts | [`dlc_model_artifact_info`](plugins/modules/dlc_model_artifact_info.py) |
| `susunola.tencentcloud.dlc_model_version_info` | Gather versions of a Tencent Cloud DLC inference model | [`dlc_model_version_info`](plugins/modules/dlc_model_version_info.py) |
| `susunola.tencentcloud.dlc_network_connection_info` | Gather information about Tencent Cloud DLC network connections | [`dlc_network_connection_info`](plugins/modules/dlc_network_connection_info.py) |
| `susunola.tencentcloud.dlc_notebook_session_info` | Gather Tencent Cloud DLC Notebook sessions | [`dlc_notebook_session_info`](plugins/modules/dlc_notebook_session_info.py) |
| `susunola.tencentcloud.dlc_notebook_session_log_info` | Gather Tencent Cloud DLC Notebook session logs | [`dlc_notebook_session_log_info`](plugins/modules/dlc_notebook_session_log_info.py) |
| `susunola.tencentcloud.dlc_notebook_statement_info` | Gather a Tencent Cloud DLC Notebook statement and SQL results | [`dlc_notebook_statement_info`](plugins/modules/dlc_notebook_statement_info.py) |
| `susunola.tencentcloud.dlc_partition_queue_info` | Gather information about Tencent Cloud DLC partition queues | [`dlc_partition_queue_info`](plugins/modules/dlc_partition_queue_info.py) |
| `susunola.tencentcloud.dlc_ray_cluster_info` | Gather information about Tencent Cloud DLC ray clusters | [`dlc_ray_cluster_info`](plugins/modules/dlc_ray_cluster_info.py) |
| `susunola.tencentcloud.dlc_ray_job_info` | Gather Tencent Cloud DLC Ray job diagnostics | [`dlc_ray_job_info`](plugins/modules/dlc_ray_job_info.py) |
| `susunola.tencentcloud.dlc_ray_job_list_info` | List Tencent Cloud DLC Ray jobs | [`dlc_ray_job_list_info`](plugins/modules/dlc_ray_job_list_info.py) |
| `susunola.tencentcloud.dlc_resource_config_info` | Gather information about Tencent Cloud DLC resource configs | [`dlc_resource_config_info`](plugins/modules/dlc_resource_config_info.py) |
| `susunola.tencentcloud.dlc_script_info` | Gather information about Tencent Cloud DLC scripts | [`dlc_script_info`](plugins/modules/dlc_script_info.py) |
| `susunola.tencentcloud.dlc_spark_app_job_info` | Gather information about Tencent Cloud DLC spark app jobs | [`dlc_spark_app_job_info`](plugins/modules/dlc_spark_app_job_info.py) |
| `susunola.tencentcloud.dlc_standard_engine_resource_group_info` | Gather information about Tencent Cloud DLC standard engine resource groups | [`dlc_standard_engine_resource_group_info`](plugins/modules/dlc_standard_engine_resource_group_info.py) |
| `susunola.tencentcloud.dlc_store_location_info` | Gather information about Tencent Cloud DLC store location | [`dlc_store_location_info`](plugins/modules/dlc_store_location_info.py) |
| `susunola.tencentcloud.dlc_table_info` | Gather information about Tencent Cloud DLC tables | [`dlc_table_info`](plugins/modules/dlc_table_info.py) |
| `susunola.tencentcloud.dlc_table_partition_info` | Gather information about Tencent Cloud DLC table partitions | [`dlc_table_partition_info`](plugins/modules/dlc_table_partition_info.py) |
| `susunola.tencentcloud.dlc_task_info` | Gather information about Tencent Cloud DLC tasks | [`dlc_task_info`](plugins/modules/dlc_task_info.py) |
| `susunola.tencentcloud.dlc_user_data_engine_config_info` | Gather information about Tencent Cloud DLC user data engine configs | [`dlc_user_data_engine_config_info`](plugins/modules/dlc_user_data_engine_config_info.py) |
| `susunola.tencentcloud.dlc_user_info` | Gather information about Tencent Cloud DLC users | [`dlc_user_info`](plugins/modules/dlc_user_info.py) |
| `susunola.tencentcloud.dlc_work_group_info` | Gather information about Tencent Cloud DLC work groups | [`dlc_work_group_info`](plugins/modules/dlc_work_group_info.py) |
| `susunola.tencentcloud.dnspod_record_info` | Gather information about DNSPod records | [`dnspod_record_info`](plugins/modules/dnspod_record_info.py) |
| `susunola.tencentcloud.domain_batch_operation_log_info` | Gather information about Tencent Cloud DOMAIN batch operation logs | [`domain_batch_operation_log_info`](plugins/modules/domain_batch_operation_log_info.py) |
| `susunola.tencentcloud.dsgc_dspa_assessment_risk_info` | Gather information about Tencent Cloud DSGC dspa assessment risks | [`dsgc_dspa_assessment_risk_info`](plugins/modules/dsgc_dspa_assessment_risk_info.py) |
| `susunola.tencentcloud.dts_subscribe_job_info` | Gather information about Tencent Cloud DTS subscribe jobs | [`dts_subscribe_job_info`](plugins/modules/dts_subscribe_job_info.py) |
| `susunola.tencentcloud.eb_event_bus_info` | Gather information about Tencent Cloud EB event buses | [`eb_event_bus_info`](plugins/modules/eb_event_bus_info.py) |
| `susunola.tencentcloud.ecdn_domain_info` | Gather information about Tencent Cloud ECDN domains | [`ecdn_domain_info`](plugins/modules/ecdn_domain_info.py) |
| `susunola.tencentcloud.ecm_address_info` | Gather information about Tencent Cloud ECM addresses | [`ecm_address_info`](plugins/modules/ecm_address_info.py) |
| `susunola.tencentcloud.eiam_application_info` | Gather information about Tencent Cloud EIAM applications | [`eiam_application_info`](plugins/modules/eiam_application_info.py) |
| `susunola.tencentcloud.eip_info` | Gather information about Tencent Cloud elastic IP addresses (EIP) | [`eip_info`](plugins/modules/eip_info.py) |
| `susunola.tencentcloud.eis_runtime_deployed_instances_mc_info` | Gather information about Tencent Cloud EIS runtime deployed instances mcs | [`eis_runtime_deployed_instances_mc_info`](plugins/modules/eis_runtime_deployed_instances_mc_info.py) |
| `susunola.tencentcloud.eks_cluster_info` | Gather information about Tencent Cloud EKS clusters | [`eks_cluster_info`](plugins/modules/eks_cluster_info.py) |
| `susunola.tencentcloud.eks_container_instance_info` | Gather information about Tencent Cloud EKS container instances | [`eks_container_instance_info`](plugins/modules/eks_container_instance_info.py) |
| `susunola.tencentcloud.elasticsearch_instance_info` | Gather information about Tencent Cloud Elasticsearch instances | [`elasticsearch_instance_info`](plugins/modules/elasticsearch_instance_info.py) |
| `susunola.tencentcloud.emr_node_data_disk_info` | Gather information about Tencent Cloud EMR node data disks | [`emr_node_data_disk_info`](plugins/modules/emr_node_data_disk_info.py) |
| `susunola.tencentcloud.es_cluster_info` | Gather information about Tencent Cloud Elasticsearch clusters | [`es_cluster_info`](plugins/modules/es_cluster_info.py) |
| `susunola.tencentcloud.ess_file_url_info` | Gather information about Tencent Cloud ESS file urls | [`ess_file_url_info`](plugins/modules/ess_file_url_info.py) |
| `susunola.tencentcloud.essbasic_template_info` | Gather information about Tencent Cloud ESSBASIC templates | [`essbasic_template_info`](plugins/modules/essbasic_template_info.py) |
| `susunola.tencentcloud.facefusion_material_info` | Gather information about Tencent Cloud FACEFUSION materials | [`facefusion_material_info`](plugins/modules/facefusion_material_info.py) |
| `susunola.tencentcloud.faceid_we_chat_bill_info` | Gather information about Tencent Cloud FACEID we chat bills | [`faceid_we_chat_bill_info`](plugins/modules/faceid_we_chat_bill_info.py) |
| `susunola.tencentcloud.fmu_model_info` | Gather information about Tencent Cloud FMU models | [`fmu_model_info`](plugins/modules/fmu_model_info.py) |
| `susunola.tencentcloud.fwm_edge_acl_rule_info` | Gather information about Tencent Cloud FWM edge acl rules | [`fwm_edge_acl_rule_info`](plugins/modules/fwm_edge_acl_rule_info.py) |
| `susunola.tencentcloud.ga2_accelerate_area_info` | Gather information about Tencent Cloud GA2 accelerate areas | [`ga2_accelerate_area_info`](plugins/modules/ga2_accelerate_area_info.py) |
| `susunola.tencentcloud.gaap_proxy_info` | Gather information about Tencent Cloud GAAP proxies | [`gaap_proxy_info`](plugins/modules/gaap_proxy_info.py) |
| `susunola.tencentcloud.gme_voice_print_info` | Gather information about Tencent Cloud GME voice prints | [`gme_voice_print_info`](plugins/modules/gme_voice_print_info.py) |
| `susunola.tencentcloud.goosefs_file_system_info` | Gather information about Tencent Cloud GOOSEFS file systems | [`goosefs_file_system_info`](plugins/modules/goosefs_file_system_info.py) |
| `susunola.tencentcloud.gs_android_app_info` | Gather information about Tencent Cloud GS android apps | [`gs_android_app_info`](plugins/modules/gs_android_app_info.py) |
| `susunola.tencentcloud.gwlb_gateway_load_balancer_info` | Gather information about Tencent Cloud GWLB gateway load balancers | [`gwlb_gateway_load_balancer_info`](plugins/modules/gwlb_gateway_load_balancer_info.py) |
| `susunola.tencentcloud.hai_application_info` | Gather information about Tencent Cloud HAI applications | [`hai_application_info`](plugins/modules/hai_application_info.py) |
| `susunola.tencentcloud.hasim_link_info` | Gather information about Tencent Cloud HASIM links | [`hasim_link_info`](plugins/modules/hasim_link_info.py) |
| `susunola.tencentcloud.havip_info` | Gather information about Tencent Cloud HAVIPs | [`havip_info`](plugins/modules/havip_info.py) |
| `susunola.tencentcloud.hunyuan_glossary_info` | Gather information about Tencent Cloud HUNYUAN glossaries | [`hunyuan_glossary_info`](plugins/modules/hunyuan_glossary_info.py) |
| `susunola.tencentcloud.iai_group_info` | Gather information about Tencent Cloud IAI groups | [`iai_group_info`](plugins/modules/iai_group_info.py) |
| `susunola.tencentcloud.iap_login_session_duration_info` | Gather information about Tencent Cloud IAP login session duration | [`iap_login_session_duration_info`](plugins/modules/iap_login_session_duration_info.py) |
| `susunola.tencentcloud.ic_sms_info` | Gather information about Tencent Cloud IC smses | [`ic_sms_info`](plugins/modules/ic_sms_info.py) |
| `susunola.tencentcloud.igtm_address_pool_info` | Gather information about Tencent Cloud IGTM address pools | [`igtm_address_pool_info`](plugins/modules/igtm_address_pool_info.py) |
| `susunola.tencentcloud.ioa_device_info` | Gather information about Tencent Cloud IOA devices | [`ioa_device_info`](plugins/modules/ioa_device_info.py) |
| `susunola.tencentcloud.iot_product_info` | Gather information about Tencent Cloud IOT products | [`iot_product_info`](plugins/modules/iot_product_info.py) |
| `susunola.tencentcloud.iotcloud_device_resource_info` | Gather information about Tencent Cloud IOTCLOUD device resources | [`iotcloud_device_resource_info`](plugins/modules/iotcloud_device_resource_info.py) |
| `susunola.tencentcloud.iotexplorer_device_position_info` | Gather information about Tencent Cloud IOTEXPLORER device positions | [`iotexplorer_device_position_info`](plugins/modules/iotexplorer_device_position_info.py) |
| `susunola.tencentcloud.iotvideo_ai_model_application_info` | Gather information about Tencent Cloud IOTVIDEO ai model applications | [`iotvideo_ai_model_application_info`](plugins/modules/iotvideo_ai_model_application_info.py) |
| `susunola.tencentcloud.iotvideoindustry_all_device_info` | Gather information about Tencent Cloud IOTVIDEOINDUSTRY all devices | [`iotvideoindustry_all_device_info`](plugins/modules/iotvideoindustry_all_device_info.py) |
| `susunola.tencentcloud.iss_device_snapshot_info` | Gather information about Tencent Cloud ISS device snapshots | [`iss_device_snapshot_info`](plugins/modules/iss_device_snapshot_info.py) |
| `susunola.tencentcloud.ivld_custom_person_info` | Gather information about Tencent Cloud IVLD custom persons | [`ivld_custom_person_info`](plugins/modules/ivld_custom_person_info.py) |
| `susunola.tencentcloud.keewidb_instance_backup_info` | Gather information about Tencent Cloud KEEWIDB instance backups | [`keewidb_instance_backup_info`](plugins/modules/keewidb_instance_backup_info.py) |
| `susunola.tencentcloud.key_pair_info` | Gather information about Tencent Cloud CVM key pairs | [`key_pair_info`](plugins/modules/key_pair_info.py) |
| `susunola.tencentcloud.kms_key_info` | Gather information about Tencent Cloud KMS keys | [`kms_key_info`](plugins/modules/kms_key_info.py) |
| `susunola.tencentcloud.kms_key_rotation_info` | Gather information about Tencent Cloud KMS key rotation status | [`kms_key_rotation_info`](plugins/modules/kms_key_rotation_info.py) |
| `susunola.tencentcloud.lcic_answer_info` | Gather information about Tencent Cloud LCIC answers | [`lcic_answer_info`](plugins/modules/lcic_answer_info.py) |
| `susunola.tencentcloud.lighthouse_disk_info` | Gather information about Tencent Cloud Lighthouse disks | [`lighthouse_disk_info`](plugins/modules/lighthouse_disk_info.py) |
| `susunola.tencentcloud.lighthouse_firewall_rules_info` | Gather information about Tencent Cloud Lighthouse firewall rules | [`lighthouse_firewall_rules_info`](plugins/modules/lighthouse_firewall_rules_info.py) |
| `susunola.tencentcloud.lighthouse_instance_info` | Gather information about Tencent Cloud Lighthouse instances | [`lighthouse_instance_info`](plugins/modules/lighthouse_instance_info.py) |
| `susunola.tencentcloud.lighthouse_key_pair_info` | Gather information about Tencent Cloud Lighthouse key pairs | [`lighthouse_key_pair_info`](plugins/modules/lighthouse_key_pair_info.py) |
| `susunola.tencentcloud.lighthouse_snapshot_info` | Gather information about Tencent Cloud Lighthouse snapshots | [`lighthouse_snapshot_info`](plugins/modules/lighthouse_snapshot_info.py) |
| `susunola.tencentcloud.live_audit_keyword_info` | Gather information about Tencent Cloud LIVE audit keywords | [`live_audit_keyword_info`](plugins/modules/live_audit_keyword_info.py) |
| `susunola.tencentcloud.lke_app_knowledge_info` | Gather information about Tencent Cloud LKE app knowledges | [`lke_app_knowledge_info`](plugins/modules/lke_app_knowledge_info.py) |
| `susunola.tencentcloud.lkeap_character_usage_info` | Gather information about Tencent Cloud LKEAP character usage | [`lkeap_character_usage_info`](plugins/modules/lkeap_character_usage_info.py) |
| `susunola.tencentcloud.lowcode_knowledge_set_info` | Gather information about Tencent Cloud LOWCODE knowledge sets | [`lowcode_knowledge_set_info`](plugins/modules/lowcode_knowledge_set_info.py) |
| `susunola.tencentcloud.mall_draw_resource_info` | Gather information about Tencent Cloud MALL draw resources | [`mall_draw_resource_info`](plugins/modules/mall_draw_resource_info.py) |
| `susunola.tencentcloud.mariadb_account_info` | Gather information about Tencent Cloud MariaDB accounts | [`mariadb_account_info`](plugins/modules/mariadb_account_info.py) |
| `susunola.tencentcloud.mariadb_backup_config_info` | Gather information about a Tencent Cloud MariaDB backup configuration | [`mariadb_backup_config_info`](plugins/modules/mariadb_backup_config_info.py) |
| `susunola.tencentcloud.mariadb_instance_info` | Gather information about TencentDB for MariaDB instances | [`mariadb_instance_info`](plugins/modules/mariadb_instance_info.py) |
| `susunola.tencentcloud.memcached_instance_info` | Gather information about Tencent Cloud MEMCACHED instances | [`memcached_instance_info`](plugins/modules/memcached_instance_info.py) |
| `susunola.tencentcloud.mmps_resource_usage_info` | Gather information about Tencent Cloud MMPS resource usages | [`mmps_resource_usage_info`](plugins/modules/mmps_resource_usage_info.py) |
| `susunola.tencentcloud.mna_access_region_info` | Gather information about Tencent Cloud MNA access regions | [`mna_access_region_info`](plugins/modules/mna_access_region_info.py) |
| `susunola.tencentcloud.mongodb_account_info` | Gather information about Tencent Cloud MongoDB accounts | [`mongodb_account_info`](plugins/modules/mongodb_account_info.py) |
| `susunola.tencentcloud.mongodb_backup_config_info` | Gather information about a Tencent Cloud MongoDB backup configuration | [`mongodb_backup_config_info`](plugins/modules/mongodb_backup_config_info.py) |
| `susunola.tencentcloud.mongodb_instance_info` | Gather information about TencentDB for MongoDB instances | [`mongodb_instance_info`](plugins/modules/mongodb_instance_info.py) |
| `susunola.tencentcloud.monitor_alarm_policy_info` | Gather information about Tencent Cloud Monitor alarm policies | [`monitor_alarm_policy_info`](plugins/modules/monitor_alarm_policy_info.py) |
| `susunola.tencentcloud.monitor_grafana_instance_info` | Gather information about Tencent Cloud Grafana instances | [`monitor_grafana_instance_info`](plugins/modules/monitor_grafana_instance_info.py) |
| `susunola.tencentcloud.monitor_grafana_notification_channel_info` | Gather information about Tencent Cloud Monitor Grafana notification channels | [`monitor_grafana_notification_channel_info`](plugins/modules/monitor_grafana_notification_channel_info.py) |
| `susunola.tencentcloud.monitor_prometheus_alert_group_info` | Gather information about Tencent Cloud Monitor Prometheus alert groups | [`monitor_prometheus_alert_group_info`](plugins/modules/monitor_prometheus_alert_group_info.py) |
| `susunola.tencentcloud.monitor_prometheus_cluster_agent_info` | Gather information about Tencent Cloud Monitor Prometheus cluster agents | [`monitor_prometheus_cluster_agent_info`](plugins/modules/monitor_prometheus_cluster_agent_info.py) |
| `susunola.tencentcloud.monitor_prometheus_grafana_binding_info` | Gather information about Tencent Cloud Monitor Prometheus instances with their managed-Grafana binding state | [`monitor_prometheus_grafana_binding_info`](plugins/modules/monitor_prometheus_grafana_binding_info.py) |
| `susunola.tencentcloud.monitor_prometheus_instance_info` | Gather information about Tencent Cloud Managed Service for Prometheus instances | [`monitor_prometheus_instance_info`](plugins/modules/monitor_prometheus_instance_info.py) |
| `susunola.tencentcloud.monitor_prometheus_record_rule_info` | Gather information about Tencent Cloud Monitor Prometheus recording rules | [`monitor_prometheus_record_rule_info`](plugins/modules/monitor_prometheus_record_rule_info.py) |
| `susunola.tencentcloud.monitor_prometheus_scrape_job_info` | Gather information about Tencent Cloud Monitor Prometheus scrape jobs | [`monitor_prometheus_scrape_job_info`](plugins/modules/monitor_prometheus_scrape_job_info.py) |
| `susunola.tencentcloud.mps_person_sample_info` | Gather information about Tencent Cloud MPS person samples | [`mps_person_sample_info`](plugins/modules/mps_person_sample_info.py) |
| `susunola.tencentcloud.mqtt_device_certificate_info` | Gather information about Tencent Cloud MQTT device certificates | [`mqtt_device_certificate_info`](plugins/modules/mqtt_device_certificate_info.py) |
| `susunola.tencentcloud.ms_shield_instance_info` | Gather information about Tencent Cloud MS shield instances | [`ms_shield_instance_info`](plugins/modules/ms_shield_instance_info.py) |
| `susunola.tencentcloud.msp_migration_project_info` | Gather information about Tencent Cloud MSP migration projects | [`msp_migration_project_info`](plugins/modules/msp_migration_project_info.py) |
| `susunola.tencentcloud.nat_gateway_dnat_rule_info` | Gather information about Tencent Cloud NAT gateway DNAT rules | [`nat_gateway_dnat_rule_info`](plugins/modules/nat_gateway_dnat_rule_info.py) |
| `susunola.tencentcloud.nat_gateway_info` | Gather information about Tencent Cloud NAT gateways | [`nat_gateway_info`](plugins/modules/nat_gateway_info.py) |
| `susunola.tencentcloud.nat_gateway_snat_rule_info` | Gather information about Tencent Cloud NAT gateway SNAT rules | [`nat_gateway_snat_rule_info`](plugins/modules/nat_gateway_snat_rule_info.py) |
| `susunola.tencentcloud.network_acl_info` | Gather information about Tencent Cloud network ACLs | [`network_acl_info`](plugins/modules/network_acl_info.py) |
| `susunola.tencentcloud.network_interface_info` | Gather information about Tencent Cloud elastic network interfaces | [`network_interface_info`](plugins/modules/network_interface_info.py) |
| `susunola.tencentcloud.oceanus_cluster_info` | Gather information about Tencent Cloud OCEANUS clusters | [`oceanus_cluster_info`](plugins/modules/oceanus_cluster_info.py) |
| `susunola.tencentcloud.oceanus_job_config_info` | Gather information about Tencent Cloud Oceanus job config versions | [`oceanus_job_config_info`](plugins/modules/oceanus_job_config_info.py) |
| `susunola.tencentcloud.oceanus_job_info` | Gather information about Tencent Cloud Oceanus jobs | [`oceanus_job_info`](plugins/modules/oceanus_job_info.py) |
| `susunola.tencentcloud.oceanus_job_savepoint_info` | Gather information about Tencent Cloud Oceanus job savepoints | [`oceanus_job_savepoint_info`](plugins/modules/oceanus_job_savepoint_info.py) |
| `susunola.tencentcloud.oceanus_resource_config_info` | Gather information about Tencent Cloud Oceanus resource config versions | [`oceanus_resource_config_info`](plugins/modules/oceanus_resource_config_info.py) |
| `susunola.tencentcloud.oceanus_resource_info` | Gather information about Tencent Cloud Oceanus resources | [`oceanus_resource_info`](plugins/modules/oceanus_resource_info.py) |
| `susunola.tencentcloud.oceanus_workspace_info` | Gather information about Tencent Cloud Oceanus workspaces | [`oceanus_workspace_info`](plugins/modules/oceanus_workspace_info.py) |
| `susunola.tencentcloud.omics_application_info` | Gather information about Tencent Cloud OMICS applications | [`omics_application_info`](plugins/modules/omics_application_info.py) |
| `susunola.tencentcloud.organization_member_info` | Gather information about Tencent Cloud Organization members | [`organization_member_info`](plugins/modules/organization_member_info.py) |
| `susunola.tencentcloud.partners_agent_deals_by_cache_info` | Gather information about Tencent Cloud PARTNERS agent deals by caches | [`partners_agent_deals_by_cache_info`](plugins/modules/partners_agent_deals_by_cache_info.py) |
| `susunola.tencentcloud.peering_connection_info` | Gather information about Tencent Cloud VPC peering connections | [`peering_connection_info`](plugins/modules/peering_connection_info.py) |
| `susunola.tencentcloud.portal_document_info` | Gather information about Tencent Cloud PORTAL documents | [`portal_document_info`](plugins/modules/portal_document_info.py) |
| `susunola.tencentcloud.postgres_instance_info` | Gather information about TencentDB for PostgreSQL instances | [`postgres_instance_info`](plugins/modules/postgres_instance_info.py) |
| `susunola.tencentcloud.postgresql_account_info` | Gather information about Tencent Cloud PostgreSQL accounts | [`postgresql_account_info`](plugins/modules/postgresql_account_info.py) |
| `susunola.tencentcloud.postgresql_backup_plan_info` | Gather information about Tencent Cloud PostgreSQL backup plans | [`postgresql_backup_plan_info`](plugins/modules/postgresql_backup_plan_info.py) |
| `susunola.tencentcloud.postgresql_parameter_template_info` | Gather information about Tencent Cloud PostgreSQL parameter templates | [`postgresql_parameter_template_info`](plugins/modules/postgresql_parameter_template_info.py) |
| `susunola.tencentcloud.privatedns_account_vpc_info` | Gather information about Tencent Cloud PRIVATEDNS account vpcs | [`privatedns_account_vpc_info`](plugins/modules/privatedns_account_vpc_info.py) |
| `susunola.tencentcloud.pts_cron_job_info` | Gather information about Tencent Cloud PTS cron jobs | [`pts_cron_job_info`](plugins/modules/pts_cron_job_info.py) |
| `susunola.tencentcloud.redis_account_info` | Gather information about Tencent Cloud Redis accounts | [`redis_account_info`](plugins/modules/redis_account_info.py) |
| `susunola.tencentcloud.redis_backup_config_info` | Gather information about a Tencent Cloud Redis backup configuration | [`redis_backup_config_info`](plugins/modules/redis_backup_config_info.py) |
| `susunola.tencentcloud.redis_instance_info` | Gather information about TencentDB for Redis instances | [`redis_instance_info`](plugins/modules/redis_instance_info.py) |
| `susunola.tencentcloud.redis_parameter_template_info` | Gather information about Tencent Cloud Redis parameter templates | [`redis_parameter_template_info`](plugins/modules/redis_parameter_template_info.py) |
| `susunola.tencentcloud.region_product_info` | Gather information about Tencent Cloud REGION products | [`region_product_info`](plugins/modules/region_product_info.py) |
| `susunola.tencentcloud.route_table_info` | Gather information about Tencent Cloud VPC route tables | [`route_table_info`](plugins/modules/route_table_info.py) |
| `susunola.tencentcloud.rum_project_info` | Gather information about Tencent Cloud RUM projects | [`rum_project_info`](plugins/modules/rum_project_info.py) |
| `susunola.tencentcloud.scf_alias_info` | Gather information about Tencent Cloud SCF function aliases | [`scf_alias_info`](plugins/modules/scf_alias_info.py) |
| `susunola.tencentcloud.scf_function_info` | Gather information about Tencent Cloud SCF functions | [`scf_function_info`](plugins/modules/scf_function_info.py) |
| `susunola.tencentcloud.scf_trigger_info` | Gather information about Tencent Cloud SCF function triggers | [`scf_trigger_info`](plugins/modules/scf_trigger_info.py) |
| `susunola.tencentcloud.scf_version_info` | Gather information about Tencent Cloud SCF function versions | [`scf_version_info`](plugins/modules/scf_version_info.py) |
| `susunola.tencentcloud.security_group_info` | Gather information about Tencent Cloud security groups | [`security_group_info`](plugins/modules/security_group_info.py) |
| `susunola.tencentcloud.security_group_rule_info` | Gather information about Tencent Cloud security group rules | [`security_group_rule_info`](plugins/modules/security_group_rule_info.py) |
| `susunola.tencentcloud.securitylake_security_alarm_table_info` | Gather information about Tencent Cloud SECURITYLAKE security alarm tables | [`securitylake_security_alarm_table_info`](plugins/modules/securitylake_security_alarm_table_info.py) |
| `susunola.tencentcloud.ses_black_email_address_info` | Gather information about Tencent Cloud SES black email addresses | [`ses_black_email_address_info`](plugins/modules/ses_black_email_address_info.py) |
| `susunola.tencentcloud.smh_library_info` | Gather information about Tencent Cloud SMH libraries | [`smh_library_info`](plugins/modules/smh_library_info.py) |
| `susunola.tencentcloud.sms_sign_info` | Gather information about Tencent Cloud SMS signs | [`sms_sign_info`](plugins/modules/sms_sign_info.py) |
| `susunola.tencentcloud.sms_signature_info` | Gather information about Tencent Cloud SMS signatures | [`sms_signature_info`](plugins/modules/sms_signature_info.py) |
| `susunola.tencentcloud.sms_template_info` | Gather information about Tencent Cloud SMS templates | [`sms_template_info`](plugins/modules/sms_template_info.py) |
| `susunola.tencentcloud.sqlserver_account_info` | Gather information about Tencent Cloud SQL Server accounts | [`sqlserver_account_info`](plugins/modules/sqlserver_account_info.py) |
| `susunola.tencentcloud.sqlserver_instance_info` | Gather information about TencentDB for SQL Server instances | [`sqlserver_instance_info`](plugins/modules/sqlserver_instance_info.py) |
| `susunola.tencentcloud.ssa_check_config_asset_info` | Gather information about Tencent Cloud SSA check config assets | [`ssa_check_config_asset_info`](plugins/modules/ssa_check_config_asset_info.py) |
| `susunola.tencentcloud.ssl_certificate_info` | Gather information about Tencent Cloud SSL certificates | [`ssl_certificate_info`](plugins/modules/ssl_certificate_info.py) |
| `susunola.tencentcloud.sslpod_domain_info` | Gather information about Tencent Cloud SSLPOD domains | [`sslpod_domain_info`](plugins/modules/sslpod_domain_info.py) |
| `susunola.tencentcloud.ssm_rotation_info` | Gather Tencent Cloud Secrets Manager rotation state | [`ssm_rotation_info`](plugins/modules/ssm_rotation_info.py) |
| `susunola.tencentcloud.ssm_secret_info` | Gather Tencent Cloud Secrets Manager metadata | [`ssm_secret_info`](plugins/modules/ssm_secret_info.py) |
| `susunola.tencentcloud.ssm_secret_version_info` | Gather Tencent Cloud Secrets Manager versions | [`ssm_secret_version_info`](plugins/modules/ssm_secret_version_info.py) |
| `susunola.tencentcloud.ssm_supported_product_info` | Gather cloud products supported by Tencent Cloud SSM | [`ssm_supported_product_info`](plugins/modules/ssm_supported_product_info.py) |
| `susunola.tencentcloud.subnet_info` | Gather information about Tencent Cloud subnets | [`subnet_info`](plugins/modules/subnet_info.py) |
| `susunola.tencentcloud.svp_saving_plan_coverage_info` | Gather information about Tencent Cloud SVP saving plan coverages | [`svp_saving_plan_coverage_info`](plugins/modules/svp_saving_plan_coverage_info.py) |
| `susunola.tencentcloud.tag_info` | Gather information about Tencent Cloud tags | [`tag_info`](plugins/modules/tag_info.py) |
| `susunola.tencentcloud.tat_command_info` | Gather information about Tencent Cloud TAT commands | [`tat_command_info`](plugins/modules/tat_command_info.py) |
| `susunola.tencentcloud.tat_invocation_info` | Gather Tencent Cloud TAT invocations and instance tasks | [`tat_invocation_info`](plugins/modules/tat_invocation_info.py) |
| `susunola.tencentcloud.tbaas_block_info` | Gather information about Tencent Cloud TBAAS blocks | [`tbaas_block_info`](plugins/modules/tbaas_block_info.py) |
| `susunola.tencentcloud.tcaplusdb_cluster_info` | Gather information about Tencent Cloud TCAPLUSDB clusters | [`tcaplusdb_cluster_info`](plugins/modules/tcaplusdb_cluster_info.py) |
| `susunola.tencentcloud.tcb_billing_info` | Gather information about Tencent Cloud TCB billings | [`tcb_billing_info`](plugins/modules/tcb_billing_info.py) |
| `susunola.tencentcloud.tcbr_cloud_run_pod_info` | Gather information about Tencent Cloud TCBR cloud run pods | [`tcbr_cloud_run_pod_info`](plugins/modules/tcbr_cloud_run_pod_info.py) |
| `susunola.tencentcloud.tcm_mesh_info` | Gather information about Tencent Cloud TCM meshes | [`tcm_mesh_info`](plugins/modules/tcm_mesh_info.py) |
| `susunola.tencentcloud.tcr_instance_info` | Gather information about Tencent Cloud TCR registries | [`tcr_instance_info`](plugins/modules/tcr_instance_info.py) |
| `susunola.tencentcloud.tcr_namespace_info` | Gather information about Tencent Cloud TCR namespaces | [`tcr_namespace_info`](plugins/modules/tcr_namespace_info.py) |
| `susunola.tencentcloud.tcr_replication_instance_info` | Gather information about Tencent Cloud TCR replication instances | [`tcr_replication_instance_info`](plugins/modules/tcr_replication_instance_info.py) |
| `susunola.tencentcloud.tcr_replication_rule_info` | Gather information about Tencent Cloud TCR replication rules | [`tcr_replication_rule_info`](plugins/modules/tcr_replication_rule_info.py) |
| `susunola.tencentcloud.tcr_repository_info` | Gather information about Tencent Cloud TCR repositories | [`tcr_repository_info`](plugins/modules/tcr_repository_info.py) |
| `susunola.tencentcloud.tcss_abnormal_process_event_info` | Gather information about Tencent Cloud TCSS abnormal process events | [`tcss_abnormal_process_event_info`](plugins/modules/tcss_abnormal_process_event_info.py) |
| `susunola.tencentcloud.tdai_agent_duty_task_info` | Gather information about Tencent Cloud TDAI agent duty tasks | [`tdai_agent_duty_task_info`](plugins/modules/tdai_agent_duty_task_info.py) |
| `susunola.tencentcloud.tdcpg_cluster_info` | Gather information about Tencent Cloud TDCPG clusters | [`tdcpg_cluster_info`](plugins/modules/tdcpg_cluster_info.py) |
| `susunola.tencentcloud.tdcpg_cluster_instance_info` | Gather information about Tencent Cloud TDCPG cluster instances | [`tdcpg_cluster_instance_info`](plugins/modules/tdcpg_cluster_instance_info.py) |
| `susunola.tencentcloud.tdid_over_summary_info` | Gather information about Tencent Cloud TDID over summary | [`tdid_over_summary_info`](plugins/modules/tdid_over_summary_info.py) |
| `susunola.tencentcloud.tdmq_amqp_cluster_info` | Gather information about Tencent Cloud TDMQ amqp clusters | [`tdmq_amqp_cluster_info`](plugins/modules/tdmq_amqp_cluster_info.py) |
| `susunola.tencentcloud.tdmq_environment_info` | Gather information about Tencent Cloud TDMQ environments | [`tdmq_environment_info`](plugins/modules/tdmq_environment_info.py) |
| `susunola.tencentcloud.tdmq_environment_role_info` | Gather information about Tencent Cloud TDMQ environment roles | [`tdmq_environment_role_info`](plugins/modules/tdmq_environment_role_info.py) |
| `susunola.tencentcloud.tdmq_rabbit_mq_binding_info` | Gather information about Tencent Cloud TDMQ rabbit mq bindings | [`tdmq_rabbit_mq_binding_info`](plugins/modules/tdmq_rabbit_mq_binding_info.py) |
| `susunola.tencentcloud.tdmq_rabbit_mq_permission_info` | Gather information about Tencent Cloud TDMQ rabbit mq permissions | [`tdmq_rabbit_mq_permission_info`](plugins/modules/tdmq_rabbit_mq_permission_info.py) |
| `susunola.tencentcloud.tdmq_rabbit_mq_user_info` | Gather information about Tencent Cloud TDMQ rabbit mq users | [`tdmq_rabbit_mq_user_info`](plugins/modules/tdmq_rabbit_mq_user_info.py) |
| `susunola.tencentcloud.tdmq_rabbit_mq_vip_instance_info` | Gather information about Tencent Cloud TDMQ rabbit mq vip instances | [`tdmq_rabbit_mq_vip_instance_info`](plugins/modules/tdmq_rabbit_mq_vip_instance_info.py) |
| `susunola.tencentcloud.tdmq_rabbit_mq_virtual_host_info` | Gather information about Tencent Cloud TDMQ rabbit mq virtual hosts | [`tdmq_rabbit_mq_virtual_host_info`](plugins/modules/tdmq_rabbit_mq_virtual_host_info.py) |
| `susunola.tencentcloud.tdmq_rocket_mq_cluster_info` | Gather information about Tencent Cloud TDMQ rocket mq clusters | [`tdmq_rocket_mq_cluster_info`](plugins/modules/tdmq_rocket_mq_cluster_info.py) |
| `susunola.tencentcloud.tdmq_rocket_mq_environment_role_info` | Gather information about Tencent Cloud TDMQ rocket mq environment roles | [`tdmq_rocket_mq_environment_role_info`](plugins/modules/tdmq_rocket_mq_environment_role_info.py) |
| `susunola.tencentcloud.tdmq_rocket_mq_group_info` | Gather information about Tencent Cloud TDMQ rocket mq groups | [`tdmq_rocket_mq_group_info`](plugins/modules/tdmq_rocket_mq_group_info.py) |
| `susunola.tencentcloud.tdmq_rocket_mq_namespace_info` | Gather information about Tencent Cloud TDMQ rocket mq namespaces | [`tdmq_rocket_mq_namespace_info`](plugins/modules/tdmq_rocket_mq_namespace_info.py) |
| `susunola.tencentcloud.tdmq_rocket_mq_role_info` | Gather information about Tencent Cloud TDMQ rocket mq roles | [`tdmq_rocket_mq_role_info`](plugins/modules/tdmq_rocket_mq_role_info.py) |
| `susunola.tencentcloud.tdmq_rocket_mq_topic_info` | Gather information about Tencent Cloud TDMQ rocket mq topics | [`tdmq_rocket_mq_topic_info`](plugins/modules/tdmq_rocket_mq_topic_info.py) |
| `susunola.tencentcloud.tdmq_subscription_info` | Gather information about Tencent Cloud TDMQ subscriptions | [`tdmq_subscription_info`](plugins/modules/tdmq_subscription_info.py) |
| `susunola.tencentcloud.tdmq_topic_info` | Gather information about Tencent Cloud TDMQ topics | [`tdmq_topic_info`](plugins/modules/tdmq_topic_info.py) |
| `susunola.tencentcloud.tdmysql_account_info` | Gather Tencent Cloud TDSQL MySQL accounts | [`tdmysql_account_info`](plugins/modules/tdmysql_account_info.py) |
| `susunola.tencentcloud.tdmysql_backup_policy_info` | Gather Tencent Cloud TDSQL MySQL backup policy | [`tdmysql_backup_policy_info`](plugins/modules/tdmysql_backup_policy_info.py) |
| `susunola.tencentcloud.tdmysql_database_object_info` | Gather Tencent Cloud TDSQL MySQL databases and objects | [`tdmysql_database_object_info`](plugins/modules/tdmysql_database_object_info.py) |
| `susunola.tencentcloud.tdmysql_db_instance_info` | Gather information about Tencent Cloud TDMYSQL db instances | [`tdmysql_db_instance_info`](plugins/modules/tdmysql_db_instance_info.py) |
| `susunola.tencentcloud.tdmysql_parameter_info` | Gather Tencent Cloud TDSQL MySQL instance parameters | [`tdmysql_parameter_info`](plugins/modules/tdmysql_parameter_info.py) |
| `susunola.tencentcloud.tem_application_info` | Gather information about Tencent Cloud TEM applications | [`tem_application_info`](plugins/modules/tem_application_info.py) |
| `susunola.tencentcloud.teo_acceleration_domain_info` | Gather information about Tencent Cloud EdgeOne acceleration domains | [`teo_acceleration_domain_info`](plugins/modules/teo_acceleration_domain_info.py) |
| `susunola.tencentcloud.teo_dns_record_info` | Gather information about Tencent Cloud EdgeOne DNS records | [`teo_dns_record_info`](plugins/modules/teo_dns_record_info.py) |
| `susunola.tencentcloud.teo_function_info` | Gather information about Tencent Cloud TEO functions | [`teo_function_info`](plugins/modules/teo_function_info.py) |
| `susunola.tencentcloud.teo_origin_group_info` | Gather information about Tencent Cloud EdgeOne origin groups | [`teo_origin_group_info`](plugins/modules/teo_origin_group_info.py) |
| `susunola.tencentcloud.teo_security_ip_group_info` | Gather information about Tencent Cloud EdgeOne security IP groups | [`teo_security_ip_group_info`](plugins/modules/teo_security_ip_group_info.py) |
| `susunola.tencentcloud.teo_zone_info` | Gather information about Tencent Cloud EdgeOne zones | [`teo_zone_info`](plugins/modules/teo_zone_info.py) |
| `susunola.tencentcloud.thpc_cluster_info` | Gather information about Tencent Cloud THPC clusters | [`thpc_cluster_info`](plugins/modules/thpc_cluster_info.py) |
| `susunola.tencentcloud.tia_job_info` | Gather information about Tencent Cloud TIA jobs | [`tia_job_info`](plugins/modules/tia_job_info.py) |
| `susunola.tencentcloud.tiia_group_info` | Gather information about Tencent Cloud TIIA groups | [`tiia_group_info`](plugins/modules/tiia_group_info.py) |
| `susunola.tencentcloud.tione_data_source_info` | Gather Tencent Cloud TIONE data sources | [`tione_data_source_info`](plugins/modules/tione_data_source_info.py) |
| `susunola.tencentcloud.tione_dataset_info` | Gather information about Tencent Cloud TIONE datasets | [`tione_dataset_info`](plugins/modules/tione_dataset_info.py) |
| `susunola.tencentcloud.tione_model_service_diagnostics_info` | Gather Tencent Cloud TIONE model service diagnostics | [`tione_model_service_diagnostics_info`](plugins/modules/tione_model_service_diagnostics_info.py) |
| `susunola.tencentcloud.tione_model_service_info` | Gather Tencent Cloud TIONE online model services | [`tione_model_service_info`](plugins/modules/tione_model_service_info.py) |
| `susunola.tencentcloud.tione_notebook_info` | Gather Tencent Cloud TIONE notebooks | [`tione_notebook_info`](plugins/modules/tione_notebook_info.py) |
| `susunola.tencentcloud.tione_training_model_version_info` | Gather Tencent Cloud TIONE training-model versions | [`tione_training_model_version_info`](plugins/modules/tione_training_model_version_info.py) |
| `susunola.tencentcloud.tione_training_task_info` | Gather Tencent Cloud TIONE training tasks | [`tione_training_task_info`](plugins/modules/tione_training_task_info.py) |
| `susunola.tencentcloud.tiw_running_task_info` | Gather information about Tencent Cloud TIW running tasks | [`tiw_running_task_info`](plugins/modules/tiw_running_task_info.py) |
| `susunola.tencentcloud.tke_cluster_autoscaler_info` | Gather information about Tencent Cloud TKE cluster autoscaler options | [`tke_cluster_autoscaler_info`](plugins/modules/tke_cluster_autoscaler_info.py) |
| `susunola.tencentcloud.tke_cluster_info` | Gather information about Tencent Cloud TKE clusters | [`tke_cluster_info`](plugins/modules/tke_cluster_info.py) |
| `susunola.tencentcloud.tke_node_pool_info` | Gather information about Tencent Cloud TKE node pools | [`tke_node_pool_info`](plugins/modules/tke_node_pool_info.py) |
| `susunola.tencentcloud.tokenhub_model_info` | Gather information about Tencent Cloud TOKENHUB models | [`tokenhub_model_info`](plugins/modules/tokenhub_model_info.py) |
| `susunola.tencentcloud.tourism_draw_resource_info` | Gather information about Tencent Cloud TOURISM draw resources | [`tourism_draw_resource_info`](plugins/modules/tourism_draw_resource_info.py) |
| `susunola.tencentcloud.trabbit_rabbit_mq_serverless_instance_info` | Gather information about Tencent Cloud TRABBIT rabbit mq serverless instances | [`trabbit_rabbit_mq_serverless_instance_info`](plugins/modules/trabbit_rabbit_mq_serverless_instance_info.py) |
| `susunola.tencentcloud.trocket_consumer_client_info` | Gather information about Tencent Cloud TROCKET consumer clients | [`trocket_consumer_client_info`](plugins/modules/trocket_consumer_client_info.py) |
| `susunola.tencentcloud.trp_code_batch_info` | Gather information about Tencent Cloud TRP code batches | [`trp_code_batch_info`](plugins/modules/trp_code_batch_info.py) |
| `susunola.tencentcloud.trro_device_info` | Gather information about Tencent Cloud TRRO devices | [`trro_device_info`](plugins/modules/trro_device_info.py) |
| `susunola.tencentcloud.trtc_call_info` | Gather information about Tencent Cloud TRTC calls | [`trtc_call_info`](plugins/modules/trtc_call_info.py) |
| `susunola.tencentcloud.tse_auto_scaler_resource_strategy_binding_group_info` | Gather information about Tencent Cloud TSE auto scaler resource strategy binding groups | [`tse_auto_scaler_resource_strategy_binding_group_info`](plugins/modules/tse_auto_scaler_resource_strategy_binding_group_info.py) |
| `susunola.tencentcloud.tse_cloud_native_api_gateway_canary_rule_info` | Gather information about Tencent Cloud TSE cloud native api gateway canary rules | [`tse_cloud_native_api_gateway_canary_rule_info`](plugins/modules/tse_cloud_native_api_gateway_canary_rule_info.py) |
| `susunola.tencentcloud.tse_cloud_native_api_gateway_certificate_info` | Gather information about Tencent Cloud TSE cloud native api gateway certificates | [`tse_cloud_native_api_gateway_certificate_info`](plugins/modules/tse_cloud_native_api_gateway_certificate_info.py) |
| `susunola.tencentcloud.tse_cloud_native_api_gateway_consumer_group_info` | Gather information about Tencent Cloud TSE cloud native api gateway consumer groups | [`tse_cloud_native_api_gateway_consumer_group_info`](plugins/modules/tse_cloud_native_api_gateway_consumer_group_info.py) |
| `susunola.tencentcloud.tse_cloud_native_api_gateway_consumer_info` | Gather information about Tencent Cloud TSE cloud native api gateway consumers | [`tse_cloud_native_api_gateway_consumer_info`](plugins/modules/tse_cloud_native_api_gateway_consumer_info.py) |
| `susunola.tencentcloud.tse_cloud_native_api_gateway_info` | Gather information about Tencent Cloud TSE cloud native api gateways | [`tse_cloud_native_api_gateway_info`](plugins/modules/tse_cloud_native_api_gateway_info.py) |
| `susunola.tencentcloud.tse_cloud_native_api_gateway_llm_model_api_info` | Gather information about Tencent Cloud TSE cloud native api gateway llm model apis | [`tse_cloud_native_api_gateway_llm_model_api_info`](plugins/modules/tse_cloud_native_api_gateway_llm_model_api_info.py) |
| `susunola.tencentcloud.tse_cloud_native_api_gateway_llm_model_service_info` | Gather information about Tencent Cloud TSE cloud native api gateway llm model services | [`tse_cloud_native_api_gateway_llm_model_service_info`](plugins/modules/tse_cloud_native_api_gateway_llm_model_service_info.py) |
| `susunola.tencentcloud.tse_cloud_native_api_gateway_route_info` | Gather information about Tencent Cloud TSE cloud native api gateway routes | [`tse_cloud_native_api_gateway_route_info`](plugins/modules/tse_cloud_native_api_gateway_route_info.py) |
| `susunola.tencentcloud.tse_cloud_native_api_gateway_secret_key_info` | Gather information about Tencent Cloud TSE cloud native api gateway secret keys | [`tse_cloud_native_api_gateway_secret_key_info`](plugins/modules/tse_cloud_native_api_gateway_secret_key_info.py) |
| `susunola.tencentcloud.tse_cloud_native_api_gateway_service_info` | Gather information about Tencent Cloud TSE cloud native api gateway services | [`tse_cloud_native_api_gateway_service_info`](plugins/modules/tse_cloud_native_api_gateway_service_info.py) |
| `susunola.tencentcloud.tse_config_file_catalog_info` | Gather Tencent Cloud TSE configuration file inventory | [`tse_config_file_catalog_info`](plugins/modules/tse_config_file_catalog_info.py) |
| `susunola.tencentcloud.tse_config_file_group_info` | Gather information about Tencent Cloud TSE config file groups | [`tse_config_file_group_info`](plugins/modules/tse_config_file_group_info.py) |
| `susunola.tencentcloud.tse_config_file_release_info` | Gather Tencent Cloud TSE configuration release audit data | [`tse_config_file_release_info`](plugins/modules/tse_config_file_release_info.py) |
| `susunola.tencentcloud.tse_config_file_template_info` | Gather Tencent Cloud TSE configuration file templates | [`tse_config_file_template_info`](plugins/modules/tse_config_file_template_info.py) |
| `susunola.tencentcloud.tse_gateway_ip_lookup_info` | Resolve a Tencent Cloud TSE gateway from its public IP | [`tse_gateway_ip_lookup_info`](plugins/modules/tse_gateway_ip_lookup_info.py) |
| `susunola.tencentcloud.tse_gateway_runtime_info` | Gather Tencent Cloud TSE gateway runtime topology | [`tse_gateway_runtime_info`](plugins/modules/tse_gateway_runtime_info.py) |
| `susunola.tencentcloud.tse_gateway_service_inventory_info` | Gather Tencent Cloud TSE gateway service and route inventory | [`tse_gateway_service_inventory_info`](plugins/modules/tse_gateway_service_inventory_info.py) |
| `susunola.tencentcloud.tse_governance_alias_info` | Gather information about Tencent Cloud TSE governance aliases | [`tse_governance_alias_info`](plugins/modules/tse_governance_alias_info.py) |
| `susunola.tencentcloud.tse_governance_instance_info` | Gather information about Tencent Cloud TSE governance instances | [`tse_governance_instance_info`](plugins/modules/tse_governance_instance_info.py) |
| `susunola.tencentcloud.tse_governance_lane_group_info` | Gather information about Tencent Cloud TSE governance lane groups | [`tse_governance_lane_group_info`](plugins/modules/tse_governance_lane_group_info.py) |
| `susunola.tencentcloud.tse_governance_namespace_info` | Gather information about Tencent Cloud TSE governance namespaces | [`tse_governance_namespace_info`](plugins/modules/tse_governance_namespace_info.py) |
| `susunola.tencentcloud.tse_governance_service_contract_info` | Gather Tencent Cloud TSE governance service contracts | [`tse_governance_service_contract_info`](plugins/modules/tse_governance_service_contract_info.py) |
| `susunola.tencentcloud.tse_governance_service_info` | Gather information about Tencent Cloud TSE governance services | [`tse_governance_service_info`](plugins/modules/tse_governance_service_info.py) |
| `susunola.tencentcloud.tse_instance_tag_info` | Gather Tencent Cloud TSE instance tag metadata | [`tse_instance_tag_info`](plugins/modules/tse_instance_tag_info.py) |
| `susunola.tencentcloud.tse_native_gateway_server_group_info` | Gather information about Tencent Cloud TSE native gateway server groups | [`tse_native_gateway_server_group_info`](plugins/modules/tse_native_gateway_server_group_info.py) |
| `susunola.tencentcloud.tse_native_gateway_service_source_info` | Gather information about Tencent Cloud TSE native gateway service sources | [`tse_native_gateway_service_source_info`](plugins/modules/tse_native_gateway_service_source_info.py) |
| `susunola.tencentcloud.tse_sre_access_address_info` | Gather Tencent Cloud TSE registry-engine access addresses | [`tse_sre_access_address_info`](plugins/modules/tse_sre_access_address_info.py) |
| `susunola.tencentcloud.tse_sre_instance_info` | Gather information about Tencent Cloud TSE sre instances | [`tse_sre_instance_info`](plugins/modules/tse_sre_instance_info.py) |
| `susunola.tencentcloud.tse_sre_topology_info` | Gather Tencent Cloud TSE registry-engine topology | [`tse_sre_topology_info`](plugins/modules/tse_sre_topology_info.py) |
| `susunola.tencentcloud.tsf_application_config_info` | Gather information about Tencent Cloud TSF application configs | [`tsf_application_config_info`](plugins/modules/tsf_application_config_info.py) |
| `susunola.tencentcloud.tsf_application_config_release_info` | Gather information about Tencent Cloud TSF config releases | [`tsf_application_config_release_info`](plugins/modules/tsf_application_config_release_info.py) |
| `susunola.tencentcloud.tsf_application_info` | Gather information about Tencent Cloud TSF applications | [`tsf_application_info`](plugins/modules/tsf_application_info.py) |
| `susunola.tencentcloud.tsf_cluster_info` | Gather information about Tencent Cloud TSF clusters | [`tsf_cluster_info`](plugins/modules/tsf_cluster_info.py) |
| `susunola.tencentcloud.tsf_container_deployment_group_info` | Gather information about Tencent Cloud TSF container deployment groups | [`tsf_container_deployment_group_info`](plugins/modules/tsf_container_deployment_group_info.py) |
| `susunola.tencentcloud.tsf_lane_info` | Gather information about Tencent Cloud TSF lanes | [`tsf_lane_info`](plugins/modules/tsf_lane_info.py) |
| `susunola.tencentcloud.tsf_lane_rule_info` | Gather information about Tencent Cloud TSF lane rules | [`tsf_lane_rule_info`](plugins/modules/tsf_lane_rule_info.py) |
| `susunola.tencentcloud.tsf_microservice_info` | Gather information about Tencent Cloud TSF microservices | [`tsf_microservice_info`](plugins/modules/tsf_microservice_info.py) |
| `susunola.tencentcloud.tsf_namespace_info` | Gather information about Tencent Cloud TSF namespaces | [`tsf_namespace_info`](plugins/modules/tsf_namespace_info.py) |
| `susunola.tencentcloud.tsf_public_config_info` | Gather information about Tencent Cloud TSF public configs | [`tsf_public_config_info`](plugins/modules/tsf_public_config_info.py) |
| `susunola.tencentcloud.tsf_repository_info` | Gather information about Tencent Cloud TSF repositories | [`tsf_repository_info`](plugins/modules/tsf_repository_info.py) |
| `susunola.tencentcloud.tsf_vm_deployment_group_info` | Gather information about Tencent Cloud TSF VM deployment groups | [`tsf_vm_deployment_group_info`](plugins/modules/tsf_vm_deployment_group_info.py) |
| `susunola.tencentcloud.vcube_resource_info` | Gather information about Tencent Cloud VCUBE resources | [`vcube_resource_info`](plugins/modules/vcube_resource_info.py) |
| `susunola.tencentcloud.vdb_instance_info` | Gather information about Tencent Cloud VDB instances | [`vdb_instance_info`](plugins/modules/vdb_instance_info.py) |
| `susunola.tencentcloud.vm_task_info` | Gather information about Tencent Cloud VM tasks | [`vm_task_info`](plugins/modules/vm_task_info.py) |
| `susunola.tencentcloud.vod_class_info` | Gather information about Tencent Cloud VOD classes | [`vod_class_info`](plugins/modules/vod_class_info.py) |
| `susunola.tencentcloud.vod_incremental_migration_strategy_info` | Gather information about Tencent Cloud VOD incremental migration strategies | [`vod_incremental_migration_strategy_info`](plugins/modules/vod_incremental_migration_strategy_info.py) |
| `susunola.tencentcloud.vod_sub_app_info` | Gather information about Tencent Cloud VOD subapplications | [`vod_sub_app_info`](plugins/modules/vod_sub_app_info.py) |
| `susunola.tencentcloud.vpc_address_template_group_info` | Gather information about Tencent Cloud VPC address template groups | [`vpc_address_template_group_info`](plugins/modules/vpc_address_template_group_info.py) |
| `susunola.tencentcloud.vpc_address_template_info` | Gather information about Tencent Cloud VPC address templates | [`vpc_address_template_info`](plugins/modules/vpc_address_template_info.py) |
| `susunola.tencentcloud.vpc_flow_log_info` | Gather information about Tencent Cloud VPC flow logs | [`vpc_flow_log_info`](plugins/modules/vpc_flow_log_info.py) |
| `susunola.tencentcloud.vpc_info` | Gather information about Tencent Cloud VPCs | [`vpc_info`](plugins/modules/vpc_info.py) |
| `susunola.tencentcloud.vpn_connection_info` | Gather information about Tencent Cloud VPN connections | [`vpn_connection_info`](plugins/modules/vpn_connection_info.py) |
| `susunola.tencentcloud.vpn_gateway_info` | Gather information about Tencent Cloud VPN gateways | [`vpn_gateway_info`](plugins/modules/vpn_gateway_info.py) |
| `susunola.tencentcloud.waf_anti_info_leak_rule_info` | Gather information about Tencent Cloud WAF anti-info-leak rules | [`waf_anti_info_leak_rule_info`](plugins/modules/waf_anti_info_leak_rule_info.py) |
| `susunola.tencentcloud.waf_anti_tamper_rule_info` | Gather information about Tencent Cloud WAF anti-tamper rules | [`waf_anti_tamper_rule_info`](plugins/modules/waf_anti_tamper_rule_info.py) |
| `susunola.tencentcloud.waf_attack_white_rule_info` | Gather information about Tencent Cloud WAF attack-whitelist rules | [`waf_attack_white_rule_info`](plugins/modules/waf_attack_white_rule_info.py) |
| `susunola.tencentcloud.waf_cc_rule_info` | Gather information about Tencent Cloud WAF CC rules | [`waf_cc_rule_info`](plugins/modules/waf_cc_rule_info.py) |
| `susunola.tencentcloud.waf_custom_rule_info` | Gather information about Tencent Cloud WAF custom rules | [`waf_custom_rule_info`](plugins/modules/waf_custom_rule_info.py) |
| `susunola.tencentcloud.waf_custom_white_rule_info` | Gather information about Tencent Cloud WAF custom-whitelist rules | [`waf_custom_white_rule_info`](plugins/modules/waf_custom_white_rule_info.py) |
| `susunola.tencentcloud.waf_host_info` | Gather information about Tencent Cloud WAF protected hosts | [`waf_host_info`](plugins/modules/waf_host_info.py) |
| `susunola.tencentcloud.waf_instance_info` | Gather information about Tencent Cloud WAF instances | [`waf_instance_info`](plugins/modules/waf_instance_info.py) |
| `susunola.tencentcloud.waf_owasp_white_rule_info` | Gather information about Tencent Cloud WAF OWASP-whitelist rules | [`waf_owasp_white_rule_info`](plugins/modules/waf_owasp_white_rule_info.py) |
| `susunola.tencentcloud.wav_activity_info` | Gather information about Tencent Cloud WAV activities | [`wav_activity_info`](plugins/modules/wav_activity_info.py) |
| `susunola.tencentcloud.wedata_project_info` | Gather information about Tencent Cloud WEDATA projects | [`wedata_project_info`](plugins/modules/wedata_project_info.py) |
| `susunola.tencentcloud.weilingwith_element_profile_page_info` | Gather information about Tencent Cloud WEILINGWITH element profile pages | [`weilingwith_element_profile_page_info`](plugins/modules/weilingwith_element_profile_page_info.py) |
| `susunola.tencentcloud.wss_cert_info` | Gather information about Tencent Cloud WSS certs | [`wss_cert_info`](plugins/modules/wss_cert_info.py) |
| `susunola.tencentcloud.yinsuda_ktv_robot_info` | Gather information about Tencent Cloud YINSUDA ktv robots | [`yinsuda_ktv_robot_info`](plugins/modules/yinsuda_ktv_robot_info.py) |
| `susunola.tencentcloud.yunjing_account_statistic_info` | Gather information about Tencent Cloud YUNJING account statistics | [`yunjing_account_statistic_info`](plugins/modules/yunjing_account_statistic_info.py) |

</details>

Most `_info` modules are generated from SDK metadata by
`scripts/generate_info_modules.py` (marked with a `# Generated by` comment;
run with `--check` to verify they are up to date). The module tables and the
`action_groups` registry are kept in sync with `scripts/sync_registry.py`
(`--check` runs in CI).

See the generated [product capability matrix](docs/product-capabilities.md)
for product-level write, discovery and reusable-role maturity.

## Included plugins

| Plugin | Type | Purpose |
| --- | --- | --- |
| `tc_wait` | action | Wait for an existing resource to reach a state by polling one of the `*_info` modules |
| `tencentcloud_resource_actions` | callback | Summarise the Tencent Cloud API calls a play made, task by task |
| `tencentcloud_cvm` | inventory | Dynamic inventory of CVM instances with constructed groups and caching |
| `tencentcloud_clb` | inventory | Dynamic inventory of CLB load balancers, listeners and backend targets |
| `tencentcloud_sg` | inventory | Dynamic inventory of security groups and their associated network interfaces |
| `tencentcloud_tke` | inventory | Dynamic inventory of TKE cluster nodes |
| `tencentcloud_cos` | inventory | Dynamic inventory of COS buckets and objects |
| `tat` | connection | Run commands and transfer files over the TAT agent (no SSH or public IP required) |
| `tag_merge` | filter | Merge tag mappings, API-shaped tag lists and SDK tag objects into one mapping |
| `cls_topic` | event_source | Stream new log records from a CLS log topic (Event-Driven Ansible) |
| `cmq_queue` | event_source | Long-poll a CMQ queue and stream messages (Event-Driven Ansible) |
| `cos_bucket` | event_source | Poll a COS bucket for new or changed objects (Event-Driven Ansible) |
| `tke_cluster` | event_source | Poll TKE cluster state changes (Event-Driven Ansible) |
| `sts_caller_identity` | lookup | Return the current caller identity (Uin, AccountId, Arn) |
| `ssm_parameter` | lookup | Read secrets from Tencent Cloud Secrets Manager (SSM) |
| `resource_id` | lookup | Resolve exact names to IDs across core network, compute, database, API Gateway, TCR and TEM resources |

## Included roles

| Role | Purpose |
| --- | --- |
| `tc_launch` | Launch CVM instances with sensible defaults over `cvm_instance` (`exact_count` / `count_tag` supported) |
| `tc_lighthouse_stack` | Provision Lighthouse instances with SSH keys, exact firewall rules, disks and snapshots |
| `tc_block_storage` | Provision CBS disks, snapshots, sharing, backup points and automatic retention policies |
| `tc_clb_http` | Create a CLB load balancer with HTTP listeners and backend targets in one call |
| `tc_alb_application_entry` | Provision ALB target groups, exact backends and HTTP, HTTPS or QUIC listeners |
| `tc_autoscaling_group` | Provision Auto Scaling groups with policies and scheduled capacity actions |
| `tc_tem_application` | Provision a TEM environment, deploy an application version and reconcile access services |
| `tc_vpc_foundation` | Build a VPC foundation with subnets, NAT gateways, routes and security controls |
| `tc_tke_platform` | Provision a TKE cluster with node pools, endpoints, addons, authentication and audit delivery |
| `tc_database_stack` | Provision TencentDB for MySQL with databases, accounts, privileges and backup retention |
| `tc_dns_zone` | Provision DNSPod domains, custom routing lines, line groups and records |
| `tc_cynosdb_cluster` | Provision CynosDB clusters, accounts, exact privileges and automatic backups |
| `tc_eventbridge_router` | Provision EventBridge buses, source connections, routing rules and targets |
| `tc_redis_stack` | Provision TencentDB for Redis with accounts, automatic backups and parameter templates |
| `tc_mongodb_stack` | Provision TencentDB for MongoDB with accounts, exact database roles and automatic backups |
| `tc_mariadb_stack` | Provision MariaDB instances, accounts, scoped privileges and automatic backups |
| `tc_mqtt_broker` | Provision MQTT instances, topics, users and ordered authorization policies |
| `tc_postgresql_stack` | Provision PostgreSQL instances, accounts, backup plans and parameter templates |
| `tc_serverless_application` | Deploy an SCF function with aliases, triggers and optional API Gateway exposure |
| `tc_api_gateway_platform` | Provision API Gateway services, APIs, releases, keys and usage plans |
| `tc_config_governance` | Operate Config recording, delivery, compliance, remediation, alerting and aggregation |
| `tc_chdfs_data_lake` | Provision CHDFS file systems, access groups, rules, mounts and bindings |
| `tc_cloud_firewall_policy` | Operate address templates and internet, NAT, VPC and DNAT firewall policy |
| `tc_elasticsearch_platform` | Provision Elasticsearch clusters, indexes and snapshots |
| `tc_sqlserver_stack` | Provision SQL Server instances, backup strategy and accounts |
| `tc_gwlb_service_chain` | Provision Gateway Load Balancers, target groups, appliances and associations |
| `tc_organization_governance` | Govern Organization nodes, members, identities and access policies |
| `tc_kms_keyring` | Govern KMS keys, automatic rotation and guarded scheduled deletion |
| `tc_direct_connect_fabric` | Provision or adopt Direct Connect circuits and private tunnels |
| `tc_cdn_delivery` | Operate CDN domains, serving state and real-time CLS access logs |
| `tc_goosefs_cache` | Provision GooseFS file systems and quota-governed Filesets |
| `tc_cloud_audit_governance` | Govern account CloudAudit delivery and scoped audit tracks |
| `tc_observability_baseline` | Establish CLS indexed topics and Cloud Monitor alarm policies |
| `tc_prometheus_platform` | Provision Managed Prometheus with collection agents, rules, alerts, notifications and Grafana bindings |
| `tc_object_storage_baseline` | Establish a secure COS bucket with encryption, lifecycle, policy, logging and replication |
| `tc_shared_file_storage` | Provision CFS with permission groups, client rules and automatic snapshot retention |
| `tc_security_baseline` | Establish CAM, CloudAudit and Config compliance controls |
| `tc_waf_application` | Manage protected WAF domains and the complete application-security rule set |
| `tc_edgeone_application` | Provision EdgeOne zones, delivery, DNS and scoped web-security policies |
| `tc_container_registry` | Provision TCR namespaces, repositories, vulnerability controls and replication |
| `tc_kafka_platform` | Provision CKafka instances, routes, users, topics and exact ACL controls |
| `tc_rocketmq_platform` | Provision TDMQ RocketMQ clusters, namespaces, roles, permissions, topics and groups |
| `tc_rabbitmq_platform` | Provision TDMQ RabbitMQ dedicated instances, users, virtual hosts, permissions and bindings |
| `tc_rabbitmq_serverless` | Manage users, vhosts, permissions, exchanges, queues and bindings in an existing RabbitMQ Serverless instance |
| `tc_cmq_messaging` | Provision CMQ queues, topics and HTTP or queue subscriptions |

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
