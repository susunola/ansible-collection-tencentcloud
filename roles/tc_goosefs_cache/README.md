# tc_goosefs_cache

Provisions or adopts a GooseFS data-cache file system and reconciles Filesets
with exact capacity, file-count and audit settings. File systems resolve by exact
name for teardown.

Topology and Fileset identity remain immutable; capacity may only expand.
Teardown deletes every declared Fileset before deleting the file system.
