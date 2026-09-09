# Real-cloud integration: trusted execution environment (P0-03) and the 26 → 30+ plan (P0-04)

> Owners: panorama P0-03 / P0-04 · gap-closure G1-b / G1-c · complements
> `docs/testing-e2e.md` (per-module C1-C10 contract) and
> `tests/integration/coverage.yml` (target / cost / module registry).
> Last synced with the repo at 26 targets (P0-01/P0-02 landed, `6d83295`).

Integration targets create **billable cloud resources in a real Tencent Cloud
account**. This document is the operator contract for that account: how
credentials are injected, when runs happen, what prevents a broken run from
leaking billable resources, how failures alert a human, and the roadmap from
26 to 30+ targets by 2026-10.

## 1. Execution model

- **Dedicated non-production sub-account.** Integration runs never touch a
  production account. The account owns nothing but CI-created resources.
- **Region pinned** to `ap-guangzhou` (`TENCENTCLOUD_REGION`). Targets read it
  from the environment and fall back to the same default in `vars/main.yml`.
- **Opt-in, never merge-blocking.** `ci.yml` (sanity + units + coverage gate)
  gates every push/PR and never touches the cloud. Real-cloud runs happen only
  through the Integration workflow: one weekly scheduled run plus manual
  `workflow_dispatch` with a target selector.
- **Serialised.** A single `concurrency` group (`tencentcloud-integration`)
  queues runs instead of cancelling them, so two runs can never fight over the
  account or double the bill, and a cancelled run can never strand resources.
- **Hard wall-clock cap.** `timeout-minutes: 40` bounds every run so a hung
  test or API deadlock cannot rack up unbounded spend.

## 2. Credential injection contract

Secrets are forwarded from GitHub repository secrets (`secrets.*`, masked in
logs) and non-secret tuning values from repository variables (`vars.*`). The
workflow's "Run integration tests" step is the single source of truth; the
tables below must stay in sync with it.

### 2.1 Base credentials

| env | source | consumed by |
|---|---|---|
| `TENCENTCLOUD_SECRET_ID` | secret | every module (via `tencentcloud_argument_spec`) |
| `TENCENTCLOUD_SECRET_KEY` | secret | every module |
| `TENCENTCLOUD_REGION` | literal `ap-guangzhou` | every target |

Use a CAM sub-account API key (never the root key). Rotate quarterly. The
modules additionally support STS `role_arn` / `profile`; CI uses the direct
key pair for simplicity.

### 2.2 Per-target gating variables

Targets self-skip (they print "Explain skipped …" and exit green) when their
gate variable is unset, so un-configured values are safe to leave empty.

