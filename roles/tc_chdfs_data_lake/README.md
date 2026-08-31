# tc_chdfs_data_lake

Provisions or adopts a CHDFS file system with access groups, exact access-rule
sets, mount points and access-group bindings. Mounts may reference access groups
created in the same run by `access_group_names`.

The role resolves file systems, access groups and scoped mount points by exact
name. Teardown disassociates mount access, removes mounts, clears rules, removes
access groups and deletes the file system last.
