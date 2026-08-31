# tc_organization_governance

Builds an Organization hierarchy and reconciles organization-created members,
their exact identity sets and member access policies. Nodes are declared
parent-first; child nodes and members may refer to earlier nodes by `parent_name`
or `node_name`.

Teardown removes policies, identities and members before deleting nodes in
reverse declaration order. Each node must provide `node_id`, or `parent_node_id`
plus `name`, during teardown. Organization membership deletion remains subject
to Tencent Cloud account and billing eligibility checks.
