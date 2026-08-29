from ansible_collections.susunola.tencentcloud.plugins.modules import cmq_queue as m
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels

P = {
    "queue_name": "jobs",
    "max_msg_heap_num": 1000000,
    "polling_wait_seconds": 10,
    "visibility_timeout": 30,
    "max_msg_size": 65536,
    "msg_retention_seconds": 345600,
    "rewind_seconds": 0,
}


def test_builders():
    assert m.build_describe_request(FakeModels(), "jobs").QueueName == "jobs"
    assert m.build_create_payload(P)["PollingWaitSeconds"] == 10
    assert m.build_delete_payload("jobs") == {"QueueName": "jobs"}
