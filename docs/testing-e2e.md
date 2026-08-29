# Real-cloud end-to-end testing

Every write module is expected to satisfy the applicable C1-C10 contract:

1. create returns `changed=true`, a stable identifier and a converged resource;
2. identical reconciliation returns `changed=false` and the same identifier;
3. check mode predicts create, update and delete without a cloud side effect;
4. mutable fields update and converge, followed by an idempotent reconciliation;
5. immutable fields fail clearly or use an explicitly requested safe replacement;
6. delete waits for absence and a second delete returns `changed=false`;
7. permission, quota, conflict, throttling and timeout errors preserve error code and request ID;
8. asynchronous resources tolerate documented eventual consistency and expose terminal failures;
9. list-backed lookup handles pagination, duplicate names and service normalization;
10. secrets never appear in return data, diff, exception text or API call telemetry.

## Resource safety

Use a dedicated non-production sub-account. Resource names must start with
`ansible-<kind>-it-`; taggable resources must include `ansible_test=true`, a
run identifier and an expiry timestamp. Tests delete resources in an `always`
block. The global `cleanup` target is the second line of defence and a scheduled
TTL reaper is the third.

The target/cost/module registry is `tests/integration/coverage.yml`. Use
`scripts/integration_impact.py` to select affected targets. High-cost targets
are opt-in and must never run in an ordinary pull request.
