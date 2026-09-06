from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_store_location import advanced_drift, create_request, desired, modify_request


class Request:
    pass


class Models:
    CreateStoreLocationRequest = ModifyAdvancedStoreLocationRequest = Request


def test_base_and_advanced_requests_are_explicit():
    create = create_request(Models, "cosn://results/")
    modify = modify_request(Models, True, "cosn://advanced/")
    assert create.StoreLocation == "cosn://results/"
    assert modify.Enable == 1 and modify.StoreLocation == "cosn://advanced/"


def test_advanced_drift_does_not_treat_read_only_fields_as_managed():
    p = {"store_location": "cosn://results/", "advanced_enabled": True, "advanced_store_location": "cosn://advanced/"}
    current = {"StoreLocation": "cosn://results/", "AdvancedEnabled": False, "AdvancedStoreLocation": "", "HasLakeFs": True}
    assert advanced_drift(p, current) == {"AdvancedEnabled": (False, True), "AdvancedStoreLocation": ("", "cosn://advanced/")}
    assert desired(p, current)["HasLakeFs"] is True
