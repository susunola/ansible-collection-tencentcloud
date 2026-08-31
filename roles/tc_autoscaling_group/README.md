# tc_autoscaling_group

Provisions or adopts an Auto Scaling group and reconciles its simple or
target-tracking policies and scheduled capacity actions. The role defaults to
zero desired capacity so its first run does not create billable CVM instances
unless that intent is explicit.

Teardown removes scheduled actions and scaling policies before the parent
group. Declare every managed child in the role variables when removing a stack.
