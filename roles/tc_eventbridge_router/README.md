# tc_eventbridge_router

Provisions or adopts an EventBridge event bus, then reconciles source
connections, routing rules and delivery targets as one event-routing solution.

Teardown removes targets before rules, then connections and the parent bus.
Because EventBridge target APIs are scoped by rule ID, rule items containing
targets must declare `rule_id` during teardown.
