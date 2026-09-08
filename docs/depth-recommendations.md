# Module Depth — Data-Driven Recommendations

Generated from plugin/modules filenames (module ↔ its `_info` sibling). A sibling `_info` is the read surface Ansible needs after a write; absence is the primary depth gap this repo can action deterministically. Capability-by-API-document review (what sub-resources Tencent offers per product) is intentionally NOT fabricated here and remains a manual step per product.

## Priority 1 — write modules missing their `_info` read surface (audit_info_coverage would flag)

Start with the domains teams use most: tse / dlc / tdmq / monitor / waf / teo / tsf / oceanus / tke.

| product | resource | _info | missing sibling |
| --- | --- | --- | --- |
| tse | 35 | 11 | 33 |
| dlc | 28 | 11 | 24 |
| tdmq | 15 | 1 | 15 |
| cos | 16 | 2 | 14 |
| waf | 13 | 1 | 13 |
| teo | 12 | 1 | 12 |
| monitor | 15 | 3 | 12 |
| tsf | 12 | 1 | 11 |
| config | 8 | 1 | 8 |
| oceanus | 9 | 1 | 8 |
| tke | 10 | 3 | 7 |
| ckafka | 9 | 3 | 6 |
| trabbit | 6 | 1 | 6 |
| cfw | 5 | 1 | 5 |
| api | 7 | 3 | 5 |
| dts | 5 | 1 | 5 |
| tcm | 5 | 1 | 4 |
| tcb | 4 | 1 | 4 |

## Priority 2 — read-only products (only `_info`, no write surface yet)

Add write modules only where there is real management demand (otherwise leave read-only).

| product | _info count |
| --- | --- |
| bdrc | 1 |
| apm | 1 |
| portal | 1 |
| igtm | 1 |
| ic | 1 |
| iss | 1 |
| wav | 1 |
| ses | 1 |
| tiw | 1 |
| tcss | 1 |
| trocket | 1 |
| lkeap | 1 |

## Priority 3 — balanced high-density domains (already have read+write pairs)

Review these against the official API surface for *sub-resources still missing* rather than blanket growth.

| product | resource | _info | total |
| --- | --- | --- | --- |
| tse | 35 | 11 | 46 |
| dlc | 28 | 11 | 39 |
| cvm | 11 | 9 | 20 |
| cos | 16 | 2 | 18 |
| monitor | 15 | 3 | 18 |
| cam | 8 | 8 | 16 |
| tione | 9 | 7 | 16 |
| tdmq | 15 | 1 | 16 |
| cdb | 7 | 7 | 14 |
| waf | 13 | 1 | 14 |
| cls | 7 | 7 | 14 |
| tke | 10 | 3 | 13 |
| teo | 12 | 1 | 13 |
| tsf | 12 | 1 | 13 |
| tdmysql | 7 | 5 | 12 |

## How to execute (needs the pinned Tencent SDK)

```bash
# pin the SDK to the committed stamp first
python -m pip install "tencentcloud-sdk-python==$(python scripts/check_sdk_drift.py --print-stamp)"
# regenerate _info modules for a product (add/refresh specs), or add a write module:
python scripts/generate_info_modules.py --resources   # adds RESOURCE_SPECS scaffolds (write-once)
python scripts/audit_info_coverage.py --check          # every write module keeps a read surface
```

Then the CI suite validates generated output (`generate_info_modules.py --check`, hidden-required
params, registries, ruff, sanity with the ignore budget guard, coverage >=72%). Prefer landing a whole
product domain per PR so review stays reviewable.

