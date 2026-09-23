# tc_container_registry

Provision a TCR Enterprise instance with private namespaces, repositories,
vulnerability controls and optional cross-region replication.

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_container_registry
      vars:
        tc_container_registry_name: production
        tc_container_registry_type: standard
        tc_container_registry_namespaces:
          - name: applications
            is_auto_scan: true
            is_prevent_vul: true
            severity: high
            repositories:
              - {name: orders, brief_description: Orders service}
            immutable_tag_rules:
              - RepositoryPattern: orders
                TagPattern: "v*"
                RepositoryDecoration: repoMatches
                TagDecoration: matches
            webhook_triggers:
              - Name: push-notify
                Condition: all
                EventTypes: [pushImage]
                Enabled: true
                Targets: [{Address: "https://hooks.example.com/tcr"}]
```

The role publishes `tc_container_registry_result`. Deletion requires an
explicit registry ID when child resources are declared and removes replication
rules, immutable tag rules, webhook triggers and repositories before namespaces and the registry
instance. Immutable rules are identified by namespace and repository/tag
patterns; webhook triggers are identified by namespace and name. To change
other fields, remove and recreate the resource explicitly.