| env | source | target | effect when unset |
|---|---|---|---|
| `TENCENTCLOUD_TKE_CLUSTER_ID` | secret | tke_addon | tke_addon skips |
| `TENCENTCLOUD_TKE_ADDON_NAME` | var | tke_addon | tke_addon skips |
| `TENCENTCLOUD_TKE_ADDON_VERSION` | var | tke_addon | tke_addon skips |
| `TENCENTCLOUD_MONITOR_NAMESPACE` | var | monitor_alarm_policy | monitor skips |
| `TENCENTCLOUD_MONITOR_NOTICE_ID` | secret | monitor_alarm_policy | notice step skips |
| `TENCENTCLOUD_PRIVATE_DNS_VPC_ID` | secret | private_dns | private_dns skips |
| `TENCENTCLOUD_CAM_GROUP_ID` | secret | cam_group_membership | group step skips |
| `TENCENTCLOUD_CAM_SUB_UIN` | secret | cam_group_membership | member step skips |
| `TENCENTCLOUD_DBBRAIN_INSTANCE_ID` | secret | dbbrain_sql_filter | dbbrain skips |
| `TENCENTCLOUD_DBBRAIN_SESSION_TOKEN` | secret | dbbrain_sql_filter | dbbrain skips |
| `TENCENTCLOUD_TCR_REGISTRY_ID` | secret | tcr_replication_instance | tcr skips |
| `TENCENTCLOUD_TCR_REPLICATION_REGION_ID` | var | tcr_replication_instance | tcr skips |
| `TENCENTCLOUD_TCR_REPLICATION_REGION_NAME` | var | tcr_replication_instance | tcr skips |
| `TENCENTCLOUD_CVM_INSTANCE_IMAGE_ID` | secret | cvm_instance | cvm_instance skips (billed) |
| `TENCENTCLOUD_CVM_INSTANCE_TYPE` | var | cvm_instance | defaults `S5.MEDIUM2` |
| `TENCENTCLOUD_RUN_BILLED_TARGETS` | var (`0`) | cdb_instance, tke_cluster | billed targets skip |
| `TENCENTCLOUD_CDB_ENGINE_VERSION` | var | cdb_instance | defaults `8.0` |
| `TENCENTCLOUD_CDB_MEMORY` | var | cdb_instance | defaults `8000` (MB) |
| `TENCENTCLOUD_CDB_VOLUME` | var | cdb_instance | defaults `100` (GB) |
| `TENCENTCLOUD_CDB_ZONE` | var | cdb_instance | defaults `ap-guangzhou-3` |
| `TENCENTCLOUD_TKE_CLUSTER_VERSION` | var | tke_cluster | platform default version |

Per-target resource pointers (image ids, cluster ids) are **secrets**; tuning
values (versions, sizes, zones) are **variables**. Never encode a billed
target's gate in the default target list — see §6 runbook for how to run them.

## 3. Billing guardrails

- Workflow: 40-minute wall cap + run serialisation + high-cost targets kept out
  of the weekly default list (registry `cost: high|medium` = opt-in only).
- Account: enable a CAM **budget alarm** on the integration sub-account
  (console-side, outside this repo) so any spend anomaly pages an operator
  even if every GitHub-side guard fails.
- Resource hygiene: names must start `ansible-<kind>-it-` and taggable
  resources must carry `ansible_test=true` so the sweeper (next section) can
  find anything that leaks.

## 4. Cleanup fallback (three lines of defence)

1. **Per-target `always:` blocks.** Every target deletes what it created even
   when the run fails mid-way. The P0-01/P0-02 flagship targets follow this
   template; the sweep below is the backstop for everything else.
2. **`cleanup` sweeper target.** The workflow runs
   `ansible-test integration cleanup` with `if: always()` **and**
   `continue-on-error: true`, i.e. even when the tests failed or timed out.
   It scans for the `ansible-*` name prefix / `ansible_test=true` tag across
   products and deletes in reverse dependency order, tolerating individual
   errors. This is the operative second line today.
3. **TTL manifest reaper (third line, partially wired).** Each created
   resource should be recorded with
   `python scripts/e2e_manifest.py add --run-id … --target … --resource-type …
   --resource-id … --region … --expires-at …`, and
   `scripts/resource_reaper.py --fail-on-expired` (run at the end of every
   workflow) flags entries past their TTL and writes `reaper-plan.json`.
   **Known gap:** no target emits manifest entries yet, so the reaper has
   nothing to audit until registration is wired into the targets — tracked as
   part of the P0-04 batches (§7). Until then line 2 is the real backstop.

## 5. Failure alerting

- Merge path: not applicable — real-cloud runs never gate merges.
- Weekly/manual runs: the workflow ends with an `if: failure()` alert step
  that POSTs a 企微-compatible text message to
  `TENCENTCLOUD_IT_ALERT_WEBHOOK` **when that secret is configured**; with no
  secret the step no-ops and the run page + uploaded artifacts
  (`integration-coverage`, `e2e-resource-manifests`) are the review surface.
- Cloud side: the §3 budget alarm catches spend anomalies independent of
  GitHub state.

## 6. Runbook

**Weekly default suite (free/low targets).** Nothing to do — the Saturday
02:00 UTC schedule runs the default list and uploads coverage + manifests.
A green run needs no review; a red run should be triaged the same day using
the alert and artifacts.

