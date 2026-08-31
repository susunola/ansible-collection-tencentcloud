# tc_cloud_audit_governance

Reconciles account-level CloudAudit management-event delivery to COS, optional
CMQ notification and KMS encryption, plus scoped audit tracks delivered to COS,
CLS or CKafka.

The account audit API has no delete operation. Teardown deletes declared tracks
first and stops account-level logging while retaining its delivery configuration.
