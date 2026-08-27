# -*- coding: utf-8 -*-
"""Auto-discovered ``_info`` module specs appended to the generator SPECS.

Written by scripts/discover_info_specs.py -- regenerate instead of editing.
Every spec was derived by introspecting the installed tencentcloud SDK
packages (request/response field names, filter model shapes, pagination
types) exactly like the curated SPECS in generate_info_modules.py.
"""

SPECS_AUTO = [
    {
        'module': 'adp_agent_release_preview_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.adp.v20260520',
        'client_module': 'adp_client',
        'client_class': 'AdpClient',
        'sdk_package': 'tencentcloud-sdk-python-adp',
        'endpoint': 'adp.tencentcloudapi.com',
        'action': 'DescribeAgentReleasePreviewList',
        'request_class': 'DescribeAgentReleasePreviewListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'ReleaseList',
        'response_total': 'TotalCount',
        'result_key': 'agent_release_previews',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud ADP agent release previews',
        'description': 'Returns ADP agent release previews visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ADP agent release previews.',
        'return_total_doc': 'Number of agent release previews reported by the API.',
        'examples': """\
- name: List all agent release previews
  tencentcloud.cloud.adp_agent_release_preview_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ags_sandbox_instance_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ags.v20250920',
        'client_module': 'ags_client',
        'client_class': 'AgsClient',
        'sdk_package': 'tencentcloud-sdk-python-ags',
        'endpoint': 'ags.tencentcloudapi.com',
        'action': 'DescribeSandboxInstanceList',
        'request_class': 'DescribeSandboxInstanceListRequest',
        'ids': {
            'param': 'sandbox_instance_ids',
            'field': 'InstanceIds',
            'doc': 'Sandbox instance IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'AGS API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'InstanceSet',
        'response_total': 'TotalCount',
        'result_key': 'sandbox_instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud AGS sandbox instances',
        'description': 'Returns AGS sandbox instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching AGS sandbox instances.',
        'return_total_doc': 'Number of sandbox instances reported by the API.',
        'examples': """\
- name: List all sandbox instances
  tencentcloud.cloud.ags_sandbox_instance_info:
    region: ap-guangzhou

- name: Find sandbox instances by ID
  tencentcloud.cloud.ags_sandbox_instance_info:
    region: ap-guangzhou
    sandbox_instance_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'ame_ktv_robot_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ame.v20190916',
        'client_module': 'ame_client',
        'client_class': 'AmeClient',
        'sdk_package': 'tencentcloud-sdk-python-ame',
        'endpoint': 'ame.tencentcloudapi.com',
        'action': 'DescribeKTVRobots',
        'request_class': 'DescribeKTVRobotsRequest',
        'ids': {
            'param': 'ktv_robot_ids',
            'field': 'RobotIds',
            'doc': 'Ktv robot IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'KTVRobotInfoSet',
        'response_total': 'TotalCount',
        'result_key': 'ktv_robots',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud AME ktv robots',
        'description': 'Returns AME ktv robots visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching AME ktv robots.',
        'return_total_doc': 'Number of ktv robots reported by the API.',
        'examples': """\
- name: List all ktv robots
  tencentcloud.cloud.ame_ktv_robot_info:
    region: ap-guangzhou

- name: Find ktv robots by ID
  tencentcloud.cloud.ame_ktv_robot_info:
    region: ap-guangzhou
    ktv_robot_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'antiddos_d_do_s_block_record_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.antiddos.v20250903',
        'client_module': 'antiddos_client',
        'client_class': 'AntiddosClient',
        'sdk_package': 'tencentcloud-sdk-python-antiddos',
        'endpoint': 'antiddos.tencentcloudapi.com',
        'action': 'DescribeDDoSBlockRecords',
        'request_class': 'DescribeDDoSBlockRecordsRequest',
        'ids': None,
        'filters': {
            'doc': 'ANTIDDOS API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'BlockRecords',
        'response_total': 'TotalCount',
        'result_key': 'd_do_s_block_records',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud ANTIDDOS d do s block records',
        'description': 'Returns ANTIDDOS d do s block records visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ANTIDDOS d do s block records.',
        'return_total_doc': 'Number of d do s block records reported by the API.',
        'examples': """\
- name: List all d do s block records
  tencentcloud.cloud.antiddos_d_do_s_block_record_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ape_auth_user_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ape.v20200513',
        'client_module': 'ape_client',
        'client_class': 'ApeClient',
        'sdk_package': 'tencentcloud-sdk-python-ape',
        'endpoint': 'ape.tencentcloudapi.com',
        'action': 'DescribeAuthUsers',
        'request_class': 'DescribeAuthUsersRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Users',
        'response_total': 'TotalCount',
        'result_key': 'auth_users',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud APE auth users',
        'description': 'Returns APE auth users visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching APE auth users.',
        'return_total_doc': 'Number of auth users reported by the API.',
        'examples': """\
- name: List all auth users
  tencentcloud.cloud.ape_auth_user_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'api_product_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.api.v20201106',
        'client_module': 'api_client',
        'client_class': 'ApiClient',
        'sdk_package': 'tencentcloud-sdk-python-api',
        'endpoint': 'api.tencentcloudapi.com',
        'action': 'DescribeProducts',
        'request_class': 'DescribeProductsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Products',
        'response_total': 'TotalCount',
        'result_key': 'products',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud API products',
        'description': 'Returns API products visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching API products.',
        'return_total_doc': 'Number of products reported by the API.',
        'examples': """\
- name: List all products
  tencentcloud.cloud.api_product_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'apis_agent_app_mcp_server_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.apis.v20240801',
        'client_module': 'apis_client',
        'client_class': 'ApisClient',
        'sdk_package': 'tencentcloud-sdk-python-apis',
        'endpoint': 'apis.tencentcloudapi.com',
        'action': 'DescribeAgentAppMcpServers',
        'request_class': 'DescribeAgentAppMcpServersRequest',
        'ids': {
            'param': 'agent_app_mcp_server_ids',
            'field': 'McpServerIDs',
            'doc': 'Agent app mcp server IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Data.Items',
        'response_total': 'Data.Total',
        'result_key': 'agent_app_mcp_servers',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud APIS agent app mcp servers',
        'description': 'Returns APIS agent app mcp servers visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching APIS agent app mcp servers.',
        'return_total_doc': 'Number of agent app mcp servers reported by the API.',
        'examples': """\
- name: List all agent app mcp servers
  tencentcloud.cloud.apis_agent_app_mcp_server_info:
    region: ap-guangzhou

- name: Find agent app mcp servers by ID
  tencentcloud.cloud.apis_agent_app_mcp_server_info:
    region: ap-guangzhou
    agent_app_mcp_server_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'apm_general_span_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.apm.v20210622',
        'client_module': 'apm_client',
        'client_class': 'ApmClient',
        'sdk_package': 'tencentcloud-sdk-python-apm',
        'endpoint': 'apm.tencentcloudapi.com',
        'action': 'DescribeGeneralSpanList',
        'request_class': 'DescribeGeneralSpanListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Spans',
        'response_total': 'TotalCount',
        'result_key': 'general_spans',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud APM general spans',
        'description': 'Returns APM general spans visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching APM general spans.',
        'return_total_doc': 'Number of general spans reported by the API.',
        'examples': """\
- name: List all general spans
  tencentcloud.cloud.apm_general_span_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'asw_flow_service_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.asw.v20200722',
        'client_module': 'asw_client',
        'client_class': 'AswClient',
        'sdk_package': 'tencentcloud-sdk-python-asw',
        'endpoint': 'asw.tencentcloudapi.com',
        'action': 'DescribeFlowServices',
        'request_class': 'DescribeFlowServicesRequest',
        'ids': None,
        'filters': {
            'doc': 'ASW API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'FlowServiceSet',
        'response_total': 'TotalCount',
        'result_key': 'flow_services',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud ASW flow services',
        'description': 'Returns ASW flow services visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ASW flow services.',
        'return_total_doc': 'Number of flow services reported by the API.',
        'examples': """\
- name: List all flow services
  tencentcloud.cloud.asw_flow_service_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'batch_compute_env_create_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.batch.v20170312',
        'client_module': 'batch_client',
        'client_class': 'BatchClient',
        'sdk_package': 'tencentcloud-sdk-python-batch',
        'endpoint': 'batch.tencentcloudapi.com',
        'action': 'DescribeComputeEnvCreateInfos',
        'request_class': 'DescribeComputeEnvCreateInfosRequest',
        'ids': {
            'param': 'compute_env_create_ids',
            'field': 'EnvIds',
            'doc': 'Compute env create IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'BATCH API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'ComputeEnvCreateInfoSet',
        'response_total': 'TotalCount',
        'result_key': 'compute_env_creates',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud BATCH compute env creates',
        'description': 'Returns BATCH compute env creates visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching BATCH compute env creates.',
        'return_total_doc': 'Number of compute env creates reported by the API.',
        'examples': """\
- name: List all compute env creates
  tencentcloud.cloud.batch_compute_env_create_info:
    region: ap-guangzhou

- name: Find compute env creates by ID
  tencentcloud.cloud.batch_compute_env_create_info:
    region: ap-guangzhou
    compute_env_create_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'bdrc_backup_vault_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.bdrc.v20260330',
        'client_module': 'bdrc_client',
        'client_class': 'BdrcClient',
        'sdk_package': 'tencentcloud-sdk-python-bdrc',
        'endpoint': 'bdrc.tencentcloudapi.com',
        'action': 'DescribeBackupVaults',
        'request_class': 'DescribeBackupVaultsRequest',
        'ids': {
            'param': 'backup_vault_ids',
            'field': 'VaultIds',
            'doc': 'Backup vault IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'BDRC API filter names mapped to lists of values.',
            'model': 'FilterModel',
        },
        'extra_params': [],
        'response_items': 'BackupVaultSet',
        'response_total': 'TotalCount',
        'result_key': 'backup_vaults',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud BDRC backup vaults',
        'description': 'Returns BDRC backup vaults visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching BDRC backup vaults.',
        'return_total_doc': 'Number of backup vaults reported by the API.',
        'examples': """\
- name: List all backup vaults
  tencentcloud.cloud.bdrc_backup_vault_info:
    region: ap-guangzhou

- name: Find backup vaults by ID
  tencentcloud.cloud.bdrc_backup_vault_info:
    region: ap-guangzhou
    backup_vault_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'bh_device_group_member_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.bh.v20230418',
        'client_module': 'bh_client',
        'client_class': 'BhClient',
        'sdk_package': 'tencentcloud-sdk-python-bh',
        'endpoint': 'bh.tencentcloudapi.com',
        'action': 'DescribeDeviceGroupMembers',
        'request_class': 'DescribeDeviceGroupMembersRequest',
        'ids': {
            'param': 'device_group_member_ids',
            'field': 'ResourceIdSet',
            'doc': 'Device group member IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'BH API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'DeviceSet',
        'response_total': 'TotalCount',
        'result_key': 'device_group_members',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud BH device group members',
        'description': 'Returns BH device group members visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching BH device group members.',
        'return_total_doc': 'Number of device group members reported by the API.',
        'examples': """\
- name: List all device group members
  tencentcloud.cloud.bh_device_group_member_info:
    region: ap-guangzhou

- name: Find device group members by ID
  tencentcloud.cloud.bh_device_group_member_info:
    region: ap-guangzhou
    device_group_member_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'bm_device_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.bm.v20180423',
        'client_module': 'bm_client',
        'client_class': 'BmClient',
        'sdk_package': 'tencentcloud-sdk-python-bm',
        'endpoint': 'bm.tencentcloudapi.com',
        'action': 'DescribeDevices',
        'request_class': 'DescribeDevicesRequest',
        'ids': {
            'param': 'device_ids',
            'field': 'InstanceIds',
            'doc': 'Device IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'DeviceInfoSet',
        'response_total': 'TotalCount',
        'result_key': 'devices',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud BM devices',
        'description': 'Returns BM devices visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching BM devices.',
        'return_total_doc': 'Number of devices reported by the API.',
        'examples': """\
- name: List all devices
  tencentcloud.cloud.bm_device_info:
    region: ap-guangzhou

- name: Find devices by ID
  tencentcloud.cloud.bm_device_info:
    region: ap-guangzhou
    device_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'bma_bp_fake_app_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.bma.v20221115',
        'client_module': 'bma_client',
        'client_class': 'BmaClient',
        'sdk_package': 'tencentcloud-sdk-python-bma',
        'endpoint': 'bma.tencentcloudapi.com',
        'action': 'DescribeBPFakeAPPList',
        'request_class': 'DescribeBPFakeAPPListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'FakeAPPList',
        'response_total': 'TotalCount',
        'result_key': 'bp_fake_apps',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud BMA bp fake apps',
        'description': 'Returns BMA bp fake apps visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching BMA bp fake apps.',
        'return_total_doc': 'Number of bp fake apps reported by the API.',
        'examples': """\
- name: List all bp fake apps
  tencentcloud.cloud.bma_bp_fake_app_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'bmeip_eip_acl_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.bmeip.v20180625',
        'client_module': 'bmeip_client',
        'client_class': 'BmeipClient',
        'sdk_package': 'tencentcloud-sdk-python-bmeip',
        'endpoint': 'bmeip.tencentcloudapi.com',
        'action': 'DescribeEipAcls',
        'request_class': 'DescribeEipAclsRequest',
        'ids': {
            'param': 'eip_acl_ids',
            'field': 'AclIds',
            'doc': 'Eip acl IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'EipAclList',
        'response_total': 'TotalCount',
        'result_key': 'eip_acls',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud BMEIP eip acls',
        'description': 'Returns BMEIP eip acls visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching BMEIP eip acls.',
        'return_total_doc': 'Number of eip acls reported by the API.',
        'examples': """\
- name: List all eip acls
  tencentcloud.cloud.bmeip_eip_acl_info:
    region: ap-guangzhou

- name: Find eip acls by ID
  tencentcloud.cloud.bmeip_eip_acl_info:
    region: ap-guangzhou
    eip_acl_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'bmlb_load_balancer_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.bmlb.v20180625',
        'client_module': 'bmlb_client',
        'client_class': 'BmlbClient',
        'sdk_package': 'tencentcloud-sdk-python-bmlb',
        'endpoint': 'bmlb.tencentcloudapi.com',
        'action': 'DescribeLoadBalancers',
        'request_class': 'DescribeLoadBalancersRequest',
        'ids': {
            'param': 'load_balancer_ids',
            'field': 'LoadBalancerIds',
            'doc': 'Load balancer IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'LoadBalancerSet',
        'response_total': 'TotalCount',
        'result_key': 'load_balancers',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud BMLB load balancers',
        'description': 'Returns BMLB load balancers visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching BMLB load balancers.',
        'return_total_doc': 'Number of load balancers reported by the API.',
        'examples': """\
- name: List all load balancers
  tencentcloud.cloud.bmlb_load_balancer_info:
    region: ap-guangzhou

- name: Find load balancers by ID
  tencentcloud.cloud.bmlb_load_balancer_info:
    region: ap-guangzhou
    load_balancer_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'bmvpc_customer_gateway_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.bmvpc.v20180625',
        'client_module': 'bmvpc_client',
        'client_class': 'BmvpcClient',
        'sdk_package': 'tencentcloud-sdk-python-bmvpc',
        'endpoint': 'bmvpc.tencentcloudapi.com',
        'action': 'DescribeCustomerGateways',
        'request_class': 'DescribeCustomerGatewaysRequest',
        'ids': {
            'param': 'customer_gateway_ids',
            'field': 'CustomerGatewayIds',
            'doc': 'Customer gateway IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'BMVPC API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'CustomerGatewaySet',
        'response_total': 'TotalCount',
        'result_key': 'customer_gateways',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud BMVPC customer gateways',
        'description': 'Returns BMVPC customer gateways visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching BMVPC customer gateways.',
        'return_total_doc': 'Number of customer gateways reported by the API.',
        'examples': """\
- name: List all customer gateways
  tencentcloud.cloud.bmvpc_customer_gateway_info:
    region: ap-guangzhou

- name: Find customer gateways by ID
  tencentcloud.cloud.bmvpc_customer_gateway_info:
    region: ap-guangzhou
    customer_gateway_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cat_probe_task_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cat.v20180409',
        'client_module': 'cat_client',
        'client_class': 'CatClient',
        'sdk_package': 'tencentcloud-sdk-python-cat',
        'endpoint': 'cat.tencentcloudapi.com',
        'action': 'DescribeProbeTasks',
        'request_class': 'DescribeProbeTasksRequest',
        'ids': {
            'param': 'probe_task_ids',
            'field': 'TaskIDs',
            'doc': 'Probe task IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'TaskSet',
        'response_total': 'Total',
        'result_key': 'probe_tasks',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CAT probe tasks',
        'description': 'Returns CAT probe tasks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CAT probe tasks.',
        'return_total_doc': 'Number of probe tasks reported by the API.',
        'examples': """\
- name: List all probe tasks
  tencentcloud.cloud.cat_probe_task_info:
    region: ap-guangzhou

- name: Find probe tasks by ID
  tencentcloud.cloud.cat_probe_task_info:
    region: ap-guangzhou
    probe_task_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'ccc_extension_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ccc.v20200210',
        'client_module': 'ccc_client',
        'client_class': 'CccClient',
        'sdk_package': 'tencentcloud-sdk-python-ccc',
        'endpoint': 'ccc.tencentcloudapi.com',
        'action': 'DescribeExtensions',
        'request_class': 'DescribeExtensionsRequest',
        'ids': {
            'param': 'extension_ids',
            'field': 'ExtensionIds',
            'doc': 'Extension IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'ExtensionList',
        'response_total': 'Total',
        'result_key': 'extensions',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud CCC extensions',
        'description': 'Returns CCC extensions visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CCC extensions.',
        'return_total_doc': 'Number of extensions reported by the API.',
        'examples': """\
- name: List all extensions
  tencentcloud.cloud.ccc_extension_info:
    region: ap-guangzhou

- name: Find extensions by ID
  tencentcloud.cloud.ccc_extension_info:
    region: ap-guangzhou
    extension_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cdc_dedicated_cluster_order_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cdc.v20201214',
        'client_module': 'cdc_client',
        'client_class': 'CdcClient',
        'sdk_package': 'tencentcloud-sdk-python-cdc',
        'endpoint': 'cdc.tencentcloudapi.com',
        'action': 'DescribeDedicatedClusterOrders',
        'request_class': 'DescribeDedicatedClusterOrdersRequest',
        'ids': {
            'param': 'dedicated_cluster_order_ids',
            'field': 'DedicatedClusterIds',
            'doc': 'Dedicated cluster order IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'DedicatedClusterOrderSet',
        'response_total': 'TotalCount',
        'result_key': 'dedicated_cluster_orders',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CDC dedicated cluster orders',
        'description': 'Returns CDC dedicated cluster orders visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDC dedicated cluster orders.',
        'return_total_doc': 'Number of dedicated cluster orders reported by the API.',
        'examples': """\
- name: List all dedicated cluster orders
  tencentcloud.cloud.cdc_dedicated_cluster_order_info:
    region: ap-guangzhou

- name: Find dedicated cluster orders by ID
  tencentcloud.cloud.cdc_dedicated_cluster_order_info:
    region: ap-guangzhou
    dedicated_cluster_order_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cds_asset_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cds.v20180420',
        'client_module': 'cds_client',
        'client_class': 'CdsClient',
        'sdk_package': 'tencentcloud-sdk-python-cds',
        'endpoint': 'cds.tencentcloudapi.com',
        'action': 'DescribeAssetsList',
        'request_class': 'DescribeAssetsListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'List',
        'response_total': 'TotalCount',
        'result_key': 'assets',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CDS assets',
        'description': 'Returns CDS assets visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDS assets.',
        'return_total_doc': 'Number of assets reported by the API.',
        'examples': """\
- name: List all assets
  tencentcloud.cloud.cds_asset_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdwch_cn_instance_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cdwch.v20200915',
        'client_module': 'cdwch_client',
        'client_class': 'CdwchClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwch',
        'endpoint': 'cdwch.tencentcloudapi.com',
        'action': 'DescribeCNInstances',
        'request_class': 'DescribeCNInstancesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'InstancesList',
        'response_total': 'TotalCount',
        'result_key': 'cn_instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CDWCH cn instances',
        'description': 'Returns CDWCH cn instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDWCH cn instances.',
        'return_total_doc': 'Number of cn instances reported by the API.',
        'examples': """\
- name: List all cn instances
  tencentcloud.cloud.cdwch_cn_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdwdoris_cluster_configs_history_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cdwdoris.v20211228',
        'client_module': 'cdwdoris_client',
        'client_class': 'CdwdorisClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwdoris',
        'endpoint': 'cdwdoris.tencentcloudapi.com',
        'action': 'DescribeClusterConfigsHistory',
        'request_class': 'DescribeClusterConfigsHistoryRequest',
        'ids': {
            'param': 'cluster_configs_history_ids',
            'field': 'ComputeGroupIds',
            'doc': 'Cluster configs history IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'ClusterConfHistory',
        'response_total': 'TotalCount',
        'result_key': 'cluster_configs_histories',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CDWDORIS cluster configs histories',
        'description': 'Returns CDWDORIS cluster configs histories visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDWDORIS cluster configs histories.',
        'return_total_doc': 'Number of cluster configs histories reported by the API.',
        'examples': """\
- name: List all cluster configs histories
  tencentcloud.cloud.cdwdoris_cluster_configs_history_info:
    region: ap-guangzhou

- name: Find cluster configs histories by ID
  tencentcloud.cloud.cdwdoris_cluster_configs_history_info:
    region: ap-guangzhou
    cluster_configs_history_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cdwpg_account_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cdwpg.v20201230',
        'client_module': 'cdwpg_client',
        'client_class': 'CdwpgClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwpg',
        'endpoint': 'cdwpg.tencentcloudapi.com',
        'action': 'DescribeAccounts',
        'request_class': 'DescribeAccountsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Accounts',
        'response_total': 'TotalCount',
        'result_key': 'accounts',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CDWPG accounts',
        'description': 'Returns CDWPG accounts visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDWPG accounts.',
        'return_total_doc': 'Number of accounts reported by the API.',
        'examples': """\
- name: List all accounts
  tencentcloud.cloud.cdwpg_account_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cetcd_etcd_instance_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cetcd.v20220325',
        'client_module': 'cetcd_client',
        'client_class': 'CetcdClient',
        'sdk_package': 'tencentcloud-sdk-python-cetcd',
        'endpoint': 'cetcd.tencentcloudapi.com',
        'action': 'DescribeEtcdInstances',
        'request_class': 'DescribeEtcdInstancesRequest',
        'ids': {
            'param': 'etcd_instance_ids',
            'field': 'InstanceIds',
            'doc': 'Etcd instance IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'CETCD API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Etcds',
        'response_total': 'TotalCount',
        'result_key': 'etcd_instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CETCD etcd instances',
        'description': 'Returns CETCD etcd instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CETCD etcd instances.',
        'return_total_doc': 'Number of etcd instances reported by the API.',
        'examples': """\
- name: List all etcd instances
  tencentcloud.cloud.cetcd_etcd_instance_info:
    region: ap-guangzhou

- name: Find etcd instances by ID
  tencentcloud.cloud.cetcd_etcd_instance_info:
    region: ap-guangzhou
    etcd_instance_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cfg_action_library_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cfg.v20210820',
        'client_module': 'cfg_client',
        'client_class': 'CfgClient',
        'sdk_package': 'tencentcloud-sdk-python-cfg',
        'endpoint': 'cfg.tencentcloudapi.com',
        'action': 'DescribeActionLibraryList',
        'request_class': 'DescribeActionLibraryListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Results',
        'response_total': 'Total',
        'result_key': 'action_libraries',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CFG action libraries',
        'description': 'Returns CFG action libraries visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CFG action libraries.',
        'return_total_doc': 'Number of action libraries reported by the API.',
        'examples': """\
- name: List all action libraries
  tencentcloud.cloud.cfg_action_library_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cfw_cluster_nat_ccn_fw_switch_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cfw.v20190904',
        'client_module': 'cfw_client',
        'client_class': 'CfwClient',
        'sdk_package': 'tencentcloud-sdk-python-cfw',
        'endpoint': 'cfw.tencentcloudapi.com',
        'action': 'DescribeClusterNatCcnFwSwitchList',
        'request_class': 'DescribeClusterNatCcnFwSwitchListRequest',
        'ids': None,
        'filters': {
            'doc': 'CFW API filter names mapped to lists of values.',
            'model': 'CommonFilter',
        },
        'extra_params': [],
        'response_items': 'Data',
        'response_total': 'Total',
        'result_key': 'cluster_nat_ccn_fw_switches',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CFW cluster nat ccn fw switches',
        'description': 'Returns CFW cluster nat ccn fw switches visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CFW cluster nat ccn fw switches.',
        'return_total_doc': 'Number of cluster nat ccn fw switches reported by the API.',
        'examples': """\
- name: List all cluster nat ccn fw switches
  tencentcloud.cloud.cfw_cluster_nat_ccn_fw_switch_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'chc_device_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.chc.v20230418',
        'client_module': 'chc_client',
        'client_class': 'ChcClient',
        'sdk_package': 'tencentcloud-sdk-python-chc',
        'endpoint': 'chc.tencentcloudapi.com',
        'action': 'DescribeDeviceList',
        'request_class': 'DescribeDeviceListRequest',
        'ids': None,
        'filters': {
            'doc': 'CHC API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'DeviceSet',
        'response_total': 'Total',
        'result_key': 'devices',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CHC devices',
        'description': 'Returns CHC devices visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CHC devices.',
        'return_total_doc': 'Number of devices reported by the API.',
        'examples': """\
- name: List all devices
  tencentcloud.cloud.chc_device_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cloudhsm_vsm_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cloudhsm.v20191112',
        'client_module': 'cloudhsm_client',
        'client_class': 'CloudhsmClient',
        'sdk_package': 'tencentcloud-sdk-python-cloudhsm',
        'endpoint': 'cloudhsm.tencentcloudapi.com',
        'action': 'DescribeVsms',
        'request_class': 'DescribeVsmsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'VsmList',
        'response_total': 'TotalCount',
        'result_key': 'vsms',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CLOUDHSM vsms',
        'description': 'Returns CLOUDHSM vsms visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CLOUDHSM vsms.',
        'return_total_doc': 'Number of vsms reported by the API.',
        'examples': """\
- name: List all vsms
  tencentcloud.cloud.cloudhsm_vsm_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cme_platform_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cme.v20191029',
        'client_module': 'cme_client',
        'client_class': 'CmeClient',
        'sdk_package': 'tencentcloud-sdk-python-cme',
        'endpoint': 'cme.tencentcloudapi.com',
        'action': 'DescribePlatforms',
        'request_class': 'DescribePlatformsRequest',
        'ids': {
            'param': 'platform_ids',
            'field': 'LicenseIds',
            'doc': 'Platform IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'PlatformInfoSet',
        'response_total': 'TotalCount',
        'result_key': 'platforms',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CME platforms',
        'description': 'Returns CME platforms visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CME platforms.',
        'return_total_doc': 'Number of platforms reported by the API.',
        'examples': """\
- name: List all platforms
  tencentcloud.cloud.cme_platform_info:
    region: ap-guangzhou

- name: Find platforms by ID
  tencentcloud.cloud.cme_platform_info:
    region: ap-guangzhou
    platform_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cmq_queue_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cmq.v20190304',
        'client_module': 'cmq_client',
        'client_class': 'CmqClient',
        'sdk_package': 'tencentcloud-sdk-python-cmq',
        'endpoint': 'cmq.tencentcloudapi.com',
        'action': 'DescribeQueueDetail',
        'request_class': 'DescribeQueueDetailRequest',
        'ids': None,
        'filters': {
            'doc': 'CMQ API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'QueueSet',
        'response_total': 'TotalCount',
        'result_key': 'queues',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CMQ queues',
        'description': 'Returns CMQ queues visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CMQ queues.',
        'return_total_doc': 'Number of queues reported by the API.',
        'examples': """\
- name: List all queues
  tencentcloud.cloud.cmq_queue_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cms_lib_sample_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cms.v20190321',
        'client_module': 'cms_client',
        'client_class': 'CmsClient',
        'sdk_package': 'tencentcloud-sdk-python-cms',
        'endpoint': 'cms.tencentcloudapi.com',
        'action': 'DescribeLibSamples',
        'request_class': 'DescribeLibSamplesRequest',
        'ids': {
            'param': 'lib_sample_ids',
            'field': 'SampleIDs',
            'doc': 'Lib sample IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Infos',
        'response_total': 'TotalCount',
        'result_key': 'lib_samples',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CMS lib samples',
        'description': 'Returns CMS lib samples visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CMS lib samples.',
        'return_total_doc': 'Number of lib samples reported by the API.',
        'examples': """\
- name: List all lib samples
  tencentcloud.cloud.cms_lib_sample_info:
    region: ap-guangzhou

- name: Find lib samples by ID
  tencentcloud.cloud.cms_lib_sample_info:
    region: ap-guangzhou
    lib_sample_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cngw_cloud_native_api_gateway_llm_model_api_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cngw.v20230418',
        'client_module': 'cngw_client',
        'client_class': 'CngwClient',
        'sdk_package': 'tencentcloud-sdk-python-cngw',
        'endpoint': 'cngw.tencentcloudapi.com',
        'action': 'DescribeCloudNativeAPIGatewayLLMModelAPIs',
        'request_class': 'DescribeCloudNativeAPIGatewayLLMModelAPIsRequest',
        'ids': None,
        'filters': {
            'doc': 'CNGW API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Result.DataList',
        'response_total': 'Result.TotalCount',
        'result_key': 'cloud_native_api_gateway_llm_model_apis',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CNGW cloud native api gateway llm model apis',
        'description': 'Returns CNGW cloud native api gateway llm model apis visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CNGW cloud native api gateway llm model apis.',
        'return_total_doc': 'Number of cloud native api gateway llm model apis reported by the API.',
        'examples': """\
- name: List all cloud native api gateway llm model apis
  tencentcloud.cloud.cngw_cloud_native_api_gateway_llm_model_api_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'config_aggregate_compliance_pack_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.config.v20220802',
        'client_module': 'config_client',
        'client_class': 'ConfigClient',
        'sdk_package': 'tencentcloud-sdk-python-config',
        'endpoint': 'config.tencentcloudapi.com',
        'action': 'ListAggregateCompliancePacks',
        'request_class': 'ListAggregateCompliancePacksRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Items',
        'response_total': 'Total',
        'result_key': 'aggregate_compliance_packs',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CONFIG aggregate compliance packs',
        'description': 'Returns CONFIG aggregate compliance packs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CONFIG aggregate compliance packs.',
        'return_total_doc': 'Number of aggregate compliance packs reported by the API.',
        'examples': """\
- name: List all aggregate compliance packs
  tencentcloud.cloud.config_aggregate_compliance_pack_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'controlcenter_account_factory_baseline_item_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.controlcenter.v20230110',
        'client_module': 'controlcenter_client',
        'client_class': 'ControlcenterClient',
        'sdk_package': 'tencentcloud-sdk-python-controlcenter',
        'endpoint': 'controlcenter.tencentcloudapi.com',
        'action': 'ListAccountFactoryBaselineItems',
        'request_class': 'ListAccountFactoryBaselineItemsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'BaselineItems',
        'response_total': 'Total',
        'result_key': 'account_factory_baseline_items',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CONTROLCENTER account factory baseline items',
        'description': 'Returns CONTROLCENTER account factory baseline items visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CONTROLCENTER account factory baseline items.',
        'return_total_doc': 'Number of account factory baseline items reported by the API.',
        'examples': """\
- name: List all account factory baseline items
  tencentcloud.cloud.controlcenter_account_factory_baseline_item_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'csip_asset_process_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.csip.v20221121',
        'client_module': 'csip_client',
        'client_class': 'CsipClient',
        'sdk_package': 'tencentcloud-sdk-python-csip',
        'endpoint': 'csip.tencentcloudapi.com',
        'action': 'DescribeAssetProcessList',
        'request_class': 'DescribeAssetProcessListRequest',
        'ids': None,
        'filters': {
            'doc': 'CSIP API filter names mapped to lists of values.',
            'model': 'Filters',
        },
        'extra_params': [],
        'response_items': 'AssetProcessList',
        'response_total': 'TotalCount',
        'result_key': 'asset_processes',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CSIP asset processes',
        'description': 'Returns CSIP asset processes visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CSIP asset processes.',
        'return_total_doc': 'Number of asset processes reported by the API.',
        'examples': """\
- name: List all asset processes
  tencentcloud.cloud.csip_asset_process_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ctem_api_sec_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ctem.v20231128',
        'client_module': 'ctem_client',
        'client_class': 'CtemClient',
        'sdk_package': 'tencentcloud-sdk-python-ctem',
        'endpoint': 'ctem.tencentcloudapi.com',
        'action': 'DescribeApiSecs',
        'request_class': 'DescribeApiSecsRequest',
        'ids': {
            'param': 'api_sec_ids',
            'field': 'EnterpriseUidList',
            'doc': 'Api sec IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'CTEM API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'List',
        'response_total': 'Total',
        'result_key': 'api_secs',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CTEM api secs',
        'description': 'Returns CTEM api secs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CTEM api secs.',
        'return_total_doc': 'Number of api secs reported by the API.',
        'examples': """\
- name: List all api secs
  tencentcloud.cloud.ctem_api_sec_info:
    region: ap-guangzhou

- name: Find api secs by ID
  tencentcloud.cloud.ctem_api_sec_info:
    region: ap-guangzhou
    api_sec_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'ctsdb_cluster_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ctsdb.v20230202',
        'client_module': 'ctsdb_client',
        'client_class': 'CtsdbClient',
        'sdk_package': 'tencentcloud-sdk-python-ctsdb',
        'endpoint': 'ctsdb.tencentcloudapi.com',
        'action': 'DescribeClusters',
        'request_class': 'DescribeClustersRequest',
        'ids': None,
        'filters': {
            'doc': 'CTSDB API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Clusters',
        'response_total': 'TotalCount',
        'result_key': 'clusters',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud CTSDB clusters',
        'description': 'Returns CTSDB clusters visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CTSDB clusters.',
        'return_total_doc': 'Number of clusters reported by the API.',
        'examples': """\
- name: List all clusters
  tencentcloud.cloud.ctsdb_cluster_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cws_monitor_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.cws.v20180312',
        'client_module': 'cws_client',
        'client_class': 'CwsClient',
        'sdk_package': 'tencentcloud-sdk-python-cws',
        'endpoint': 'cws.tencentcloudapi.com',
        'action': 'DescribeMonitors',
        'request_class': 'DescribeMonitorsRequest',
        'ids': None,
        'filters': {
            'doc': 'CWS API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Monitors',
        'response_total': 'TotalCount',
        'result_key': 'monitors',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CWS monitors',
        'description': 'Returns CWS monitors visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CWS monitors.',
        'return_total_doc': 'Number of monitors reported by the API.',
        'examples': """\
- name: List all monitors
  tencentcloud.cloud.cws_monitor_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'dasb_device_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.dasb.v20191018',
        'client_module': 'dasb_client',
        'client_class': 'DasbClient',
        'sdk_package': 'tencentcloud-sdk-python-dasb',
        'endpoint': 'dasb.tencentcloudapi.com',
        'action': 'DescribeDevices',
        'request_class': 'DescribeDevicesRequest',
        'ids': {
            'param': 'device_ids',
            'field': 'ResourceIdSet',
            'doc': 'Device IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'DASB API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'DeviceSet',
        'response_total': 'TotalCount',
        'result_key': 'devices',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DASB devices',
        'description': 'Returns DASB devices visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DASB devices.',
        'return_total_doc': 'Number of devices reported by the API.',
        'examples': """\
- name: List all devices
  tencentcloud.cloud.dasb_device_info:
    region: ap-guangzhou

- name: Find devices by ID
  tencentcloud.cloud.dasb_device_info:
    region: ap-guangzhou
    device_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'dayu_resource_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.dayu.v20180709',
        'client_module': 'dayu_client',
        'client_class': 'DayuClient',
        'sdk_package': 'tencentcloud-sdk-python-dayu',
        'endpoint': 'dayu.tencentcloudapi.com',
        'action': 'DescribeResourceList',
        'request_class': 'DescribeResourceListRequest',
        'ids': {
            'param': 'resource_ids',
            'field': 'IdList',
            'doc': 'Resource IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'ServicePacks',
        'response_total': 'Total',
        'result_key': 'resources',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DAYU resources',
        'description': 'Returns DAYU resources visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DAYU resources.',
        'return_total_doc': 'Number of resources reported by the API.',
        'examples': """\
- name: List all resources
  tencentcloud.cloud.dayu_resource_info:
    region: ap-guangzhou

- name: Find resources by ID
  tencentcloud.cloud.dayu_resource_info:
    region: ap-guangzhou
    resource_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'dbbrain_db_diag_event_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.dbbrain.v20210527',
        'client_module': 'dbbrain_client',
        'client_class': 'DbbrainClient',
        'sdk_package': 'tencentcloud-sdk-python-dbbrain',
        'endpoint': 'dbbrain.tencentcloudapi.com',
        'action': 'DescribeDBDiagEvents',
        'request_class': 'DescribeDBDiagEventsRequest',
        'ids': {
            'param': 'db_diag_event_ids',
            'field': 'InstanceIds',
            'doc': 'Db diag event IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Items',
        'response_total': 'TotalCount',
        'result_key': 'db_diag_events',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DBBRAIN db diag events',
        'description': 'Returns DBBRAIN db diag events visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DBBRAIN db diag events.',
        'return_total_doc': 'Number of db diag events reported by the API.',
        'examples': """\
- name: List all db diag events
  tencentcloud.cloud.dbbrain_db_diag_event_info:
    region: ap-guangzhou

- name: Find db diag events by ID
  tencentcloud.cloud.dbbrain_db_diag_event_info:
    region: ap-guangzhou
    db_diag_event_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'dbdc_db_custom_cluster_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.dbdc.v20201029',
        'client_module': 'dbdc_client',
        'client_class': 'DbdcClient',
        'sdk_package': 'tencentcloud-sdk-python-dbdc',
        'endpoint': 'dbdc.tencentcloudapi.com',
        'action': 'DescribeDBCustomClusters',
        'request_class': 'DescribeDBCustomClustersRequest',
        'ids': {
            'param': 'db_custom_cluster_ids',
            'field': 'ClusterIds',
            'doc': 'Db custom cluster IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'DBDC API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'ClusterSet',
        'response_total': 'TotalCount',
        'result_key': 'db_custom_clusters',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DBDC db custom clusters',
        'description': 'Returns DBDC db custom clusters visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DBDC db custom clusters.',
        'return_total_doc': 'Number of db custom clusters reported by the API.',
        'examples': """\
- name: List all db custom clusters
  tencentcloud.cloud.dbdc_db_custom_cluster_info:
    region: ap-guangzhou

- name: Find db custom clusters by ID
  tencentcloud.cloud.dbdc_db_custom_cluster_info:
    region: ap-guangzhou
    db_custom_cluster_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'dbs_backup_plan_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.dbs.v20211108',
        'client_module': 'dbs_client',
        'client_class': 'DbsClient',
        'sdk_package': 'tencentcloud-sdk-python-dbs',
        'endpoint': 'dbs.tencentcloudapi.com',
        'action': 'DescribeBackupPlans',
        'request_class': 'DescribeBackupPlansRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Items',
        'response_total': 'TotalCount',
        'result_key': 'backup_plans',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DBS backup plans',
        'description': 'Returns DBS backup plans visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DBS backup plans.',
        'return_total_doc': 'Number of backup plans reported by the API.',
        'examples': """\
- name: List all backup plans
  tencentcloud.cloud.dbs_backup_plan_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'dc_direct_connect_tunnel_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.dc.v20180410',
        'client_module': 'dc_client',
        'client_class': 'DcClient',
        'sdk_package': 'tencentcloud-sdk-python-dc',
        'endpoint': 'dc.tencentcloudapi.com',
        'action': 'DescribeDirectConnectTunnels',
        'request_class': 'DescribeDirectConnectTunnelsRequest',
        'ids': {
            'param': 'direct_connect_tunnel_ids',
            'field': 'DirectConnectTunnelIds',
            'doc': 'Direct connect tunnel IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'DC API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'DirectConnectTunnelSet',
        'response_total': 'TotalCount',
        'result_key': 'direct_connect_tunnels',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DC direct connect tunnels',
        'description': 'Returns DC direct connect tunnels visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DC direct connect tunnels.',
        'return_total_doc': 'Number of direct connect tunnels reported by the API.',
        'examples': """\
- name: List all direct connect tunnels
  tencentcloud.cloud.dc_direct_connect_tunnel_info:
    region: ap-guangzhou

- name: Find direct connect tunnels by ID
  tencentcloud.cloud.dc_direct_connect_tunnel_info:
    region: ap-guangzhou
    direct_connect_tunnel_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'dcdb_dcdb_instance_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.dcdb.v20180411',
        'client_module': 'dcdb_client',
        'client_class': 'DcdbClient',
        'sdk_package': 'tencentcloud-sdk-python-dcdb',
        'endpoint': 'dcdb.tencentcloudapi.com',
        'action': 'DescribeDCDBInstances',
        'request_class': 'DescribeDCDBInstancesRequest',
        'ids': {
            'param': 'dcdb_instance_ids',
            'field': 'InstanceIds',
            'doc': 'Dcdb instance IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Instances',
        'response_total': 'TotalCount',
        'result_key': 'dcdb_instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DCDB dcdb instances',
        'description': 'Returns DCDB dcdb instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DCDB dcdb instances.',
        'return_total_doc': 'Number of dcdb instances reported by the API.',
        'examples': """\
- name: List all dcdb instances
  tencentcloud.cloud.dcdb_dcdb_instance_info:
    region: ap-guangzhou

- name: Find dcdb instances by ID
  tencentcloud.cloud.dcdb_dcdb_instance_info:
    region: ap-guangzhou
    dcdb_instance_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'dlc_task_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.dlc.v20210125',
        'client_module': 'dlc_client',
        'client_class': 'DlcClient',
        'sdk_package': 'tencentcloud-sdk-python-dlc',
        'endpoint': 'dlc.tencentcloudapi.com',
        'action': 'DescribeTaskList',
        'request_class': 'DescribeTaskListRequest',
        'ids': {
            'param': 'task_ids',
            'field': 'HouseIds',
            'doc': 'Task IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'DLC API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'TaskList',
        'response_total': 'TotalCount',
        'result_key': 'tasks',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DLC tasks',
        'description': 'Returns DLC tasks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DLC tasks.',
        'return_total_doc': 'Number of tasks reported by the API.',
        'examples': """\
- name: List all tasks
  tencentcloud.cloud.dlc_task_info:
    region: ap-guangzhou

- name: Find tasks by ID
  tencentcloud.cloud.dlc_task_info:
    region: ap-guangzhou
    task_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'domain_batch_operation_log_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.domain.v20180808',
        'client_module': 'domain_client',
        'client_class': 'DomainClient',
        'sdk_package': 'tencentcloud-sdk-python-domain',
        'endpoint': 'domain.tencentcloudapi.com',
        'action': 'DescribeBatchOperationLogDetails',
        'request_class': 'DescribeBatchOperationLogDetailsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'DomainBatchDetailSet',
        'response_total': 'TotalCount',
        'result_key': 'batch_operation_logs',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DOMAIN batch operation logs',
        'description': 'Returns DOMAIN batch operation logs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DOMAIN batch operation logs.',
        'return_total_doc': 'Number of batch operation logs reported by the API.',
        'examples': """\
- name: List all batch operation logs
  tencentcloud.cloud.domain_batch_operation_log_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'dsgc_dspa_assessment_risk_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.dsgc.v20190723',
        'client_module': 'dsgc_client',
        'client_class': 'DsgcClient',
        'sdk_package': 'tencentcloud-sdk-python-dsgc',
        'endpoint': 'dsgc.tencentcloudapi.com',
        'action': 'DescribeDSPAAssessmentRisks',
        'request_class': 'DescribeDSPAAssessmentRisksRequest',
        'ids': None,
        'filters': {
            'doc': 'DSGC API filter names mapped to lists of values.',
            'model': 'DspaAssessmentFilter',
        },
        'extra_params': [],
        'response_items': 'Items',
        'response_total': 'TotalCount',
        'result_key': 'dspa_assessment_risks',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DSGC dspa assessment risks',
        'description': 'Returns DSGC dspa assessment risks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DSGC dspa assessment risks.',
        'return_total_doc': 'Number of dspa assessment risks reported by the API.',
        'examples': """\
- name: List all dspa assessment risks
  tencentcloud.cloud.dsgc_dspa_assessment_risk_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'dts_subscribe_job_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.dts.v20211206',
        'client_module': 'dts_client',
        'client_class': 'DtsClient',
        'sdk_package': 'tencentcloud-sdk-python-dts',
        'endpoint': 'dts.tencentcloudapi.com',
        'action': 'DescribeSubscribeJobs',
        'request_class': 'DescribeSubscribeJobsRequest',
        'ids': {
            'param': 'subscribe_job_ids',
            'field': 'SubscribeIds',
            'doc': 'Subscribe job IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Items',
        'response_total': 'TotalCount',
        'result_key': 'subscribe_jobs',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DTS subscribe jobs',
        'description': 'Returns DTS subscribe jobs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DTS subscribe jobs.',
        'return_total_doc': 'Number of subscribe jobs reported by the API.',
        'examples': """\
- name: List all subscribe jobs
  tencentcloud.cloud.dts_subscribe_job_info:
    region: ap-guangzhou

- name: Find subscribe jobs by ID
  tencentcloud.cloud.dts_subscribe_job_info:
    region: ap-guangzhou
    subscribe_job_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'eb_event_bus_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.eb.v20210416',
        'client_module': 'eb_client',
        'client_class': 'EbClient',
        'sdk_package': 'tencentcloud-sdk-python-eb',
        'endpoint': 'eb.tencentcloudapi.com',
        'action': 'ListEventBuses',
        'request_class': 'ListEventBusesRequest',
        'ids': None,
        'filters': {
            'doc': 'EB API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'EventBuses',
        'response_total': 'TotalCount',
        'result_key': 'event_buses',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud EB event buses',
        'description': 'Returns EB event buses visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching EB event buses.',
        'return_total_doc': 'Number of event buses reported by the API.',
        'examples': """\
- name: List all event buses
  tencentcloud.cloud.eb_event_bus_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ecdn_domain_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ecdn.v20191012',
        'client_module': 'ecdn_client',
        'client_class': 'EcdnClient',
        'sdk_package': 'tencentcloud-sdk-python-ecdn',
        'endpoint': 'ecdn.tencentcloudapi.com',
        'action': 'DescribeDomains',
        'request_class': 'DescribeDomainsRequest',
        'ids': None,
        'filters': {
            'doc': 'ECDN API filter names mapped to lists of values.',
            'model': 'DomainFilter',
            'value_field': 'Value',
        },
        'extra_params': [],
        'response_items': 'Domains',
        'response_total': 'TotalCount',
        'result_key': 'domains',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud ECDN domains',
        'description': 'Returns ECDN domains visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ECDN domains.',
        'return_total_doc': 'Number of domains reported by the API.',
        'examples': """\
- name: List all domains
  tencentcloud.cloud.ecdn_domain_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ecm_address_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ecm.v20190719',
        'client_module': 'ecm_client',
        'client_class': 'EcmClient',
        'sdk_package': 'tencentcloud-sdk-python-ecm',
        'endpoint': 'ecm.tencentcloudapi.com',
        'action': 'DescribeAddresses',
        'request_class': 'DescribeAddressesRequest',
        'ids': {
            'param': 'address_ids',
            'field': 'AddressIds',
            'doc': 'Address IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'ECM API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'AddressSet',
        'response_total': 'TotalCount',
        'result_key': 'addresses',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud ECM addresses',
        'description': 'Returns ECM addresses visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ECM addresses.',
        'return_total_doc': 'Number of addresses reported by the API.',
        'examples': """\
- name: List all addresses
  tencentcloud.cloud.ecm_address_info:
    region: ap-guangzhou

- name: Find addresses by ID
  tencentcloud.cloud.ecm_address_info:
    region: ap-guangzhou
    address_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'eiam_application_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.eiam.v20210420',
        'client_module': 'eiam_client',
        'client_class': 'EiamClient',
        'sdk_package': 'tencentcloud-sdk-python-eiam',
        'endpoint': 'eiam.tencentcloudapi.com',
        'action': 'ListApplications',
        'request_class': 'ListApplicationsRequest',
        'ids': {
            'param': 'application_ids',
            'field': 'ApplicationIdList',
            'doc': 'Application IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'ApplicationInfoList',
        'response_total': 'TotalCount',
        'result_key': 'applications',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud EIAM applications',
        'description': 'Returns EIAM applications visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching EIAM applications.',
        'return_total_doc': 'Number of applications reported by the API.',
        'examples': """\
- name: List all applications
  tencentcloud.cloud.eiam_application_info:
    region: ap-guangzhou

- name: Find applications by ID
  tencentcloud.cloud.eiam_application_info:
    region: ap-guangzhou
    application_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'eis_runtime_deployed_instances_mc_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.eis.v20210601',
        'client_module': 'eis_client',
        'client_class': 'EisClient',
        'sdk_package': 'tencentcloud-sdk-python-eis',
        'endpoint': 'eis.tencentcloudapi.com',
        'action': 'ListRuntimeDeployedInstancesMC',
        'request_class': 'ListRuntimeDeployedInstancesMCRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Instances',
        'response_total': 'TotalCount',
        'result_key': 'runtime_deployed_instances_mcs',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud EIS runtime deployed instances mcs',
        'description': 'Returns EIS runtime deployed instances mcs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching EIS runtime deployed instances mcs.',
        'return_total_doc': 'Number of runtime deployed instances mcs reported by the API.',
        'examples': """\
- name: List all runtime deployed instances mcs
  tencentcloud.cloud.eis_runtime_deployed_instances_mc_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'emr_node_data_disk_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.emr.v20190103',
        'client_module': 'emr_client',
        'client_class': 'EmrClient',
        'sdk_package': 'tencentcloud-sdk-python-emr',
        'endpoint': 'emr.tencentcloudapi.com',
        'action': 'DescribeNodeDataDisks',
        'request_class': 'DescribeNodeDataDisksRequest',
        'ids': {
            'param': 'node_data_disk_ids',
            'field': 'CvmInstanceIds',
            'doc': 'Node data disk IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'EMR API filter names mapped to lists of values.',
            'model': 'Filters',
        },
        'extra_params': [],
        'response_items': 'CBSList',
        'response_total': 'TotalCount',
        'result_key': 'node_data_disks',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud EMR node data disks',
        'description': 'Returns EMR node data disks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching EMR node data disks.',
        'return_total_doc': 'Number of node data disks reported by the API.',
        'examples': """\
- name: List all node data disks
  tencentcloud.cloud.emr_node_data_disk_info:
    region: ap-guangzhou

- name: Find node data disks by ID
  tencentcloud.cloud.emr_node_data_disk_info:
    region: ap-guangzhou
    node_data_disk_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'ess_file_url_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ess.v20201111',
        'client_module': 'ess_client',
        'client_class': 'EssClient',
        'sdk_package': 'tencentcloud-sdk-python-ess',
        'endpoint': 'ess.tencentcloudapi.com',
        'action': 'DescribeFileUrls',
        'request_class': 'DescribeFileUrlsRequest',
        'ids': {
            'param': 'file_url_ids',
            'field': 'BusinessIds',
            'doc': 'File url IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'FileUrls',
        'response_total': 'TotalCount',
        'result_key': 'file_urls',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud ESS file urls',
        'description': 'Returns ESS file urls visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ESS file urls.',
        'return_total_doc': 'Number of file urls reported by the API.',
        'examples': """\
- name: List all file urls
  tencentcloud.cloud.ess_file_url_info:
    region: ap-guangzhou

- name: Find file urls by ID
  tencentcloud.cloud.ess_file_url_info:
    region: ap-guangzhou
    file_url_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'essbasic_template_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.essbasic.v20210526',
        'client_module': 'essbasic_client',
        'client_class': 'EssbasicClient',
        'sdk_package': 'tencentcloud-sdk-python-essbasic',
        'endpoint': 'essbasic.tencentcloudapi.com',
        'action': 'DescribeTemplates',
        'request_class': 'DescribeTemplatesRequest',
        'ids': {
            'param': 'template_ids',
            'field': 'TemplateIds',
            'doc': 'Template IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Templates',
        'response_total': 'TotalCount',
        'result_key': 'templates',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud ESSBASIC templates',
        'description': 'Returns ESSBASIC templates visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ESSBASIC templates.',
        'return_total_doc': 'Number of templates reported by the API.',
        'examples': """\
- name: List all templates
  tencentcloud.cloud.essbasic_template_info:
    region: ap-guangzhou

- name: Find templates by ID
  tencentcloud.cloud.essbasic_template_info:
    region: ap-guangzhou
    template_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'fwm_edge_acl_rule_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.fwm.v20250611',
        'client_module': 'fwm_client',
        'client_class': 'FwmClient',
        'sdk_package': 'tencentcloud-sdk-python-fwm',
        'endpoint': 'fwm.tencentcloudapi.com',
        'action': 'DescribeEdgeAclRules',
        'request_class': 'DescribeEdgeAclRulesRequest',
        'ids': None,
        'filters': {
            'doc': 'FWM API filter names mapped to lists of values.',
            'model': 'CommonFilter',
        },
        'extra_params': [],
        'response_items': 'Rules',
        'response_total': 'TotalCount',
        'result_key': 'edge_acl_rules',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud FWM edge acl rules',
        'description': 'Returns FWM edge acl rules visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching FWM edge acl rules.',
        'return_total_doc': 'Number of edge acl rules reported by the API.',
        'examples': """\
- name: List all edge acl rules
  tencentcloud.cloud.fwm_edge_acl_rule_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ga2_accelerate_area_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ga2.v20250115',
        'client_module': 'ga2_client',
        'client_class': 'Ga2Client',
        'sdk_package': 'tencentcloud-sdk-python-ga2',
        'endpoint': 'ga2.tencentcloudapi.com',
        'action': 'DescribeAccelerateAreas',
        'request_class': 'DescribeAccelerateAreasRequest',
        'ids': None,
        'filters': {
            'doc': 'GA2 API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'AccelerateAreaSet',
        'response_total': 'TotalCount',
        'result_key': 'accelerate_areas',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud GA2 accelerate areas',
        'description': 'Returns GA2 accelerate areas visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching GA2 accelerate areas.',
        'return_total_doc': 'Number of accelerate areas reported by the API.',
        'examples': """\
- name: List all accelerate areas
  tencentcloud.cloud.ga2_accelerate_area_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'goosefs_file_system_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.goosefs.v20220519',
        'client_module': 'goosefs_client',
        'client_class': 'GoosefsClient',
        'sdk_package': 'tencentcloud-sdk-python-goosefs',
        'endpoint': 'goosefs.tencentcloudapi.com',
        'action': 'DescribeFileSystems',
        'request_class': 'DescribeFileSystemsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'FSAttributeList',
        'response_total': 'TotalCount',
        'result_key': 'file_systems',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud GOOSEFS file systems',
        'description': 'Returns GOOSEFS file systems visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching GOOSEFS file systems.',
        'return_total_doc': 'Number of file systems reported by the API.',
        'examples': """\
- name: List all file systems
  tencentcloud.cloud.goosefs_file_system_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'gs_android_app_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.gs.v20191118',
        'client_module': 'gs_client',
        'client_class': 'GsClient',
        'sdk_package': 'tencentcloud-sdk-python-gs',
        'endpoint': 'gs.tencentcloudapi.com',
        'action': 'DescribeAndroidApps',
        'request_class': 'DescribeAndroidAppsRequest',
        'ids': {
            'param': 'android_app_ids',
            'field': 'AndroidAppIds',
            'doc': 'Android app IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'GS API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Apps',
        'response_total': 'TotalCount',
        'result_key': 'android_apps',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud GS android apps',
        'description': 'Returns GS android apps visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching GS android apps.',
        'return_total_doc': 'Number of android apps reported by the API.',
        'examples': """\
- name: List all android apps
  tencentcloud.cloud.gs_android_app_info:
    region: ap-guangzhou

- name: Find android apps by ID
  tencentcloud.cloud.gs_android_app_info:
    region: ap-guangzhou
    android_app_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'gwlb_gateway_load_balancer_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.gwlb.v20240906',
        'client_module': 'gwlb_client',
        'client_class': 'GwlbClient',
        'sdk_package': 'tencentcloud-sdk-python-gwlb',
        'endpoint': 'gwlb.tencentcloudapi.com',
        'action': 'DescribeGatewayLoadBalancers',
        'request_class': 'DescribeGatewayLoadBalancersRequest',
        'ids': {
            'param': 'gateway_load_balancer_ids',
            'field': 'LoadBalancerIds',
            'doc': 'Gateway load balancer IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'GWLB API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'LoadBalancerSet',
        'response_total': 'TotalCount',
        'result_key': 'gateway_load_balancers',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud GWLB gateway load balancers',
        'description': 'Returns GWLB gateway load balancers visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching GWLB gateway load balancers.',
        'return_total_doc': 'Number of gateway load balancers reported by the API.',
        'examples': """\
- name: List all gateway load balancers
  tencentcloud.cloud.gwlb_gateway_load_balancer_info:
    region: ap-guangzhou

- name: Find gateway load balancers by ID
  tencentcloud.cloud.gwlb_gateway_load_balancer_info:
    region: ap-guangzhou
    gateway_load_balancer_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'hai_application_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.hai.v20230812',
        'client_module': 'hai_client',
        'client_class': 'HaiClient',
        'sdk_package': 'tencentcloud-sdk-python-hai',
        'endpoint': 'hai.tencentcloudapi.com',
        'action': 'DescribeApplications',
        'request_class': 'DescribeApplicationsRequest',
        'ids': {
            'param': 'application_ids',
            'field': 'ApplicationIds',
            'doc': 'Application IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'HAI API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'ApplicationSet',
        'response_total': 'TotalCount',
        'result_key': 'applications',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud HAI applications',
        'description': 'Returns HAI applications visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching HAI applications.',
        'return_total_doc': 'Number of applications reported by the API.',
        'examples': """\
- name: List all applications
  tencentcloud.cloud.hai_application_info:
    region: ap-guangzhou

- name: Find applications by ID
  tencentcloud.cloud.hai_application_info:
    region: ap-guangzhou
    application_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'hasim_link_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.hasim.v20210716',
        'client_module': 'hasim_client',
        'client_class': 'HasimClient',
        'sdk_package': 'tencentcloud-sdk-python-hasim',
        'endpoint': 'hasim.tencentcloudapi.com',
        'action': 'DescribeLinks',
        'request_class': 'DescribeLinksRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Data.List',
        'response_total': 'Data.Total',
        'result_key': 'links',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud HASIM links',
        'description': 'Returns HASIM links visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching HASIM links.',
        'return_total_doc': 'Number of links reported by the API.',
        'examples': """\
- name: List all links
  tencentcloud.cloud.hasim_link_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ic_sms_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ic.v20190307',
        'client_module': 'ic_client',
        'client_class': 'IcClient',
        'sdk_package': 'tencentcloud-sdk-python-ic',
        'endpoint': 'ic.tencentcloudapi.com',
        'action': 'DescribeSms',
        'request_class': 'DescribeSmsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'List',
        'response_total': 'Total',
        'result_key': 'smses',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud IC smses',
        'description': 'Returns IC smses visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching IC smses.',
        'return_total_doc': 'Number of smses reported by the API.',
        'examples': """\
- name: List all smses
  tencentcloud.cloud.ic_sms_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'igtm_address_pool_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.igtm.v20231024',
        'client_module': 'igtm_client',
        'client_class': 'IgtmClient',
        'sdk_package': 'tencentcloud-sdk-python-igtm',
        'endpoint': 'igtm.tencentcloudapi.com',
        'action': 'DescribeAddressPoolList',
        'request_class': 'DescribeAddressPoolListRequest',
        'ids': None,
        'filters': {
            'doc': 'IGTM API filter names mapped to lists of values.',
            'model': 'ResourceFilter',
            'value_field': 'Value',
        },
        'extra_params': [],
        'response_items': 'AddressPoolSet',
        'response_total': 'TotalCount',
        'result_key': 'address_pools',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud IGTM address pools',
        'description': 'Returns IGTM address pools visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching IGTM address pools.',
        'return_total_doc': 'Number of address pools reported by the API.',
        'examples': """\
- name: List all address pools
  tencentcloud.cloud.igtm_address_pool_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'iotcloud_device_resource_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.iotcloud.v20210408',
        'client_module': 'iotcloud_client',
        'client_class': 'IotcloudClient',
        'sdk_package': 'tencentcloud-sdk-python-iotcloud',
        'endpoint': 'iotcloud.tencentcloudapi.com',
        'action': 'DescribeDeviceResources',
        'request_class': 'DescribeDeviceResourcesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Result',
        'response_total': 'TotalCount',
        'result_key': 'device_resources',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud IOTCLOUD device resources',
        'description': 'Returns IOTCLOUD device resources visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching IOTCLOUD device resources.',
        'return_total_doc': 'Number of device resources reported by the API.',
        'examples': """\
- name: List all device resources
  tencentcloud.cloud.iotcloud_device_resource_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'iotexplorer_device_position_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.iotexplorer.v20190423',
        'client_module': 'iotexplorer_client',
        'client_class': 'IotexplorerClient',
        'sdk_package': 'tencentcloud-sdk-python-iotexplorer',
        'endpoint': 'iotexplorer.tencentcloudapi.com',
        'action': 'DescribeDevicePositionList',
        'request_class': 'DescribeDevicePositionListRequest',
        'ids': {
            'param': 'device_position_ids',
            'field': 'ProductIdList',
            'doc': 'Device position IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Positions',
        'response_total': 'Total',
        'result_key': 'device_positions',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud IOTEXPLORER device positions',
        'description': 'Returns IOTEXPLORER device positions visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching IOTEXPLORER device positions.',
        'return_total_doc': 'Number of device positions reported by the API.',
        'examples': """\
- name: List all device positions
  tencentcloud.cloud.iotexplorer_device_position_info:
    region: ap-guangzhou

- name: Find device positions by ID
  tencentcloud.cloud.iotexplorer_device_position_info:
    region: ap-guangzhou
    device_position_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'iotvideo_ai_model_application_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.iotvideo.v20211125',
        'client_module': 'iotvideo_client',
        'client_class': 'IotvideoClient',
        'sdk_package': 'tencentcloud-sdk-python-iotvideo',
        'endpoint': 'iotvideo.tencentcloudapi.com',
        'action': 'DescribeAIModelApplications',
        'request_class': 'DescribeAIModelApplicationsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Applications',
        'response_total': 'TotalCount',
        'result_key': 'ai_model_applications',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud IOTVIDEO ai model applications',
        'description': 'Returns IOTVIDEO ai model applications visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching IOTVIDEO ai model applications.',
        'return_total_doc': 'Number of ai model applications reported by the API.',
        'examples': """\
- name: List all ai model applications
  tencentcloud.cloud.iotvideo_ai_model_application_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'iotvideoindustry_all_device_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.iotvideoindustry.v20201201',
        'client_module': 'iotvideoindustry_client',
        'client_class': 'IotvideoindustryClient',
        'sdk_package': 'tencentcloud-sdk-python-iotvideoindustry',
        'endpoint': 'iotvideoindustry.tencentcloudapi.com',
        'action': 'DescribeAllDeviceList',
        'request_class': 'DescribeAllDeviceListRequest',
        'ids': {
            'param': 'all_device_ids',
            'field': 'DeviceIds',
            'doc': 'All device IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Devices',
        'response_total': 'TotalCount',
        'result_key': 'all_devices',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud IOTVIDEOINDUSTRY all devices',
        'description': 'Returns IOTVIDEOINDUSTRY all devices visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching IOTVIDEOINDUSTRY all devices.',
        'return_total_doc': 'Number of all devices reported by the API.',
        'examples': """\
- name: List all all devices
  tencentcloud.cloud.iotvideoindustry_all_device_info:
    region: ap-guangzhou

- name: Find all devices by ID
  tencentcloud.cloud.iotvideoindustry_all_device_info:
    region: ap-guangzhou
    all_device_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'iss_device_snapshot_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.iss.v20230517',
        'client_module': 'iss_client',
        'client_class': 'IssClient',
        'sdk_package': 'tencentcloud-sdk-python-iss',
        'endpoint': 'iss.tencentcloudapi.com',
        'action': 'ListDeviceSnapshots',
        'request_class': 'ListDeviceSnapshotsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Data',
        'response_total': 'TotalCount',
        'result_key': 'device_snapshots',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud ISS device snapshots',
        'description': 'Returns ISS device snapshots visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ISS device snapshots.',
        'return_total_doc': 'Number of device snapshots reported by the API.',
        'examples': """\
- name: List all device snapshots
  tencentcloud.cloud.iss_device_snapshot_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ivld_custom_person_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ivld.v20210903',
        'client_module': 'ivld_client',
        'client_class': 'IvldClient',
        'sdk_package': 'tencentcloud-sdk-python-ivld',
        'endpoint': 'ivld.tencentcloudapi.com',
        'action': 'DescribeCustomPersons',
        'request_class': 'DescribeCustomPersonsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'PersonInfoSet',
        'response_total': 'TotalCount',
        'result_key': 'custom_persons',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud IVLD custom persons',
        'description': 'Returns IVLD custom persons visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching IVLD custom persons.',
        'return_total_doc': 'Number of custom persons reported by the API.',
        'examples': """\
- name: List all custom persons
  tencentcloud.cloud.ivld_custom_person_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'keewidb_instance_backup_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.keewidb.v20220308',
        'client_module': 'keewidb_client',
        'client_class': 'KeewidbClient',
        'sdk_package': 'tencentcloud-sdk-python-keewidb',
        'endpoint': 'keewidb.tencentcloudapi.com',
        'action': 'DescribeInstanceBackups',
        'request_class': 'DescribeInstanceBackupsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'BackupRecord',
        'response_total': 'TotalCount',
        'result_key': 'instance_backups',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud KEEWIDB instance backups',
        'description': 'Returns KEEWIDB instance backups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching KEEWIDB instance backups.',
        'return_total_doc': 'Number of instance backups reported by the API.',
        'examples': """\
- name: List all instance backups
  tencentcloud.cloud.keewidb_instance_backup_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'live_audit_keyword_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.live.v20180801',
        'client_module': 'live_client',
        'client_class': 'LiveClient',
        'sdk_package': 'tencentcloud-sdk-python-live',
        'endpoint': 'live.tencentcloudapi.com',
        'action': 'DescribeAuditKeywords',
        'request_class': 'DescribeAuditKeywordsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Infos',
        'response_total': 'Total',
        'result_key': 'audit_keywords',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud LIVE audit keywords',
        'description': 'Returns LIVE audit keywords visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching LIVE audit keywords.',
        'return_total_doc': 'Number of audit keywords reported by the API.',
        'examples': """\
- name: List all audit keywords
  tencentcloud.cloud.live_audit_keyword_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'lke_app_knowledge_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.lke.v20231130',
        'client_module': 'lke_client',
        'client_class': 'LkeClient',
        'sdk_package': 'tencentcloud-sdk-python-lke',
        'endpoint': 'lke.tencentcloudapi.com',
        'action': 'ListAppKnowledgeDetail',
        'request_class': 'ListAppKnowledgeDetailRequest',
        'ids': {
            'param': 'app_knowledge_ids',
            'field': 'AppBizIds',
            'doc': 'App knowledge IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'List',
        'response_total': 'Total',
        'result_key': 'app_knowledges',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud LKE app knowledges',
        'description': 'Returns LKE app knowledges visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching LKE app knowledges.',
        'return_total_doc': 'Number of app knowledges reported by the API.',
        'examples': """\
- name: List all app knowledges
  tencentcloud.cloud.lke_app_knowledge_info:
    region: ap-guangzhou

- name: Find app knowledges by ID
  tencentcloud.cloud.lke_app_knowledge_info:
    region: ap-guangzhou
    app_knowledge_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'lowcode_knowledge_set_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.lowcode.v20210108',
        'client_module': 'lowcode_client',
        'client_class': 'LowcodeClient',
        'sdk_package': 'tencentcloud-sdk-python-lowcode',
        'endpoint': 'lowcode.tencentcloudapi.com',
        'action': 'DescribeKnowledgeSetList',
        'request_class': 'DescribeKnowledgeSetListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Data.KnowledgeSets',
        'response_total': 'Data.Total',
        'result_key': 'knowledge_sets',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud LOWCODE knowledge sets',
        'description': 'Returns LOWCODE knowledge sets visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching LOWCODE knowledge sets.',
        'return_total_doc': 'Number of knowledge sets reported by the API.',
        'examples': """\
- name: List all knowledge sets
  tencentcloud.cloud.lowcode_knowledge_set_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'mall_draw_resource_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.mall.v20230518',
        'client_module': 'mall_client',
        'client_class': 'MallClient',
        'sdk_package': 'tencentcloud-sdk-python-mall',
        'endpoint': 'mall.tencentcloudapi.com',
        'action': 'DescribeDrawResourceList',
        'request_class': 'DescribeDrawResourceListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'ResourceDrawList',
        'response_total': 'TotalCount',
        'result_key': 'draw_resources',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud MALL draw resources',
        'description': 'Returns MALL draw resources visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MALL draw resources.',
        'return_total_doc': 'Number of draw resources reported by the API.',
        'examples': """\
- name: List all draw resources
  tencentcloud.cloud.mall_draw_resource_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'memcached_instance_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.memcached.v20190318',
        'client_module': 'memcached_client',
        'client_class': 'MemcachedClient',
        'sdk_package': 'tencentcloud-sdk-python-memcached',
        'endpoint': 'memcached.tencentcloudapi.com',
        'action': 'DescribeInstances',
        'request_class': 'DescribeInstancesRequest',
        'ids': {
            'param': 'instance_ids',
            'field': 'InstanceIds',
            'doc': 'Instance IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'InstanceList',
        'response_total': 'TotalNum',
        'result_key': 'instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud MEMCACHED instances',
        'description': 'Returns MEMCACHED instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MEMCACHED instances.',
        'return_total_doc': 'Number of instances reported by the API.',
        'examples': """\
- name: List all instances
  tencentcloud.cloud.memcached_instance_info:
    region: ap-guangzhou

- name: Find instances by ID
  tencentcloud.cloud.memcached_instance_info:
    region: ap-guangzhou
    instance_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'mps_person_sample_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.mps.v20190612',
        'client_module': 'mps_client',
        'client_class': 'MpsClient',
        'sdk_package': 'tencentcloud-sdk-python-mps',
        'endpoint': 'mps.tencentcloudapi.com',
        'action': 'DescribePersonSamples',
        'request_class': 'DescribePersonSamplesRequest',
        'ids': {
            'param': 'person_sample_ids',
            'field': 'PersonIds',
            'doc': 'Person sample IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'PersonSet',
        'response_total': 'TotalCount',
        'result_key': 'person_samples',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud MPS person samples',
        'description': 'Returns MPS person samples visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MPS person samples.',
        'return_total_doc': 'Number of person samples reported by the API.',
        'examples': """\
- name: List all person samples
  tencentcloud.cloud.mps_person_sample_info:
    region: ap-guangzhou

- name: Find person samples by ID
  tencentcloud.cloud.mps_person_sample_info:
    region: ap-guangzhou
    person_sample_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'mqtt_device_certificate_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.mqtt.v20240516',
        'client_module': 'mqtt_client',
        'client_class': 'MqttClient',
        'sdk_package': 'tencentcloud-sdk-python-mqtt',
        'endpoint': 'mqtt.tencentcloudapi.com',
        'action': 'DescribeDeviceCertificates',
        'request_class': 'DescribeDeviceCertificatesRequest',
        'ids': None,
        'filters': {
            'doc': 'MQTT API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Data',
        'response_total': 'TotalCount',
        'result_key': 'device_certificates',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud MQTT device certificates',
        'description': 'Returns MQTT device certificates visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MQTT device certificates.',
        'return_total_doc': 'Number of device certificates reported by the API.',
        'examples': """\
- name: List all device certificates
  tencentcloud.cloud.mqtt_device_certificate_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ms_shield_instance_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ms.v20180408',
        'client_module': 'ms_client',
        'client_class': 'MsClient',
        'sdk_package': 'tencentcloud-sdk-python-ms',
        'endpoint': 'ms.tencentcloudapi.com',
        'action': 'DescribeShieldInstances',
        'request_class': 'DescribeShieldInstancesRequest',
        'ids': {
            'param': 'shield_instance_ids',
            'field': 'ItemIds',
            'doc': 'Shield instance IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'AppSet',
        'response_total': 'TotalCount',
        'result_key': 'shield_instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud MS shield instances',
        'description': 'Returns MS shield instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MS shield instances.',
        'return_total_doc': 'Number of shield instances reported by the API.',
        'examples': """\
- name: List all shield instances
  tencentcloud.cloud.ms_shield_instance_info:
    region: ap-guangzhou

- name: Find shield instances by ID
  tencentcloud.cloud.ms_shield_instance_info:
    region: ap-guangzhou
    shield_instance_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'msp_migration_project_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.msp.v20180319',
        'client_module': 'msp_client',
        'client_class': 'MspClient',
        'sdk_package': 'tencentcloud-sdk-python-msp',
        'endpoint': 'msp.tencentcloudapi.com',
        'action': 'ListMigrationProject',
        'request_class': 'ListMigrationProjectRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Projects',
        'response_total': 'TotalCount',
        'result_key': 'migration_projects',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud MSP migration projects',
        'description': 'Returns MSP migration projects visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MSP migration projects.',
        'return_total_doc': 'Number of migration projects reported by the API.',
        'examples': """\
- name: List all migration projects
  tencentcloud.cloud.msp_migration_project_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'oceanus_cluster_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.oceanus.v20190422',
        'client_module': 'oceanus_client',
        'client_class': 'OceanusClient',
        'sdk_package': 'tencentcloud-sdk-python-oceanus',
        'endpoint': 'oceanus.tencentcloudapi.com',
        'action': 'DescribeClusters',
        'request_class': 'DescribeClustersRequest',
        'ids': {
            'param': 'cluster_ids',
            'field': 'ClusterIds',
            'doc': 'Cluster IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'OCEANUS API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'ClusterSet',
        'response_total': 'TotalCount',
        'result_key': 'clusters',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud OCEANUS clusters',
        'description': 'Returns OCEANUS clusters visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching OCEANUS clusters.',
        'return_total_doc': 'Number of clusters reported by the API.',
        'examples': """\
- name: List all clusters
  tencentcloud.cloud.oceanus_cluster_info:
    region: ap-guangzhou

- name: Find clusters by ID
  tencentcloud.cloud.oceanus_cluster_info:
    region: ap-guangzhou
    cluster_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'omics_application_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.omics.v20221128',
        'client_module': 'omics_client',
        'client_class': 'OmicsClient',
        'sdk_package': 'tencentcloud-sdk-python-omics',
        'endpoint': 'omics.tencentcloudapi.com',
        'action': 'DescribeApplications',
        'request_class': 'DescribeApplicationsRequest',
        'ids': None,
        'filters': {
            'doc': 'OMICS API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Applications',
        'response_total': 'TotalCount',
        'result_key': 'applications',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud OMICS applications',
        'description': 'Returns OMICS applications visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching OMICS applications.',
        'return_total_doc': 'Number of applications reported by the API.',
        'examples': """\
- name: List all applications
  tencentcloud.cloud.omics_application_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'partners_agent_deals_by_cache_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.partners.v20180321',
        'client_module': 'partners_client',
        'client_class': 'PartnersClient',
        'sdk_package': 'tencentcloud-sdk-python-partners',
        'endpoint': 'partners.tencentcloudapi.com',
        'action': 'DescribeAgentDealsByCache',
        'request_class': 'DescribeAgentDealsByCacheRequest',
        'ids': {
            'param': 'agent_deals_by_cache_ids',
            'field': 'BigDealIds',
            'doc': 'Agent deals by cache IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'AgentDealSet',
        'response_total': 'TotalCount',
        'result_key': 'agent_deals_by_caches',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud PARTNERS agent deals by caches',
        'description': 'Returns PARTNERS agent deals by caches visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching PARTNERS agent deals by caches.',
        'return_total_doc': 'Number of agent deals by caches reported by the API.',
        'examples': """\
- name: List all agent deals by caches
  tencentcloud.cloud.partners_agent_deals_by_cache_info:
    region: ap-guangzhou

- name: Find agent deals by caches by ID
  tencentcloud.cloud.partners_agent_deals_by_cache_info:
    region: ap-guangzhou
    agent_deals_by_cache_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'privatedns_account_vpc_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.privatedns.v20201028',
        'client_module': 'privatedns_client',
        'client_class': 'PrivatednsClient',
        'sdk_package': 'tencentcloud-sdk-python-privatedns',
        'endpoint': 'privatedns.tencentcloudapi.com',
        'action': 'DescribeAccountVpcList',
        'request_class': 'DescribeAccountVpcListRequest',
        'ids': None,
        'filters': {
            'doc': 'PRIVATEDNS API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'VpcSet',
        'response_total': 'TotalCount',
        'result_key': 'account_vpcs',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud PRIVATEDNS account vpcs',
        'description': 'Returns PRIVATEDNS account vpcs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching PRIVATEDNS account vpcs.',
        'return_total_doc': 'Number of account vpcs reported by the API.',
        'examples': """\
- name: List all account vpcs
  tencentcloud.cloud.privatedns_account_vpc_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'pts_cron_job_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.pts.v20210728',
        'client_module': 'pts_client',
        'client_class': 'PtsClient',
        'sdk_package': 'tencentcloud-sdk-python-pts',
        'endpoint': 'pts.tencentcloudapi.com',
        'action': 'DescribeCronJobs',
        'request_class': 'DescribeCronJobsRequest',
        'ids': {
            'param': 'cron_job_ids',
            'field': 'CronJobIds',
            'doc': 'Cron job IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'CronJobSet',
        'response_total': 'Total',
        'result_key': 'cron_jobs',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud PTS cron jobs',
        'description': 'Returns PTS cron jobs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching PTS cron jobs.',
        'return_total_doc': 'Number of cron jobs reported by the API.',
        'examples': """\
- name: List all cron jobs
  tencentcloud.cloud.pts_cron_job_info:
    region: ap-guangzhou

- name: Find cron jobs by ID
  tencentcloud.cloud.pts_cron_job_info:
    region: ap-guangzhou
    cron_job_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'region_product_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.region.v20220627',
        'client_module': 'region_client',
        'client_class': 'RegionClient',
        'sdk_package': 'tencentcloud-sdk-python-region',
        'endpoint': 'region.tencentcloudapi.com',
        'action': 'DescribeProducts',
        'request_class': 'DescribeProductsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Products',
        'response_total': 'TotalCount',
        'result_key': 'products',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud REGION products',
        'description': 'Returns REGION products visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching REGION products.',
        'return_total_doc': 'Number of products reported by the API.',
        'examples': """\
- name: List all products
  tencentcloud.cloud.region_product_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'rum_project_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.rum.v20210622',
        'client_module': 'rum_client',
        'client_class': 'RumClient',
        'sdk_package': 'tencentcloud-sdk-python-rum',
        'endpoint': 'rum.tencentcloudapi.com',
        'action': 'DescribeProjects',
        'request_class': 'DescribeProjectsRequest',
        'ids': None,
        'filters': {
            'doc': 'RUM API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'ProjectSet',
        'response_total': 'TotalCount',
        'result_key': 'projects',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud RUM projects',
        'description': 'Returns RUM projects visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching RUM projects.',
        'return_total_doc': 'Number of projects reported by the API.',
        'examples': """\
- name: List all projects
  tencentcloud.cloud.rum_project_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'securitylake_security_alarm_table_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.securitylake.v20240117',
        'client_module': 'securitylake_client',
        'client_class': 'SecuritylakeClient',
        'sdk_package': 'tencentcloud-sdk-python-securitylake',
        'endpoint': 'securitylake.tencentcloudapi.com',
        'action': 'DescribeSecurityAlarmTableList',
        'request_class': 'DescribeSecurityAlarmTableListRequest',
        'ids': None,
        'filters': {
            'doc': 'SECURITYLAKE API filter names mapped to lists of values.',
            'model': 'WebSearchFilter',
        },
        'extra_params': [],
        'response_items': 'AlarmList',
        'response_total': 'TotalCount',
        'result_key': 'security_alarm_tables',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud SECURITYLAKE security alarm tables',
        'description': 'Returns SECURITYLAKE security alarm tables visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching SECURITYLAKE security alarm tables.',
        'return_total_doc': 'Number of security alarm tables reported by the API.',
        'examples': """\
- name: List all security alarm tables
  tencentcloud.cloud.securitylake_security_alarm_table_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ses_black_email_address_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ses.v20201002',
        'client_module': 'ses_client',
        'client_class': 'SesClient',
        'sdk_package': 'tencentcloud-sdk-python-ses',
        'endpoint': 'ses.tencentcloudapi.com',
        'action': 'ListBlackEmailAddress',
        'request_class': 'ListBlackEmailAddressRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'BlackList',
        'response_total': 'TotalCount',
        'result_key': 'black_email_addresses',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud SES black email addresses',
        'description': 'Returns SES black email addresses visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching SES black email addresses.',
        'return_total_doc': 'Number of black email addresses reported by the API.',
        'examples': """\
- name: List all black email addresses
  tencentcloud.cloud.ses_black_email_address_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'smh_library_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.smh.v20210712',
        'client_module': 'smh_client',
        'client_class': 'SmhClient',
        'sdk_package': 'tencentcloud-sdk-python-smh',
        'endpoint': 'smh.tencentcloudapi.com',
        'action': 'DescribeLibraries',
        'request_class': 'DescribeLibrariesRequest',
        'ids': {
            'param': 'library_ids',
            'field': 'LibraryIds',
            'doc': 'Library IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'List',
        'response_total': 'TotalCount',
        'result_key': 'libraries',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud SMH libraries',
        'description': 'Returns SMH libraries visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching SMH libraries.',
        'return_total_doc': 'Number of libraries reported by the API.',
        'examples': """\
- name: List all libraries
  tencentcloud.cloud.smh_library_info:
    region: ap-guangzhou

- name: Find libraries by ID
  tencentcloud.cloud.smh_library_info:
    region: ap-guangzhou
    library_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'ssa_check_config_asset_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.ssa.v20180608',
        'client_module': 'ssa_client',
        'client_class': 'SsaClient',
        'sdk_package': 'tencentcloud-sdk-python-ssa',
        'endpoint': 'ssa.tencentcloudapi.com',
        'action': 'DescribeCheckConfigAssetList',
        'request_class': 'DescribeCheckConfigAssetListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'CheckAssetsList',
        'response_total': 'Total',
        'result_key': 'check_config_assets',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud SSA check config assets',
        'description': 'Returns SSA check config assets visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching SSA check config assets.',
        'return_total_doc': 'Number of check config assets reported by the API.',
        'examples': """\
- name: List all check config assets
  tencentcloud.cloud.ssa_check_config_asset_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'sslpod_domain_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.sslpod.v20190605',
        'client_module': 'sslpod_client',
        'client_class': 'SslpodClient',
        'sdk_package': 'tencentcloud-sdk-python-sslpod',
        'endpoint': 'sslpod.tencentcloudapi.com',
        'action': 'DescribeDomains',
        'request_class': 'DescribeDomainsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Data.Result',
        'response_total': 'Data.Total',
        'result_key': 'domains',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud SSLPOD domains',
        'description': 'Returns SSLPOD domains visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching SSLPOD domains.',
        'return_total_doc': 'Number of domains reported by the API.',
        'examples': """\
- name: List all domains
  tencentcloud.cloud.sslpod_domain_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'svp_saving_plan_coverage_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.svp.v20240125',
        'client_module': 'svp_client',
        'client_class': 'SvpClient',
        'sdk_package': 'tencentcloud-sdk-python-svp',
        'endpoint': 'svp.tencentcloudapi.com',
        'action': 'DescribeSavingPlanCoverage',
        'request_class': 'DescribeSavingPlanCoverageRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'DetailSet',
        'response_total': 'TotalCount',
        'result_key': 'saving_plan_coverages',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud SVP saving plan coverages',
        'description': 'Returns SVP saving plan coverages visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching SVP saving plan coverages.',
        'return_total_doc': 'Number of saving plan coverages reported by the API.',
        'examples': """\
- name: List all saving plan coverages
  tencentcloud.cloud.svp_saving_plan_coverage_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tcaplusdb_cluster_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tcaplusdb.v20190823',
        'client_module': 'tcaplusdb_client',
        'client_class': 'TcaplusdbClient',
        'sdk_package': 'tencentcloud-sdk-python-tcaplusdb',
        'endpoint': 'tcaplusdb.tencentcloudapi.com',
        'action': 'DescribeClusters',
        'request_class': 'DescribeClustersRequest',
        'ids': {
            'param': 'cluster_ids',
            'field': 'ClusterIds',
            'doc': 'Cluster IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'TCAPLUSDB API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Clusters',
        'response_total': 'TotalCount',
        'result_key': 'clusters',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TCAPLUSDB clusters',
        'description': 'Returns TCAPLUSDB clusters visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TCAPLUSDB clusters.',
        'return_total_doc': 'Number of clusters reported by the API.',
        'examples': """\
- name: List all clusters
  tencentcloud.cloud.tcaplusdb_cluster_info:
    region: ap-guangzhou

- name: Find clusters by ID
  tencentcloud.cloud.tcaplusdb_cluster_info:
    region: ap-guangzhou
    cluster_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'tcb_billing_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tcb.v20180608',
        'client_module': 'tcb_client',
        'client_class': 'TcbClient',
        'sdk_package': 'tencentcloud-sdk-python-tcb',
        'endpoint': 'tcb.tencentcloudapi.com',
        'action': 'DescribeBillingInfo',
        'request_class': 'DescribeBillingInfoRequest',
        'ids': {
            'param': 'billing_ids',
            'field': 'EnvIds',
            'doc': 'Billing IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'EnvBillingInfoList',
        'response_total': 'Total',
        'result_key': 'billings',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TCB billings',
        'description': 'Returns TCB billings visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TCB billings.',
        'return_total_doc': 'Number of billings reported by the API.',
        'examples': """\
- name: List all billings
  tencentcloud.cloud.tcb_billing_info:
    region: ap-guangzhou

- name: Find billings by ID
  tencentcloud.cloud.tcb_billing_info:
    region: ap-guangzhou
    billing_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'tcm_mesh_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tcm.v20210413',
        'client_module': 'tcm_client',
        'client_class': 'TcmClient',
        'sdk_package': 'tencentcloud-sdk-python-tcm',
        'endpoint': 'tcm.tencentcloudapi.com',
        'action': 'DescribeMeshList',
        'request_class': 'DescribeMeshListRequest',
        'ids': None,
        'filters': {
            'doc': 'TCM API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'MeshList',
        'response_total': 'Total',
        'result_key': 'meshes',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TCM meshes',
        'description': 'Returns TCM meshes visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TCM meshes.',
        'return_total_doc': 'Number of meshes reported by the API.',
        'examples': """\
- name: List all meshes
  tencentcloud.cloud.tcm_mesh_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tcss_abnormal_process_event_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tcss.v20201101',
        'client_module': 'tcss_client',
        'client_class': 'TcssClient',
        'sdk_package': 'tencentcloud-sdk-python-tcss',
        'endpoint': 'tcss.tencentcloudapi.com',
        'action': 'DescribeAbnormalProcessEvents',
        'request_class': 'DescribeAbnormalProcessEventsRequest',
        'ids': None,
        'filters': {
            'doc': 'TCSS API filter names mapped to lists of values.',
            'model': 'RunTimeFilters',
        },
        'extra_params': [],
        'response_items': 'EventSet',
        'response_total': 'TotalCount',
        'result_key': 'abnormal_process_events',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TCSS abnormal process events',
        'description': 'Returns TCSS abnormal process events visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TCSS abnormal process events.',
        'return_total_doc': 'Number of abnormal process events reported by the API.',
        'examples': """\
- name: List all abnormal process events
  tencentcloud.cloud.tcss_abnormal_process_event_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tdai_agent_duty_task_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tdai.v20250717',
        'client_module': 'tdai_client',
        'client_class': 'TdaiClient',
        'sdk_package': 'tencentcloud-sdk-python-tdai',
        'endpoint': 'tdai.tencentcloudapi.com',
        'action': 'DescribeAgentDutyTasks',
        'request_class': 'DescribeAgentDutyTasksRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'DutyTasks',
        'response_total': 'TotalCount',
        'result_key': 'agent_duty_tasks',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TDAI agent duty tasks',
        'description': 'Returns TDAI agent duty tasks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TDAI agent duty tasks.',
        'return_total_doc': 'Number of agent duty tasks reported by the API.',
        'examples': """\
- name: List all agent duty tasks
  tencentcloud.cloud.tdai_agent_duty_task_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tdcpg_cluster_instance_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tdcpg.v20211118',
        'client_module': 'tdcpg_client',
        'client_class': 'TdcpgClient',
        'sdk_package': 'tencentcloud-sdk-python-tdcpg',
        'endpoint': 'tdcpg.tencentcloudapi.com',
        'action': 'DescribeClusterInstances',
        'request_class': 'DescribeClusterInstancesRequest',
        'ids': None,
        'filters': {
            'doc': 'TDCPG API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'InstanceSet',
        'response_total': 'TotalCount',
        'result_key': 'cluster_instances',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud TDCPG cluster instances',
        'description': 'Returns TDCPG cluster instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TDCPG cluster instances.',
        'return_total_doc': 'Number of cluster instances reported by the API.',
        'examples': """\
- name: List all cluster instances
  tencentcloud.cloud.tdcpg_cluster_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tdmq_amqp_cluster_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tdmq.v20200217',
        'client_module': 'tdmq_client',
        'client_class': 'TdmqClient',
        'sdk_package': 'tencentcloud-sdk-python-tdmq',
        'endpoint': 'tdmq.tencentcloudapi.com',
        'action': 'DescribeAMQPClusters',
        'request_class': 'DescribeAMQPClustersRequest',
        'ids': {
            'param': 'amqp_cluster_ids',
            'field': 'ClusterIdList',
            'doc': 'Amqp cluster IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'TDMQ API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'ClusterList',
        'response_total': 'TotalCount',
        'result_key': 'amqp_clusters',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TDMQ amqp clusters',
        'description': 'Returns TDMQ amqp clusters visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TDMQ amqp clusters.',
        'return_total_doc': 'Number of amqp clusters reported by the API.',
        'examples': """\
- name: List all amqp clusters
  tencentcloud.cloud.tdmq_amqp_cluster_info:
    region: ap-guangzhou

- name: Find amqp clusters by ID
  tencentcloud.cloud.tdmq_amqp_cluster_info:
    region: ap-guangzhou
    amqp_cluster_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'tdmysql_db_instance_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tdmysql.v20211122',
        'client_module': 'tdmysql_client',
        'client_class': 'TdmysqlClient',
        'sdk_package': 'tencentcloud-sdk-python-tdmysql',
        'endpoint': 'tdmysql.tencentcloudapi.com',
        'action': 'DescribeDBInstances',
        'request_class': 'DescribeDBInstancesRequest',
        'ids': None,
        'filters': {
            'doc': 'TDMYSQL API filter names mapped to lists of values.',
            'model': 'InstanceFilter',
        },
        'extra_params': [],
        'response_items': 'Instances',
        'response_total': 'TotalCount',
        'result_key': 'db_instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TDMYSQL db instances',
        'description': 'Returns TDMYSQL db instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TDMYSQL db instances.',
        'return_total_doc': 'Number of db instances reported by the API.',
        'examples': """\
- name: List all db instances
  tencentcloud.cloud.tdmysql_db_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tem_application_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tem.v20210701',
        'client_module': 'tem_client',
        'client_class': 'TemClient',
        'sdk_package': 'tencentcloud-sdk-python-tem',
        'endpoint': 'tem.tencentcloudapi.com',
        'action': 'DescribeApplications',
        'request_class': 'DescribeApplicationsRequest',
        'ids': None,
        'filters': {
            'doc': 'TEM API filter names mapped to lists of values.',
            'model': 'QueryFilter',
            'value_field': 'Value',
        },
        'extra_params': [],
        'response_items': 'Result.Records',
        'response_total': 'Result.Total',
        'result_key': 'applications',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TEM applications',
        'description': 'Returns TEM applications visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TEM applications.',
        'return_total_doc': 'Number of applications reported by the API.',
        'examples': """\
- name: List all applications
  tencentcloud.cloud.tem_application_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'teo_function_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.teo.v20220901',
        'client_module': 'teo_client',
        'client_class': 'TeoClient',
        'sdk_package': 'tencentcloud-sdk-python-teo',
        'endpoint': 'teo.tencentcloudapi.com',
        'action': 'DescribeFunctions',
        'request_class': 'DescribeFunctionsRequest',
        'ids': {
            'param': 'function_ids',
            'field': 'FunctionIds',
            'doc': 'Function IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'TEO API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Functions',
        'response_total': 'TotalCount',
        'result_key': 'functions',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TEO functions',
        'description': 'Returns TEO functions visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TEO functions.',
        'return_total_doc': 'Number of functions reported by the API.',
        'examples': """\
- name: List all functions
  tencentcloud.cloud.teo_function_info:
    region: ap-guangzhou

- name: Find functions by ID
  tencentcloud.cloud.teo_function_info:
    region: ap-guangzhou
    function_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'thpc_cluster_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.thpc.v20230321',
        'client_module': 'thpc_client',
        'client_class': 'ThpcClient',
        'sdk_package': 'tencentcloud-sdk-python-thpc',
        'endpoint': 'thpc.tencentcloudapi.com',
        'action': 'DescribeClusters',
        'request_class': 'DescribeClustersRequest',
        'ids': {
            'param': 'cluster_ids',
            'field': 'ClusterIds',
            'doc': 'Cluster IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'THPC API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'ClusterSet',
        'response_total': 'TotalCount',
        'result_key': 'clusters',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud THPC clusters',
        'description': 'Returns THPC clusters visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching THPC clusters.',
        'return_total_doc': 'Number of clusters reported by the API.',
        'examples': """\
- name: List all clusters
  tencentcloud.cloud.thpc_cluster_info:
    region: ap-guangzhou

- name: Find clusters by ID
  tencentcloud.cloud.thpc_cluster_info:
    region: ap-guangzhou
    cluster_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'tione_dataset_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tione.v20211111',
        'client_module': 'tione_client',
        'client_class': 'TioneClient',
        'sdk_package': 'tencentcloud-sdk-python-tione',
        'endpoint': 'tione.tencentcloudapi.com',
        'action': 'DescribeDatasets',
        'request_class': 'DescribeDatasetsRequest',
        'ids': {
            'param': 'dataset_ids',
            'field': 'DatasetIds',
            'doc': 'Dataset IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'TIONE API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'DatasetGroups',
        'response_total': 'TotalCount',
        'result_key': 'datasets',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TIONE datasets',
        'description': 'Returns TIONE datasets visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TIONE datasets.',
        'return_total_doc': 'Number of datasets reported by the API.',
        'examples': """\
- name: List all datasets
  tencentcloud.cloud.tione_dataset_info:
    region: ap-guangzhou

- name: Find datasets by ID
  tencentcloud.cloud.tione_dataset_info:
    region: ap-guangzhou
    dataset_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'tiw_running_task_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tiw.v20190919',
        'client_module': 'tiw_client',
        'client_class': 'TiwClient',
        'sdk_package': 'tencentcloud-sdk-python-tiw',
        'endpoint': 'tiw.tencentcloudapi.com',
        'action': 'DescribeRunningTasks',
        'request_class': 'DescribeRunningTasksRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Tasks',
        'response_total': 'Total',
        'result_key': 'running_tasks',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TIW running tasks',
        'description': 'Returns TIW running tasks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TIW running tasks.',
        'return_total_doc': 'Number of running tasks reported by the API.',
        'examples': """\
- name: List all running tasks
  tencentcloud.cloud.tiw_running_task_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tokenhub_model_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tokenhub.v20260322',
        'client_module': 'tokenhub_client',
        'client_class': 'TokenhubClient',
        'sdk_package': 'tencentcloud-sdk-python-tokenhub',
        'endpoint': 'tokenhub.tencentcloudapi.com',
        'action': 'DescribeModelList',
        'request_class': 'DescribeModelListRequest',
        'ids': {
            'param': 'model_ids',
            'field': 'ModelIds',
            'doc': 'Model IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'ModelSet',
        'response_total': 'TotalCount',
        'result_key': 'models',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TOKENHUB models',
        'description': 'Returns TOKENHUB models visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TOKENHUB models.',
        'return_total_doc': 'Number of models reported by the API.',
        'examples': """\
- name: List all models
  tencentcloud.cloud.tokenhub_model_info:
    region: ap-guangzhou

- name: Find models by ID
  tencentcloud.cloud.tokenhub_model_info:
    region: ap-guangzhou
    model_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'tourism_draw_resource_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tourism.v20230215',
        'client_module': 'tourism_client',
        'client_class': 'TourismClient',
        'sdk_package': 'tencentcloud-sdk-python-tourism',
        'endpoint': 'tourism.tencentcloudapi.com',
        'action': 'DescribeDrawResourceList',
        'request_class': 'DescribeDrawResourceListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'ResourceDrawList',
        'response_total': 'TotalCount',
        'result_key': 'draw_resources',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud TOURISM draw resources',
        'description': 'Returns TOURISM draw resources visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TOURISM draw resources.',
        'return_total_doc': 'Number of draw resources reported by the API.',
        'examples': """\
- name: List all draw resources
  tencentcloud.cloud.tourism_draw_resource_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'trabbit_rabbit_mq_serverless_instance_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.trabbit.v20230418',
        'client_module': 'trabbit_client',
        'client_class': 'TrabbitClient',
        'sdk_package': 'tencentcloud-sdk-python-trabbit',
        'endpoint': 'trabbit.tencentcloudapi.com',
        'action': 'ListRabbitMQServerlessInstances',
        'request_class': 'ListRabbitMQServerlessInstancesRequest',
        'ids': None,
        'filters': {
            'doc': 'TRABBIT API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Instances',
        'response_total': 'TotalCount',
        'result_key': 'rabbit_mq_serverless_instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TRABBIT rabbit mq serverless instances',
        'description': 'Returns TRABBIT rabbit mq serverless instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TRABBIT rabbit mq serverless instances.',
        'return_total_doc': 'Number of rabbit mq serverless instances reported by the API.',
        'examples': """\
- name: List all rabbit mq serverless instances
  tencentcloud.cloud.trabbit_rabbit_mq_serverless_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'trocket_consumer_client_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.trocket.v20230308',
        'client_module': 'trocket_client',
        'client_class': 'TrocketClient',
        'sdk_package': 'tencentcloud-sdk-python-trocket',
        'endpoint': 'trocket.tencentcloudapi.com',
        'action': 'DescribeConsumerClientList',
        'request_class': 'DescribeConsumerClientListRequest',
        'ids': None,
        'filters': {
            'doc': 'TROCKET API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Data',
        'response_total': 'TotalCount',
        'result_key': 'consumer_clients',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TROCKET consumer clients',
        'description': 'Returns TROCKET consumer clients visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TROCKET consumer clients.',
        'return_total_doc': 'Number of consumer clients reported by the API.',
        'examples': """\
- name: List all consumer clients
  tencentcloud.cloud.trocket_consumer_client_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'trp_code_batch_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.trp.v20210515',
        'client_module': 'trp_client',
        'client_class': 'TrpClient',
        'sdk_package': 'tencentcloud-sdk-python-trp',
        'endpoint': 'trp.tencentcloudapi.com',
        'action': 'DescribeCodeBatches',
        'request_class': 'DescribeCodeBatchesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'CodeBatches',
        'response_total': 'TotalCount',
        'result_key': 'code_batches',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud TRP code batches',
        'description': 'Returns TRP code batches visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TRP code batches.',
        'return_total_doc': 'Number of code batches reported by the API.',
        'examples': """\
- name: List all code batches
  tencentcloud.cloud.trp_code_batch_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'trro_device_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.trro.v20220325',
        'client_module': 'trro_client',
        'client_class': 'TrroClient',
        'sdk_package': 'tencentcloud-sdk-python-trro',
        'endpoint': 'trro.tencentcloudapi.com',
        'action': 'DescribeDeviceList',
        'request_class': 'DescribeDeviceListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Devices',
        'response_total': 'Total',
        'result_key': 'devices',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud TRRO devices',
        'description': 'Returns TRRO devices visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TRRO devices.',
        'return_total_doc': 'Number of devices reported by the API.',
        'examples': """\
- name: List all devices
  tencentcloud.cloud.trro_device_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'trtc_call_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.trtc.v20190722',
        'client_module': 'trtc_client',
        'client_class': 'TrtcClient',
        'sdk_package': 'tencentcloud-sdk-python-trtc',
        'endpoint': 'trtc.tencentcloudapi.com',
        'action': 'DescribeCallDetailInfo',
        'request_class': 'DescribeCallDetailInfoRequest',
        'ids': {
            'param': 'call_ids',
            'field': 'UserIds',
            'doc': 'Call IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'UserList',
        'response_total': 'Total',
        'result_key': 'calls',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud TRTC calls',
        'description': 'Returns TRTC calls visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TRTC calls.',
        'return_total_doc': 'Number of calls reported by the API.',
        'examples': """\
- name: List all calls
  tencentcloud.cloud.trtc_call_info:
    region: ap-guangzhou

- name: Find calls by ID
  tencentcloud.cloud.trtc_call_info:
    region: ap-guangzhou
    call_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'tse_sre_instance_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tse.v20201207',
        'client_module': 'tse_client',
        'client_class': 'TseClient',
        'sdk_package': 'tencentcloud-sdk-python-tse',
        'endpoint': 'tse.tencentcloudapi.com',
        'action': 'DescribeSREInstances',
        'request_class': 'DescribeSREInstancesRequest',
        'ids': None,
        'filters': {
            'doc': 'TSE API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Content',
        'response_total': 'TotalCount',
        'result_key': 'sre_instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TSE sre instances',
        'description': 'Returns TSE sre instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TSE sre instances.',
        'return_total_doc': 'Number of sre instances reported by the API.',
        'examples': """\
- name: List all sre instances
  tencentcloud.cloud.tse_sre_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tsf_application_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.tsf.v20180326',
        'client_module': 'tsf_client',
        'client_class': 'TsfClient',
        'sdk_package': 'tencentcloud-sdk-python-tsf',
        'endpoint': 'tsf.tencentcloudapi.com',
        'action': 'DescribeApplications',
        'request_class': 'DescribeApplicationsRequest',
        'ids': {
            'param': 'application_ids',
            'field': 'ApplicationIdList',
            'doc': 'Application IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Result.Content',
        'response_total': 'Result.TotalCount',
        'result_key': 'applications',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TSF applications',
        'description': 'Returns TSF applications visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TSF applications.',
        'return_total_doc': 'Number of applications reported by the API.',
        'examples': """\
- name: List all applications
  tencentcloud.cloud.tsf_application_info:
    region: ap-guangzhou

- name: Find applications by ID
  tencentcloud.cloud.tsf_application_info:
    region: ap-guangzhou
    application_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'vcube_vcube_resource_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.vcube.v20220410',
        'client_module': 'vcube_client',
        'client_class': 'VcubeClient',
        'sdk_package': 'tencentcloud-sdk-python-vcube',
        'endpoint': 'vcube.tencentcloudapi.com',
        'action': 'DescribeVcubeResourcesList',
        'request_class': 'DescribeVcubeResourcesListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'ResourceList',
        'response_total': 'TotalCount',
        'result_key': 'vcube_resources',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud VCUBE vcube resources',
        'description': 'Returns VCUBE vcube resources visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching VCUBE vcube resources.',
        'return_total_doc': 'Number of vcube resources reported by the API.',
        'examples': """\
- name: List all vcube resources
  tencentcloud.cloud.vcube_vcube_resource_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'vdb_instance_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.vdb.v20230616',
        'client_module': 'vdb_client',
        'client_class': 'VdbClient',
        'sdk_package': 'tencentcloud-sdk-python-vdb',
        'endpoint': 'vdb.tencentcloudapi.com',
        'action': 'DescribeInstances',
        'request_class': 'DescribeInstancesRequest',
        'ids': {
            'param': 'instance_ids',
            'field': 'InstanceIds',
            'doc': 'Instance IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Items',
        'response_total': 'TotalCount',
        'result_key': 'instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud VDB instances',
        'description': 'Returns VDB instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching VDB instances.',
        'return_total_doc': 'Number of instances reported by the API.',
        'examples': """\
- name: List all instances
  tencentcloud.cloud.vdb_instance_info:
    region: ap-guangzhou

- name: Find instances by ID
  tencentcloud.cloud.vdb_instance_info:
    region: ap-guangzhou
    instance_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'vod_incremental_migration_strategy_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.vod.v20240718',
        'client_module': 'vod_client',
        'client_class': 'VodClient',
        'sdk_package': 'tencentcloud-sdk-python-vod',
        'endpoint': 'vod.tencentcloudapi.com',
        'action': 'DescribeIncrementalMigrationStrategyInfos',
        'request_class': 'DescribeIncrementalMigrationStrategyInfosRequest',
        'ids': None,
        'filters': {
            'doc': 'VOD API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'StrategyInfoSet',
        'response_total': 'TotalCount',
        'result_key': 'incremental_migration_strategies',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud VOD incremental migration strategies',
        'description': 'Returns VOD incremental migration strategies visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching VOD incremental migration strategies.',
        'return_total_doc': 'Number of incremental migration strategies reported by the API.',
        'examples': """\
- name: List all incremental migration strategies
  tencentcloud.cloud.vod_incremental_migration_strategy_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'wedata_project_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.wedata.v20250806',
        'client_module': 'wedata_client',
        'client_class': 'WedataClient',
        'sdk_package': 'tencentcloud-sdk-python-wedata',
        'endpoint': 'wedata.tencentcloudapi.com',
        'action': 'ListProjects',
        'request_class': 'ListProjectsRequest',
        'ids': {
            'param': 'project_ids',
            'field': 'ProjectIds',
            'doc': 'Project IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Data.Items',
        'response_total': 'Data.TotalCount',
        'result_key': 'projects',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud WEDATA projects',
        'description': 'Returns WEDATA projects visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching WEDATA projects.',
        'return_total_doc': 'Number of projects reported by the API.',
        'examples': """\
- name: List all projects
  tencentcloud.cloud.wedata_project_info:
    region: ap-guangzhou

- name: Find projects by ID
  tencentcloud.cloud.wedata_project_info:
    region: ap-guangzhou
    project_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'weilingwith_element_profile_page_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.weilingwith.v20230427',
        'client_module': 'weilingwith_client',
        'client_class': 'WeilingwithClient',
        'sdk_package': 'tencentcloud-sdk-python-weilingwith',
        'endpoint': 'weilingwith.tencentcloudapi.com',
        'action': 'DescribeElementProfilePage',
        'request_class': 'DescribeElementProfilePageRequest',
        'ids': {
            'param': 'element_profile_page_ids',
            'field': 'ParentElementIds',
            'doc': 'Element profile page IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Result.List',
        'response_total': 'Result.TotalCount',
        'result_key': 'element_profile_pages',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud WEILINGWITH element profile pages',
        'description': 'Returns WEILINGWITH element profile pages visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching WEILINGWITH element profile pages.',
        'return_total_doc': 'Number of element profile pages reported by the API.',
        'examples': """\
- name: List all element profile pages
  tencentcloud.cloud.weilingwith_element_profile_page_info:
    region: ap-guangzhou

- name: Find element profile pages by ID
  tencentcloud.cloud.weilingwith_element_profile_page_info:
    region: ap-guangzhou
    element_profile_page_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'wss_cert_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.wss.v20180426',
        'client_module': 'wss_client',
        'client_class': 'WssClient',
        'sdk_package': 'tencentcloud-sdk-python-wss',
        'endpoint': 'wss.tencentcloudapi.com',
        'action': 'DescribeCertList',
        'request_class': 'DescribeCertListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'CertificateSet',
        'response_total': 'TotalCount',
        'result_key': 'certs',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud WSS certs',
        'description': 'Returns WSS certs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching WSS certs.',
        'return_total_doc': 'Number of certs reported by the API.',
        'examples': """\
- name: List all certs
  tencentcloud.cloud.wss_cert_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'yinsuda_ktv_robot_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.yinsuda.v20220527',
        'client_module': 'yinsuda_client',
        'client_class': 'YinsudaClient',
        'sdk_package': 'tencentcloud-sdk-python-yinsuda',
        'endpoint': 'yinsuda.tencentcloudapi.com',
        'action': 'DescribeKTVRobots',
        'request_class': 'DescribeKTVRobotsRequest',
        'ids': {
            'param': 'ktv_robot_ids',
            'field': 'RobotIds',
            'doc': 'Ktv robot IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'KTVRobotInfoSet',
        'response_total': 'TotalCount',
        'result_key': 'ktv_robots',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud YINSUDA ktv robots',
        'description': 'Returns YINSUDA ktv robots visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching YINSUDA ktv robots.',
        'return_total_doc': 'Number of ktv robots reported by the API.',
        'examples': """\
- name: List all ktv robots
  tencentcloud.cloud.yinsuda_ktv_robot_info:
    region: ap-guangzhou

- name: Find ktv robots by ID
  tencentcloud.cloud.yinsuda_ktv_robot_info:
    region: ap-guangzhou
    ktv_robot_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'yunjing_account_statistic_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.yunjing.v20180228',
        'client_module': 'yunjing_client',
        'client_class': 'YunjingClient',
        'sdk_package': 'tencentcloud-sdk-python-yunjing',
        'endpoint': 'yunjing.tencentcloudapi.com',
        'action': 'DescribeAccountStatistics',
        'request_class': 'DescribeAccountStatisticsRequest',
        'ids': None,
        'filters': {
            'doc': 'YUNJING API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'AccountStatistics',
        'response_total': 'TotalCount',
        'result_key': 'account_statistics',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud YUNJING account statistics',
        'description': 'Returns YUNJING account statistics visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching YUNJING account statistics.',
        'return_total_doc': 'Number of account statistics reported by the API.',
        'examples': """\
- name: List all account statistics
  tencentcloud.cloud.yunjing_account_statistic_info:
    region: ap-guangzhou
""",
    },
]
