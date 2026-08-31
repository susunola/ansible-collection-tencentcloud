# tc_elasticsearch_platform

Provisions or adopts a Tencent Cloud Elasticsearch cluster, reconciles indexes
and manages named snapshots. The role resolves clusters by exact name and hides
all tasks that carry cluster passwords.

Teardown deletes declared snapshots and indexes before the cluster. A snapshot
protected by COS retention lock remains subject to the provider retention period
and cannot be force-deleted by the role.
