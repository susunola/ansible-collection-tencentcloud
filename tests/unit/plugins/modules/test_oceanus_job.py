from ansible_collections.susunola.tencentcloud.plugins.modules.oceanus_job import _folder_for_job


def test_folder_for_job_finds_nested_placement():
    tree={"Id":"root","JobSet":[],"Children":[{"Id":"folder-a","JobSet":[{"JobId":"job-1"}],"Children":[]}]}
    assert _folder_for_job(tree,"job-1")=="folder-a"


def test_folder_for_job_returns_none_for_missing_job():
    assert _folder_for_job({"Id":"root","JobSet":[],"Children":[]},"missing") is None
