# tc_cdn_delivery

Reconciles CDN domain configuration and running/stopped serving state, then
binds real-time access logs to CLS topics with exact domain/area sets.

Teardown removes CLS topics before domains. The underlying domain module now
stops an online domain and waits for `offline` before deleting it, eliminating
the provider-side stop/delete race.
