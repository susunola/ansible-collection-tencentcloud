# -*- coding: utf-8 -*-
"""Auto-discovered ``_info`` module specs appended to the generator SPECS.

Written by scripts/discover_info_specs.py -- regenerate instead of editing.
Every spec was derived by introspecting the installed tencentcloud SDK
packages (request/response field names, filter model shapes, pagination
types) exactly like the curated SPECS in generate_info_modules.py.
``GENERATED_SDK_VERSION`` records the SDK release the specs were
discovered against; scripts/check_sdk_drift.py pins CI to it.
"""

GENERATED_SDK_VERSION = '3.1.164'


SPECS_AUTO = [
    {
        'module': 'acp_scan_task_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.acp.v20220105',
        'client_module': 'acp_client',
        'client_class': 'AcpClient',
        'sdk_package': 'tencentcloud-sdk-python-acp',
        'endpoint': 'acp.tencentcloudapi.com',
        'action': 'DescribeScanTaskList',
        'request_class': 'DescribeScanTaskListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Data',
        'response_total': 'Total',
        'result_key': 'scan_tasks',
        'pagination_type': 'page',
        'page_number_field': 'PageNo',
        'short_description': 'Gather information about Tencent Cloud ACP scan tasks',
        'description': 'Returns ACP scan tasks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ACP scan tasks.',
        'return_total_doc': 'Number of scan tasks reported by the API.',
        'examples': """\
- name: List all scan tasks
  susunola.tencentcloud.acp_scan_task_info:
    region: ap-guangzhou
""",
    },
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
  susunola.tencentcloud.adp_agent_release_preview_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'advisor_strategy_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.advisor.v20200721',
        'client_module': 'advisor_client',
        'client_class': 'AdvisorClient',
        'sdk_package': 'tencentcloud-sdk-python-advisor',
        'endpoint': 'advisor.tencentcloudapi.com',
        'action': 'DescribeStrategies',
        'request_class': 'DescribeStrategiesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Strategies',
        'response_total': None,
        'result_key': 'strategies',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud ADVISOR strategies',
        'description': 'Returns ADVISOR strategies visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ADVISOR strategies.',
        'return_total_doc': 'Number of strategies returned (the API reports no total count).',
        'examples': """\
- name: List all strategies
  susunola.tencentcloud.advisor_strategy_info:
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
  susunola.tencentcloud.ags_sandbox_instance_info:
    region: ap-guangzhou

- name: Find sandbox instances by ID
  susunola.tencentcloud.ags_sandbox_instance_info:
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
  susunola.tencentcloud.ame_ktv_robot_info:
    region: ap-guangzhou

- name: Find ktv robots by ID
  susunola.tencentcloud.ame_ktv_robot_info:
    region: ap-guangzhou
    ktv_robot_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'ams_task_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.ams.v20201229',
        'client_module': 'ams_client',
        'client_class': 'AmsClient',
        'sdk_package': 'tencentcloud-sdk-python-ams',
        'endpoint': 'ams.tencentcloudapi.com',
        'action': 'DescribeTasks',
        'request_class': 'DescribeTasksRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Data',
        'response_total': None,
        'result_key': 'tasks',
        'pagination_type': 'token',
        'token_request_field': 'PageToken',
        'token_response_field': 'PageToken',
        'page_size_field': 'Limit',
        'list_over_field': None,
        'short_description': 'Gather information about Tencent Cloud AMS tasks',
        'description': 'Returns AMS tasks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching AMS tasks.',
        'return_total_doc': 'Number of tasks returned (the API reports no total count).',
        'examples': """\
- name: List all tasks
  susunola.tencentcloud.ams_task_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'anicloud_resource_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.anicloud.v20220923',
        'client_module': 'anicloud_client',
        'client_class': 'AnicloudClient',
        'sdk_package': 'tencentcloud-sdk-python-anicloud',
        'endpoint': 'anicloud.tencentcloudapi.com',
        'action': 'QueryResource',
        'request_class': 'QueryResourceRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Resources',
        'response_total': 'Total',
        'result_key': 'resources',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud ANICLOUD resources',
        'description': 'Returns ANICLOUD resources visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ANICLOUD resources.',
        'return_total_doc': 'Number of resources reported by the API.',
        'examples': """\
- name: List all resources
  susunola.tencentcloud.anicloud_resource_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'antiddos_ddos_block_record_info',
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
        'result_key': 'ddos_block_records',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud ANTIDDOS DDoS block records',
        'description': 'Returns ANTIDDOS DDoS block records visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ANTIDDOS DDoS block records.',
        'return_total_doc': 'Number of DDoS block records reported by the API.',
        'examples': """\
- name: List all DDoS block records
  susunola.tencentcloud.antiddos_ddos_block_record_info:
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
  susunola.tencentcloud.ape_auth_user_info:
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
  susunola.tencentcloud.api_product_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'api_gateway_api_key_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.apigateway.v20180808',
        'client_module': 'apigateway_client',
        'client_class': 'ApigatewayClient',
        'sdk_package': 'tencentcloud-sdk-python-apigateway',
        'endpoint': 'apigateway.tencentcloudapi.com',
        'action': 'DescribeApiKeysStatus',
        'request_class': 'DescribeApiKeysStatusRequest',
        'ids': None,
        'filters': {
            'doc': 'APIGATEWAY API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Result.ApiKeySet',
        'response_total': 'Result.TotalCount',
        'result_key': 'api_keys',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud APIGATEWAY api keys',
        'description': 'Returns APIGATEWAY api keys visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching APIGATEWAY api keys.',
        'return_total_doc': 'Number of api keys reported by the API.',
        'examples': """\
- name: List all api keys
  susunola.tencentcloud.api_gateway_api_key_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'api_gateway_service_release_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.apigateway.v20180808',
        'client_module': 'apigateway_client',
        'client_class': 'ApigatewayClient',
        'sdk_package': 'tencentcloud-sdk-python-apigateway',
        'endpoint': 'apigateway.tencentcloudapi.com',
        'action': 'DescribeServiceEnvironmentReleaseHistory',
        'request_class': 'DescribeServiceEnvironmentReleaseHistoryRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'service_id',
                'field': 'ServiceId',
                'type': 'str',
                'required': False,
                'doc': 'Service id. API field C(ServiceId).',
            },
            {
                'name': 'environment_name',
                'field': 'EnvironmentName',
                'type': 'str',
                'required': False,
                'doc': 'Environment name. API field C(EnvironmentName).',
            },
        ],
        'response_items': 'Result.VersionList',
        'response_total': 'Result.TotalCount',
        'result_key': 'service_environment_release_histories',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud APIGATEWAY service environment release histories',
        'description': 'Returns APIGATEWAY service environment release histories visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching APIGATEWAY service environment release histories.',
        'return_total_doc': 'Number of service environment release histories reported by the API.',
        'examples': """\
- name: List all service environment release histories
  susunola.tencentcloud.api_gateway_service_release_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'api_gateway_usage_plan_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.apigateway.v20180808',
        'client_module': 'apigateway_client',
        'client_class': 'ApigatewayClient',
        'sdk_package': 'tencentcloud-sdk-python-apigateway',
        'endpoint': 'apigateway.tencentcloudapi.com',
        'action': 'DescribeUsagePlansStatus',
        'request_class': 'DescribeUsagePlansStatusRequest',
        'ids': None,
        'filters': {
            'doc': 'APIGATEWAY API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Result.UsagePlanStatusSet',
        'response_total': 'Result.TotalCount',
        'result_key': 'usage_plans',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud APIGATEWAY usage plans',
        'description': 'Returns APIGATEWAY usage plans visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching APIGATEWAY usage plans.',
        'return_total_doc': 'Number of usage plans reported by the API.',
        'examples': """\
- name: List all usage plans
  susunola.tencentcloud.api_gateway_usage_plan_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'api_gateway_usage_plan_binding_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.apigateway.v20180808',
        'client_module': 'apigateway_client',
        'client_class': 'ApigatewayClient',
        'sdk_package': 'tencentcloud-sdk-python-apigateway',
        'endpoint': 'apigateway.tencentcloudapi.com',
        'action': 'DescribeServiceUsagePlan',
        'request_class': 'DescribeServiceUsagePlanRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'service_id',
                'field': 'ServiceId',
                'type': 'str',
                'required': False,
                'doc': 'Service id. API field C(ServiceId).',
            },
        ],
        'response_items': 'Result.ServiceUsagePlanList',
        'response_total': 'Result.TotalCount',
        'result_key': 'service_usage_plans',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud APIGATEWAY service usage plans',
        'description': 'Returns APIGATEWAY service usage plans visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching APIGATEWAY service usage plans.',
        'return_total_doc': 'Number of service usage plans reported by the API.',
        'examples': """\
- name: List all service usage plans
  susunola.tencentcloud.api_gateway_usage_plan_binding_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'api_gateway_usage_plan_key_binding_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.apigateway.v20180808',
        'client_module': 'apigateway_client',
        'client_class': 'ApigatewayClient',
        'sdk_package': 'tencentcloud-sdk-python-apigateway',
        'endpoint': 'apigateway.tencentcloudapi.com',
        'action': 'DescribeUsagePlanSecretIds',
        'request_class': 'DescribeUsagePlanSecretIdsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'usage_plan_id',
                'field': 'UsagePlanId',
                'type': 'str',
                'required': False,
                'doc': 'Usage plan id. API field C(UsagePlanId).',
            },
        ],
        'response_items': 'Result.AccessKeyList',
        'response_total': 'Result.TotalCount',
        'result_key': 'usage_plan_secret_ids',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud APIGATEWAY usage plan secret ids',
        'description': 'Returns APIGATEWAY usage plan secret ids visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching APIGATEWAY usage plan secret ids.',
        'return_total_doc': 'Number of usage plan secret ids reported by the API.',
        'examples': """\
- name: List all usage plan secret ids
  susunola.tencentcloud.api_gateway_usage_plan_key_binding_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'apigateway_api_app_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.apigateway.v20180808',
        'client_module': 'apigateway_client',
        'client_class': 'ApigatewayClient',
        'sdk_package': 'tencentcloud-sdk-python-apigateway',
        'endpoint': 'apigateway.tencentcloudapi.com',
        'action': 'DescribeApiAppsStatus',
        'request_class': 'DescribeApiAppsStatusRequest',
        'ids': None,
        'filters': {
            'doc': 'APIGATEWAY API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Result.ApiAppSet',
        'response_total': 'Result.TotalCount',
        'result_key': 'api_apps',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud APIGATEWAY api apps',
        'description': 'Returns APIGATEWAY api apps visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching APIGATEWAY api apps.',
        'return_total_doc': 'Number of api apps reported by the API.',
        'examples': """\
- name: List all api apps
  susunola.tencentcloud.apigateway_api_app_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'apigateway_ip_strategy_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.apigateway.v20180808',
        'client_module': 'apigateway_client',
        'client_class': 'ApigatewayClient',
        'sdk_package': 'tencentcloud-sdk-python-apigateway',
        'endpoint': 'apigateway.tencentcloudapi.com',
        'action': 'DescribeIPStrategysStatus',
        'request_class': 'DescribeIPStrategysStatusRequest',
        'ids': None,
        'filters': {
            'doc': 'APIGATEWAY API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'service_id',
                'field': 'ServiceId',
                'type': 'str',
                'required': False,
                'doc': 'Service id. API field C(ServiceId).',
            },
        ],
        'response_items': 'Result.StrategySet',
        'response_total': 'Result.TotalCount',
        'result_key': 'ip_strategies',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud APIGATEWAY ip strategies',
        'description': 'Returns APIGATEWAY ip strategies visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching APIGATEWAY ip strategies.',
        'return_total_doc': 'Number of ip strategies reported by the API.',
        'examples': """\
- name: List all ip strategies
  susunola.tencentcloud.apigateway_ip_strategy_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'apigateway_plugin_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.apigateway.v20180808',
        'client_module': 'apigateway_client',
        'client_class': 'ApigatewayClient',
        'sdk_package': 'tencentcloud-sdk-python-apigateway',
        'endpoint': 'apigateway.tencentcloudapi.com',
        'action': 'DescribePlugins',
        'request_class': 'DescribePluginsRequest',
        'ids': {
            'param': 'plugin_ids',
            'field': 'PluginIds',
            'doc': 'Plugin IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'APIGATEWAY API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'plugin_name',
                'field': 'PluginName',
                'type': 'str',
                'required': False,
                'doc': 'Plugin name. API field C(PluginName).',
            },
            {
                'name': 'plugin_type',
                'field': 'PluginType',
                'type': 'str',
                'required': False,
                'doc': 'Plugin type. API field C(PluginType).',
            },
        ],
        'response_items': 'Result.PluginSet',
        'response_total': 'Result.TotalCount',
        'result_key': 'plugins',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud APIGATEWAY plugins',
        'description': 'Returns APIGATEWAY plugins visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching APIGATEWAY plugins.',
        'return_total_doc': 'Number of plugins reported by the API.',
        'examples': """\
- name: List all plugins
  susunola.tencentcloud.apigateway_plugin_info:
    region: ap-guangzhou

- name: Find plugins by ID
  susunola.tencentcloud.apigateway_plugin_info:
    region: ap-guangzhou
    plugin_ids: [x-xxxxxxxx]
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
  susunola.tencentcloud.apis_agent_app_mcp_server_info:
    region: ap-guangzhou

- name: Find agent app mcp servers by ID
  susunola.tencentcloud.apis_agent_app_mcp_server_info:
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
  susunola.tencentcloud.apm_general_span_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'asr_async_recognition_task_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.asr.v20190614',
        'client_module': 'asr_client',
        'client_class': 'AsrClient',
        'sdk_package': 'tencentcloud-sdk-python-asr',
        'endpoint': 'asr.tencentcloudapi.com',
        'action': 'DescribeAsyncRecognitionTasks',
        'request_class': 'DescribeAsyncRecognitionTasksRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Data.Tasks',
        'response_total': None,
        'result_key': 'async_recognition_tasks',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud ASR async recognition tasks',
        'description': 'Returns ASR async recognition tasks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ASR async recognition tasks.',
        'return_total_doc': 'Number of async recognition tasks returned (the API reports no total count).',
        'examples': """\
- name: List all async recognition tasks
  susunola.tencentcloud.asr_async_recognition_task_info:
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
  susunola.tencentcloud.asw_flow_service_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'as_scaling_policy_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.autoscaling.v20180419',
        'client_module': 'autoscaling_client',
        'client_class': 'AutoscalingClient',
        'sdk_package': 'tencentcloud-sdk-python-autoscaling',
        'endpoint': 'as.tencentcloudapi.com',
        'action': 'DescribeScalingPolicies',
        'request_class': 'DescribeScalingPoliciesRequest',
        'ids': {
            'param': 'scaling_policy_ids',
            'field': 'AutoScalingPolicyIds',
            'doc': 'Scaling policy IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'AUTOSCALING API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'ScalingPolicySet',
        'response_total': 'TotalCount',
        'result_key': 'scaling_policies',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud AUTOSCALING scaling policies',
        'description': 'Returns AUTOSCALING scaling policies visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching AUTOSCALING scaling policies.',
        'return_total_doc': 'Number of scaling policies reported by the API.',
        'examples': """\
- name: List all scaling policies
  susunola.tencentcloud.as_scaling_policy_info:
    region: ap-guangzhou

- name: Find scaling policies by ID
  susunola.tencentcloud.as_scaling_policy_info:
    region: ap-guangzhou
    scaling_policy_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'as_scheduled_action_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.autoscaling.v20180419',
        'client_module': 'autoscaling_client',
        'client_class': 'AutoscalingClient',
        'sdk_package': 'tencentcloud-sdk-python-autoscaling',
        'endpoint': 'as.tencentcloudapi.com',
        'action': 'DescribeScheduledActions',
        'request_class': 'DescribeScheduledActionsRequest',
        'ids': {
            'param': 'scheduled_action_ids',
            'field': 'ScheduledActionIds',
            'doc': 'Scheduled action IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'AUTOSCALING API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'ScheduledActionSet',
        'response_total': 'TotalCount',
        'result_key': 'scheduled_actions',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud AUTOSCALING scheduled actions',
        'description': 'Returns AUTOSCALING scheduled actions visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching AUTOSCALING scheduled actions.',
        'return_total_doc': 'Number of scheduled actions reported by the API.',
        'examples': """\
- name: List all scheduled actions
  susunola.tencentcloud.as_scheduled_action_info:
    region: ap-guangzhou

- name: Find scheduled actions by ID
  susunola.tencentcloud.as_scheduled_action_info:
    region: ap-guangzhou
    scheduled_action_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'ba_auth_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.ba.v20200720',
        'client_module': 'ba_client',
        'client_class': 'BaClient',
        'sdk_package': 'tencentcloud-sdk-python-ba',
        'endpoint': 'ba.tencentcloudapi.com',
        'action': 'DescribeGetAuthInfo',
        'request_class': 'DescribeGetAuthInfoRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': None,
        'response_total': None,
        'result_key': 'auth',
        'pagination_type': 'none',
        'short_description': 'Gather information about Tencent Cloud BA auth',
        'description': 'Returns BA auth visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching BA auth.',
        'return_total_doc': '',
        'examples': """\
- name: Show the auth
  susunola.tencentcloud.ba_auth_info:
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
  susunola.tencentcloud.batch_compute_env_create_info:
    region: ap-guangzhou

- name: Find compute env creates by ID
  susunola.tencentcloud.batch_compute_env_create_info:
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
  susunola.tencentcloud.bdrc_backup_vault_info:
    region: ap-guangzhou

- name: Find backup vaults by ID
  susunola.tencentcloud.bdrc_backup_vault_info:
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
  susunola.tencentcloud.bh_device_group_member_info:
    region: ap-guangzhou

- name: Find device group members by ID
  susunola.tencentcloud.bh_device_group_member_info:
    region: ap-guangzhou
    device_group_member_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'bi_auth_api_key_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.bi.v20220105',
        'client_module': 'bi_client',
        'client_class': 'BiClient',
        'sdk_package': 'tencentcloud-sdk-python-bi',
        'endpoint': 'bi.tencentcloudapi.com',
        'action': 'DescribeAuthApiKeyList',
        'request_class': 'DescribeAuthApiKeyListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Data.List',
        'response_total': 'Data.Total',
        'result_key': 'auth_api_keys',
        'pagination_type': 'page',
        'page_number_field': 'PageNo',
        'short_description': 'Gather information about Tencent Cloud BI auth api keys',
        'description': 'Returns BI auth api keys visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching BI auth api keys.',
        'return_total_doc': 'Number of auth api keys reported by the API.',
        'examples': """\
- name: List all auth api keys
  susunola.tencentcloud.bi_auth_api_key_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'bizlive_worker_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.bizlive.v20190313',
        'client_module': 'bizlive_client',
        'client_class': 'BizliveClient',
        'sdk_package': 'tencentcloud-sdk-python-bizlive',
        'endpoint': 'bizlive.tencentcloudapi.com',
        'action': 'DescribeWorkers',
        'request_class': 'DescribeWorkersRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'RegionDetail',
        'response_total': None,
        'result_key': 'workers',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud BIZLIVE workers',
        'description': 'Returns BIZLIVE workers visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching BIZLIVE workers.',
        'return_total_doc': 'Number of workers returned (the API reports no total count).',
        'examples': """\
- name: List all workers
  susunola.tencentcloud.bizlive_worker_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.bm_device_info:
    region: ap-guangzhou

- name: Find devices by ID
  susunola.tencentcloud.bm_device_info:
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
  susunola.tencentcloud.bma_bp_fake_app_info:
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
  susunola.tencentcloud.bmeip_eip_acl_info:
    region: ap-guangzhou

- name: Find eip acls by ID
  susunola.tencentcloud.bmeip_eip_acl_info:
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
  susunola.tencentcloud.bmlb_load_balancer_info:
    region: ap-guangzhou

- name: Find load balancers by ID
  susunola.tencentcloud.bmlb_load_balancer_info:
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
  susunola.tencentcloud.bmvpc_customer_gateway_info:
    region: ap-guangzhou

- name: Find customer gateways by ID
  susunola.tencentcloud.bmvpc_customer_gateway_info:
    region: ap-guangzhou
    customer_gateway_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'bsca_kb_component_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.bsca.v20210811',
        'client_module': 'bsca_client',
        'client_class': 'BscaClient',
        'sdk_package': 'tencentcloud-sdk-python-bsca',
        'endpoint': 'bsca.tencentcloudapi.com',
        'action': 'SearchKBComponent',
        'request_class': 'SearchKBComponentRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'ComponentList',
        'response_total': 'Total',
        'result_key': 'kb_components',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud BSCA kb components',
        'description': 'Returns BSCA kb components visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching BSCA kb components.',
        'return_total_doc': 'Number of kb components reported by the API.',
        'examples': """\
- name: List all kb components
  susunola.tencentcloud.bsca_kb_component_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'captcha_user_all_app_id_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.captcha.v20190722',
        'client_module': 'captcha_client',
        'client_class': 'CaptchaClient',
        'sdk_package': 'tencentcloud-sdk-python-captcha',
        'endpoint': 'captcha.tencentcloudapi.com',
        'action': 'DescribeCaptchaUserAllAppId',
        'request_class': 'DescribeCaptchaUserAllAppIdRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Data',
        'response_total': None,
        'result_key': 'user_all_app_ids',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CAPTCHA user all app ids',
        'description': 'Returns CAPTCHA user all app ids visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CAPTCHA user all app ids.',
        'return_total_doc': 'Number of user all app ids reported by the API.',
        'examples': """\
- name: List all user all app ids
  susunola.tencentcloud.captcha_user_all_app_id_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.cat_probe_task_info:
    region: ap-guangzhou

- name: Find probe tasks by ID
  susunola.tencentcloud.cat_probe_task_info:
    region: ap-guangzhou
    probe_task_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cbs_disk_backup_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cbs.v20170312',
        'client_module': 'cbs_client',
        'client_class': 'CbsClient',
        'sdk_package': 'tencentcloud-sdk-python-cbs',
        'endpoint': 'cbs.tencentcloudapi.com',
        'action': 'DescribeDiskBackups',
        'request_class': 'DescribeDiskBackupsRequest',
        'ids': {
            'param': 'disk_backup_ids',
            'field': 'DiskBackupIds',
            'doc': 'Disk backup IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'CBS API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'order',
                'field': 'Order',
                'type': 'str',
                'required': False,
                'doc': 'Order. API field C(Order).',
            },
            {
                'name': 'order_field',
                'field': 'OrderField',
                'type': 'str',
                'required': False,
                'doc': 'Order field. API field C(OrderField).',
            },
        ],
        'response_items': 'DiskBackupSet',
        'response_total': 'TotalCount',
        'result_key': 'disk_backups',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CBS disk backups',
        'description': 'Returns CBS disk backups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CBS disk backups.',
        'return_total_doc': 'Number of disk backups reported by the API.',
        'examples': """\
- name: List all disk backups
  susunola.tencentcloud.cbs_disk_backup_info:
    region: ap-guangzhou

- name: Find disk backups by ID
  susunola.tencentcloud.cbs_disk_backup_info:
    region: ap-guangzhou
    disk_backup_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cbs_snapshot_share_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cbs.v20170312',
        'client_module': 'cbs_client',
        'client_class': 'CbsClient',
        'sdk_package': 'tencentcloud-sdk-python-cbs',
        'endpoint': 'cbs.tencentcloudapi.com',
        'action': 'DescribeSnapshotSharePermission',
        'request_class': 'DescribeSnapshotSharePermissionRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'snapshot_id',
                'field': 'SnapshotId',
                'type': 'str',
                'required': False,
                'doc': 'Snapshot id. API field C(SnapshotId).',
            },
        ],
        'response_items': 'SharePermissionSet',
        'response_total': None,
        'result_key': 'snapshot_share_permissions',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CBS snapshot share permissions',
        'description': 'Returns CBS snapshot share permissions visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CBS snapshot share permissions.',
        'return_total_doc': 'Number of snapshot share permissions returned (the API reports no total count).',
        'examples': """\