**Billed targets (`cvm_instance`, `cdb_instance`, `tke_cluster`).** One target
per dispatch — each exceeds the provision budget comfortably inside the
40-minute cap only on its own:

| target | expected wall time | requires |
|---|---|---|
| cvm_instance | 5-15 min (boot wait) | `TENCENTCLOUD_CVM_INSTANCE_IMAGE_ID` |
| cdb_instance | 10-20 min (delivery wait) | `TENCENTCLOUD_RUN_BILLED_TARGETS=1` |
| tke_cluster | 15-30 min (poll to Running) | `TENCENTCLOUD_RUN_BILLED_TARGETS=1` |

Dispatch with `inputs.targets` set to the single target name and the required
secrets/variables configured. `state=absent` on cdb_instance **isolates**
(billing stops, instance lingers in the recycle bin) and tke_cluster deletion
is queued by the API — check `e2e-resources`/`reaper-plan` artifacts or the
account console if a run dies between create and delete.

**Reading a run.** Skipped targets print an "Explain skipped …" debug task and
pass green; real coverage is visible only when the gate variable is set.

## 7. Roadmap: 26 → 30+ targets by 2026-10 (P0-04 / G1-c)

Direction from panorama G1-c: keep covering the flagship modules first, in
product-depth order, on the customer lines most used with the ones already
landed (CVM → network → database → container → storage/object → serverless →
messaging). Flagship status today: 5/13 have a dedicated target
(`cvm_instance`, `vpc`, `subnet`, `cdb_instance`, `tke_cluster`); `eip` and
`clb_load_balancer` are intentionally scenario-covered by `network` /
`clb_http` and get no dedicated target.

| ID | target | flagship | line | cost | async | why now |
|---|---|---|---|---|---|---|
| R1 | `cos_object` | ✅ | storage | free/low | no | object ops are the most-used COS surface; `cos_bucket` target already exists, this completes the pair |
| R2 | `cbs_disk` | ✅ | storage (CVM adj.) | low | no | cloud disks ship in the same orders as CVM; zone-local, no attach step needed for the spine |
| R3 | `scf_function` | ✅ | serverless | low | partial | function create/read/delete is cheap; rounds out the "compute" line |
| R4 | `nat_gateway` | ✅ | network | medium | no | last flagship on the network line; vpc/subnet/eip prerequisites now proven by `network` |
| R5 | `redis_instance` | ✅ | database | high | yes (10-20 m) | second database flagship after cdb; single-target dispatches only |
| R6 | `ckafka_instance` | ✅ | messaging | high | yes | messaging flagship; billed broker, keep out of default list |
| R7 | register `lighthouse` | — | compute | low | no | target dir already exists but is unregistered (registry inconsistency); registering + default-listing is a free +1 |
| R8 | register `cvm_image` | — | CVM | free | no | dir exists, unregistered; register only (needs a source-instance secret to run) |
| R9 | register `cleanup` | — | hygiene | free | no | make the registry mirror the sweeper target that CI already runs |

Milestones:

- **2026-09 (now → month end):** land `cos_object` + `cbs_disk` (R1/R2), and
  register the three orphan dirs (R7/R8/R9) → 28 target dirs, registry
  consistent, all new entries green on their first trusted-env dispatch.
- **2026-10:** land `scf_function`, `nat_gateway` (R3/R4) → 30 dirs, then
  `redis_instance` / `ckafka_instance` (R5/R6) → 32 dirs. Acceptance per
  panorama G1-c: **30+ targets all green before 2026-10 end**.

Every new target must pass `scripts/audit_integration_targets.py`, register in
`coverage.yml` (free/low joins the workflow default list; medium/high stays
opt-in), and follow the provision → assert → cleanup template from
`tests/integration/targets/cvm_instance/`. When a target lands, update the
counts in this document and in `docs/gap-closure.md` G1.
