# tc_rabbitmq_serverless

Adopts an existing RabbitMQ Serverless instance and manages users, virtual
hosts, permissions, exchanges, queues and bindings. The collection currently
provides instance discovery but not instance creation, so `instance_id` is an
explicit required boundary rather than an implied capability.

Teardown removes bindings first, then permissions, queues, exchanges, virtual
hosts and users. It intentionally leaves the externally managed instance intact.
