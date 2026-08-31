from ansible_collections.susunola.tencentcloud.plugins.modules.oceanus_resource import create_request
class Model:
    def from_json_string(self,value): self.value=value
class Models:
    ResourceLoc=Model
    CreateResourceRequest=type("Request",(),{})
def test_create_request_preserves_workspace_and_initial_version_metadata():
    p={"name":"app","workspace_id":"space-1","resource_location":{"StorageType":1},"resource_type":1,"remark":"r","version_remark":"v1","folder_id":"root"}
    r=create_request(Models,p)
    assert r.Name=="app" and r.WorkSpaceId=="space-1" and r.ResourceConfigRemark=="v1"
