# tc_tione_ml_pipeline

Composes an auditable TIONE workflow from optional data-source and dataset
registration through training, model-version registration, online deployment,
and operational state convergence.

Each stage accepts the options of its corresponding collection module. Stages
with an empty dictionary are skipped. When a model version is registered and
the service does not provide `model_info`, the role binds its stable model and
version IDs automatically. The resulting objects are published in
`tc_tione_ml_pipeline_result`.

Deletion runs in reverse dependency order and requires both stable IDs in each
stage dictionary and `tc_tione_ml_pipeline_allow_destroy: true`.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_tione_ml_pipeline
      vars:
        tc_tione_ml_pipeline_training_task:
          name: fraud-training
          charge_type: POSTPAID_BY_HOUR
          resource_configs:
            - {Role: WORKER, InstanceType: TI.GN10X.2XLARGE40.POST, InstanceNum: 1}
        tc_tione_ml_pipeline_model_version:
          model_id: model-xxxxxxxx
          version: v3
          reason: automated promotion
          training_model_cos_path: {Bucket: ml-models-1250000000, Region: ap-guangzhou, Paths: [/fraud/v3/]}
        tc_tione_ml_pipeline_model_service:
          service_group_name: fraud-detection
          charge_type: POSTPAID_BY_HOUR
          image_info: {ImageType: TCR, ImageUrl: ccr.ccs.tencentyun.com/ml/fraud:v3}
          instance_type: TI.S.LARGE.POST
          replicas: 2
```
