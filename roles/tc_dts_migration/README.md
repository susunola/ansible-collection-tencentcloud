# tc_dts_migration

Builds a complete DTS migration workflow: purchase or discover the migration
job, reconcile source/destination and migration options, run the mandatory
preflight check, and optionally start the migration.

`tc_dts_migration_auto_start` defaults to `false`, so configuration and checks
can be reviewed before data movement begins. Destruction is separately guarded
by `tc_dts_migration_allow_destroy`.
