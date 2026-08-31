# tc_kafka_platform

Provisions a CKafka instance with access routes, users, topics, exact ACL grants
and reusable prefix or preset ACL rules. Existing instances can be adopted by
ID, and teardown resolves an exact name before removing child resources.

The role intentionally excludes CKafka DataHub resources because they form a
separate integration pipeline lifecycle.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_kafka_platform
      vars:
        tc_kafka_platform_region: ap-guangzhou
        tc_kafka_platform_name: production-events
        tc_kafka_platform_zones: [100003]
        tc_kafka_platform_vpc_id: vpc-xxxxxxxx
        tc_kafka_platform_subnet_id: subnet-xxxxxxxx
        tc_kafka_platform_instance_type: 1
        tc_kafka_platform_specification: profession
        tc_kafka_platform_version: "2.8.1"
        tc_kafka_platform_disk_type: CLOUD_BASIC
        tc_kafka_platform_disk_size: 500
        tc_kafka_platform_bandwidth: 40
        tc_kafka_platform_partitions: 400
        tc_kafka_platform_retention_minutes: 10080
        tc_kafka_platform_topics:
          - topic_name: orders
            partition_num: 6
            replica_num: 3
```
