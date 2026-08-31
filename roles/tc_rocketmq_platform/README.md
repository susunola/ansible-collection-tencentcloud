# tc_rocketmq_platform

Provisions or adopts a TDMQ RocketMQ cluster with roles, namespaces, topics,
consumer groups and exact namespace permissions.

Teardown removes permissions before groups and topics, namespaces before roles,
and the cluster last. Role output does not expose RocketMQ credential fields.
