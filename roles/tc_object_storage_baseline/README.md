# tc_object_storage_baseline

Creates a private COS bucket and composes versioning, CORS, lifecycle, tags,
default encryption, policy, logging, static website, replication and hotlink
protection. Object Lock and intelligent tiering are explicit opt-ins because COS
does not allow them to be disabled after enablement.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_object_storage_baseline
      vars:
        tc_object_storage_baseline_region: ap-guangzhou
        tc_object_storage_baseline_name: production-artifacts
        tc_object_storage_baseline_versioning: true
        tc_object_storage_baseline_tags:
          environment: production
        tc_object_storage_baseline_lifecycle:
          - id: archive
            prefix: archives/
            status: enabled
            transitions:
              - days: 30
                storage_class: ARCHIVE
```

The default is private with AES-256 server-side encryption. Bucket deletion is
deliberately non-destructive: the role removes reversible bucket configuration,
then asks COS to delete the bucket. COS rejects deletion until all current and
noncurrent object versions and multipart uploads have been removed.
