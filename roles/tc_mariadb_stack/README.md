# tc_mariadb_stack

Provisions TencentDB for MariaDB with application accounts, exact privilege
sets at global, database, object or column scope, and automatic backups.

Teardown clears declared privilege scopes before deleting accounts. The default
instance action is isolation into the recycle bin. Permanent destruction is a
second explicit run with `tc_mariadb_stack_purge: true` after isolation.
