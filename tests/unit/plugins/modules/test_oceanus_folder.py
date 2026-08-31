from ansible_collections.susunola.tencentcloud.plugins.modules.oceanus_folder import _walk, nonempty


def test_walk_flattens_nested_folder_tree():
    root={"Id":"root","Children":[{"Id":"a","Children":[{"Id":"b"}]}]}
    assert [item["Id"] for item in _walk(root)]==["root","a","b"]


def test_nonempty_covers_job_and_resource_folders():
    assert nonempty({"JobSet":[{"JobId":"j"}]},{})
    assert nonempty({"Items":[{"ResourceId":"r"}]},{})
    assert not nonempty({"Children":[],"Items":[]},{})