- name: List all snapshot share permissions
  susunola.tencentcloud.cbs_snapshot_share_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.ccc_extension_info:
    region: ap-guangzhou

- name: Find extensions by ID
  susunola.tencentcloud.ccc_extension_info:
    region: ap-guangzhou
    extension_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cdb_audit_rule_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdb.v20170320',
        'client_module': 'cdb_client',
        'client_class': 'CdbClient',
        'sdk_package': 'tencentcloud-sdk-python-cdb',
        'endpoint': 'cdb.tencentcloudapi.com',
        'action': 'DescribeAuditRules',
        'request_class': 'DescribeAuditRulesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'rule_id',
                'field': 'RuleId',
                'type': 'str',
                'required': False,
                'doc': 'Rule id. API field C(RuleId).',
            },
            {
                'name': 'rule_name',
                'field': 'RuleName',
                'type': 'str',
                'required': False,
                'doc': 'Rule name. API field C(RuleName).',
            },
        ],
        'response_items': 'Items',
        'response_total': 'TotalCount',
        'result_key': 'audit_rules',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CDB audit rules',
        'description': 'Returns CDB audit rules visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDB audit rules.',
        'return_total_doc': 'Number of audit rules reported by the API.',
        'examples': """\
- name: List all audit rules
  susunola.tencentcloud.cdb_audit_rule_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdb_audit_rule_template_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdb.v20170320',
        'client_module': 'cdb_client',
        'client_class': 'CdbClient',
        'sdk_package': 'tencentcloud-sdk-python-cdb',
        'endpoint': 'cdb.tencentcloudapi.com',
        'action': 'DescribeAuditRuleTemplates',
        'request_class': 'DescribeAuditRuleTemplatesRequest',
        'ids': {
            'param': 'audit_rule_template_ids',
            'field': 'RuleTemplateIds',
            'doc': 'Audit rule template IDs to return.',
        },
        'filters': None,
        'extra_params': [
            {
                'name': 'rule_template_names',
                'field': 'RuleTemplateNames',
                'type': 'list',
                'required': False,
                'doc': 'Rule template names. API field C(RuleTemplateNames).',
                'elements': 'str',
            },
            {
                'name': 'alarm_level',
                'field': 'AlarmLevel',
                'type': 'int',
                'required': False,
                'doc': 'Alarm level. API field C(AlarmLevel).',
            },
            {
                'name': 'alarm_policy',
                'field': 'AlarmPolicy',
                'type': 'int',
                'required': False,
                'doc': 'Alarm policy. API field C(AlarmPolicy).',
            },
        ],
        'response_items': 'Items',
        'response_total': 'TotalCount',
        'result_key': 'audit_rule_templates',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CDB audit rule templates',
        'description': 'Returns CDB audit rule templates visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDB audit rule templates.',
        'return_total_doc': 'Number of audit rule templates reported by the API.',
        'examples': """\
- name: List all audit rule templates
  susunola.tencentcloud.cdb_audit_rule_template_info:
    region: ap-guangzhou

- name: Find audit rule templates by ID
  susunola.tencentcloud.cdb_audit_rule_template_info:
    region: ap-guangzhou
    audit_rule_template_ids: [x-xxxxxxxx]
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
  susunola.tencentcloud.cdc_dedicated_cluster_order_info:
    region: ap-guangzhou

- name: Find dedicated cluster orders by ID
  susunola.tencentcloud.cdc_dedicated_cluster_order_info:
    region: ap-guangzhou
    dedicated_cluster_order_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cdn_cls_log_topic_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdn.v20180606',
        'client_module': 'cdn_client',
        'client_class': 'CdnClient',
        'sdk_package': 'tencentcloud-sdk-python-cdn',
        'endpoint': 'cdn.tencentcloudapi.com',
        'action': 'ListClsLogTopics',
        'request_class': 'ListClsLogTopicsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'channel',
                'field': 'Channel',
                'type': 'str',
                'required': False,
                'doc': 'Channel. API field C(Channel).',
            },
        ],
        'response_items': 'Topics',
        'response_total': None,
        'result_key': 'cls_log_topics',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CDN cls log topics',
        'description': 'Returns CDN cls log topics visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDN cls log topics.',
        'return_total_doc': 'Number of cls log topics returned (the API reports no total count).',
        'examples': """\
- name: List all cls log topics
  susunola.tencentcloud.cdn_cls_log_topic_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.cds_asset_info:
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
  susunola.tencentcloud.cdwch_cn_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdwch_instance_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdwch.v20200915',
        'client_module': 'cdwch_client',
        'client_class': 'CdwchClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwch',
        'endpoint': 'cdwch.tencentcloudapi.com',
        'action': 'DescribeCNInstances',
        'request_class': 'DescribeCNInstancesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'search_instance_id',
                'field': 'SearchInstanceID',
                'type': 'str',
                'required': False,
                'doc': 'Search instance id. API field C(SearchInstanceID).',
            },
            {
                'name': 'search_instance_name',
                'field': 'SearchInstanceName',
                'type': 'str',
                'required': False,
                'doc': 'Search instance name. API field C(SearchInstanceName).',
            },
            {
                'name': 'instance_type',
                'field': 'InstanceType',
                'type': 'str',
                'required': False,
                'doc': 'Instance type. API field C(InstanceType).',
            },
            {
                'name': 'components',
                'field': 'Components',
                'type': 'list',
                'required': False,
                'doc': 'Components. API field C(Components).',
                'elements': 'str',
            },
        ],
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
  susunola.tencentcloud.cdwch_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdwch_backup_config_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdwch.v20200915',
        'client_module': 'cdwch_client',
        'client_class': 'CdwchClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwch',
        'endpoint': 'cdwch.tencentcloudapi.com',
        'action': 'DescribeBackUpSchedule',
        'request_class': 'DescribeBackUpScheduleRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': 'BackUpContents',
        'response_total': None,
        'result_key': 'backup_configs',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CDWCH backup configs',
        'description': 'Returns CDWCH backup configs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDWCH backup configs.',
        'return_total_doc': 'Number of backup configs returned (the API reports no total count).',
        'examples': """\
- name: List all backup configs
  susunola.tencentcloud.cdwch_backup_config_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdwch_parameter_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdwch.v20200915',
        'client_module': 'cdwch_client',
        'client_class': 'CdwchClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwch',
        'endpoint': 'cdwch.tencentcloudapi.com',
        'action': 'DescribeInstanceKeyValConfigs',
        'request_class': 'DescribeInstanceKeyValConfigsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'search_config_name',
                'field': 'SearchConfigName',
                'type': 'str',
                'required': False,
                'doc': 'Search config name. API field C(SearchConfigName).',
            },
        ],
        'response_items': 'ConfigItems',
        'response_total': None,
        'result_key': 'parameters',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CDWCH parameters',
        'description': 'Returns CDWCH parameters visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDWCH parameters.',
        'return_total_doc': 'Number of parameters returned (the API reports no total count).',
        'examples': """\
- name: List all parameters
  susunola.tencentcloud.cdwch_parameter_info:
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
  susunola.tencentcloud.cdwdoris_cluster_configs_history_info:
    region: ap-guangzhou

- name: Find cluster configs histories by ID
  susunola.tencentcloud.cdwdoris_cluster_configs_history_info:
    region: ap-guangzhou
    cluster_configs_history_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cdwdoris_cooldown_policy_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdwdoris.v20211228',
        'client_module': 'cdwdoris_client',
        'client_class': 'CdwdorisClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwdoris',
        'endpoint': 'cdwdoris.tencentcloudapi.com',
        'action': 'DescribeCoolDownPolicies',
        'request_class': 'DescribeCoolDownPoliciesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': 'List',
        'response_total': None,
        'result_key': 'cool_down_policies',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CDWDORIS cool down policies',
        'description': 'Returns CDWDORIS cool down policies visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDWDORIS cool down policies.',
        'return_total_doc': 'Number of cool down policies returned (the API reports no total count).',
        'examples': """\
- name: List all cool down policies
  susunola.tencentcloud.cdwdoris_cooldown_policy_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdwdoris_instance_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdwdoris.v20211228',
        'client_module': 'cdwdoris_client',
        'client_class': 'CdwdorisClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwdoris',
        'endpoint': 'cdwdoris.tencentcloudapi.com',
        'action': 'DescribeInstances',
        'request_class': 'DescribeInstancesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'search_instance_id',
                'field': 'SearchInstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Search instance id. API field C(SearchInstanceId).',
            },
            {
                'name': 'search_instance_name',
                'field': 'SearchInstanceName',
                'type': 'str',
                'required': False,
                'doc': 'Search instance name. API field C(SearchInstanceName).',
            },
            {
                'name': 'instance_type',
                'field': 'InstanceType',
                'type': 'int',
                'required': False,
                'doc': 'Instance type. API field C(InstanceType).',
            },
        ],
        'response_items': 'InstancesList',
        'response_total': 'TotalCount',
        'result_key': 'instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CDWDORIS instances',
        'description': 'Returns CDWDORIS instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDWDORIS instances.',
        'return_total_doc': 'Number of instances reported by the API.',
        'examples': """\
- name: List all instances
  susunola.tencentcloud.cdwdoris_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdwdoris_user_workload_group_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdwdoris.v20211228',
        'client_module': 'cdwdoris_client',
        'client_class': 'CdwdorisClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwdoris',
        'endpoint': 'cdwdoris.tencentcloudapi.com',
        'action': 'DescribeUserBindWorkloadGroup',
        'request_class': 'DescribeUserBindWorkloadGroupRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': 'UserBindInfos',
        'response_total': None,
        'result_key': 'user_bind_workload_groups',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CDWDORIS user bind workload groups',
        'description': 'Returns CDWDORIS user bind workload groups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDWDORIS user bind workload groups.',
        'return_total_doc': 'Number of user bind workload groups returned (the API reports no total count).',
        'examples': """\
- name: List all user bind workload groups
  susunola.tencentcloud.cdwdoris_user_workload_group_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdwdoris_workload_group_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdwdoris.v20211228',
        'client_module': 'cdwdoris_client',
        'client_class': 'CdwdorisClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwdoris',
        'endpoint': 'cdwdoris.tencentcloudapi.com',
        'action': 'DescribeWorkloadGroup',
        'request_class': 'DescribeWorkloadGroupRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': 'WorkloadGroups',
        'response_total': None,
        'result_key': 'workload_groups',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CDWDORIS workload groups',
        'description': 'Returns CDWDORIS workload groups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDWDORIS workload groups.',
        'return_total_doc': 'Number of workload groups returned (the API reports no total count).',
        'examples': """\
- name: List all workload groups
  susunola.tencentcloud.cdwdoris_workload_group_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.cdwpg_account_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdwpg_hba_config_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdwpg.v20201230',
        'client_module': 'cdwpg_client',
        'client_class': 'CdwpgClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwpg',
        'endpoint': 'cdwpg.tencentcloudapi.com',
        'action': 'DescribeUserHbaConfig',
        'request_class': 'DescribeUserHbaConfigRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': 'HbaConfigs',
        'response_total': 'TotalCount',
        'result_key': 'user_hba_configs',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CDWPG user hba configs',
        'description': 'Returns CDWPG user hba configs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDWPG user hba configs.',
        'return_total_doc': 'Number of user hba configs reported by the API.',
        'examples': """\
- name: List all user hba configs
  susunola.tencentcloud.cdwpg_hba_config_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdwpg_instance_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdwpg.v20201230',
        'client_module': 'cdwpg_client',
        'client_class': 'CdwpgClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwpg',
        'endpoint': 'cdwpg.tencentcloudapi.com',
        'action': 'DescribeInstances',
        'request_class': 'DescribeInstancesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'search_instance_id',
                'field': 'SearchInstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Search instance id. API field C(SearchInstanceId).',
            },
            {
                'name': 'search_instance_name',
                'field': 'SearchInstanceName',
                'type': 'str',
                'required': False,
                'doc': 'Search instance name. API field C(SearchInstanceName).',
            },
        ],
        'response_items': 'InstancesList',
        'response_total': 'TotalCount',
        'result_key': 'instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CDWPG instances',
        'description': 'Returns CDWPG instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDWPG instances.',
        'return_total_doc': 'Number of instances reported by the API.',
        'examples': """\
- name: List all instances
  susunola.tencentcloud.cdwpg_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdwpg_parameter_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cdwpg.v20201230',
        'client_module': 'cdwpg_client',
        'client_class': 'CdwpgClient',
        'sdk_package': 'tencentcloud-sdk-python-cdwpg',
        'endpoint': 'cdwpg.tencentcloudapi.com',
        'action': 'DescribeDBParams',
        'request_class': 'DescribeDBParamsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'node_types',
                'field': 'NodeTypes',
                'type': 'list',
                'required': False,
                'doc': 'Node types. API field C(NodeTypes).',
                'elements': 'str',
            },
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': 'Items',
        'response_total': 'TotalCount',
        'result_key': 'parameters',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CDWPG parameters',
        'description': 'Returns CDWPG parameters visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDWPG parameters.',
        'return_total_doc': 'Number of parameters reported by the API.',
        'examples': """\
- name: List all parameters
  susunola.tencentcloud.cdwpg_parameter_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cdz_cloud_dedicated_zone_host_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.cdz.v20221123',
        'client_module': 'cdz_client',
        'client_class': 'CdzClient',
        'sdk_package': 'tencentcloud-sdk-python-cdz',
        'endpoint': 'cdz.tencentcloudapi.com',
        'action': 'DescribeCloudDedicatedZoneHosts',
        'request_class': 'DescribeCloudDedicatedZoneHostsRequest',
        'ids': {
            'param': 'cloud_dedicated_zone_host_ids',
            'field': 'HostUuids',
            'doc': 'Cloud dedicated zone host IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'CloudDedicatedZoneHostsInfoSet',
        'response_total': None,
        'result_key': 'cloud_dedicated_zone_hosts',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CDZ cloud dedicated zone hosts',
        'description': 'Returns CDZ cloud dedicated zone hosts visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CDZ cloud dedicated zone hosts.',
        'return_total_doc': 'Number of cloud dedicated zone hosts returned (the API reports no total count).',
        'examples': """\
- name: List all cloud dedicated zone hosts
  susunola.tencentcloud.cdz_cloud_dedicated_zone_host_info:
    region: ap-guangzhou

- name: Find cloud dedicated zone hosts by ID
  susunola.tencentcloud.cdz_cloud_dedicated_zone_host_info:
    region: ap-guangzhou
    cloud_dedicated_zone_host_ids: [x-xxxxxxxx]
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
  susunola.tencentcloud.cetcd_etcd_instance_info:
    region: ap-guangzhou

- name: Find etcd instances by ID
  susunola.tencentcloud.cetcd_etcd_instance_info:
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
  susunola.tencentcloud.cfg_action_library_info:
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
  susunola.tencentcloud.cfw_cluster_nat_ccn_fw_switch_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cfw_address_template_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cfw.v20190904',
        'client_module': 'cfw_client',
        'client_class': 'CfwClient',
        'sdk_package': 'tencentcloud-sdk-python-cfw',
        'endpoint': 'cfw.tencentcloudapi.com',
        'action': 'DescribeAddressTemplateList',
        'request_class': 'DescribeAddressTemplateListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'by',
                'field': 'By',
                'type': 'str',
                'required': False,
                'doc': 'By. API field C(By).',
            },
            {
                'name': 'order',
                'field': 'Order',
                'type': 'str',
                'required': False,
                'doc': 'Order. API field C(Order).',
            },
            {
                'name': 'search_value',
                'field': 'SearchValue',
                'type': 'str',
                'required': False,
                'doc': 'Search value. API field C(SearchValue).',
            },
            {
                'name': 'uuid',
                'field': 'Uuid',
                'type': 'str',
                'required': False,
                'doc': 'Uuid. API field C(Uuid).',
            },
            {
                'name': 'template_type',
                'field': 'TemplateType',
                'type': 'str',
                'required': False,
                'doc': 'Template type. API field C(TemplateType).',
            },
            {
                'name': 'template_id',
                'field': 'TemplateId',
                'type': 'str',
                'required': False,
                'doc': 'Template id. API field C(TemplateId).',
            },
        ],
        'response_items': 'Data',
        'response_total': 'Total',
        'result_key': 'address_templates',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CFW address templates',
        'description': 'Returns CFW address templates visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CFW address templates.',
        'return_total_doc': 'Number of address templates reported by the API.',
        'examples': """\
- name: List all address templates
  susunola.tencentcloud.cfw_address_template_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cfw_nat_dnat_rule_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cfw.v20190904',
        'client_module': 'cfw_client',
        'client_class': 'CfwClient',
        'sdk_package': 'tencentcloud-sdk-python-cfw',
        'endpoint': 'cfw.tencentcloudapi.com',
        'action': 'DescribeNatFwDnatRule',
        'request_class': 'DescribeNatFwDnatRuleRequest',
        'ids': None,
        'filters': {
            'doc': 'CFW API filter names mapped to lists of values.',
            'model': 'CommonFilter',
        },
        'extra_params': [
            {
                'name': 'index',
                'field': 'Index',
                'type': 'str',
                'required': False,
                'doc': 'Index. API field C(Index).',
            },
            {
                'name': 'start_time',
                'field': 'StartTime',
                'type': 'str',
                'required': False,
                'doc': 'Start time. API field C(StartTime).',
            },
            {
                'name': 'end_time',
                'field': 'EndTime',
                'type': 'str',
                'required': False,
                'doc': 'End time. API field C(EndTime).',
            },
            {
                'name': 'order',
                'field': 'Order',
                'type': 'str',
                'required': False,
                'doc': 'Order. API field C(Order).',
            },
            {
                'name': 'by',
                'field': 'By',
                'type': 'str',
                'required': False,
                'doc': 'By. API field C(By).',
            },
        ],
        'response_items': 'Data',
        'response_total': 'Total',
        'result_key': 'nat_fw_dnat_rules',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CFW nat fw dnat rules',
        'description': 'Returns CFW nat fw dnat rules visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CFW nat fw dnat rules.',
        'return_total_doc': 'Number of nat fw dnat rules reported by the API.',
        'examples': """\
- name: List all nat fw dnat rules
  susunola.tencentcloud.cfw_nat_dnat_rule_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cfw_internet_acl_rule_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cfw.v20190904',
        'client_module': 'cfw_client',
        'client_class': 'CfwClient',
        'sdk_package': 'tencentcloud-sdk-python-cfw',
        'endpoint': 'cfw.tencentcloudapi.com',
        'action': 'DescribeAclRule',
        'request_class': 'DescribeAclRuleRequest',
        'ids': None,
        'filters': {
            'doc': 'CFW API filter names mapped to lists of values.',
            'model': 'CommonFilter',
        },
        'extra_params': [
            {
                'name': 'index',
                'field': 'Index',
                'type': 'str',
                'required': False,
                'doc': 'Index. API field C(Index).',
            },
            {
                'name': 'start_time',
                'field': 'StartTime',
                'type': 'str',
                'required': False,
                'doc': 'Start time. API field C(StartTime).',
            },
            {
                'name': 'end_time',
                'field': 'EndTime',
                'type': 'str',
                'required': False,
                'doc': 'End time. API field C(EndTime).',
            },
            {
                'name': 'order',
                'field': 'Order',
                'type': 'str',
                'required': False,
                'doc': 'Order. API field C(Order).',
            },
            {
                'name': 'by',
                'field': 'By',
                'type': 'str',
                'required': False,
                'doc': 'By. API field C(By).',
            },
        ],
        'response_items': 'Data',
        'response_total': 'Total',
        'result_key': 'acl_rules',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CFW acl rules',
        'description': 'Returns CFW acl rules visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CFW acl rules.',
        'return_total_doc': 'Number of acl rules reported by the API.',
        'examples': """\
- name: List all acl rules
  susunola.tencentcloud.cfw_internet_acl_rule_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cfw_nat_acl_rule_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cfw.v20190904',
        'client_module': 'cfw_client',
        'client_class': 'CfwClient',
        'sdk_package': 'tencentcloud-sdk-python-cfw',
        'endpoint': 'cfw.tencentcloudapi.com',
        'action': 'DescribeNatAcRule',
        'request_class': 'DescribeNatAcRuleRequest',
        'ids': None,
        'filters': {
            'doc': 'CFW API filter names mapped to lists of values.',
            'model': 'CommonFilter',
        },
        'extra_params': [
            {
                'name': 'index',
                'field': 'Index',
                'type': 'str',
                'required': False,
                'doc': 'Index. API field C(Index).',
            },
            {
                'name': 'start_time',
                'field': 'StartTime',
                'type': 'str',
                'required': False,
                'doc': 'Start time. API field C(StartTime).',
            },
            {
                'name': 'end_time',
                'field': 'EndTime',
                'type': 'str',
                'required': False,
                'doc': 'End time. API field C(EndTime).',
            },
            {
                'name': 'order',
                'field': 'Order',
                'type': 'str',
                'required': False,
                'doc': 'Order. API field C(Order).',
            },
            {
                'name': 'by',
                'field': 'By',
                'type': 'str',
                'required': False,
                'doc': 'By. API field C(By).',
            },
        ],
        'response_items': 'Data',
        'response_total': 'Total',
        'result_key': 'nat_ac_rules',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CFW nat ac rules',
        'description': 'Returns CFW nat ac rules visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CFW nat ac rules.',
        'return_total_doc': 'Number of nat ac rules reported by the API.',
        'examples': """\
- name: List all nat ac rules
  susunola.tencentcloud.cfw_nat_acl_rule_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cfw_vpc_acl_rule_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cfw.v20190904',
        'client_module': 'cfw_client',
        'client_class': 'CfwClient',
        'sdk_package': 'tencentcloud-sdk-python-cfw',
        'endpoint': 'cfw.tencentcloudapi.com',
        'action': 'DescribeVpcAcRule',
        'request_class': 'DescribeVpcAcRuleRequest',
        'ids': None,
        'filters': {
            'doc': 'CFW API filter names mapped to lists of values.',
            'model': 'CommonFilter',
        },
        'extra_params': [
            {
                'name': 'index',
                'field': 'Index',
                'type': 'str',
                'required': False,
                'doc': 'Index. API field C(Index).',
            },
            {
                'name': 'start_time',
                'field': 'StartTime',
                'type': 'str',
                'required': False,
                'doc': 'Start time. API field C(StartTime).',
            },
            {
                'name': 'end_time',
                'field': 'EndTime',
                'type': 'str',
                'required': False,
                'doc': 'End time. API field C(EndTime).',
            },
            {
                'name': 'order',
                'field': 'Order',
                'type': 'str',
                'required': False,
                'doc': 'Order. API field C(Order).',
            },
            {
                'name': 'by',
                'field': 'By',
                'type': 'str',
                'required': False,
                'doc': 'By. API field C(By).',
            },
        ],
        'response_items': 'Data',
        'response_total': 'Total',
        'result_key': 'vpc_ac_rules',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CFW vpc ac rules',
        'description': 'Returns CFW vpc ac rules visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CFW vpc ac rules.',
        'return_total_doc': 'Number of vpc ac rules reported by the API.',
        'examples': """\
- name: List all vpc ac rules
  susunola.tencentcloud.cfw_vpc_acl_rule_info:
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
  susunola.tencentcloud.chc_device_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'chdfs_file_system_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.chdfs.v20201112',
        'client_module': 'chdfs_client',
        'client_class': 'ChdfsClient',
        'sdk_package': 'tencentcloud-sdk-python-chdfs',
        'endpoint': 'chdfs.tencentcloudapi.com',
        'action': 'DescribeFileSystems',
        'request_class': 'DescribeFileSystemsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'FileSystems',
        'response_total': None,
        'result_key': 'file_systems',
        'pagination_type': 'token',
        'token_request_field': 'FileSystemIdMarker',
        'token_response_field': 'NextFileSystemIdMarker',
        'page_size_field': None,
        'list_over_field': 'IsOver',
        'short_description': 'Gather information about Tencent Cloud CHDFS file systems',
        'description': 'Returns CHDFS file systems visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CHDFS file systems.',
        'return_total_doc': 'Number of file systems returned (the API reports no total count).',
        'examples': """\
- name: List all file systems
  susunola.tencentcloud.chdfs_file_system_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'chdfs_access_group_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.chdfs.v20201112',
        'client_module': 'chdfs_client',
        'client_class': 'ChdfsClient',
        'sdk_package': 'tencentcloud-sdk-python-chdfs',
        'endpoint': 'chdfs.tencentcloudapi.com',
        'action': 'DescribeAccessGroups',
        'request_class': 'DescribeAccessGroupsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'vpc_id',
                'field': 'VpcId',
                'type': 'str',
                'required': False,
                'doc': 'Vpc id. API field C(VpcId).',
            },
            {
                'name': 'owner_uin',
                'field': 'OwnerUin',
                'type': 'int',
                'required': False,
                'doc': 'Owner uin. API field C(OwnerUin).',
            },
        ],
        'response_items': 'AccessGroups',
        'response_total': None,
        'result_key': 'access_groups',
        'pagination_type': 'token',
        'token_request_field': 'AccessGroupIdMarker',
        'token_response_field': 'NextAccessGroupIdMarker',
        'page_size_field': None,
        'list_over_field': 'IsOver',
        'short_description': 'Gather information about Tencent Cloud CHDFS access groups',
        'description': 'Returns CHDFS access groups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CHDFS access groups.',
        'return_total_doc': 'Number of access groups returned (the API reports no total count).',
        'examples': """\
- name: List all access groups
  susunola.tencentcloud.chdfs_access_group_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'chdfs_access_rules_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.chdfs.v20201112',
        'client_module': 'chdfs_client',
        'client_class': 'ChdfsClient',
        'sdk_package': 'tencentcloud-sdk-python-chdfs',
        'endpoint': 'chdfs.tencentcloudapi.com',
        'action': 'DescribeAccessRules',
        'request_class': 'DescribeAccessRulesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'access_group_id',
                'field': 'AccessGroupId',
                'type': 'str',
                'required': False,
                'doc': 'Access group id. API field C(AccessGroupId).',
            },
        ],
        'response_items': 'AccessRules',
        'response_total': None,
        'result_key': 'access_rules',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CHDFS access rules',
        'description': 'Returns CHDFS access rules visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CHDFS access rules.',
        'return_total_doc': 'Number of access rules returned (the API reports no total count).',
        'examples': """\
- name: List all access rules
  susunola.tencentcloud.chdfs_access_rules_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'chdfs_mount_point_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.chdfs.v20201112',
        'client_module': 'chdfs_client',
        'client_class': 'ChdfsClient',
        'sdk_package': 'tencentcloud-sdk-python-chdfs',
        'endpoint': 'chdfs.tencentcloudapi.com',
        'action': 'DescribeMountPoints',
        'request_class': 'DescribeMountPointsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'file_system_id',
                'field': 'FileSystemId',
                'type': 'str',
                'required': False,
                'doc': 'File system id. API field C(FileSystemId).',
            },
            {
                'name': 'access_group_id',
                'field': 'AccessGroupId',
                'type': 'str',
                'required': False,
                'doc': 'Access group id. API field C(AccessGroupId).',
            },
            {
                'name': 'owner_uin',
                'field': 'OwnerUin',
                'type': 'int',
                'required': False,
                'doc': 'Owner uin. API field C(OwnerUin).',
            },
        ],
        'response_items': 'MountPoints',
        'response_total': None,
        'result_key': 'mount_points',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CHDFS mount points',
        'description': 'Returns CHDFS mount points visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CHDFS mount points.',
        'return_total_doc': 'Number of mount points returned (the API reports no total count).',
        'examples': """\
