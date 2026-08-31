# tc_observability_baseline

Create a CLS logset, indexed topics and Cloud Monitor alarm policies from one
declaration. This establishes the shared logging and alerting substrate used by
application and platform roles.

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_observability_baseline
      vars:
        tc_observability_baseline_logset_name: production
        tc_observability_baseline_topics:
          - name: application
            period: 30
            index: {enabled: true, contain_zh: true}
        tc_observability_baseline_alarm_policies:
          - name: cvm-cpu-high
            namespace: QCE/CVM
            condition:
              IsUnionRule: 0
              Rules: []
            notice_ids: [notice-xxxxxxxx]
```

The role publishes `tc_observability_baseline_result`. Policy condition and
filter payloads retain Tencent Cloud API shape because metric dimensions and
operators vary across products.
