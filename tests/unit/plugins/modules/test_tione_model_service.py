from ansible_collections.susunola.tencentcloud.plugins.modules.tione_model_service import create_request, modify_request, normalize, drift


class Object:
    def from_json_string(self, value):
        self.value = value


class Models:
    CreateModelServiceRequest = ModifyModelServiceRequest = ModelInfo = ImageInfo = EnvVar = ResourceInfo = HorizontalPodAutoscaler = LogConfig = Tag = (
        CronScaleJob
    ) = ScheduledAction = VolumeMount = ServiceLimit = ServiceEIP = HealthProbe = RollingUpdate = ResourceSupplyAttribute = Object


def params():
    result = {key: None for key in __import__("ansible_collections.susunola.tencentcloud.plugins.modules.tione_model_service", fromlist=["FIELDS"]).FIELDS}
    result.update(
        project_id="p1",
        service_id="s1",
        service_group_id="g1",
        charge_type="POSTPAID_BY_HOUR",
        image_info={"ImageType": "TCR"},
        replicas=2,
        tags=[{"TagKey": "env", "TagValue": "prod"}],
        service_description="v2",
    )
    return result


def test_normalize_flattens_service_info_and_sorts_tags():
    value = normalize({"ServiceId": "s1", "Tags": [{"TagKey": "z"}, {"TagKey": "a"}], "ServiceInfo": {"Replicas": 2}})
    assert value["Replicas"] == 2 and value["Tags"][0]["TagKey"] == "a" and "ServiceInfo" not in value


def test_create_request_builds_new_version_and_nested_models():
    request = create_request(Models, params())
    assert request.ServiceGroupId == "g1" and request.NewVersion is True and request.Replicas == 2
    assert '"ImageType": "TCR"' in request.ImageInfo.value


def test_modify_request_excludes_create_only_fields():
    request = modify_request(Models, params())
    assert request.ServiceId == "s1" and request.ServiceDescription == "v2" and request.Replicas == 2
    assert not hasattr(request, "ChargeType") and not hasattr(request, "Tags")


def test_drift_separates_mutable_and_create_only_fields():
    p = params()
    current = {"ChargeType": "PREPAID", "Replicas": 1, "ServiceDescription": "v1", "ImageInfo": {"ImageType": "TCR"}, "Tags": p["tags"]}
    mutable, immutable = drift(p, current)
    assert set(mutable) == {"Replicas", "ServiceDescription"} and set(immutable) == {"ChargeType"}
