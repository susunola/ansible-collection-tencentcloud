from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_repository import desired


def test_repository_maps_storage_and_description():
    params = {"name": "packages", "repository_type": "private", "description": "production", "bucket_name": "packages-1250000000", "bucket_region": "ap-guangzhou", "directory": "releases"}
    assert desired(params) == {"RepositoryName": "packages", "RepositoryType": "private", "RepositoryDesc": "production", "BucketName": "packages-1250000000", "BucketRegion": "ap-guangzhou", "Directory": "releases"}
