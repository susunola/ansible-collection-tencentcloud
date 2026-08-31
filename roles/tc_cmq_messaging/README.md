# tc_cmq_messaging

Provisions CMQ queues and topics with HTTP or queue subscriptions. All
resources use stable service-side names as their identity.

Teardown removes subscriptions before topics and deletes queues last because a
queue may still be referenced as a subscription endpoint.
