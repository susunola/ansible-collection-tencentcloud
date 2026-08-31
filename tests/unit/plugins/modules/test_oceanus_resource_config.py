from ansible_collections.susunola.tencentcloud.plugins.modules.oceanus_resource_config import desired, managed_value


def test_desired_manages_location_and_explicit_remark():
    location={"StorageType":1,"Param":{"Bucket":"artifacts","Path":"jobs/a.jar","Region":"ap-guangzhou"}}
    assert desired({"resource_location":location,"remark":"release-2"})=={"ResourceLoc":location,"Remark":"release-2"}


def test_desired_does_not_manage_omitted_remark():
    location={"StorageType":1,"Param":{"Bucket":"artifacts","Path":"jobs/a.jar"}}
    assert desired({"resource_location":location,"remark":None})=={"ResourceLoc":location}


def test_managed_value_ignores_sdk_noise_inside_resource_location():
    target={"ResourceLoc":{"StorageType":1,"Param":{"Bucket":"artifacts","Path":"jobs/a.jar"}}}
    current={"ResourceLoc":{"StorageType":1,"Param":{"Bucket":"artifacts","Path":"jobs/a.jar","Region":None},"FlinkConnectorJarUri":None},"Status":1}
    assert managed_value(current,target)==target