- name: List all mount points
  susunola.tencentcloud.chdfs_mount_point_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ciam_user_store_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.ciam.v20220331',
        'client_module': 'ciam_client',
        'client_class': 'CiamClient',
        'sdk_package': 'tencentcloud-sdk-python-ciam',
        'endpoint': 'ciam.tencentcloudapi.com',
        'action': 'ListUserStore',
        'request_class': 'ListUserStoreRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'UserStoreSet',
        'response_total': None,
        'result_key': 'user_stores',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CIAM user stores',
        'description': 'Returns CIAM user stores visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CIAM user stores.',
        'return_total_doc': 'Number of user stores returned (the API reports no total count).',
        'examples': """\
- name: List all user stores
  susunola.tencentcloud.ciam_user_store_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ckafka_acl_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.ckafka.v20190819',
        'client_module': 'ckafka_client',
        'client_class': 'CkafkaClient',
        'sdk_package': 'tencentcloud-sdk-python-ckafka',
        'endpoint': 'ckafka.tencentcloudapi.com',
        'action': 'DescribeACL',
        'request_class': 'DescribeACLRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'resource_type',
                'field': 'ResourceType',
                'type': 'int',
                'required': False,
                'doc': 'Resource type. API field C(ResourceType).',
            },
            {
                'name': 'resource_name',
                'field': 'ResourceName',
                'type': 'str',
                'required': False,
                'doc': 'Resource name. API field C(ResourceName).',
            },
        ],
        'response_items': 'Result.AclList',
        'response_total': 'Result.TotalCount',
        'result_key': 'acls',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CKAFKA acls',
        'description': 'Returns CKAFKA acls visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CKAFKA acls.',
        'return_total_doc': 'Number of acls reported by the API.',
        'examples': """\
- name: List all acls
  susunola.tencentcloud.ckafka_acl_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ckafka_acl_rule_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.ckafka.v20190819',
        'client_module': 'ckafka_client',
        'client_class': 'CkafkaClient',
        'sdk_package': 'tencentcloud-sdk-python-ckafka',
        'endpoint': 'ckafka.tencentcloudapi.com',
        'action': 'DescribeAclRule',
        'request_class': 'DescribeAclRuleRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'rule_name',
                'field': 'RuleName',
                'type': 'str',
                'required': False,
                'doc': 'Rule name. API field C(RuleName).',
            },
            {
                'name': 'pattern_type',
                'field': 'PatternType',
                'type': 'str',
                'required': False,
                'doc': 'Pattern type. API field C(PatternType).',
            },
            {
                'name': 'is_simplified',
                'field': 'IsSimplified',
                'type': 'bool',
                'required': False,
                'doc': 'Is simplified. API field C(IsSimplified).',
            },
        ],
        'response_items': 'Result.AclRuleList',
        'response_total': 'Result.TotalCount',
        'result_key': 'acl_rules',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CKAFKA acl rules',
        'description': 'Returns CKAFKA acl rules visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CKAFKA acl rules.',
        'return_total_doc': 'Number of acl rules reported by the API.',
        'examples': """\
- name: List all acl rules
  susunola.tencentcloud.ckafka_acl_rule_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ckafka_datahub_connection_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.ckafka.v20190819',
        'client_module': 'ckafka_client',
        'client_class': 'CkafkaClient',
        'sdk_package': 'tencentcloud-sdk-python-ckafka',
        'endpoint': 'ckafka.tencentcloudapi.com',
        'action': 'DescribeConnectResources',
        'request_class': 'DescribeConnectResourcesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'type',
                'field': 'Type',
                'type': 'str',
                'required': False,
                'doc': 'Type. API field C(Type).',
            },
            {
                'name': 'search_word',
                'field': 'SearchWord',
                'type': 'str',
                'required': False,
                'doc': 'Search word. API field C(SearchWord).',
            },
            {
                'name': 'resource_region',
                'field': 'ResourceRegion',
                'type': 'str',
                'required': False,
                'doc': 'Resource region. API field C(ResourceRegion).',
            },
        ],
        'response_items': 'Result.ConnectResourceList',
        'response_total': 'Result.TotalCount',
        'result_key': 'datahub_connections',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CKAFKA datahub connections',
        'description': 'Returns CKAFKA datahub connections visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CKAFKA datahub connections.',
        'return_total_doc': 'Number of datahub connections reported by the API.',
        'examples': """\
- name: List all datahub connections
  susunola.tencentcloud.ckafka_datahub_connection_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ckafka_datahub_task_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.ckafka.v20190819',
        'client_module': 'ckafka_client',
        'client_class': 'CkafkaClient',
        'sdk_package': 'tencentcloud-sdk-python-ckafka',
        'endpoint': 'ckafka.tencentcloudapi.com',
        'action': 'DescribeDatahubTasks',
        'request_class': 'DescribeDatahubTasksRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'search_word',
                'field': 'SearchWord',
                'type': 'str',
                'required': False,
                'doc': 'Search word. API field C(SearchWord).',
            },
            {
                'name': 'target_type',
                'field': 'TargetType',
                'type': 'str',
                'required': False,
                'doc': 'Target type. API field C(TargetType).',
            },
            {
                'name': 'task_type',
                'field': 'TaskType',
                'type': 'str',
                'required': False,
                'doc': 'Task type. API field C(TaskType).',
            },
            {
                'name': 'source_type',
                'field': 'SourceType',
                'type': 'str',
                'required': False,
                'doc': 'Source type. API field C(SourceType).',
            },
            {
                'name': 'resource',
                'field': 'Resource',
                'type': 'str',
                'required': False,
                'doc': 'Resource. API field C(Resource).',
            },
        ],
        'response_items': 'Result.TaskList',
        'response_total': 'Result.TotalCount',
        'result_key': 'datahub_tasks',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CKAFKA datahub tasks',
        'description': 'Returns CKAFKA datahub tasks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CKAFKA datahub tasks.',
        'return_total_doc': 'Number of datahub tasks reported by the API.',
        'examples': """\
- name: List all datahub tasks
  susunola.tencentcloud.ckafka_datahub_task_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ckafka_datahub_topic_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.ckafka.v20190819',
        'client_module': 'ckafka_client',
        'client_class': 'CkafkaClient',
        'sdk_package': 'tencentcloud-sdk-python-ckafka',
        'endpoint': 'ckafka.tencentcloudapi.com',
        'action': 'DescribeDatahubTopics',
        'request_class': 'DescribeDatahubTopicsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'search_word',
                'field': 'SearchWord',
                'type': 'str',
                'required': False,
                'doc': 'Search word. API field C(SearchWord).',
            },
            {
                'name': 'query_from_connect_resource',
                'field': 'QueryFromConnectResource',
                'type': 'bool',
                'required': False,
                'doc': 'Query from connect resource. API field C(QueryFromConnectResource).',
            },
            {
                'name': 'connect_resource_id',
                'field': 'ConnectResourceId',
                'type': 'str',
                'required': False,
                'doc': 'Connect resource id. API field C(ConnectResourceId).',
            },
            {
                'name': 'topic_regular_expression',
                'field': 'TopicRegularExpression',
                'type': 'str',
                'required': False,
                'doc': 'Topic regular expression. API field C(TopicRegularExpression).',
            },
        ],
        'response_items': 'Result.TopicList',
        'response_total': 'Result.TotalCount',
        'result_key': 'datahub_topics',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CKAFKA datahub topics',
        'description': 'Returns CKAFKA datahub topics visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CKAFKA datahub topics.',
        'return_total_doc': 'Number of datahub topics reported by the API.',
        'examples': """\
- name: List all datahub topics
  susunola.tencentcloud.ckafka_datahub_topic_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ckafka_route_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.ckafka.v20190819',
        'client_module': 'ckafka_client',
        'client_class': 'CkafkaClient',
        'sdk_package': 'tencentcloud-sdk-python-ckafka',
        'endpoint': 'ckafka.tencentcloudapi.com',
        'action': 'DescribeRoute',
        'request_class': 'DescribeRouteRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'route_id',
                'field': 'RouteId',
                'type': 'int',
                'required': False,
                'doc': 'Route id. API field C(RouteId).',
            },
            {
                'name': 'main_route_flag',
                'field': 'MainRouteFlag',
                'type': 'bool',
                'required': False,
                'doc': 'Main route flag. API field C(MainRouteFlag).',
            },
        ],
        'response_items': 'Result.Routers',
        'response_total': None,
        'result_key': 'routes',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CKAFKA routes',
        'description': 'Returns CKAFKA routes visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CKAFKA routes.',
        'return_total_doc': 'Number of routes returned (the API reports no total count).',
        'examples': """\
- name: List all routes
  susunola.tencentcloud.ckafka_route_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cloudaudit_audit_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cloudaudit.v20190319',
        'client_module': 'cloudaudit_client',
        'client_class': 'CloudauditClient',
        'sdk_package': 'tencentcloud-sdk-python-cloudaudit',
        'endpoint': 'cloudaudit.tencentcloudapi.com',
        'action': 'ListAudits',
        'request_class': 'ListAuditsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'AuditSummarys',
        'response_total': None,
        'result_key': 'audits',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CLOUDAUDIT audits',
        'description': 'Returns CLOUDAUDIT audits visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CLOUDAUDIT audits.',
        'return_total_doc': 'Number of audits returned (the API reports no total count).',
        'examples': """\
- name: List all audits
  susunola.tencentcloud.cloudaudit_audit_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cloudaudit_track_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cloudaudit.v20190319',
        'client_module': 'cloudaudit_client',
        'client_class': 'CloudauditClient',
        'sdk_package': 'tencentcloud-sdk-python-cloudaudit',
        'endpoint': 'cloudaudit.tencentcloudapi.com',
        'action': 'DescribeAuditTracks',
        'request_class': 'DescribeAuditTracksRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Tracks',
        'response_total': 'TotalCount',
        'result_key': 'audit_tracks',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud CLOUDAUDIT audit tracks',
        'description': 'Returns CLOUDAUDIT audit tracks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CLOUDAUDIT audit tracks.',
        'return_total_doc': 'Number of audit tracks reported by the API.',
        'examples': """\
- name: List all audit tracks
  susunola.tencentcloud.cloudaudit_track_info:
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
  susunola.tencentcloud.cloudhsm_vsm_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cloudrc_resource_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.cloudrc.v20240606',
        'client_module': 'cloudrc_client',
        'client_class': 'CloudrcClient',
        'sdk_package': 'tencentcloud-sdk-python-cloudrc',
        'endpoint': 'cloudrc.tencentcloudapi.com',
        'action': 'SearchResources',
        'request_class': 'SearchResourcesRequest',
        'ids': None,
        'filters': {
            'doc': 'CLOUDRC API filter names mapped to lists of values.',
            'model': 'ExtendedFilter',
            'name_field': 'Key',
        },
        'extra_params': [],
        'response_items': 'Resources',
        'response_total': None,
        'result_key': 'resources',
        'pagination_type': 'token',
        'list_over_field': None,
        'short_description': 'Gather information about Tencent Cloud CLOUDRC resources',
        'description': 'Returns CLOUDRC resources visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CLOUDRC resources.',
        'return_total_doc': 'Number of resources returned (the API reports no total count).',
        'examples': """\
- name: List all resources
  susunola.tencentcloud.cloudrc_resource_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cloudstudio_image_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.cloudstudio.v20230508',
        'client_module': 'cloudstudio_client',
        'client_class': 'CloudstudioClient',
        'sdk_package': 'tencentcloud-sdk-python-cloudstudio',
        'endpoint': 'cloudstudio.tencentcloudapi.com',
        'action': 'DescribeImages',
        'request_class': 'DescribeImagesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Images',
        'response_total': None,
        'result_key': 'images',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud CLOUDSTUDIO images',
        'description': 'Returns CLOUDSTUDIO images visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CLOUDSTUDIO images.',
        'return_total_doc': 'Number of images returned (the API reports no total count).',
        'examples': """\
- name: List all images
  susunola.tencentcloud.cloudstudio_image_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cls_alarm_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cls.v20201016',
        'client_module': 'cls_client',
        'client_class': 'ClsClient',
        'sdk_package': 'tencentcloud-sdk-python-cls',
        'endpoint': 'cls.tencentcloudapi.com',
        'action': 'DescribeAlarms',
        'request_class': 'DescribeAlarmsRequest',
        'ids': None,
        'filters': {
            'doc': 'CLS API filter names mapped to lists of values.',
            'name_field': 'Key',
        },
        'extra_params': [],
        'response_items': 'Alarms',
        'response_total': 'TotalCount',
        'result_key': 'alarms',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CLS alarms',
        'description': 'Returns CLS alarms visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CLS alarms.',
        'return_total_doc': 'Number of alarms reported by the API.',
        'examples': """\
- name: List all alarms
  susunola.tencentcloud.cls_alarm_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cls_alarm_notice_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cls.v20201016',
        'client_module': 'cls_client',
        'client_class': 'ClsClient',
        'sdk_package': 'tencentcloud-sdk-python-cls',
        'endpoint': 'cls.tencentcloudapi.com',
        'action': 'DescribeAlarmNotices',
        'request_class': 'DescribeAlarmNoticesRequest',
        'ids': None,
        'filters': {
            'doc': 'CLS API filter names mapped to lists of values.',
            'name_field': 'Key',
        },
        'extra_params': [
            {
                'name': 'has_alarm_shield_count',
                'field': 'HasAlarmShieldCount',
                'type': 'bool',
                'required': False,
                'doc': 'Has alarm shield count. API field C(HasAlarmShieldCount).',
            },
        ],
        'response_items': 'AlarmNotices',
        'response_total': 'TotalCount',
        'result_key': 'alarm_notices',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CLS alarm notices',
        'description': 'Returns CLS alarm notices visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CLS alarm notices.',
        'return_total_doc': 'Number of alarm notices reported by the API.',
        'examples': """\
- name: List all alarm notices
  susunola.tencentcloud.cls_alarm_notice_info:
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
  susunola.tencentcloud.cme_platform_info:
    region: ap-guangzhou

- name: Find platforms by ID
  susunola.tencentcloud.cme_platform_info:
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
  susunola.tencentcloud.cmq_queue_info:
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
  susunola.tencentcloud.cms_lib_sample_info:
    region: ap-guangzhou

- name: Find lib samples by ID
  susunola.tencentcloud.cms_lib_sample_info:
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
  susunola.tencentcloud.cngw_cloud_native_api_gateway_llm_model_api_info:
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
  susunola.tencentcloud.config_aggregate_compliance_pack_info:
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
  susunola.tencentcloud.controlcenter_account_factory_baseline_item_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cpdp_merchant_info_for_management_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.cpdp.v20190820',
        'client_module': 'cpdp_client',
        'client_class': 'CpdpClient',
        'sdk_package': 'tencentcloud-sdk-python-cpdp',
        'endpoint': 'cpdp.tencentcloudapi.com',
        'action': 'QueryMerchantInfoForManagement',
        'request_class': 'QueryMerchantInfoForManagementRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Result.List',
        'response_total': 'Result.Total',
        'result_key': 'merchant_info_for_managements',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud CPDP merchant info for managements',
        'description': 'Returns CPDP merchant info for managements visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CPDP merchant info for managements.',
        'return_total_doc': 'Number of merchant info for managements reported by the API.',
        'examples': """\
