# tc_config_governance

Operates Tencent Cloud Config as a governance platform: resource recording,
delivery, compliance rules, per-rule remediation, compliance packs, alarms and
optional cross-account aggregation.

Rule items may include `remediations`. Compliance-pack rules require explicit
Config rule IDs. For teardown, remediation-bearing rules require `rule_id`.
Config aggregators are create/adopt-only because the cloud API exposes no update
or delete operation; the role rejects aggregator teardown instead of claiming a
false lifecycle guarantee.
