# Real-cloud integration: trusted execution environment (P0-03) and the 30 → 34+ plan (P0-04)

> Owners: panorama P0-03 / P0-04 · gap-closure G1-b / G1-c · complements
> `docs/testing-e2e.md` (per-module C1-C10 contract) and
> `tests/integration/coverage.yml` (target / cost / module registry).
> Last synced with the repo at 34 targets (P0-01/P0-02 landed, `6d83295`;
> the four pure-configuration theme-#1 targets and `apigateway_ip_strategy`
> added after it).

Integration targets create **billable cloud resources in a real Tencent Cloud
account**. This document is the operator contract for that account: how
credentials are injected, when runs happen, what prevents a broken run from
leaking billable resources, how failures alert a human, and the roadmap from
30 to 34+ targets by 2026-10.

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
| `TENCENTCLOUD_TOKEN` | secret | optional STS token, forwarded to the profile |
| `TENCENTCLOUD_REGION` | literal `ap-guangzhou` | every target |

Use a CAM sub-account API key (never the root key). Rotate quarterly. The
modules additionally support STS `role_arn` / `profile`; CI uses the direct
key pair for simplicity.

Without `TENCENTCLOUD_SECRET_ID` every step of the `Integration` workflow is
guarded off, and the `Require Tencent Cloud credentials` step then **fails** the
run. That is deliberate: both triggers (`schedule`, `workflow_dispatch`) run on
the canonical repository, so a credential-less run is a misconfiguration. Left
unhandled it would skip all 10 downstream steps and still report success - a
green run that executed no test.

### 2.2 Per-target gating variables

Targets self-skip (they print "Explain skipped …" and exit green) when their
gate variable is unset, so un-configured values are safe to leave empty.
Every variable below is read through `e2e_inputs` (§2.5) first and the real
environment second, so a value materialised into
`$HOME/.tencentcloud/e2e_inputs.yml` does reach the target even though
`ansible-test` empties the environment.

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
| `TENCENTCLOUD_APIGW_SERVICE_ID` | secret | apigateway_ip_strategy | a throwaway service is created instead (and skipped if the product is unavailable) |
| `TENCENTCLOUD_TCR_NAMESPACE` | var | tcr_immutable_tag_rule, tcr_webhook_trigger | both TCR targets skip |
| `TENCENTCLOUD_TCR_WEBHOOK_URL` | secret | tcr_webhook_trigger | tcr_webhook_trigger skips |
| `TENCENTCLOUD_CLS_ALARM_TOPIC_ID` | secret | cls_alarm | cls_alarm skips |
| `TENCENTCLOUD_REDIS_INSTANCE_ID` | secret | redis_replication_group | redis skips (billed, also needs `TENCENTCLOUD_RUN_BILLED_TARGETS=1`) |

Per-target resource pointers (image ids, cluster ids) are **secrets**; tuning
values (versions, sizes, zones) are **variables**. Never encode a billed
target's gate in the default target list — see §6 runbook for how to run them.

### 2.3 The `ansible-test` environment sanitiser (and why a profile file is the contract)

`ansible-test` does **not** forward the caller's environment to the
`ansible-playbook` process it spawns. `common_environment()` in
`ansible_test._internal.util` rebuilds the environment from scratch: only
`HOME`, `PATH`, `LC_ALL` plus a short platform-compatibility list
(`LD_LIBRARY_PATH`, `SSH_AUTH_SOCK`, `LDFLAGS`, `CFLAGS`, …) survive. Every
`TENCENTCLOUD_*` variable — including the two above — is dropped, and every
module then fails with:

```
Set secret_id and secret_key, their TENCENTCLOUD_* environment variables, or
the secret_id/secret_key keys of a profile in ~/.tencentcloud/default.configure.
```

The same applies to the controller-side `lookup('env', …)` calls in the
targets' `vars/main.yml`: they resolve **inside** `ansible-playbook`, so the
per-target gate variables of §2.2 are empty as well. That is safe by design
(targets self-skip) but it means a gate can never be *enabled* through the
workflow's `env:` block alone.

The one channel that survives is `HOME`, and every module already falls back to
the TCCLI profile `$HOME/.tencentcloud/default.configure` for `secret_id`,
`secret_key`, `token` and `region` (`plugins/module_utils/client.py`). The
workflow therefore materialises the secrets into that file before invoking
`ansible-test`:

```console
export TENCENTCLOUD_SECRET_ID=… TENCENTCLOUD_SECRET_KEY=…
export TENCENTCLOUD_REGION=ap-guangzhou          # optional; default below
python scripts/integration_credentials.py --write
python scripts/integration_credentials.py --check   # verify, exit 1 when absent
ansible-test integration key_pair --local
```

