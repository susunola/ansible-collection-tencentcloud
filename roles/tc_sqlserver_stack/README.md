# tc_sqlserver_stack

Provisions or adopts a TencentDB for SQL Server instance, configures its backup
strategy and reconciles accounts with exact database privilege sets. Account
tasks are hidden because account declarations may contain passwords.

Teardown removes declared accounts before acting on the instance. The default
`state: absent` isolates the instance for recovery; `purge: true` permanently
deletes only an instance that is already isolated, so permanent removal requires
an intentional second run.
