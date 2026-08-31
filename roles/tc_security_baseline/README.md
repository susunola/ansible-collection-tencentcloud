# tc_security_baseline

Establish an account security baseline spanning CAM identities and policies,
CloudAudit event delivery and Config compliance rules.

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_security_baseline
      vars:
        tc_security_baseline_policies:
          - policy_name: ReadOnlyOperations
            policy_document:
              version: '2.0'
              statement:
                - {effect: allow, action: ['monitor:Describe*', 'cls:Describe*'], resource: ['*']}
            attachments:
              - {target_type: role, target_name: OperationsAuditor}
        tc_security_baseline_audit_tracks:
          - name: all-actions
            storage_type: cls
            storage_region: ap-guangzhou
            storage_name: topic-xxxxxxxx
```

For deletion with attachments, provide each custom policy's numeric
`policy_id`; attachments are removed before the policy. Policy documents and
Config rule parameters remain structured mappings and are compared
semantically by their modules.