- name: List all merchant info for managements
  susunola.tencentcloud.cpdp_merchant_info_for_management_info:
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
  susunola.tencentcloud.csip_asset_process_info:
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
  susunola.tencentcloud.ctem_api_sec_info:
    region: ap-guangzhou

- name: Find api secs by ID
  susunola.tencentcloud.ctem_api_sec_info:
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
  susunola.tencentcloud.ctsdb_cluster_info:
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
  susunola.tencentcloud.cws_monitor_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cynosdb_account_privilege_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.cynosdb.v20190107',
        'client_module': 'cynosdb_client',
        'client_class': 'CynosdbClient',
        'sdk_package': 'tencentcloud-sdk-python-cynosdb',
        'endpoint': 'cynosdb.tencentcloudapi.com',
        'action': 'DescribeAccountPrivileges',
        'request_class': 'DescribeAccountPrivilegesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'cluster_id',
                'field': 'ClusterId',
                'type': 'str',
                'required': False,
                'doc': 'Cluster id. API field C(ClusterId).',
            },
            {
                'name': 'account_name',
                'field': 'AccountName',
                'type': 'str',
                'required': False,
                'doc': 'Account name. API field C(AccountName).',
            },
            {
                'name': 'host',
                'field': 'Host',
                'type': 'str',
                'required': False,
                'doc': 'Host. API field C(Host).',
            },
            {
                'name': 'db',
                'field': 'Db',
                'type': 'str',
                'required': False,
                'doc': 'Db. API field C(Db).',
            },
            {
                'name': 'type',
                'field': 'Type',
                'type': 'str',
                'required': False,
                'doc': 'Type. API field C(Type).',
            },
            {
                'name': 'table_name',
                'field': 'TableName',
                'type': 'str',
                'required': False,
                'doc': 'Table name. API field C(TableName).',
            },
        ],
        'response_items': None,
        'response_total': None,
        'result_key': 'account_privilege',
        'pagination_type': 'none',
        'short_description': 'Gather information about Tencent Cloud CYNOSDB account privilege',
        'description': 'Returns CYNOSDB account privilege visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching CYNOSDB account privilege.',
        'return_total_doc': '',
        'examples': """\
- name: Show the account privilege
  susunola.tencentcloud.cynosdb_account_privilege_info:
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
  susunola.tencentcloud.dasb_device_info:
    region: ap-guangzhou

- name: Find devices by ID
  susunola.tencentcloud.dasb_device_info:
    region: ap-guangzhou
    device_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'dataagent_chunk_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.dataagent.v20250513',
        'client_module': 'dataagent_client',
        'client_class': 'DataagentClient',
        'sdk_package': 'tencentcloud-sdk-python-dataagent',
        'endpoint': 'dataagent.tencentcloudapi.com',
        'action': 'QueryChunkList',
        'request_class': 'QueryChunkListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Chunks',
        'response_total': 'Total',
        'result_key': 'chunks',
        'pagination_type': 'page',
        'page_number_field': 'Page',
        'short_description': 'Gather information about Tencent Cloud DATAAGENT chunks',
        'description': 'Returns DATAAGENT chunks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DATAAGENT chunks.',
        'return_total_doc': 'Number of chunks reported by the API.',
        'examples': """\
- name: List all chunks
  susunola.tencentcloud.dataagent_chunk_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.dayu_resource_info:
    region: ap-guangzhou

- name: Find resources by ID
  susunola.tencentcloud.dayu_resource_info:
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
  susunola.tencentcloud.dbbrain_db_diag_event_info:
    region: ap-guangzhou

- name: Find db diag events by ID
  susunola.tencentcloud.dbbrain_db_diag_event_info:
    region: ap-guangzhou
    db_diag_event_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'dbbrain_sql_filter_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.dbbrain.v20210527',
        'client_module': 'dbbrain_client',
        'client_class': 'DbbrainClient',
        'sdk_package': 'tencentcloud-sdk-python-dbbrain',
        'endpoint': 'dbbrain.tencentcloudapi.com',
        'action': 'DescribeSqlFilters',
        'request_class': 'DescribeSqlFiltersRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'filter_ids',
                'field': 'FilterIds',
                'type': 'list',
                'required': False,
                'doc': 'Filter ids. API field C(FilterIds).',
                'elements': 'int',
            },
            {
                'name': 'statuses',
                'field': 'Statuses',
                'type': 'list',
                'required': False,
                'doc': 'Statuses. API field C(Statuses).',
                'elements': 'str',
            },
            {
                'name': 'product',
                'field': 'Product',
                'type': 'str',
                'required': False,
                'doc': 'Product. API field C(Product).',
            },
        ],
        'response_items': 'Items',
        'response_total': 'TotalCount',
        'result_key': 'sql_filters',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DBBRAIN sql filters',
        'description': 'Returns DBBRAIN sql filters visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DBBRAIN sql filters.',
        'return_total_doc': 'Number of sql filters reported by the API.',
        'examples': """\
- name: List all sql filters
  susunola.tencentcloud.dbbrain_sql_filter_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.dbdc_db_custom_cluster_info:
    region: ap-guangzhou

- name: Find db custom clusters by ID
  susunola.tencentcloud.dbdc_db_custom_cluster_info:
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
  susunola.tencentcloud.dbs_backup_plan_info:
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
  susunola.tencentcloud.dc_direct_connect_tunnel_info:
    region: ap-guangzhou

- name: Find direct connect tunnels by ID
  susunola.tencentcloud.dc_direct_connect_tunnel_info:
    region: ap-guangzhou
    direct_connect_tunnel_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'dcdb_instance_info',
        'version_added': '0.8.0',
        'service_package': 'tencentcloud.dcdb.v20180411',
        'client_module': 'dcdb_client',
        'client_class': 'DcdbClient',
        'sdk_package': 'tencentcloud-sdk-python-dcdb',
        'endpoint': 'dcdb.tencentcloudapi.com',
        'action': 'DescribeDCDBInstances',
        'request_class': 'DescribeDCDBInstancesRequest',
        'ids': {
            'param': 'instance_ids',
            'field': 'InstanceIds',
            'doc': 'Instances IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Instances',
        'response_total': 'TotalCount',
        'result_key': 'instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DCDB instances',
        'description': 'Returns DCDB instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DCDB instances.',
        'return_total_doc': 'Number of instances reported by the API.',
        'examples': """\
- name: List all instances
  susunola.tencentcloud.dcdb_instance_info:
    region: ap-guangzhou

- name: Find instances by ID
  susunola.tencentcloud.dcdb_instance_info:
    region: ap-guangzhou
    instance_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'dcdb_account_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.dcdb.v20180411',
        'client_module': 'dcdb_client',
        'client_class': 'DcdbClient',
        'sdk_package': 'tencentcloud-sdk-python-dcdb',
        'endpoint': 'dcdb.tencentcloudapi.com',
        'action': 'DescribeAccounts',
        'request_class': 'DescribeAccountsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': 'Users',
        'response_total': None,
        'result_key': 'accounts',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud DCDB accounts',
        'description': 'Returns DCDB accounts visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DCDB accounts.',
        'return_total_doc': 'Number of accounts returned (the API reports no total count).',
        'examples': """\
- name: List all accounts
  susunola.tencentcloud.dcdb_account_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'dcdb_account_privilege_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.dcdb.v20180411',
        'client_module': 'dcdb_client',
        'client_class': 'DcdbClient',
        'sdk_package': 'tencentcloud-sdk-python-dcdb',
        'endpoint': 'dcdb.tencentcloudapi.com',
        'action': 'DescribeAccountPrivileges',
        'request_class': 'DescribeAccountPrivilegesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'user_name',
                'field': 'UserName',
                'type': 'str',
                'required': False,
                'doc': 'User name. API field C(UserName).',
            },
            {
                'name': 'host',
                'field': 'Host',
                'type': 'str',
                'required': False,
                'doc': 'Host. API field C(Host).',
            },
            {
                'name': 'db_name',
                'field': 'DbName',
                'type': 'str',
                'required': False,
                'doc': 'Db name. API field C(DbName).',
            },
            {
                'name': 'type',
                'field': 'Type',
                'type': 'str',
                'required': False,
                'doc': 'Type. API field C(Type).',
            },
            {
                'name': 'object',
                'field': 'Object',
                'type': 'str',
                'required': False,
                'doc': 'Object. API field C(Object).',
            },
            {
                'name': 'col_name',
                'field': 'ColName',
                'type': 'str',
                'required': False,
                'doc': 'Col name. API field C(ColName).',
            },
        ],
        'response_items': None,
        'response_total': None,
        'result_key': 'account_privilege',
        'pagination_type': 'none',
        'short_description': 'Gather information about Tencent Cloud DCDB account privilege',
        'description': 'Returns DCDB account privilege visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DCDB account privilege.',
        'return_total_doc': '',
        'examples': """\
- name: Show the account privilege
  susunola.tencentcloud.dcdb_account_privilege_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'dcdb_backup_config_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.dcdb.v20180411',
        'client_module': 'dcdb_client',
        'client_class': 'DcdbClient',
        'sdk_package': 'tencentcloud-sdk-python-dcdb',
        'endpoint': 'dcdb.tencentcloudapi.com',
        'action': 'DescribeBackupConfigs',
        'request_class': 'DescribeBackupConfigsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': 'BackupConfigSet',
        'response_total': None,
        'result_key': 'backup_configs',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud DCDB backup configs',
        'description': 'Returns DCDB backup configs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DCDB backup configs.',
        'return_total_doc': 'Number of backup configs returned (the API reports no total count).',
        'examples': """\
- name: List all backup configs
  susunola.tencentcloud.dcdb_backup_config_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'dcdb_security_config_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.dcdb.v20180411',
        'client_module': 'dcdb_client',
        'client_class': 'DcdbClient',
        'sdk_package': 'tencentcloud-sdk-python-dcdb',
        'endpoint': 'dcdb.tencentcloudapi.com',
        'action': 'DescribeDBSecurityGroups',
        'request_class': 'DescribeDBSecurityGroupsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'product',
                'field': 'Product',
                'type': 'str',
                'required': False,
                'doc': 'Product. API field C(Product).',
            },
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': 'Groups',
        'response_total': None,
        'result_key': 'db_security_groups',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud DCDB db security groups',
        'description': 'Returns DCDB db security groups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DCDB db security groups.',
        'return_total_doc': 'Number of db security groups returned (the API reports no total count).',
        'examples': """\
- name: List all db security groups
  susunola.tencentcloud.dcdb_security_config_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.dlc_task_info:
    region: ap-guangzhou

- name: Find tasks by ID
  susunola.tencentcloud.dlc_task_info:
    region: ap-guangzhou
    task_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'dnspod_custom_line_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.dnspod.v20210323',
        'client_module': 'dnspod_client',
        'client_class': 'DnspodClient',
        'sdk_package': 'tencentcloud-sdk-python-dnspod',
        'endpoint': 'dnspod.tencentcloudapi.com',
        'action': 'DescribeDomainCustomLineList',
        'request_class': 'DescribeDomainCustomLineListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'domain',
                'field': 'Domain',
                'type': 'str',
                'required': False,
                'doc': 'Domain. API field C(Domain).',
            },
            {
                'name': 'domain_id',
                'field': 'DomainId',
                'type': 'int',
                'required': False,
                'doc': 'Domain id. API field C(DomainId).',
            },
        ],
        'response_items': 'LineList',
        'response_total': None,
        'result_key': 'domain_custom_lines',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud DNSPOD domain custom lines',
        'description': 'Returns DNSPOD domain custom lines visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DNSPOD domain custom lines.',
        'return_total_doc': 'Number of domain custom lines returned (the API reports no total count).',
        'examples': """\
- name: List all domain custom lines
  susunola.tencentcloud.dnspod_custom_line_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'dnspod_domain_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.dnspod.v20210323',
        'client_module': 'dnspod_client',
        'client_class': 'DnspodClient',
        'sdk_package': 'tencentcloud-sdk-python-dnspod',
        'endpoint': 'dnspod.tencentcloudapi.com',
        'action': 'DescribeDomainList',
        'request_class': 'DescribeDomainListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'type',
                'field': 'Type',
                'type': 'str',
                'required': False,
                'doc': 'Type. API field C(Type).',
            },
            {
                'name': 'group_id',
                'field': 'GroupId',
                'type': 'int',
                'required': False,
                'doc': 'Group id. API field C(GroupId).',
            },
            {
                'name': 'keyword',
                'field': 'Keyword',
                'type': 'str',
                'required': False,
                'doc': 'Keyword. API field C(Keyword).',
                'no_log': False,
            },
        ],
        'response_items': 'DomainList',
        'response_total': None,
        'result_key': 'domains',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DNSPOD domains',
        'description': 'Returns DNSPOD domains visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DNSPOD domains.',
        'return_total_doc': 'Number of domains returned (the API reports no total count).',
        'examples': """\
- name: List all domains
  susunola.tencentcloud.dnspod_domain_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'dnspod_line_group_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.dnspod.v20210323',
        'client_module': 'dnspod_client',
        'client_class': 'DnspodClient',
        'sdk_package': 'tencentcloud-sdk-python-dnspod',
        'endpoint': 'dnspod.tencentcloudapi.com',
        'action': 'DescribeLineGroupList',
        'request_class': 'DescribeLineGroupListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'domain',
                'field': 'Domain',
                'type': 'str',
                'required': False,
                'doc': 'Domain. API field C(Domain).',
            },
            {
                'name': 'sort_type',
                'field': 'SortType',
                'type': 'str',
                'required': False,
                'doc': 'Sort type. API field C(SortType).',
            },
            {
                'name': 'domain_id',
                'field': 'DomainId',
                'type': 'int',
                'required': False,
                'doc': 'Domain id. API field C(DomainId).',
            },
        ],
        'response_items': 'LineGroups',
        'response_total': None,
        'result_key': 'line_groups',
        'pagination_type': 'int',
        'page_size_field': 'Length',
        'short_description': 'Gather information about Tencent Cloud DNSPOD line groups',
        'description': 'Returns DNSPOD line groups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DNSPOD line groups.',
        'return_total_doc': 'Number of line groups returned (the API reports no total count).',
        'examples': """\
- name: List all line groups
  susunola.tencentcloud.dnspod_line_group_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.domain_batch_operation_log_info:
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
  susunola.tencentcloud.dsgc_dspa_assessment_risk_info:
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
  susunola.tencentcloud.dts_subscribe_job_info:
    region: ap-guangzhou

- name: Find subscribe jobs by ID
  susunola.tencentcloud.dts_subscribe_job_info:
    region: ap-guangzhou
    subscribe_job_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'dts_consumer_group_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.dts.v20211206',
        'client_module': 'dts_client',
        'client_class': 'DtsClient',
        'sdk_package': 'tencentcloud-sdk-python-dts',
        'endpoint': 'dts.tencentcloudapi.com',
        'action': 'DescribeConsumerGroups',
        'request_class': 'DescribeConsumerGroupsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'subscribe_id',
                'field': 'SubscribeId',
                'type': 'str',
                'required': False,
                'doc': 'Subscribe id. API field C(SubscribeId).',
            },
        ],
        'response_items': 'Items',
        'response_total': 'TotalCount',
        'result_key': 'consumer_groups',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DTS consumer groups',
        'description': 'Returns DTS consumer groups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DTS consumer groups.',
        'return_total_doc': 'Number of consumer groups reported by the API.',
        'examples': """\
- name: List all consumer groups
  susunola.tencentcloud.dts_consumer_group_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'dts_migration_check_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.dts.v20211206',
        'client_module': 'dts_client',
        'client_class': 'DtsClient',
        'sdk_package': 'tencentcloud-sdk-python-dts',
        'endpoint': 'dts.tencentcloudapi.com',
        'action': 'DescribeMigrationCheckJob',
        'request_class': 'DescribeMigrationCheckJobRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'job_id',
                'field': 'JobId',
                'type': 'str',
                'required': False,
                'doc': 'Job id. API field C(JobId).',
            },
        ],
        'response_items': 'StepInfo',
        'response_total': None,
        'result_key': 'migration_check_jobs',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud DTS migration check jobs',
        'description': 'Returns DTS migration check jobs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DTS migration check jobs.',
        'return_total_doc': 'Number of migration check jobs returned (the API reports no total count).',
        'examples': """\
- name: List all migration check jobs
  susunola.tencentcloud.dts_migration_check_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'dts_migration_job_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.dts.v20211206',
        'client_module': 'dts_client',
        'client_class': 'DtsClient',
        'sdk_package': 'tencentcloud-sdk-python-dts',
        'endpoint': 'dts.tencentcloudapi.com',
        'action': 'DescribeMigrationJobs',
        'request_class': 'DescribeMigrationJobsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'job_id',
                'field': 'JobId',
                'type': 'str',
                'required': False,
                'doc': 'Job id. API field C(JobId).',
            },
            {
                'name': 'job_name',
                'field': 'JobName',
                'type': 'str',
                'required': False,
                'doc': 'Job name. API field C(JobName).',
            },
            {
                'name': 'status',
                'field': 'Status',
                'type': 'list',
                'required': False,
                'doc': 'Status. API field C(Status).',
                'elements': 'str',
            },
            {
                'name': 'src_instance_id',
                'field': 'SrcInstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Src instance id. API field C(SrcInstanceId).',
            },
            {
                'name': 'src_region',
                'field': 'SrcRegion',
                'type': 'str',
                'required': False,
                'doc': 'Src region. API field C(SrcRegion).',
            },
            {
                'name': 'src_database_type',
                'field': 'SrcDatabaseType',
                'type': 'list',
                'required': False,
                'doc': 'Src database type. API field C(SrcDatabaseType).',
                'elements': 'str',
            },
            {
                'name': 'src_access_type',
                'field': 'SrcAccessType',
                'type': 'list',
                'required': False,
                'doc': 'Src access type. API field C(SrcAccessType).',
                'elements': 'str',
            },
            {
                'name': 'dst_instance_id',
                'field': 'DstInstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Dst instance id. API field C(DstInstanceId).',
            },
            {
                'name': 'dst_region',
                'field': 'DstRegion',
                'type': 'str',
                'required': False,
                'doc': 'Dst region. API field C(DstRegion).',
            },
            {
                'name': 'dst_database_type',
                'field': 'DstDatabaseType',
                'type': 'list',
                'required': False,
                'doc': 'Dst database type. API field C(DstDatabaseType).',
                'elements': 'str',
            },
            {
                'name': 'dst_access_type',
                'field': 'DstAccessType',
                'type': 'list',
                'required': False,
                'doc': 'Dst access type. API field C(DstAccessType).',
                'elements': 'str',
            },
            {
                'name': 'run_mode',
                'field': 'RunMode',
                'type': 'str',
                'required': False,
                'doc': 'Run mode. API field C(RunMode).',
            },
            {
                'name': 'order_seq',
                'field': 'OrderSeq',
                'type': 'str',
                'required': False,
                'doc': 'Order seq. API field C(OrderSeq).',
            },
        ],
        'response_items': 'JobList',
        'response_total': 'TotalCount',
        'result_key': 'migration_jobs',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud DTS migration jobs',
        'description': 'Returns DTS migration jobs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching DTS migration jobs.',
        'return_total_doc': 'Number of migration jobs reported by the API.',
        'examples': """\
- name: List all migration jobs
  susunola.tencentcloud.dts_migration_job_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.eb_event_bus_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'eb_connection_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.eb.v20210416',
        'client_module': 'eb_client',
        'client_class': 'EbClient',
        'sdk_package': 'tencentcloud-sdk-python-eb',
        'endpoint': 'eb.tencentcloudapi.com',
        'action': 'ListConnections',
        'request_class': 'ListConnectionsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'event_bus_id',
                'field': 'EventBusId',
                'type': 'str',
                'required': False,
                'doc': 'Event bus id. API field C(EventBusId).',
            },
            {
                'name': 'order_by',
                'field': 'OrderBy',
                'type': 'str',
                'required': False,
                'doc': 'Order by. API field C(OrderBy).',
            },
            {
                'name': 'order',
                'field': 'Order',
                'type': 'str',
                'required': False,
                'doc': 'Order. API field C(Order).',
            },
        ],
        'response_items': 'Connections',
        'response_total': 'TotalCount',
        'result_key': 'connections',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud EB connections',
        'description': 'Returns EB connections visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching EB connections.',
        'return_total_doc': 'Number of connections reported by the API.',
        'examples': """\
- name: List all connections
  susunola.tencentcloud.eb_connection_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'eb_rule_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.eb.v20210416',
        'client_module': 'eb_client',
        'client_class': 'EbClient',
        'sdk_package': 'tencentcloud-sdk-python-eb',
        'endpoint': 'eb.tencentcloudapi.com',
        'action': 'ListRules',
        'request_class': 'ListRulesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'event_bus_id',
                'field': 'EventBusId',
                'type': 'str',
                'required': False,
                'doc': 'Event bus id. API field C(EventBusId).',
            },
            {
                'name': 'order_by',
                'field': 'OrderBy',
                'type': 'str',
                'required': False,
                'doc': 'Order by. API field C(OrderBy).',
            },
            {
                'name': 'order',
                'field': 'Order',
                'type': 'str',
                'required': False,
                'doc': 'Order. API field C(Order).',
            },
        ],
        'response_items': 'Rules',
        'response_total': 'TotalCount',
        'result_key': 'rules',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud EB rules',
        'description': 'Returns EB rules visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching EB rules.',
        'return_total_doc': 'Number of rules reported by the API.',
        'examples': """\
