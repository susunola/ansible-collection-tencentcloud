from ansible_collections.susunola.tencentcloud.plugins.modules.oceanus_job_config import desired, normalize_resource_refs
def test_desired_only_manages_explicit_fields(): assert desired({"program_args":"SELECT 1","default_parallelism":4,"auto_recover":None,**{k:None for k in ("entrypoint_class","remark","properties","cos_bucket","log_collect","log_collect_type","cls_logset_id","cls_topic_id","log_level","checkpoint_retained","checkpoint_timeout","checkpoint_interval","job_manager_cpu","job_manager_memory","task_manager_cpu","task_manager_memory","flink_version","jdk_version")}})=={"ProgramArgs":"SELECT 1","DefaultParallelism":4}
def test_desired_maps_auto_recovery_switch():
    base={k:None for k in FIELDS_FOR_TEST}
    base["auto_recover"]=False
    assert desired(base)["AutoRecover"]==-1
def test_resource_refs_compare_without_response_metadata_or_order():
    values=[{"ResourceId":"r-b","Version":2,"Type":0,"Name":"b"},{"ResourceId":"r-a","Version":1,"Type":1,"SystemProvide":0}]
    assert normalize_resource_refs(values)==[{"ResourceId":"r-b","Version":2,"Type":0},{"ResourceId":"r-a","Version":1,"Type":1}]
FIELDS_FOR_TEST=("entrypoint_class","program_args","remark","default_parallelism","properties","resource_refs","cos_bucket","log_collect","log_collect_type","cls_logset_id","cls_topic_id","log_level","checkpoint_retained","checkpoint_timeout","checkpoint_interval","job_manager_cpu","job_manager_memory","task_manager_cpu","task_manager_memory","flink_version","jdk_version")
