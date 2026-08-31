# tc_prometheus_platform

Provisions or adopts Managed Prometheus with cluster agents, scrape jobs,
recording rules, alert groups, Alertmanager, global notifications and Grafana
bindings. Agents containing scrape jobs must declare their service `agent_id`.

Teardown removes scrape jobs before agents, then rules, alerts and Grafana
bindings before the instance. Singleton notification configurations disappear
with the instance because the service exposes replacement but no delete API.
