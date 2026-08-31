# tc_cynosdb_cluster

Provisions a CynosDB MySQL or PostgreSQL-compatible cluster with application
accounts, exact global/database/table privilege sets and automatic backups.

Teardown clears account privileges before deleting accounts. The default cluster
action is isolation; permanent removal is a second explicit run with
`tc_cynosdb_cluster_purge: true` after isolation.