- name: List all rules
  susunola.tencentcloud.eb_rule_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'eb_target_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.eb.v20210416',
        'client_module': 'eb_client',
        'client_class': 'EbClient',
        'sdk_package': 'tencentcloud-sdk-python-eb',
        'endpoint': 'eb.tencentcloudapi.com',
        'action': 'ListTargets',
        'request_class': 'ListTargetsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'event_bus_id',
                'field': 'EventBusId',
                'type': 'str',
                'required': False,
                'doc': 'Event bus id. API field C(EventBusId).',
            },
            {
                'name': 'rule_id',
                'field': 'RuleId',
                'type': 'str',
                'required': False,
                'doc': 'Rule id. API field C(RuleId).',
            },
            {
                'name': 'order_by',
                'field': 'OrderBy',
                'type': 'str',
                'required': False,
                'doc': 'Order by. API field C(OrderBy).',
            },
            {
                'name': 'order',
                'field': 'Order',
                'type': 'str',
                'required': False,
                'doc': 'Order. API field C(Order).',
            },
        ],
        'response_items': 'Targets',
        'response_total': 'TotalCount',
        'result_key': 'targets',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud EB targets',
        'description': 'Returns EB targets visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching EB targets.',
        'return_total_doc': 'Number of targets reported by the API.',
        'examples': """\
- name: List all targets
  susunola.tencentcloud.eb_target_info:
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
  susunola.tencentcloud.ecdn_domain_info:
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
  susunola.tencentcloud.ecm_address_info:
    region: ap-guangzhou

- name: Find addresses by ID
  susunola.tencentcloud.ecm_address_info:
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
  susunola.tencentcloud.eiam_application_info:
    region: ap-guangzhou

- name: Find applications by ID
  susunola.tencentcloud.eiam_application_info:
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
  susunola.tencentcloud.eis_runtime_deployed_instances_mc_info:
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
  susunola.tencentcloud.emr_node_data_disk_info:
    region: ap-guangzhou

- name: Find node data disks by ID
  susunola.tencentcloud.emr_node_data_disk_info:
    region: ap-guangzhou
    node_data_disk_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'emr_auto_scale_strategy_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.emr.v20190103',
        'client_module': 'emr_client',
        'client_class': 'EmrClient',
        'sdk_package': 'tencentcloud-sdk-python-emr',
        'endpoint': 'emr.tencentcloudapi.com',
        'action': 'DescribeAutoScaleStrategies',
        'request_class': 'DescribeAutoScaleStrategiesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'group_id',
                'field': 'GroupId',
                'type': 'int',
                'required': False,
                'doc': 'Group id. API field C(GroupId).',
            },
        ],
        'response_items': 'LoadAutoScaleStrategies',
        'response_total': None,
        'result_key': 'auto_scale_strategies',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud EMR auto scale strategies',
        'description': 'Returns EMR auto scale strategies visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching EMR auto scale strategies.',
        'return_total_doc': 'Number of auto scale strategies returned (the API reports no total count).',
        'examples': """\
- name: List all auto scale strategies
  susunola.tencentcloud.emr_auto_scale_strategy_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'emr_cluster_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.emr.v20190103',
        'client_module': 'emr_client',
        'client_class': 'EmrClient',
        'sdk_package': 'tencentcloud-sdk-python-emr',
        'endpoint': 'emr.tencentcloudapi.com',
        'action': 'DescribeInstances',
        'request_class': 'DescribeInstancesRequest',
        'ids': {
            'param': 'cluster_ids',
            'field': 'InstanceIds',
            'doc': 'Cluster IDs to return.',
        },
        'filters': None,
        'extra_params': [
            {
                'name': 'display_strategy',
                'field': 'DisplayStrategy',
                'type': 'str',
                'required': False,
                'doc': 'Display strategy. API field C(DisplayStrategy).',
            },
            {
                'name': 'project_id',
                'field': 'ProjectId',
                'type': 'int',
                'required': False,
                'doc': 'Project id. API field C(ProjectId).',
            },
            {
                'name': 'order_field',
                'field': 'OrderField',
                'type': 'str',
                'required': False,
                'doc': 'Order field. API field C(OrderField).',
            },
            {
                'name': 'asc',
                'field': 'Asc',
                'type': 'int',
                'required': False,
                'doc': 'Asc. API field C(Asc).',
            },
        ],
        'response_items': 'ClusterList',
        'response_total': None,
        'result_key': 'clusters',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud EMR clusters',
        'description': 'Returns EMR clusters visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching EMR clusters.',
        'return_total_doc': 'Number of clusters returned (the API reports no total count).',
        'examples': """\
- name: List all clusters
  susunola.tencentcloud.emr_cluster_info:
    region: ap-guangzhou

- name: Find clusters by ID
  susunola.tencentcloud.emr_cluster_info:
    region: ap-guangzhou
    cluster_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'elasticsearch_index_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.es.v20180416',
        'client_module': 'es_client',
        'client_class': 'EsClient',
        'sdk_package': 'tencentcloud-sdk-python-es',
        'endpoint': 'es.tencentcloudapi.com',
        'action': 'DescribeIndexList',
        'request_class': 'DescribeIndexListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'index_type',
                'field': 'IndexType',
                'type': 'str',
                'required': False,
                'doc': 'Index type. API field C(IndexType).',
            },
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'index_name',
                'field': 'IndexName',
                'type': 'str',
                'required': False,
                'doc': 'Index name. API field C(IndexName).',
            },
            {
                'name': 'username',
                'field': 'Username',
                'type': 'str',
                'required': False,
                'doc': 'Username. API field C(Username).',
            },
            {
                'name': 'password',
                'field': 'Password',
                'type': 'str',
                'required': False,
                'doc': 'Password. API field C(Password).',
                'no_log': True,
            },
            {
                'name': 'order_by',
                'field': 'OrderBy',
                'type': 'str',
                'required': False,
                'doc': 'Order by. API field C(OrderBy).',
            },
            {
                'name': 'index_status_list',
                'field': 'IndexStatusList',
                'type': 'list',
                'required': False,
                'doc': 'Index status list. API field C(IndexStatusList).',
                'elements': 'str',
            },
            {
                'name': 'order',
                'field': 'Order',
                'type': 'str',
                'required': False,
                'doc': 'Order. API field C(Order).',
            },
        ],
        'response_items': 'IndexMetaFields',
        'response_total': 'TotalCount',
        'result_key': 'indexes',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud ES indexes',
        'description': 'Returns ES indexes visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ES indexes.',
        'return_total_doc': 'Number of indexes reported by the API.',
        'examples': """\
- name: List all indexes
  susunola.tencentcloud.elasticsearch_index_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'elasticsearch_snapshot_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.es.v20180416',
        'client_module': 'es_client',
        'client_class': 'EsClient',
        'sdk_package': 'tencentcloud-sdk-python-es',
        'endpoint': 'es.tencentcloudapi.com',
        'action': 'DescribeClusterSnapshot',
        'request_class': 'DescribeClusterSnapshotRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'repository_name',
                'field': 'RepositoryName',
                'type': 'str',
                'required': False,
                'doc': 'Repository name. API field C(RepositoryName).',
            },
            {
                'name': 'snapshot_name',
                'field': 'SnapshotName',
                'type': 'str',
                'required': False,
                'doc': 'Snapshot name. API field C(SnapshotName).',
            },
        ],
        'response_items': 'Snapshots',
        'response_total': None,
        'result_key': 'cluster_snapshots',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud ES cluster snapshots',
        'description': 'Returns ES cluster snapshots visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ES cluster snapshots.',
        'return_total_doc': 'Number of cluster snapshots returned (the API reports no total count).',
        'examples': """\
- name: List all cluster snapshots
  susunola.tencentcloud.elasticsearch_snapshot_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.ess_file_url_info:
    region: ap-guangzhou

- name: Find file urls by ID
  susunola.tencentcloud.ess_file_url_info:
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
  susunola.tencentcloud.essbasic_template_info:
    region: ap-guangzhou

- name: Find templates by ID
  susunola.tencentcloud.essbasic_template_info:
    region: ap-guangzhou
    template_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'facefusion_material_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.facefusion.v20220927',
        'client_module': 'facefusion_client',
        'client_class': 'FacefusionClient',
        'sdk_package': 'tencentcloud-sdk-python-facefusion',
        'endpoint': 'facefusion.tencentcloudapi.com',
        'action': 'DescribeMaterialList',
        'request_class': 'DescribeMaterialListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'MaterialInfos',
        'response_total': None,
        'result_key': 'materials',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud FACEFUSION materials',
        'description': 'Returns FACEFUSION materials visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching FACEFUSION materials.',
        'return_total_doc': 'Number of materials returned (the API reports no total count).',
        'examples': """\
- name: List all materials
  susunola.tencentcloud.facefusion_material_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'faceid_we_chat_bill_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.faceid.v20180301',
        'client_module': 'faceid_client',
        'client_class': 'FaceidClient',
        'sdk_package': 'tencentcloud-sdk-python-faceid',
        'endpoint': 'faceid.tencentcloudapi.com',
        'action': 'GetWeChatBillDetails',
        'request_class': 'GetWeChatBillDetailsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'WeChatBillDetails',
        'response_total': None,
        'result_key': 'we_chat_bills',
        'pagination_type': 'token',
        'token_request_field': 'Cursor',
        'token_response_field': 'NextCursor',
        'page_size_field': None,
        'list_over_field': None,
        'has_more_field': 'HasNextPage',
        'short_description': 'Gather information about Tencent Cloud FACEID we chat bills',
        'description': 'Returns FACEID we chat bills visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching FACEID we chat bills.',
        'return_total_doc': 'Number of we chat bills returned (the API reports no total count).',
        'examples': """\
- name: List all we chat bills
  susunola.tencentcloud.faceid_we_chat_bill_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'fmu_model_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.fmu.v20191213',
        'client_module': 'fmu_client',
        'client_class': 'FmuClient',
        'sdk_package': 'tencentcloud-sdk-python-fmu',
        'endpoint': 'fmu.tencentcloudapi.com',
        'action': 'GetModelList',
        'request_class': 'GetModelListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'ModelInfos',
        'response_total': None,
        'result_key': 'models',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud FMU models',
        'description': 'Returns FMU models visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching FMU models.',
        'return_total_doc': 'Number of models returned (the API reports no total count).',
        'examples': """\
- name: List all models
  susunola.tencentcloud.fmu_model_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.fwm_edge_acl_rule_info:
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
  susunola.tencentcloud.ga2_accelerate_area_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'gaap_listener_real_servers_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.gaap.v20180529',
        'client_module': 'gaap_client',
        'client_class': 'GaapClient',
        'sdk_package': 'tencentcloud-sdk-python-gaap',
        'endpoint': 'gaap.tencentcloudapi.com',
        'action': 'DescribeListenerRealServers',
        'request_class': 'DescribeListenerRealServersRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'listener_id',
                'field': 'ListenerId',
                'type': 'str',
                'required': False,
                'doc': 'Listener id. API field C(ListenerId).',
            },
        ],
        'response_items': 'RealServerSet',
        'response_total': 'TotalCount',
        'result_key': 'listener_real_servers',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud GAAP listener real servers',
        'description': 'Returns GAAP listener real servers visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching GAAP listener real servers.',
        'return_total_doc': 'Number of listener real servers reported by the API.',
        'examples': """\
- name: List all listener real servers
  susunola.tencentcloud.gaap_listener_real_servers_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'gaap_real_server_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.gaap.v20180529',
        'client_module': 'gaap_client',
        'client_class': 'GaapClient',
        'sdk_package': 'tencentcloud-sdk-python-gaap',
        'endpoint': 'gaap.tencentcloudapi.com',
        'action': 'DescribeRealServers',
        'request_class': 'DescribeRealServersRequest',
        'ids': None,
        'filters': {
            'doc': 'GAAP API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'project_id',
                'field': 'ProjectId',
                'type': 'int',
                'required': False,
                'doc': 'Project id. API field C(ProjectId).',
            },
            {
                'name': 'search_value',
                'field': 'SearchValue',
                'type': 'str',
                'required': False,
                'doc': 'Search value. API field C(SearchValue).',
            },
        ],
        'response_items': 'RealServerSet',
        'response_total': 'TotalCount',
        'result_key': 'real_servers',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud GAAP real servers',
        'description': 'Returns GAAP real servers visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching GAAP real servers.',
        'return_total_doc': 'Number of real servers reported by the API.',
        'examples': """\
- name: List all real servers
  susunola.tencentcloud.gaap_real_server_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'gme_voice_print_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.gme.v20180711',
        'client_module': 'gme_client',
        'client_class': 'GmeClient',
        'sdk_package': 'tencentcloud-sdk-python-gme',
        'endpoint': 'gme.tencentcloudapi.com',
        'action': 'DescribeVoicePrint',
        'request_class': 'DescribeVoicePrintRequest',
        'ids': {
            'param': 'voice_print_ids',
            'field': 'VoicePrintIdList',
            'doc': 'Voice print IDs to return.',
        },
        'filters': None,
        'extra_params': [],
        'response_items': 'Data',
        'response_total': 'TotalCount',
        'result_key': 'voice_prints',
        'pagination_type': 'page',
        'page_number_field': 'PageIndex',
        'short_description': 'Gather information about Tencent Cloud GME voice prints',
        'description': 'Returns GME voice prints visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching GME voice prints.',
        'return_total_doc': 'Number of voice prints reported by the API.',
        'examples': """\
- name: List all voice prints
  susunola.tencentcloud.gme_voice_print_info:
    region: ap-guangzhou

- name: Find voice prints by ID
  susunola.tencentcloud.gme_voice_print_info:
    region: ap-guangzhou
    voice_print_ids: [x-xxxxxxxx]
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
  susunola.tencentcloud.goosefs_file_system_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'goosefs_fileset_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.goosefs.v20220519',
        'client_module': 'goosefs_client',
        'client_class': 'GoosefsClient',
        'sdk_package': 'tencentcloud-sdk-python-goosefs',
        'endpoint': 'goosefs.tencentcloudapi.com',
        'action': 'DescribeFilesets',
        'request_class': 'DescribeFilesetsRequest',
        'ids': {
            'param': 'fileset_ids',
            'field': 'FilesetIds',
            'doc': 'Fileset IDs to return.',
        },
        'filters': None,
        'extra_params': [
            {
                'name': 'file_system_id',
                'field': 'FileSystemId',
                'type': 'str',
                'required': False,
                'doc': 'File system id. API field C(FileSystemId).',
            },
            {
                'name': 'fileset_dirs',
                'field': 'FilesetDirs',
                'type': 'list',
                'required': False,
                'doc': 'Fileset dirs. API field C(FilesetDirs).',
                'elements': 'str',
            },
        ],
        'response_items': 'FilesetList',
        'response_total': None,
        'result_key': 'filesets',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud GOOSEFS filesets',
        'description': 'Returns GOOSEFS filesets visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching GOOSEFS filesets.',
        'return_total_doc': 'Number of filesets returned (the API reports no total count).',
        'examples': """\
- name: List all filesets
  susunola.tencentcloud.goosefs_fileset_info:
    region: ap-guangzhou

- name: Find filesets by ID
  susunola.tencentcloud.goosefs_fileset_info:
    region: ap-guangzhou
    fileset_ids: [x-xxxxxxxx]
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
  susunola.tencentcloud.gs_android_app_info:
    region: ap-guangzhou

- name: Find android apps by ID
  susunola.tencentcloud.gs_android_app_info:
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
  susunola.tencentcloud.gwlb_gateway_load_balancer_info:
    region: ap-guangzhou

- name: Find gateway load balancers by ID
  susunola.tencentcloud.gwlb_gateway_load_balancer_info:
    region: ap-guangzhou
    gateway_load_balancer_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'gwlb_load_balancer_info',
        'version_added': '1.5.0',
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
        'extra_params': [
            {
                'name': 'search_key',
                'field': 'SearchKey',
                'type': 'str',
                'required': False,
                'doc': 'Search key. API field C(SearchKey).',
                'no_log': False,
            },
        ],
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
  susunola.tencentcloud.gwlb_load_balancer_info:
    region: ap-guangzhou