The script writes mode `0600`, omits empty keys, never prints a secret, and
exits `2` when the key pair is missing. Use the identical two commands for a
local trusted-environment run — the only difference is `TENCENTCLOUD_REGION`,
which the intl test account sets to `ap-hongkong`.

Consequence to remember when writing a target: **anything the test needs from
the environment must come from a file under `$HOME`, not from `env:`.**

### 2.4 Products the account cannot host (API Gateway, CAM, Monitor)

Some creates fail for reasons that have nothing to do with the module. Three
cases are known on the intl test account, and all of them are **account
capability gaps** rather than regressions:

```
API Gateway  CreateService  → FailedOperation.LimitingResourceCreated:
                              The API gateway product has been stopped for
                              sale, and no new resources can be created.
             CreatePlugin   → InternalError (same condition, no code)
CAM          AddUser        → AuthFailure.UnauthorizedOperation:
                              you are not authorized to perform operation
                              (cam:AddUser)
Monitor      CreateAlarmPolicy → InvalidParameter: "INVALID_ARGUMENT":
                              view not found: QCE/CVM
```

API Gateway refuses in `ap-guangzhou`, `ap-hongkong`, `ap-singapore`,
`ap-shanghai` and `ap-beijing` alike, so no region switch works around it. The
Monitor failure is not about the namespace either: every namespace
`DescribeProductList` returns (`qce/dlc`, `qce/tke2`, `qce/excluster`, …) is
rejected with the same "view not found", which means the account has no alarm
view map loaded at all.

Rather than leave permanently red targets, the affected ones treat these codes
as **"this account cannot host the product"** and skip their lifecycle with a
debug explanation:

| Target | Skips on |
| --- | --- |
| `api_gateway_service`, `apigateway_plugin`, `apigateway_ip_strategy` | `LimitingResourceCreated` / `InternalError` / "stopped for sale" |
| `cam_user` | `AuthFailure.UnauthorizedOperation` on `AddUser` |
| `monitor_alarm_policy` | `InvalidParameter` containing "view not found" |

Any other error still fails the run, so a genuine regression is never masked.
On an account that does have the product the same targets run the full
create → idempotency → check-mode → delete contract unchanged.

### 2.5 Non-secret inputs: the same file channel

Credentials are only half the problem. Before this existed, every gate in §2.2
was unreachable: the workflow's `env:` block was stripped, so
`lookup('env', …)` was empty and the gated targets could never be switched on -
not locally, not in CI. `scripts/integration_inputs.py` copies every
`TENCENTCLOUD_*` variable plus `GITHUB_RUN_ID` into
`$HOME/.tencentcloud/e2e_inputs.yml` (mode 0600; the key pair and the STS token
are deliberately excluded, they belong to §2.3):

```console
export TENCENTCLOUD_RUN_BILLED_TARGETS=1
python scripts/integration_inputs.py --write
python scripts/integration_inputs.py --check     # exit 1 when the file is absent
python scripts/integration_inputs.py --dry-run   # print masked, write nothing
ansible-test integration cdb_instance --local
```

Targets pick the values up in `vars/main.yml`:

```yaml
e2e_inputs: >-
  {{ lookup('ansible.builtin.file', lookup('env', 'HOME') ~ '/.tencentcloud/e2e_inputs.yml', errors='ignore')
     | default('', true) | from_yaml | default({}, true) }}
tencentcloud_region: "{{ e2e_inputs.TENCENTCLOUD_REGION
                          | default(lookup('env', 'TENCENTCLOUD_REGION'), true)
                          | default('ap-guangzhou', true) }}"
```

A missing file yields `{}`, so the documented default still applies and a plain
`ansible-playbook` run (where `env` *does* work) is unaffected.

## 3. Billing guardrails

- Workflow: 40-minute wall cap + run serialisation + high-cost targets kept out
  of the weekly default list (registry `cost: high|medium` = opt-in only).
- Account: enable a CAM **budget alarm** on the integration sub-account
  (console-side, outside this repo) so any spend anomaly pages an operator
  even if every GitHub-side guard fails.
- Resource hygiene: names must start `ansible-<kind>-it-` and taggable
  resources must carry `ansible_test=true` so the sweeper (next section) can
  find anything that leaks. Some APIs forbid `-` in a name — the CVM key pair
  API rejects it with `InvalidParameterValue: 包含不合法的字符'-'` — so those
  targets use the underscore spelling `ansible_<kind>_it_*`; the sweeper
  accepts both separators.

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

## 7. Roadmap: 30 → 34+ targets by 2026-10 (P0-04 / G1-c)

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
