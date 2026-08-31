# tc_edgeone_application

Provisions or adopts an EdgeOne zone with origin groups, acceleration domains,
DNS records, security IP groups, web-security templates and zone, template or
host scoped managed, custom, exception, rate-limiting and Bot Lite policies.

Template creation and policy binding occur in one run using the returned
template ID. Teardown requires declared template IDs, clears policies and
bindings first, then removes templates, delivery resources, origins and the
zone in dependency order.