- name: Find gateway load balancers by ID
  susunola.tencentcloud.gwlb_load_balancer_info:
    region: ap-guangzhou
    gateway_load_balancer_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'gwlb_target_group_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.gwlb.v20240906',
        'client_module': 'gwlb_client',
        'client_class': 'GwlbClient',
        'sdk_package': 'tencentcloud-sdk-python-gwlb',
        'endpoint': 'gwlb.tencentcloudapi.com',
        'action': 'DescribeTargetGroups',
        'request_class': 'DescribeTargetGroupsRequest',
        'ids': {
            'param': 'target_group_ids',
            'field': 'TargetGroupIds',
            'doc': 'Target group IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'GWLB API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'TargetGroupSet',
        'response_total': 'TotalCount',
        'result_key': 'target_groups',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud GWLB target groups',
        'description': 'Returns GWLB target groups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching GWLB target groups.',
        'return_total_doc': 'Number of target groups reported by the API.',
        'examples': """\
- name: List all target groups
  susunola.tencentcloud.gwlb_target_group_info:
    region: ap-guangzhou

- name: Find target groups by ID
  susunola.tencentcloud.gwlb_target_group_info:
    region: ap-guangzhou
    target_group_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'gwlb_target_group_instances_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.gwlb.v20240906',
        'client_module': 'gwlb_client',
        'client_class': 'GwlbClient',
        'sdk_package': 'tencentcloud-sdk-python-gwlb',
        'endpoint': 'gwlb.tencentcloudapi.com',
        'action': 'DescribeTargetGroupInstances',
        'request_class': 'DescribeTargetGroupInstancesRequest',
        'ids': None,
        'filters': {
            'doc': 'GWLB API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'TargetGroupInstanceSet',
        'response_total': 'TotalCount',
        'result_key': 'target_group_instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud GWLB target group instances',
        'description': 'Returns GWLB target group instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching GWLB target group instances.',
        'return_total_doc': 'Number of target group instances reported by the API.',
        'examples': """\
- name: List all target group instances
  susunola.tencentcloud.gwlb_target_group_instances_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.hai_application_info:
    region: ap-guangzhou

- name: Find applications by ID
  susunola.tencentcloud.hai_application_info:
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
  susunola.tencentcloud.hasim_link_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'hunyuan_glossary_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.hunyuan.v20230901',
        'client_module': 'hunyuan_client',
        'client_class': 'HunyuanClient',
        'sdk_package': 'tencentcloud-sdk-python-hunyuan',
        'endpoint': 'hunyuan.tencentcloudapi.com',
        'action': 'ListGlossary',
        'request_class': 'ListGlossaryRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Glossaries',
        'response_total': 'Total',
        'result_key': 'glossaries',
        'pagination_type': 'page',
        'page_number_field': 'Page',
        'short_description': 'Gather information about Tencent Cloud HUNYUAN glossaries',
        'description': 'Returns HUNYUAN glossaries visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching HUNYUAN glossaries.',
        'return_total_doc': 'Number of glossaries reported by the API.',
        'examples': """\
- name: List all glossaries
  susunola.tencentcloud.hunyuan_glossary_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'iai_group_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.iai.v20200303',
        'client_module': 'iai_client',
        'client_class': 'IaiClient',
        'sdk_package': 'tencentcloud-sdk-python-iai',
        'endpoint': 'iai.tencentcloudapi.com',
        'action': 'GetGroupList',
        'request_class': 'GetGroupListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'GroupInfos',
        'response_total': None,
        'result_key': 'groups',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud IAI groups',
        'description': 'Returns IAI groups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching IAI groups.',
        'return_total_doc': 'Number of groups returned (the API reports no total count).',
        'examples': """\
- name: List all groups
  susunola.tencentcloud.iai_group_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'iap_login_session_duration_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.iap.v20240713',
        'client_module': 'iap_client',
        'client_class': 'IapClient',
        'sdk_package': 'tencentcloud-sdk-python-iap',
        'endpoint': 'iap.tencentcloudapi.com',
        'action': 'DescribeIAPLoginSessionDuration',
        'request_class': 'DescribeIAPLoginSessionDurationRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': None,
        'response_total': None,
        'result_key': 'login_session_duration',
        'pagination_type': 'none',
        'short_description': 'Gather information about Tencent Cloud IAP login session duration',
        'description': 'Returns IAP login session duration visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching IAP login session duration.',
        'return_total_doc': '',
        'examples': """\
- name: Show the login session duration
  susunola.tencentcloud.iap_login_session_duration_info:
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
  susunola.tencentcloud.ic_sms_info:
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
  susunola.tencentcloud.igtm_address_pool_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'ioa_device_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.ioa.v20220601',
        'client_module': 'ioa_client',
        'client_class': 'IoaClient',
        'sdk_package': 'tencentcloud-sdk-python-ioa',
        'endpoint': 'ioa.tencentcloudapi.com',
        'action': 'DescribeDevices',
        'request_class': 'DescribeDevicesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Data.Items',
        'response_total': None,
        'result_key': 'devices',
        'pagination_type': 'page',
        'page_number_field': 'PageNum',
        'short_description': 'Gather information about Tencent Cloud IOA devices',
        'description': 'Returns IOA devices visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching IOA devices.',
        'return_total_doc': 'Number of devices returned (the API reports no total count).',
        'examples': """\
- name: List all devices
  susunola.tencentcloud.ioa_device_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'iot_product_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.iot.v20180123',
        'client_module': 'iot_client',
        'client_class': 'IotClient',
        'sdk_package': 'tencentcloud-sdk-python-iot',
        'endpoint': 'iot.tencentcloudapi.com',
        'action': 'GetProducts',
        'request_class': 'GetProductsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Products',
        'response_total': 'Total',
        'result_key': 'products',
        'pagination_type': 'int',
        'page_size_field': 'Length',
        'short_description': 'Gather information about Tencent Cloud IOT products',
        'description': 'Returns IOT products visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching IOT products.',
        'return_total_doc': 'Number of products reported by the API.',
        'examples': """\
- name: List all products
  susunola.tencentcloud.iot_product_info:
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
  susunola.tencentcloud.iotcloud_device_resource_info:
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
  susunola.tencentcloud.iotexplorer_device_position_info:
    region: ap-guangzhou

- name: Find device positions by ID
  susunola.tencentcloud.iotexplorer_device_position_info:
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
  susunola.tencentcloud.iotvideo_ai_model_application_info:
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
  susunola.tencentcloud.iotvideoindustry_all_device_info:
    region: ap-guangzhou

- name: Find all devices by ID
  susunola.tencentcloud.iotvideoindustry_all_device_info:
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
  susunola.tencentcloud.iss_device_snapshot_info:
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
  susunola.tencentcloud.ivld_custom_person_info:
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
  susunola.tencentcloud.keewidb_instance_backup_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'lcic_answer_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.lcic.v20220817',
        'client_module': 'lcic_client',
        'client_class': 'LcicClient',
        'sdk_package': 'tencentcloud-sdk-python-lcic',
        'endpoint': 'lcic.tencentcloudapi.com',
        'action': 'DescribeAnswerList',
        'request_class': 'DescribeAnswerListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'AnswerInfo',
        'response_total': 'Total',
        'result_key': 'answers',
        'pagination_type': 'page',
        'page_number_field': 'Page',
        'page_size_field': 'Limit',
        'short_description': 'Gather information about Tencent Cloud LCIC answers',
        'description': 'Returns LCIC answers visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching LCIC answers.',
        'return_total_doc': 'Number of answers reported by the API.',
        'examples': """\
- name: List all answers
  susunola.tencentcloud.lcic_answer_info:
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
  susunola.tencentcloud.live_audit_keyword_info:
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
  susunola.tencentcloud.lke_app_knowledge_info:
    region: ap-guangzhou

- name: Find app knowledges by ID
  susunola.tencentcloud.lke_app_knowledge_info:
    region: ap-guangzhou
    app_knowledge_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'lkeap_character_usage_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.lkeap.v20240522',
        'client_module': 'lkeap_client',
        'client_class': 'LkeapClient',
        'sdk_package': 'tencentcloud-sdk-python-lkeap',
        'endpoint': 'lkeap.tencentcloudapi.com',
        'action': 'GetCharacterUsage',
        'request_class': 'GetCharacterUsageRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': None,
        'response_total': None,
        'result_key': 'character_usage',
        'pagination_type': 'none',
        'short_description': 'Gather information about Tencent Cloud LKEAP character usage',
        'description': 'Returns LKEAP character usage visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching LKEAP character usage.',
        'return_total_doc': '',
        'examples': """\
- name: Show the character usage
  susunola.tencentcloud.lkeap_character_usage_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.lowcode_knowledge_set_info:
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
  susunola.tencentcloud.mall_draw_resource_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'mariadb_account_privilege_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.mariadb.v20170312',
        'client_module': 'mariadb_client',
        'client_class': 'MariadbClient',
        'sdk_package': 'tencentcloud-sdk-python-mariadb',
        'endpoint': 'mariadb.tencentcloudapi.com',
        'action': 'DescribeAccountPrivileges',
        'request_class': 'DescribeAccountPrivilegesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'user_name',
                'field': 'UserName',
                'type': 'str',
                'required': False,
                'doc': 'User name. API field C(UserName).',
            },
            {
                'name': 'host',
                'field': 'Host',
                'type': 'str',
                'required': False,
                'doc': 'Host. API field C(Host).',
            },
            {
                'name': 'db_name',
                'field': 'DbName',
                'type': 'str',
                'required': False,
                'doc': 'Db name. API field C(DbName).',
            },
            {
                'name': 'type',
                'field': 'Type',
                'type': 'str',
                'required': False,
                'doc': 'Type. API field C(Type).',
            },
            {
                'name': 'object',
                'field': 'Object',
                'type': 'str',
                'required': False,
                'doc': 'Object. API field C(Object).',
            },
            {
                'name': 'col_name',
                'field': 'ColName',
                'type': 'str',
                'required': False,
                'doc': 'Col name. API field C(ColName).',
            },
        ],
        'response_items': None,
        'response_total': None,
        'result_key': 'account_privilege',
        'pagination_type': 'none',
        'short_description': 'Gather information about Tencent Cloud MARIADB account privilege',
        'description': 'Returns MARIADB account privilege visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MARIADB account privilege.',
        'return_total_doc': '',
        'examples': """\
- name: Show the account privilege
  susunola.tencentcloud.mariadb_account_privilege_info:
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
  susunola.tencentcloud.memcached_instance_info:
    region: ap-guangzhou

- name: Find instances by ID
  susunola.tencentcloud.memcached_instance_info:
    region: ap-guangzhou
    instance_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'mmps_resource_usage_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.mmps.v20200710',
        'client_module': 'mmps_client',
        'client_class': 'MmpsClient',
        'sdk_package': 'tencentcloud-sdk-python-mmps',
        'endpoint': 'mmps.tencentcloudapi.com',
        'action': 'DescribeResourceUsageInfo',
        'request_class': 'DescribeResourceUsageInfoRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Data',
        'response_total': 'Total',
        'result_key': 'resource_usages',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud MMPS resource usages',
        'description': 'Returns MMPS resource usages visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MMPS resource usages.',
        'return_total_doc': 'Number of resource usages reported by the API.',
        'examples': """\
- name: List all resource usages
  susunola.tencentcloud.mmps_resource_usage_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'mna_access_region_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.mna.v20210119',
        'client_module': 'mna_client',
        'client_class': 'MnaClient',
        'sdk_package': 'tencentcloud-sdk-python-mna',
        'endpoint': 'mna.tencentcloudapi.com',
        'action': 'DescribeAccessRegions',
        'request_class': 'DescribeAccessRegionsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'RegionList',
        'response_total': None,
        'result_key': 'access_regions',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud MNA access regions',
        'description': 'Returns MNA access regions visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MNA access regions.',
        'return_total_doc': 'Number of access regions returned (the API reports no total count).',
        'examples': """\
- name: List all access regions
  susunola.tencentcloud.mna_access_region_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.mps_person_sample_info:
    region: ap-guangzhou

- name: Find person samples by ID
  susunola.tencentcloud.mps_person_sample_info:
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
  susunola.tencentcloud.mqtt_device_certificate_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'mqtt_authorization_policy_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.mqtt.v20240516',
        'client_module': 'mqtt_client',
        'client_class': 'MqttClient',
        'sdk_package': 'tencentcloud-sdk-python-mqtt',
        'endpoint': 'mqtt.tencentcloudapi.com',
        'action': 'DescribeAuthorizationPolicies',
        'request_class': 'DescribeAuthorizationPoliciesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': 'Data',
        'response_total': None,
        'result_key': 'authorization_policies',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud MQTT authorization policies',
        'description': 'Returns MQTT authorization policies visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MQTT authorization policies.',
        'return_total_doc': 'Number of authorization policies returned (the API reports no total count).',
        'examples': """\
- name: List all authorization policies
  susunola.tencentcloud.mqtt_authorization_policy_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'mqtt_instance_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.mqtt.v20240516',
        'client_module': 'mqtt_client',
        'client_class': 'MqttClient',
        'sdk_package': 'tencentcloud-sdk-python-mqtt',
        'endpoint': 'mqtt.tencentcloudapi.com',
        'action': 'DescribeInstanceList',
        'request_class': 'DescribeInstanceListRequest',
        'ids': None,
        'filters': {
            'doc': 'MQTT API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'Data',
        'response_total': 'TotalCount',
        'result_key': 'instances',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud MQTT instances',
        'description': 'Returns MQTT instances visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MQTT instances.',
        'return_total_doc': 'Number of instances reported by the API.',
        'examples': """\
- name: List all instances
  susunola.tencentcloud.mqtt_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'mqtt_topic_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.mqtt.v20240516',
        'client_module': 'mqtt_client',
        'client_class': 'MqttClient',
        'sdk_package': 'tencentcloud-sdk-python-mqtt',
        'endpoint': 'mqtt.tencentcloudapi.com',
        'action': 'DescribeTopicList',
        'request_class': 'DescribeTopicListRequest',
        'ids': None,
        'filters': {
            'doc': 'MQTT API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': 'Data',
        'response_total': 'TotalCount',
        'result_key': 'topics',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud MQTT topics',
        'description': 'Returns MQTT topics visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MQTT topics.',
        'return_total_doc': 'Number of topics reported by the API.',
        'examples': """\
- name: List all topics
  susunola.tencentcloud.mqtt_topic_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'mqtt_user_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.mqtt.v20240516',
        'client_module': 'mqtt_client',
        'client_class': 'MqttClient',
        'sdk_package': 'tencentcloud-sdk-python-mqtt',
        'endpoint': 'mqtt.tencentcloudapi.com',
        'action': 'DescribeUserList',
        'request_class': 'DescribeUserListRequest',
        'ids': None,
        'filters': {
            'doc': 'MQTT API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': 'Data',
        'response_total': 'TotalCount',
        'result_key': 'users',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud MQTT users',
        'description': 'Returns MQTT users visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching MQTT users.',
        'return_total_doc': 'Number of users reported by the API.',
        'examples': """\
- name: List all users
  susunola.tencentcloud.mqtt_user_info:
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
  susunola.tencentcloud.ms_shield_instance_info:
    region: ap-guangzhou

- name: Find shield instances by ID
  susunola.tencentcloud.ms_shield_instance_info:
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
  susunola.tencentcloud.msp_migration_project_info:
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
  susunola.tencentcloud.oceanus_cluster_info:
    region: ap-guangzhou

- name: Find clusters by ID
  susunola.tencentcloud.oceanus_cluster_info:
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
  susunola.tencentcloud.omics_application_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'organization_member_identity_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.organization.v20210331',
        'client_module': 'organization_client',
        'client_class': 'OrganizationClient',
        'sdk_package': 'tencentcloud-sdk-python-organization',
        'endpoint': 'organization.tencentcloudapi.com',
        'action': 'DescribeOrganizationMemberAuthIdentities',
        'request_class': 'DescribeOrganizationMemberAuthIdentitiesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'member_uin',
                'field': 'MemberUin',
                'type': 'int',
                'required': False,
                'doc': 'Member uin. API field C(MemberUin).',
            },
            {
                'name': 'identity_id',
                'field': 'IdentityId',
                'type': 'int',
                'required': False,
                'doc': 'Identity id. API field C(IdentityId).',
            },
        ],
        'response_items': 'Items',
        'response_total': 'Total',
        'result_key': 'member_auth_identities',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud ORGANIZATION member auth identities',
        'description': 'Returns ORGANIZATION member auth identities visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ORGANIZATION member auth identities.',
        'return_total_doc': 'Number of member auth identities reported by the API.',
        'examples': """\
- name: List all member auth identities
  susunola.tencentcloud.organization_member_identity_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'organization_member_policy_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.organization.v20210331',
        'client_module': 'organization_client',
        'client_class': 'OrganizationClient',
        'sdk_package': 'tencentcloud-sdk-python-organization',
        'endpoint': 'organization.tencentcloudapi.com',
        'action': 'DescribeOrganizationMemberPolicies',
        'request_class': 'DescribeOrganizationMemberPoliciesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'member_uin',
                'field': 'MemberUin',
                'type': 'int',
                'required': False,
                'doc': 'Member uin. API field C(MemberUin).',
            },
            {
                'name': 'search_key',
                'field': 'SearchKey',
                'type': 'str',
                'required': False,
                'doc': 'Search key. API field C(SearchKey).',
                'no_log': False,
            },
        ],
        'response_items': 'Items',
        'response_total': 'Total',
        'result_key': 'member_policies',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud ORGANIZATION member policies',
        'description': 'Returns ORGANIZATION member policies visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ORGANIZATION member policies.',
        'return_total_doc': 'Number of member policies reported by the API.',
        'examples': """\
- name: List all member policies
  susunola.tencentcloud.organization_member_policy_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'organization_node_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.organization.v20210331',
        'client_module': 'organization_client',
        'client_class': 'OrganizationClient',
        'sdk_package': 'tencentcloud-sdk-python-organization',
        'endpoint': 'organization.tencentcloudapi.com',
        'action': 'DescribeOrganizationNodes',
        'request_class': 'DescribeOrganizationNodesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Items',
        'response_total': 'Total',
        'result_key': 'nodes',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud ORGANIZATION nodes',
        'description': 'Returns ORGANIZATION nodes visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching ORGANIZATION nodes.',
        'return_total_doc': 'Number of nodes reported by the API.',
        'examples': """\
- name: List all nodes
  susunola.tencentcloud.organization_node_info:
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
  susunola.tencentcloud.partners_agent_deals_by_cache_info:
    region: ap-guangzhou

- name: Find agent deals by caches by ID
  susunola.tencentcloud.partners_agent_deals_by_cache_info:
    region: ap-guangzhou
    agent_deals_by_cache_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'portal_document_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.portal.v20230413',
        'client_module': 'portal_client',
        'client_class': 'PortalClient',
        'sdk_package': 'tencentcloud-sdk-python-portal',
        'endpoint': 'portal.tencentcloudapi.com',
        'action': 'SearchDocuments',
        'request_class': 'SearchDocumentsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Documents',
        'response_total': 'Total',
        'result_key': 'documents',
        'pagination_type': 'page',
        'page_number_field': 'Page',
        'short_description': 'Gather information about Tencent Cloud PORTAL documents',
        'description': 'Returns PORTAL documents visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching PORTAL documents.',
        'return_total_doc': 'Number of documents reported by the API.',
        'examples': """\
- name: List all documents
  susunola.tencentcloud.portal_document_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.privatedns_account_vpc_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'private_dns_account_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.privatedns.v20201028',
        'client_module': 'privatedns_client',
        'client_class': 'PrivatednsClient',
        'sdk_package': 'tencentcloud-sdk-python-privatedns',
        'endpoint': 'privatedns.tencentcloudapi.com',
        'action': 'DescribePrivateDNSAccountList',
        'request_class': 'DescribePrivateDNSAccountListRequest',
        'ids': None,
        'filters': {
            'doc': 'PRIVATEDNS API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'AccountSet',
        'response_total': 'TotalCount',
        'result_key': 'private_dns_accounts',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud PRIVATEDNS private dns accounts',
        'description': 'Returns PRIVATEDNS private dns accounts visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching PRIVATEDNS private dns accounts.',
        'return_total_doc': 'Number of private dns accounts reported by the API.',
        'examples': """\
- name: List all private dns accounts
  susunola.tencentcloud.private_dns_account_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'private_dns_record_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.privatedns.v20201028',
        'client_module': 'privatedns_client',
        'client_class': 'PrivatednsClient',
        'sdk_package': 'tencentcloud-sdk-python-privatedns',
        'endpoint': 'privatedns.tencentcloudapi.com',
        'action': 'DescribePrivateZoneRecordList',
        'request_class': 'DescribePrivateZoneRecordListRequest',
        'ids': None,
        'filters': {
            'doc': 'PRIVATEDNS API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'zone_id',
                'field': 'ZoneId',
                'type': 'str',
                'required': False,
                'doc': 'Zone id. API field C(ZoneId).',
            },
        ],
        'response_items': 'RecordSet',
        'response_total': 'TotalCount',
        'result_key': 'private_zone_records',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud PRIVATEDNS private zone records',
        'description': 'Returns PRIVATEDNS private zone records visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching PRIVATEDNS private zone records.',
        'return_total_doc': 'Number of private zone records reported by the API.',
        'examples': """\
- name: List all private zone records
  susunola.tencentcloud.private_dns_record_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'private_dns_zone_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.privatedns.v20201028',
        'client_module': 'privatedns_client',
        'client_class': 'PrivatednsClient',
        'sdk_package': 'tencentcloud-sdk-python-privatedns',
        'endpoint': 'privatedns.tencentcloudapi.com',
        'action': 'DescribePrivateZoneList',
        'request_class': 'DescribePrivateZoneListRequest',
        'ids': None,
        'filters': {
            'doc': 'PRIVATEDNS API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'PrivateZoneSet',
        'response_total': 'TotalCount',
        'result_key': 'private_zones',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud PRIVATEDNS private zones',
        'description': 'Returns PRIVATEDNS private zones visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching PRIVATEDNS private zones.',
        'return_total_doc': 'Number of private zones reported by the API.',
        'examples': """\
- name: List all private zones
  susunola.tencentcloud.private_dns_zone_info:
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
  susunola.tencentcloud.pts_cron_job_info:
    region: ap-guangzhou

- name: Find cron jobs by ID
  susunola.tencentcloud.pts_cron_job_info:
    region: ap-guangzhou
    cron_job_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'redis_replication_group_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.redis.v20180412',
        'client_module': 'redis_client',
        'client_class': 'RedisClient',
        'sdk_package': 'tencentcloud-sdk-python-redis',
        'endpoint': 'redis.tencentcloudapi.com',
        'action': 'DescribeReplicationGroup',
        'request_class': 'DescribeReplicationGroupRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'group_id',
                'field': 'GroupId',
                'type': 'str',
                'required': False,
                'doc': 'Group id. API field C(GroupId).',
            },
            {
                'name': 'search_key',
                'field': 'SearchKey',
                'type': 'str',
                'required': False,
                'doc': 'Search key. API field C(SearchKey).',
                'no_log': False,
            },
        ],
        'response_items': 'Groups',
        'response_total': 'TotalCount',
        'result_key': 'replication_groups',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud REDIS replication groups',
        'description': 'Returns REDIS replication groups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching REDIS replication groups.',
        'return_total_doc': 'Number of replication groups reported by the API.',
        'examples': """\
- name: List all replication groups
  susunola.tencentcloud.redis_replication_group_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.region_product_info:
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
  susunola.tencentcloud.rum_project_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'scf_custom_domain_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.scf.v20180416',
        'client_module': 'scf_client',
        'client_class': 'ScfClient',
        'sdk_package': 'tencentcloud-sdk-python-scf',
        'endpoint': 'scf.tencentcloudapi.com',
        'action': 'ListCustomDomains',
        'request_class': 'ListCustomDomainsRequest',
        'ids': None,
        'filters': {
            'doc': 'SCF API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'order_by',
                'field': 'OrderBy',
                'type': 'str',
                'required': False,
                'doc': 'Order by. API field C(OrderBy).',
            },
            {
                'name': 'order',
                'field': 'Order',
                'type': 'str',
                'required': False,
                'doc': 'Order. API field C(Order).',
            },
        ],
        'response_items': 'Domains',
        'response_total': 'Total',
        'result_key': 'custom_domains',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud SCF custom domains',
        'description': 'Returns SCF custom domains visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching SCF custom domains.',
        'return_total_doc': 'Number of custom domains reported by the API.',
        'examples': """\
- name: List all custom domains
  susunola.tencentcloud.scf_custom_domain_info:
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
  susunola.tencentcloud.securitylake_security_alarm_table_info:
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
  susunola.tencentcloud.ses_black_email_address_info:
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
  susunola.tencentcloud.smh_library_info:
    region: ap-guangzhou

- name: Find libraries by ID
  susunola.tencentcloud.smh_library_info:
    region: ap-guangzhou
    library_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'sms_sign_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.sms.v20210111',
        'client_module': 'sms_client',
        'client_class': 'SmsClient',
        'sdk_package': 'tencentcloud-sdk-python-sms',
        'endpoint': 'sms.tencentcloudapi.com',
        'action': 'DescribeSmsSignList',
        'request_class': 'DescribeSmsSignListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'DescribeSignListStatusSet',
        'response_total': None,
        'result_key': 'signs',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud SMS signs',
        'description': 'Returns SMS signs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching SMS signs.',
        'return_total_doc': 'Number of signs reported by the API.',
        'examples': """\
- name: List all signs
  susunola.tencentcloud.sms_sign_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.ssa_check_config_asset_info:
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
  susunola.tencentcloud.sslpod_domain_info:
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
  susunola.tencentcloud.svp_saving_plan_coverage_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tat_invoker_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tat.v20201028',
        'client_module': 'tat_client',
        'client_class': 'TatClient',
        'sdk_package': 'tencentcloud-sdk-python-tat',
        'endpoint': 'tat.tencentcloudapi.com',
        'action': 'DescribeInvokers',
        'request_class': 'DescribeInvokersRequest',
        'ids': {
            'param': 'invoker_ids',
            'field': 'InvokerIds',
            'doc': 'Invoker IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'TAT API filter names mapped to lists of values.',
        },
        'extra_params': [],
        'response_items': 'InvokerSet',
        'response_total': 'TotalCount',
        'result_key': 'invokers',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TAT invokers',
        'description': 'Returns TAT invokers visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TAT invokers.',
        'return_total_doc': 'Number of invokers reported by the API.',
        'examples': """\
- name: List all invokers
  susunola.tencentcloud.tat_invoker_info:
    region: ap-guangzhou

- name: Find invokers by ID
  susunola.tencentcloud.tat_invoker_info:
    region: ap-guangzhou
    invoker_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'tbaas_block_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.tbaas.v20180416',
        'client_module': 'tbaas_client',
        'client_class': 'TbaasClient',
        'sdk_package': 'tencentcloud-sdk-python-tbaas',
        'endpoint': 'tbaas.tencentcloudapi.com',
        'action': 'GetBlockList',
        'request_class': 'GetBlockListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'BlockList',
        'response_total': 'TotalCount',
        'result_key': 'blocks',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TBAAS blocks',
        'description': 'Returns TBAAS blocks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TBAAS blocks.',
        'return_total_doc': 'Number of blocks reported by the API.',
        'examples': """\
- name: List all blocks
  susunola.tencentcloud.tbaas_block_info:
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
  susunola.tencentcloud.tcaplusdb_cluster_info:
    region: ap-guangzhou

- name: Find clusters by ID
  susunola.tencentcloud.tcaplusdb_cluster_info:
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
  susunola.tencentcloud.tcb_billing_info:
    region: ap-guangzhou

- name: Find billings by ID
  susunola.tencentcloud.tcb_billing_info:
    region: ap-guangzhou
    billing_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'tcb_auth_domain_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tcb.v20180608',
        'client_module': 'tcb_client',
        'client_class': 'TcbClient',
        'sdk_package': 'tencentcloud-sdk-python-tcb',
        'endpoint': 'tcb.tencentcloudapi.com',
        'action': 'DescribeAuthDomains',
        'request_class': 'DescribeAuthDomainsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'env_id',
                'field': 'EnvId',
                'type': 'str',
                'required': False,
                'doc': 'Env id. API field C(EnvId).',
            },
        ],
        'response_items': 'Domains',
        'response_total': None,
        'result_key': 'auth_domains',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud TCB auth domains',
        'description': 'Returns TCB auth domains visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TCB auth domains.',
        'return_total_doc': 'Number of auth domains returned (the API reports no total count).',
        'examples': """\
- name: List all auth domains
  susunola.tencentcloud.tcb_auth_domain_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tcb_environment_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tcb.v20180608',
        'client_module': 'tcb_client',
        'client_class': 'TcbClient',
        'sdk_package': 'tencentcloud-sdk-python-tcb',
        'endpoint': 'tcb.tencentcloudapi.com',
        'action': 'DescribeEnvs',
        'request_class': 'DescribeEnvsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'env_id',
                'field': 'EnvId',
                'type': 'str',
                'required': False,
                'doc': 'Env id. API field C(EnvId).',
            },
            {
                'name': 'is_visible',
                'field': 'IsVisible',
                'type': 'bool',
                'required': False,
                'doc': 'Is visible. API field C(IsVisible).',
            },
            {
                'name': 'channels',
                'field': 'Channels',
                'type': 'list',
                'required': False,
                'doc': 'Channels. API field C(Channels).',
                'elements': 'str',
            },
        ],
        'response_items': 'EnvList',
        'response_total': 'Total',
        'result_key': 'envs',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TCB envs',
        'description': 'Returns TCB envs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TCB envs.',
        'return_total_doc': 'Number of envs reported by the API.',
        'examples': """\
