# tc_dcdb_stack

Provisions a DCDB/TDSQL MySQL instance and reconciles its automatic backup
schedule, accounts and scoped privilege sets. Teardown clears declared
privileges before accounts, then isolates the instance. Teardown requires
`tc_dcdb_stack_allow_isolate=true`; permanent purge remains a separate opt-in.
