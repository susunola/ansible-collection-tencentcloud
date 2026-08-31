# tc_rabbitmq_platform

Provisions or adopts a TDMQ RabbitMQ dedicated instance with users, virtual
hosts, exact permissions and bindings to existing exchanges and queues.

Passwords are accepted only for creation or explicit rotation and are hidden
from task output. Teardown removes bindings and permissions before virtual
hosts and users, disables deletion protection, and removes the instance last.
