from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_application import comparable, desired


def test_application_desired_only_manages_explicit_fields():
    params = {"name": "orders", "application_type": "C", "microservice_type": "N",
              "description": "orders-api", "remark_name": None, "runtime_type": None,
              "program_language": None, "framework_type": "SpringCloud", "apm_instance_id": None,
              "ignore_create_image_repository": None, "create_same_name_image_repository": None}
    assert desired(params) == {"ApplicationName": "orders", "ApplicationType": "C",
                               "MicroserviceType": "N", "ApplicationDesc": "orders-api",
                               "FrameworkType": "SpringCloud"}


def test_application_comparison_ignores_server_metadata():
    target = {"ApplicationName": "orders", "ApplicationDesc": "managed"}
    current = dict(target, ApplicationId="application-1", CreateTime="today")
    assert comparable(current, target) == target