- name: List all envs
  susunola.tencentcloud.tcb_environment_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tcb_http_service_route_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tcb.v20180608',
        'client_module': 'tcb_client',
        'client_class': 'TcbClient',
        'sdk_package': 'tencentcloud-sdk-python-tcb',
        'endpoint': 'tcb.tencentcloudapi.com',
        'action': 'DescribeHTTPServiceRoute',
        'request_class': 'DescribeHTTPServiceRouteRequest',
        'ids': None,
        'filters': {
            'doc': 'TCB API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'env_id',
                'field': 'EnvId',
                'type': 'str',
                'required': False,
                'doc': 'Env id. API field C(EnvId).',
            },
        ],
        'response_items': 'Domains',
        'response_total': 'TotalCount',
        'result_key': 'http_service_routes',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TCB http service routes',
        'description': 'Returns TCB http service routes visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TCB http service routes.',
        'return_total_doc': 'Number of http service routes reported by the API.',
        'examples': """\
- name: List all http service routes
  susunola.tencentcloud.tcb_http_service_route_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tcb_static_store_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tcb.v20180608',
        'client_module': 'tcb_client',
        'client_class': 'TcbClient',
        'sdk_package': 'tencentcloud-sdk-python-tcb',
        'endpoint': 'tcb.tencentcloudapi.com',
        'action': 'DescribeStaticStore',
        'request_class': 'DescribeStaticStoreRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'env_id',
                'field': 'EnvId',
                'type': 'str',
                'required': False,
                'doc': 'Env id. API field C(EnvId).',
            },
        ],
        'response_items': 'Data',
        'response_total': None,
        'result_key': 'static_stores',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud TCB static stores',
        'description': 'Returns TCB static stores visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TCB static stores.',
        'return_total_doc': 'Number of static stores returned (the API reports no total count).',
        'examples': """\
- name: List all static stores
  susunola.tencentcloud.tcb_static_store_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tcbr_cloud_run_pod_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.tcbr.v20220217',
        'client_module': 'tcbr_client',
        'client_class': 'TcbrClient',
        'sdk_package': 'tencentcloud-sdk-python-tcbr',
        'endpoint': 'tcbr.tencentcloudapi.com',
        'action': 'DescribeCloudRunPodList',
        'request_class': 'DescribeCloudRunPodListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'PodList',
        'response_total': 'TotalCount',
        'result_key': 'cloud_run_pods',
        'pagination_type': 'page',
        'page_number_field': 'PageNum',
        'short_description': 'Gather information about Tencent Cloud TCBR cloud run pods',
        'description': 'Returns TCBR cloud run pods visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TCBR cloud run pods.',
        'return_total_doc': 'Number of cloud run pods reported by the API.',
        'examples': """\
- name: List all cloud run pods
  susunola.tencentcloud.tcbr_cloud_run_pod_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.tcm_mesh_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tcm_access_log_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tcm.v20210413',
        'client_module': 'tcm_client',
        'client_class': 'TcmClient',
        'sdk_package': 'tencentcloud-sdk-python-tcm',
        'endpoint': 'tcm.tencentcloudapi.com',
        'action': 'DescribeAccessLogConfig',
        'request_class': 'DescribeAccessLogConfigRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'mesh_id',
                'field': 'MeshId',
                'type': 'str',
                'required': False,
                'doc': 'Mesh id. API field C(MeshId).',
            },
        ],
        'response_items': 'SelectedRange.Items',
        'response_total': None,
        'result_key': 'access_log_configs',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud TCM access log configs',
        'description': 'Returns TCM access log configs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TCM access log configs.',
        'return_total_doc': 'Number of access log configs returned (the API reports no total count).',
        'examples': """\
- name: List all access log configs
  susunola.tencentcloud.tcm_access_log_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tcr_immutable_tag_rule_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tcr.v20190924',
        'client_module': 'tcr_client',
        'client_class': 'TcrClient',
        'sdk_package': 'tencentcloud-sdk-python-tcr',
        'endpoint': 'tcr.tencentcloudapi.com',
        'action': 'DescribeImmutableTagRules',
        'request_class': 'DescribeImmutableTagRulesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'registry_id',
                'field': 'RegistryId',
                'type': 'str',
                'required': False,
                'doc': 'Registry id. API field C(RegistryId).',
            },
        ],
        'response_items': 'Rules',
        'response_total': 'Total',
        'result_key': 'immutable_tag_rules',
        'pagination_type': 'page',
        'page_number_field': 'Page',
        'short_description': 'Gather information about Tencent Cloud TCR immutable tag rules',
        'description': 'Returns TCR immutable tag rules visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TCR immutable tag rules.',
        'return_total_doc': 'Number of immutable tag rules reported by the API.',
        'examples': """\
- name: List all immutable tag rules
  susunola.tencentcloud.tcr_immutable_tag_rule_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tcr_webhook_trigger_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tcr.v20190924',
        'client_module': 'tcr_client',
        'client_class': 'TcrClient',
        'sdk_package': 'tencentcloud-sdk-python-tcr',
        'endpoint': 'tcr.tencentcloudapi.com',
        'action': 'DescribeWebhookTrigger',
        'request_class': 'DescribeWebhookTriggerRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'registry_id',
                'field': 'RegistryId',
                'type': 'str',
                'required': False,
                'doc': 'Registry id. API field C(RegistryId).',
            },
            {
                'name': 'namespace',
                'field': 'Namespace',
                'type': 'str',
                'required': False,
                'doc': 'Namespace. API field C(Namespace).',
            },
        ],
        'response_items': 'Triggers',
        'response_total': 'TotalCount',
        'result_key': 'webhook_triggers',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TCR webhook triggers',
        'description': 'Returns TCR webhook triggers visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TCR webhook triggers.',
        'return_total_doc': 'Number of webhook triggers reported by the API.',
        'examples': """\
- name: List all webhook triggers
  susunola.tencentcloud.tcr_webhook_trigger_info:
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
  susunola.tencentcloud.tcss_abnormal_process_event_info:
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
  susunola.tencentcloud.tdai_agent_duty_task_info:
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
  susunola.tencentcloud.tdcpg_cluster_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tdcpg_account_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tdcpg.v20211118',
        'client_module': 'tdcpg_client',
        'client_class': 'TdcpgClient',
        'sdk_package': 'tencentcloud-sdk-python-tdcpg',
        'endpoint': 'tdcpg.tencentcloudapi.com',
        'action': 'DescribeAccounts',
        'request_class': 'DescribeAccountsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'cluster_id',
                'field': 'ClusterId',
                'type': 'str',
                'required': False,
                'doc': 'Cluster id. API field C(ClusterId).',
            },
        ],
        'response_items': 'AccountSet',
        'response_total': 'TotalCount',
        'result_key': 'accounts',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud TDCPG accounts',
        'description': 'Returns TDCPG accounts visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TDCPG accounts.',
        'return_total_doc': 'Number of accounts reported by the API.',
        'examples': """\
- name: List all accounts
  susunola.tencentcloud.tdcpg_account_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tdcpg_endpoint_wan_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tdcpg.v20211118',
        'client_module': 'tdcpg_client',
        'client_class': 'TdcpgClient',
        'sdk_package': 'tencentcloud-sdk-python-tdcpg',
        'endpoint': 'tdcpg.tencentcloudapi.com',
        'action': 'DescribeClusterEndpoints',
        'request_class': 'DescribeClusterEndpointsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'cluster_id',
                'field': 'ClusterId',
                'type': 'str',
                'required': False,
                'doc': 'Cluster id. API field C(ClusterId).',
            },
        ],
        'response_items': 'EndpointSet',
        'response_total': 'TotalCount',
        'result_key': 'cluster_endpoints',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud TDCPG cluster endpoints',
        'description': 'Returns TDCPG cluster endpoints visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TDCPG cluster endpoints.',
        'return_total_doc': 'Number of cluster endpoints reported by the API.',
        'examples': """\
- name: List all cluster endpoints
  susunola.tencentcloud.tdcpg_endpoint_wan_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tdcpg_instance_state_info',
        'version_added': '1.5.0',
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
        'extra_params': [
            {
                'name': 'cluster_id',
                'field': 'ClusterId',
                'type': 'str',
                'required': False,
                'doc': 'Cluster id. API field C(ClusterId).',
            },
            {
                'name': 'order_by',
                'field': 'OrderBy',
                'type': 'str',
                'required': False,
                'doc': 'Order by. API field C(OrderBy).',
            },
            {
                'name': 'order_by_type',
                'field': 'OrderByType',
                'type': 'str',
                'required': False,
                'doc': 'Order by type. API field C(OrderByType).',
            },
        ],
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
  susunola.tencentcloud.tdcpg_instance_state_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tdid_over_summary_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.tdid.v20210519',
        'client_module': 'tdid_client',
        'client_class': 'TdidClient',
        'sdk_package': 'tencentcloud-sdk-python-tdid',
        'endpoint': 'tdid.tencentcloudapi.com',
        'action': 'GetOverSummary',
        'request_class': 'GetOverSummaryRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': None,
        'response_total': None,
        'result_key': 'over_summary',
        'pagination_type': 'none',
        'short_description': 'Gather information about Tencent Cloud TDID over summary',
        'description': 'Returns TDID over summary visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TDID over summary.',
        'return_total_doc': '',
        'examples': """\
- name: Show the over summary
  susunola.tencentcloud.tdid_over_summary_info:
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
  susunola.tencentcloud.tdmq_amqp_cluster_info:
    region: ap-guangzhou

- name: Find amqp clusters by ID
  susunola.tencentcloud.tdmq_amqp_cluster_info:
    region: ap-guangzhou
    amqp_cluster_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'cmq_topic_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tdmq.v20200217',
        'client_module': 'tdmq_client',
        'client_class': 'TdmqClient',
        'sdk_package': 'tencentcloud-sdk-python-tdmq',
        'endpoint': 'tdmq.tencentcloudapi.com',
        'action': 'DescribeCmqTopics',
        'request_class': 'DescribeCmqTopicsRequest',
        'ids': None,
        'filters': {
            'doc': 'TDMQ API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'topic_name',
                'field': 'TopicName',
                'type': 'str',
                'required': False,
                'doc': 'Topic name. API field C(TopicName).',
            },
            {
                'name': 'topic_name_list',
                'field': 'TopicNameList',
                'type': 'list',
                'required': False,
                'doc': 'Topic name list. API field C(TopicNameList).',
                'elements': 'str',
            },
            {
                'name': 'is_tag_filter',
                'field': 'IsTagFilter',
                'type': 'bool',
                'required': False,
                'doc': 'Is tag filter. API field C(IsTagFilter).',
            },
        ],
        'response_items': 'TopicList',
        'response_total': 'TotalCount',
        'result_key': 'cmq_topics',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TDMQ cmq topics',
        'description': 'Returns TDMQ cmq topics visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TDMQ cmq topics.',
        'return_total_doc': 'Number of cmq topics reported by the API.',
        'examples': """\
- name: List all cmq topics
  susunola.tencentcloud.cmq_topic_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'cmq_subscription_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tdmq.v20200217',
        'client_module': 'tdmq_client',
        'client_class': 'TdmqClient',
        'sdk_package': 'tencentcloud-sdk-python-tdmq',
        'endpoint': 'tdmq.tencentcloudapi.com',
        'action': 'DescribeCmqSubscriptionDetail',
        'request_class': 'DescribeCmqSubscriptionDetailRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'topic_name',
                'field': 'TopicName',
                'type': 'str',
                'required': False,
                'doc': 'Topic name. API field C(TopicName).',
            },
            {
                'name': 'subscription_name',
                'field': 'SubscriptionName',
                'type': 'str',
                'required': False,
                'doc': 'Subscription name. API field C(SubscriptionName).',
            },
            {
                'name': 'queue_name',
                'field': 'QueueName',
                'type': 'str',
                'required': False,
                'doc': 'Queue name. API field C(QueueName).',
            },
            {
                'name': 'query_type',
                'field': 'QueryType',
                'type': 'str',
                'required': False,
                'doc': 'Query type. API field C(QueryType).',
            },
        ],
        'response_items': 'SubscriptionSet',
        'response_total': 'TotalCount',
        'result_key': 'cmq_subscriptions',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TDMQ cmq subscriptions',
        'description': 'Returns TDMQ cmq subscriptions visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TDMQ cmq subscriptions.',
        'return_total_doc': 'Number of cmq subscriptions reported by the API.',
        'examples': """\
- name: List all cmq subscriptions
  susunola.tencentcloud.cmq_subscription_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.tdmysql_db_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tdmysql_account_privilege_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tdmysql.v20211122',
        'client_module': 'tdmysql_client',
        'client_class': 'TdmysqlClient',
        'sdk_package': 'tencentcloud-sdk-python-tdmysql',
        'endpoint': 'tdmysql.tencentcloudapi.com',
        'action': 'DescribeUserPrivileges',
        'request_class': 'DescribeUserPrivilegesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'host',
                'field': 'Host',
                'type': 'str',
                'required': False,
                'doc': 'Host. API field C(Host).',
            },
            {
                'name': 'user_name',
                'field': 'UserName',
                'type': 'str',
                'required': False,
                'doc': 'User name. API field C(UserName).',
            },
            {
                'name': 'db_name',
                'field': 'DbName',
                'type': 'str',
                'required': False,
                'doc': 'Db name. API field C(DbName).',
            },
            {
                'name': 'object',
                'field': 'Object',
                'type': 'str',
                'required': False,
                'doc': 'Object. API field C(Object).',
            },
            {
                'name': 'object_type',
                'field': 'ObjectType',
                'type': 'str',
                'required': False,
                'doc': 'Object type. API field C(ObjectType).',
            },
            {
                'name': 'col_name',
                'field': 'ColName',
                'type': 'str',
                'required': False,
                'doc': 'Col name. API field C(ColName).',
            },
        ],
        'response_items': None,
        'response_total': None,
        'result_key': 'user_privilege',
        'pagination_type': 'none',
        'short_description': 'Gather information about Tencent Cloud TDMYSQL user privilege',
        'description': 'Returns TDMYSQL user privilege visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TDMYSQL user privilege.',
        'return_total_doc': '',
        'examples': """\
- name: Show the user privilege
  susunola.tencentcloud.tdmysql_account_privilege_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tdmysql_maintenance_window_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tdmysql.v20211122',
        'client_module': 'tdmysql_client',
        'client_class': 'TdmysqlClient',
        'sdk_package': 'tencentcloud-sdk-python-tdmysql',
        'endpoint': 'tdmysql.tencentcloudapi.com',
        'action': 'DescribeMaintenanceWindow',
        'request_class': 'DescribeMaintenanceWindowRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': None,
        'response_total': None,
        'result_key': 'maintenance_window',
        'pagination_type': 'none',
        'short_description': 'Gather information about Tencent Cloud TDMYSQL maintenance window',
        'description': 'Returns TDMYSQL maintenance window visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TDMYSQL maintenance window.',
        'return_total_doc': '',
        'examples': """\
- name: Show the maintenance window
  susunola.tencentcloud.tdmysql_maintenance_window_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tdmysql_ssl_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tdmysql.v20211122',
        'client_module': 'tdmysql_client',
        'client_class': 'TdmysqlClient',
        'sdk_package': 'tencentcloud-sdk-python-tdmysql',
        'endpoint': 'tdmysql.tencentcloudapi.com',
        'action': 'DescribeInstanceSSLStatus',
        'request_class': 'DescribeInstanceSSLStatusRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
        ],
        'response_items': None,
        'response_total': None,
        'result_key': 'instance_ssl',
        'pagination_type': 'none',
        'short_description': 'Gather information about Tencent Cloud TDMYSQL instance ssl',
        'description': 'Returns TDMYSQL instance ssl visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TDMYSQL instance ssl.',
        'return_total_doc': '',
        'examples': """\
- name: Show the instance ssl
  susunola.tencentcloud.tdmysql_ssl_info:
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
  susunola.tencentcloud.tem_application_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tem_application_service_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tem.v20210701',
        'client_module': 'tem_client',
        'client_class': 'TemClient',
        'sdk_package': 'tencentcloud-sdk-python-tem',
        'endpoint': 'tem.tencentcloudapi.com',
        'action': 'DescribeApplicationServiceList',
        'request_class': 'DescribeApplicationServiceListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'environment_id',
                'field': 'EnvironmentId',
                'type': 'str',
                'required': False,
                'doc': 'Environment id. API field C(EnvironmentId).',
            },
            {
                'name': 'application_id',
                'field': 'ApplicationId',
                'type': 'str',
                'required': False,
                'doc': 'Application id. API field C(ApplicationId).',
            },
            {
                'name': 'source_channel',
                'field': 'SourceChannel',
                'type': 'int',
                'required': False,
                'doc': 'Source channel. API field C(SourceChannel).',
            },
        ],
        'response_items': 'Result.PortMappings',
        'response_total': None,
        'result_key': 'application_services',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud TEM application services',
        'description': 'Returns TEM application services visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TEM application services.',
        'return_total_doc': 'Number of application services returned (the API reports no total count).',
        'examples': """\
- name: List all application services
  susunola.tencentcloud.tem_application_service_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tem_environment_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tem.v20210701',
        'client_module': 'tem_client',
        'client_class': 'TemClient',
        'sdk_package': 'tencentcloud-sdk-python-tem',
        'endpoint': 'tem.tencentcloudapi.com',
        'action': 'DescribeEnvironments',
        'request_class': 'DescribeEnvironmentsRequest',
        'ids': None,
        'filters': {
            'doc': 'TEM API filter names mapped to lists of values.',
            'model': 'QueryFilter',
            'value_field': 'Value',
        },
        'extra_params': [
            {
                'name': 'source_channel',
                'field': 'SourceChannel',
                'type': 'int',
                'required': False,
                'doc': 'Source channel. API field C(SourceChannel).',
            },
            {
                'name': 'environment_id',
                'field': 'EnvironmentId',
                'type': 'str',
                'required': False,
                'doc': 'Environment id. API field C(EnvironmentId).',
            },
        ],
        'response_items': 'Result.Records',
        'response_total': 'Result.Total',
        'result_key': 'environments',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TEM environments',
        'description': 'Returns TEM environments visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TEM environments.',
        'return_total_doc': 'Number of environments reported by the API.',
        'examples': """\
- name: List all environments
  susunola.tencentcloud.tem_environment_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tem_application_deployment_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tem.v20210701',
        'client_module': 'tem_client',
        'client_class': 'TemClient',
        'sdk_package': 'tencentcloud-sdk-python-tem',
        'endpoint': 'tem.tencentcloudapi.com',
        'action': 'DescribeDeployApplicationDetail',
        'request_class': 'DescribeDeployApplicationDetailRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'application_id',
                'field': 'ApplicationId',
                'type': 'str',
                'required': False,
                'doc': 'Application id. API field C(ApplicationId).',
            },
            {
                'name': 'environment_id',
                'field': 'EnvironmentId',
                'type': 'str',
                'required': False,
                'doc': 'Environment id. API field C(EnvironmentId).',
            },
            {
                'name': 'version_id',
                'field': 'VersionId',
                'type': 'str',
                'required': False,
                'doc': 'Version id. API field C(VersionId).',
            },
        ],
        'response_items': 'Result.OtherBatchDetail',
        'response_total': None,
        'result_key': 'deployments',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud TEM deployments',
        'description': 'Returns TEM deployments visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TEM deployments.',
        'return_total_doc': 'Number of deployments returned (the API reports no total count).',
        'examples': """\
- name: List all deployments
  susunola.tencentcloud.tem_application_deployment_info:
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
  susunola.tencentcloud.teo_function_info:
    region: ap-guangzhou

- name: Find functions by ID
  susunola.tencentcloud.teo_function_info:
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
  susunola.tencentcloud.thpc_cluster_info:
    region: ap-guangzhou

- name: Find clusters by ID
  susunola.tencentcloud.thpc_cluster_info:
    region: ap-guangzhou
    cluster_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'tia_job_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.tia.v20180226',
        'client_module': 'tia_client',
        'client_class': 'TiaClient',
        'sdk_package': 'tencentcloud-sdk-python-tia',
        'endpoint': 'tia.tencentcloudapi.com',
        'action': 'ListJobs',
        'request_class': 'ListJobsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Jobs',
        'response_total': None,
        'result_key': 'jobs',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TIA jobs',
        'description': 'Returns TIA jobs visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TIA jobs.',
        'return_total_doc': 'Number of jobs returned (the API reports no total count).',
        'examples': """\
- name: List all jobs
  susunola.tencentcloud.tia_job_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tiia_group_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.tiia.v20190529',
        'client_module': 'tiia_client',
        'client_class': 'TiiaClient',
        'sdk_package': 'tencentcloud-sdk-python-tiia',
        'endpoint': 'tiia.tencentcloudapi.com',
        'action': 'DescribeGroups',
        'request_class': 'DescribeGroupsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Groups',
        'response_total': None,
        'result_key': 'groups',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TIIA groups',
        'description': 'Returns TIIA groups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TIIA groups.',
        'return_total_doc': 'Number of groups returned (the API reports no total count).',
        'examples': """\
- name: List all groups
  susunola.tencentcloud.tiia_group_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.tione_dataset_info:
    region: ap-guangzhou

- name: Find datasets by ID
  susunola.tencentcloud.tione_dataset_info:
    region: ap-guangzhou
    dataset_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'tione_model_service_state_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tione.v20211111',
        'client_module': 'tione_client',
        'client_class': 'TioneClient',
        'sdk_package': 'tencentcloud-sdk-python-tione',
        'endpoint': 'tione.tencentcloudapi.com',
        'action': 'DescribeModelServiceGroup',
        'request_class': 'DescribeModelServiceGroupRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'service_group_id',
                'field': 'ServiceGroupId',
                'type': 'str',
                'required': False,
                'doc': 'Service group id. API field C(ServiceGroupId).',
            },
            {
                'name': 'ti_project_id',
                'field': 'TiProjectId',
                'type': 'str',
                'required': False,
                'doc': 'Ti project id. API field C(TiProjectId).',
            },
        ],
        'response_items': 'ServiceGroup.Services',
        'response_total': None,
        'result_key': 'model_services',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud TIONE model services',
        'description': 'Returns TIONE model services visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TIONE model services.',
        'return_total_doc': 'Number of model services returned (the API reports no total count).',
        'examples': """\
