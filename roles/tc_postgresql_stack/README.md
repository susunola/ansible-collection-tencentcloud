# tc_postgresql_stack

Provisions TencentDB for PostgreSQL with accounts, explicit password rotation,
backup plans and an optional reusable parameter template.

Teardown removes backup plans and accounts first. By default the instance is
isolated into the recycle bin. Permanent destruction is deliberately two-step:
after isolation, run again with `tc_postgresql_stack_purge: true`. Templates are
retained unless `remove_on_absent: true` is explicitly selected.