- name: List all model services
  susunola.tencentcloud.tione_model_service_state_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tione_model_service_traffic_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tione.v20211111',
        'client_module': 'tione_client',
        'client_class': 'TioneClient',
        'sdk_package': 'tencentcloud-sdk-python-tione',
        'endpoint': 'tione.tencentcloudapi.com',
        'action': 'DescribeModelServiceGroups',
        'request_class': 'DescribeModelServiceGroupsRequest',
        'ids': None,
        'filters': {
            'doc': 'TIONE API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'ti_project_id',
                'field': 'TiProjectId',
                'type': 'str',
                'required': False,
                'doc': 'Ti project id. API field C(TiProjectId).',
            },
            {
                'name': 'order',
                'field': 'Order',
                'type': 'str',
                'required': False,
                'doc': 'Order. API field C(Order).',
            },
            {
                'name': 'order_field',
                'field': 'OrderField',
                'type': 'str',
                'required': False,
                'doc': 'Order field. API field C(OrderField).',
            },
        ],
        'response_items': 'ServiceGroups',
        'response_total': 'TotalCount',
        'result_key': 'model_service_groups',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TIONE model service groups',
        'description': 'Returns TIONE model service groups visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TIONE model service groups.',
        'return_total_doc': 'Number of model service groups reported by the API.',
        'examples': """\
- name: List all model service groups
  susunola.tencentcloud.tione_model_service_traffic_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.tiw_running_task_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tke_cls_log_config_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tke.v20180525',
        'client_module': 'tke_client',
        'client_class': 'TkeClient',
        'sdk_package': 'tencentcloud-sdk-python-tke',
        'endpoint': 'tke.tencentcloudapi.com',
        'action': 'DescribeLogConfigs',
        'request_class': 'DescribeLogConfigsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'cluster_id',
                'field': 'ClusterId',
                'type': 'str',
                'required': False,
                'doc': 'Cluster id. API field C(ClusterId).',
            },
            {
                'name': 'cluster_type',
                'field': 'ClusterType',
                'type': 'str',
                'required': False,
                'doc': 'Cluster type. API field C(ClusterType).',
            },
            {
                'name': 'log_config_names',
                'field': 'LogConfigNames',
                'type': 'str',
                'required': False,
                'doc': 'Log config names. API field C(LogConfigNames).',
            },
        ],
        'response_items': None,
        'response_total': None,
        'result_key': 'log_config',
        'pagination_type': 'none',
        'short_description': 'Gather information about Tencent Cloud TKE log config',
        'description': 'Returns TKE log config visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TKE log config.',
        'return_total_doc': '',
        'examples': """\
- name: Show the log config
  susunola.tencentcloud.tke_cls_log_config_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tke_cluster_route_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tke.v20180525',
        'client_module': 'tke_client',
        'client_class': 'TkeClient',
        'sdk_package': 'tencentcloud-sdk-python-tke',
        'endpoint': 'tke.tencentcloudapi.com',
        'action': 'DescribeClusterRoutes',
        'request_class': 'DescribeClusterRoutesRequest',
        'ids': None,
        'filters': {
            'doc': 'TKE API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'route_table_name',
                'field': 'RouteTableName',
                'type': 'str',
                'required': False,
                'doc': 'Route table name. API field C(RouteTableName).',
            },
        ],
        'response_items': 'RouteSet',
        'response_total': 'TotalCount',
        'result_key': 'cluster_routes',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud TKE cluster routes',
        'description': 'Returns TKE cluster routes visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TKE cluster routes.',
        'return_total_doc': 'Number of cluster routes reported by the API.',
        'examples': """\
- name: List all cluster routes
  susunola.tencentcloud.tke_cluster_route_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'tke_cluster_route_table_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.tke.v20180525',
        'client_module': 'tke_client',
        'client_class': 'TkeClient',
        'sdk_package': 'tencentcloud-sdk-python-tke',
        'endpoint': 'tke.tencentcloudapi.com',
        'action': 'DescribeClusterRouteTables',
        'request_class': 'DescribeClusterRouteTablesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'RouteTableSet',
        'response_total': 'TotalCount',
        'result_key': 'cluster_route_tables',
        'pagination_type': 'list',
        'short_description': 'Gather information about Tencent Cloud TKE cluster route tables',
        'description': 'Returns TKE cluster route tables visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TKE cluster route tables.',
        'return_total_doc': 'Number of cluster route tables reported by the API.',
        'examples': """\
- name: List all cluster route tables
  susunola.tencentcloud.tke_cluster_route_table_info:
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
  susunola.tencentcloud.tokenhub_model_info:
    region: ap-guangzhou

- name: Find models by ID
  susunola.tencentcloud.tokenhub_model_info:
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
  susunola.tencentcloud.tourism_draw_resource_info:
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
  susunola.tencentcloud.trabbit_rabbit_mq_serverless_instance_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'trabbit_serverless_binding_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.trabbit.v20230418',
        'client_module': 'trabbit_client',
        'client_class': 'TrabbitClient',
        'sdk_package': 'tencentcloud-sdk-python-trabbit',
        'endpoint': 'trabbit.tencentcloudapi.com',
        'action': 'DescribeRabbitMQServerlessBindings',
        'request_class': 'DescribeRabbitMQServerlessBindingsRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'virtual_host',
                'field': 'VirtualHost',
                'type': 'str',
                'required': False,
                'doc': 'Virtual host. API field C(VirtualHost).',
            },
            {
                'name': 'search_word',
                'field': 'SearchWord',
                'type': 'str',
                'required': False,
                'doc': 'Search word. API field C(SearchWord).',
            },
            {
                'name': 'source_exchange',
                'field': 'SourceExchange',
                'type': 'str',
                'required': False,
                'doc': 'Source exchange. API field C(SourceExchange).',
            },
            {
                'name': 'queue_name',
                'field': 'QueueName',
                'type': 'str',
                'required': False,
                'doc': 'Queue name. API field C(QueueName).',
            },
            {
                'name': 'destination_exchange',
                'field': 'DestinationExchange',
                'type': 'str',
                'required': False,
                'doc': 'Destination exchange. API field C(DestinationExchange).',
            },
        ],
        'response_items': 'BindingInfoList',
        'response_total': 'TotalCount',
        'result_key': 'serverless_bindings',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TRABBIT serverless bindings',
        'description': 'Returns TRABBIT serverless bindings visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TRABBIT serverless bindings.',
        'return_total_doc': 'Number of serverless bindings reported by the API.',
        'examples': """\
- name: List all serverless bindings
  susunola.tencentcloud.trabbit_serverless_binding_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'trabbit_serverless_exchange_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.trabbit.v20230418',
        'client_module': 'trabbit_client',
        'client_class': 'TrabbitClient',
        'sdk_package': 'tencentcloud-sdk-python-trabbit',
        'endpoint': 'trabbit.tencentcloudapi.com',
        'action': 'DescribeRabbitMQServerlessExchanges',
        'request_class': 'DescribeRabbitMQServerlessExchangesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'virtual_host',
                'field': 'VirtualHost',
                'type': 'str',
                'required': False,
                'doc': 'Virtual host. API field C(VirtualHost).',
            },
            {
                'name': 'search_word',
                'field': 'SearchWord',
                'type': 'str',
                'required': False,
                'doc': 'Search word. API field C(SearchWord).',
            },
            {
                'name': 'exchange_type_filters',
                'field': 'ExchangeTypeFilters',
                'type': 'list',
                'required': False,
                'doc': 'Exchange type filters. API field C(ExchangeTypeFilters).',
                'elements': 'str',
            },
            {
                'name': 'exchange_creator_filters',
                'field': 'ExchangeCreatorFilters',
                'type': 'list',
                'required': False,
                'doc': 'Exchange creator filters. API field C(ExchangeCreatorFilters).',
                'elements': 'str',
            },
            {
                'name': 'exchange_name',
                'field': 'ExchangeName',
                'type': 'str',
                'required': False,
                'doc': 'Exchange name. API field C(ExchangeName).',
            },
            {
                'name': 'sort_element',
                'field': 'SortElement',
                'type': 'str',
                'required': False,
                'doc': 'Sort element. API field C(SortElement).',
            },
            {
                'name': 'sort_order',
                'field': 'SortOrder',
                'type': 'str',
                'required': False,
                'doc': 'Sort order. API field C(SortOrder).',
            },
        ],
        'response_items': 'ExchangeInfoList',
        'response_total': 'TotalCount',
        'result_key': 'serverless_exchanges',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TRABBIT serverless exchanges',
        'description': 'Returns TRABBIT serverless exchanges visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TRABBIT serverless exchanges.',
        'return_total_doc': 'Number of serverless exchanges reported by the API.',
        'examples': """\
- name: List all serverless exchanges
  susunola.tencentcloud.trabbit_serverless_exchange_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'trabbit_serverless_permission_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.trabbit.v20230418',
        'client_module': 'trabbit_client',
        'client_class': 'TrabbitClient',
        'sdk_package': 'tencentcloud-sdk-python-trabbit',
        'endpoint': 'trabbit.tencentcloudapi.com',
        'action': 'DescribeRabbitMQServerlessPermission',
        'request_class': 'DescribeRabbitMQServerlessPermissionRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'user',
                'field': 'User',
                'type': 'str',
                'required': False,
                'doc': 'User. API field C(User).',
            },
            {
                'name': 'virtual_host',
                'field': 'VirtualHost',
                'type': 'str',
                'required': False,
                'doc': 'Virtual host. API field C(VirtualHost).',
            },
        ],
        'response_items': 'RabbitMQPermissionList',
        'response_total': 'TotalCount',
        'result_key': 'serverless_permissions',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TRABBIT serverless permissions',
        'description': 'Returns TRABBIT serverless permissions visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TRABBIT serverless permissions.',
        'return_total_doc': 'Number of serverless permissions reported by the API.',
        'examples': """\
- name: List all serverless permissions
  susunola.tencentcloud.trabbit_serverless_permission_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'trabbit_serverless_queue_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.trabbit.v20230418',
        'client_module': 'trabbit_client',
        'client_class': 'TrabbitClient',
        'sdk_package': 'tencentcloud-sdk-python-trabbit',
        'endpoint': 'trabbit.tencentcloudapi.com',
        'action': 'DescribeRabbitMQServerlessQueues',
        'request_class': 'DescribeRabbitMQServerlessQueuesRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'virtual_host',
                'field': 'VirtualHost',
                'type': 'str',
                'required': False,
                'doc': 'Virtual host. API field C(VirtualHost).',
            },
            {
                'name': 'search_word',
                'field': 'SearchWord',
                'type': 'str',
                'required': False,
                'doc': 'Search word. API field C(SearchWord).',
            },
            {
                'name': 'queue_type',
                'field': 'QueueType',
                'type': 'str',
                'required': False,
                'doc': 'Queue type. API field C(QueueType).',
            },
            {
                'name': 'sort_element',
                'field': 'SortElement',
                'type': 'str',
                'required': False,
                'doc': 'Sort element. API field C(SortElement).',
            },
            {
                'name': 'sort_order',
                'field': 'SortOrder',
                'type': 'str',
                'required': False,
                'doc': 'Sort order. API field C(SortOrder).',
            },
        ],
        'response_items': 'QueueInfoList',
        'response_total': 'TotalCount',
        'result_key': 'serverless_queues',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TRABBIT serverless queues',
        'description': 'Returns TRABBIT serverless queues visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TRABBIT serverless queues.',
        'return_total_doc': 'Number of serverless queues reported by the API.',
        'examples': """\
- name: List all serverless queues
  susunola.tencentcloud.trabbit_serverless_queue_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'trabbit_serverless_user_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.trabbit.v20230418',
        'client_module': 'trabbit_client',
        'client_class': 'TrabbitClient',
        'sdk_package': 'tencentcloud-sdk-python-trabbit',
        'endpoint': 'trabbit.tencentcloudapi.com',
        'action': 'DescribeRabbitMQServerlessUser',
        'request_class': 'DescribeRabbitMQServerlessUserRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'search_user',
                'field': 'SearchUser',
                'type': 'str',
                'required': False,
                'doc': 'Search user. API field C(SearchUser).',
            },
            {
                'name': 'user',
                'field': 'User',
                'type': 'str',
                'required': False,
                'doc': 'User. API field C(User).',
            },
            {
                'name': 'tags',
                'field': 'Tags',
                'type': 'list',
                'required': False,
                'doc': 'Tags. API field C(Tags).',
                'elements': 'str',
            },
        ],
        'response_items': 'RabbitMQUserList',
        'response_total': 'TotalCount',
        'result_key': 'serverless_users',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TRABBIT serverless users',
        'description': 'Returns TRABBIT serverless users visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TRABBIT serverless users.',
        'return_total_doc': 'Number of serverless users reported by the API.',
        'examples': """\
- name: List all serverless users
  susunola.tencentcloud.trabbit_serverless_user_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'trabbit_serverless_vhost_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.trabbit.v20230418',
        'client_module': 'trabbit_client',
        'client_class': 'TrabbitClient',
        'sdk_package': 'tencentcloud-sdk-python-trabbit',
        'endpoint': 'trabbit.tencentcloudapi.com',
        'action': 'DescribeRabbitMQServerlessVirtualHost',
        'request_class': 'DescribeRabbitMQServerlessVirtualHostRequest',
        'ids': None,
        'filters': None,
        'extra_params': [
            {
                'name': 'instance_id',
                'field': 'InstanceId',
                'type': 'str',
                'required': False,
                'doc': 'Instance id. API field C(InstanceId).',
            },
            {
                'name': 'virtual_host',
                'field': 'VirtualHost',
                'type': 'str',
                'required': False,
                'doc': 'Virtual host. API field C(VirtualHost).',
            },
            {
                'name': 'sort_element',
                'field': 'SortElement',
                'type': 'str',
                'required': False,
                'doc': 'Sort element. API field C(SortElement).',
            },
            {
                'name': 'sort_order',
                'field': 'SortOrder',
                'type': 'str',
                'required': False,
                'doc': 'Sort order. API field C(SortOrder).',
            },
        ],
        'response_items': 'VirtualHostList',
        'response_total': 'TotalCount',
        'result_key': 'serverless_vhosts',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud TRABBIT serverless vhosts',
        'description': 'Returns TRABBIT serverless vhosts visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching TRABBIT serverless vhosts.',
        'return_total_doc': 'Number of serverless vhosts reported by the API.',
        'examples': """\
- name: List all serverless vhosts
  susunola.tencentcloud.trabbit_serverless_vhost_info:
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
  susunola.tencentcloud.trocket_consumer_client_info:
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
  susunola.tencentcloud.trp_code_batch_info:
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
  susunola.tencentcloud.trro_device_info:
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
  susunola.tencentcloud.trtc_call_info:
    region: ap-guangzhou

- name: Find calls by ID
  susunola.tencentcloud.trtc_call_info:
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
  susunola.tencentcloud.tse_sre_instance_info:
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
  susunola.tencentcloud.tsf_application_info:
    region: ap-guangzhou

- name: Find applications by ID
  susunola.tencentcloud.tsf_application_info:
    region: ap-guangzhou
    application_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'vcube_resource_info',
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
        'result_key': 'resources',
        'pagination_type': 'page',
        'short_description': 'Gather information about Tencent Cloud VCUBE resources',
        'description': 'Returns VCUBE resources visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching VCUBE resources.',
        'return_total_doc': 'Number of resources reported by the API.',
        'examples': """\
- name: List all resources
  susunola.tencentcloud.vcube_resource_info:
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
  susunola.tencentcloud.vdb_instance_info:
    region: ap-guangzhou

- name: Find instances by ID
  susunola.tencentcloud.vdb_instance_info:
    region: ap-guangzhou
    instance_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'vm_task_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.vm.v20210922',
        'client_module': 'vm_client',
        'client_class': 'VmClient',
        'sdk_package': 'tencentcloud-sdk-python-vm',
        'endpoint': 'vm.tencentcloudapi.com',
        'action': 'DescribeTasks',
        'request_class': 'DescribeTasksRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'Data',
        'response_total': None,
        'result_key': 'tasks',
        'pagination_type': 'token',
        'token_request_field': 'PageToken',
        'token_response_field': 'PageToken',
        'page_size_field': 'Limit',
        'list_over_field': None,
        'short_description': 'Gather information about Tencent Cloud VM tasks',
        'description': 'Returns VM tasks visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching VM tasks.',
        'return_total_doc': 'Number of tasks returned (the API reports no total count).',
        'examples': """\
- name: List all tasks
  susunola.tencentcloud.vm_task_info:
    region: ap-guangzhou
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
  susunola.tencentcloud.vod_incremental_migration_strategy_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'privatelink_endpoint_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.vpc.v20170312',
        'client_module': 'vpc_client',
        'client_class': 'VpcClient',
        'sdk_package': 'tencentcloud-sdk-python-vpc',
        'endpoint': 'vpc.tencentcloudapi.com',
        'action': 'DescribeVpcEndPoint',
        'request_class': 'DescribeVpcEndPointRequest',
        'ids': None,
        'filters': {
            'doc': 'VPC API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'end_point_id',
                'field': 'EndPointId',
                'type': 'list',
                'required': False,
                'doc': 'End point id. API field C(EndPointId).',
                'elements': 'str',
            },
            {
                'name': 'ip_address_type',
                'field': 'IpAddressType',
                'type': 'str',
                'required': False,
                'doc': 'Ip address type. API field C(IpAddressType).',
            },
            {
                'name': 'max_results',
                'field': 'MaxResults',
                'type': 'int',
                'required': False,
                'doc': 'Max results. API field C(MaxResults).',
            },
        ],
        'response_items': 'EndPointSet',
        'response_total': 'TotalCount',
        'result_key': 'end_points',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud VPC end points',
        'description': 'Returns VPC end points visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching VPC end points.',
        'return_total_doc': 'Number of end points reported by the API.',
        'examples': """\
- name: List all end points
  susunola.tencentcloud.privatelink_endpoint_info:
    region: ap-guangzhou
""",
    },
    {
        'module': 'privatelink_endpoint_service_info',
        'version_added': '1.5.0',
        'service_package': 'tencentcloud.vpc.v20170312',
        'client_module': 'vpc_client',
        'client_class': 'VpcClient',
        'sdk_package': 'tencentcloud-sdk-python-vpc',
        'endpoint': 'vpc.tencentcloudapi.com',
        'action': 'DescribeVpcEndPointService',
        'request_class': 'DescribeVpcEndPointServiceRequest',
        'ids': {
            'param': 'end_point_service_ids',
            'field': 'EndPointServiceIds',
            'doc': 'End point service IDs to return. Mutually exclusive with O(filters).',
        },
        'filters': {
            'doc': 'VPC API filter names mapped to lists of values.',
        },
        'extra_params': [
            {
                'name': 'is_list_authorized_end_point_service',
                'field': 'IsListAuthorizedEndPointService',
                'type': 'bool',
                'required': False,
                'doc': 'Is list authorized end point service. API field C(IsListAuthorizedEndPointService).',
            },
            {
                'name': 'ip_address_type',
                'field': 'IpAddressType',
                'type': 'str',
                'required': False,
                'doc': 'Ip address type. API field C(IpAddressType).',
            },
            {
                'name': 'max_results',
                'field': 'MaxResults',
                'type': 'int',
                'required': False,
                'doc': 'Max results. API field C(MaxResults).',
            },
        ],
        'response_items': 'EndPointServiceSet',
        'response_total': 'TotalCount',
        'result_key': 'end_point_services',
        'pagination_type': 'int',
        'short_description': 'Gather information about Tencent Cloud VPC end point services',
        'description': 'Returns VPC end point services visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching VPC end point services.',
        'return_total_doc': 'Number of end point services reported by the API.',
        'examples': """\
- name: List all end point services
  susunola.tencentcloud.privatelink_endpoint_service_info:
    region: ap-guangzhou

- name: Find end point services by ID
  susunola.tencentcloud.privatelink_endpoint_service_info:
    region: ap-guangzhou
    end_point_service_ids: [x-xxxxxxxx]
""",
    },
    {
        'module': 'wav_activity_info',
        'version_added': '0.9.0',
        'service_package': 'tencentcloud.wav.v20210129',
        'client_module': 'wav_client',
        'client_class': 'WavClient',
        'sdk_package': 'tencentcloud-sdk-python-wav',
        'endpoint': 'wav.tencentcloudapi.com',
        'action': 'QueryActivityList',
        'request_class': 'QueryActivityListRequest',
        'ids': None,
        'filters': None,
        'extra_params': [],
        'response_items': 'PageData',
        'response_total': None,
        'result_key': 'activities',
        'pagination_type': 'token',
        'token_request_field': 'Cursor',
        'token_response_field': 'NextCursor',
        'page_size_field': 'Limit',
        'list_over_field': None,
        'short_description': 'Gather information about Tencent Cloud WAV activities',
        'description': 'Returns WAV activities visible in a Tencent Cloud region.',
        'return_items_doc': 'Matching WAV activities.',
        'return_total_doc': 'Number of activities returned (the API reports no total count).',
        'examples': """\
- name: List all activities
  susunola.tencentcloud.wav_activity_info:
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
  susunola.tencentcloud.wedata_project_info:
    region: ap-guangzhou

- name: Find projects by ID
  susunola.tencentcloud.wedata_project_info:
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
  susunola.tencentcloud.weilingwith_element_profile_page_info:
    region: ap-guangzhou

- name: Find element profile pages by ID
  susunola.tencentcloud.weilingwith_element_profile_page_info:
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
  susunola.tencentcloud.wss_cert_info:
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
  susunola.tencentcloud.yinsuda_ktv_robot_info:
    region: ap-guangzhou

- name: Find ktv robots by ID
  susunola.tencentcloud.yinsuda_ktv_robot_info:
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
  susunola.tencentcloud.yunjing_account_statistic_info:
    region: ap-guangzhou
""",
    },
]
