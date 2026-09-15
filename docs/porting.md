# Porting guide

How to move an existing `tencentcloudstack/tencentcloud` Terraform module, or a
raw Tencent Cloud SDK script, onto this collection.

The guide only describes things the code actually does. Every module name,
option and helper named here was read out of this repository; the Terraform
column was read out of the provider's own documentation sources. Where the two
disagree, the disagreement is called out instead of papered over.

Companion reading: [`development.md`](development.md) is the *authoring*
convention (how to write a module); this document is the *translation*
convention (how to express what you already have).

## 1. The mental model

| You have | You write | What replaces the machinery you lose |
| --- | --- | --- |
| `resource "tencentcloud_x" "y"` | a task calling `susunola.tencentcloud.<module>` | nothing — the task *is* the resource |
| `terraform.tfstate` | nothing | a `Describe*` lookup at the top of every module run |
| `terraform plan` | `ansible-playbook --check --diff` | `maybe_diff()` + `lifecycle.plan_changes()` |
| `terraform apply` | `ansible-playbook` | same code path; check mode only gates the write |
| `terraform destroy` | `state: absent` | `lifecycle.delete_resource()` / `soft_delete()` |
| `terraform import` | nothing to do | address the resource by `name` or `<x>_id`; it is adopted on the next run |
| `data "tencentcloud_x" "y"` | `<module>_info`, or the `resource_id` lookup | see [§2.2](#22-data-sources-and-lookups) |
| `count` / `for_each` | `loop` | see [§3.4](#34-count-foreach-dependson-and-outputs) |
| `depends_on` | task order, `register`, `set_fact` | see [§3.4](#34-count-foreach-dependson-and-outputs) |
| `output` | `register` / `set_fact` / role result facts | see [§3.4](#34-count-foreach-dependson-and-outputs) |

The one structural difference: **Terraform reconciles a graph against a stored
state; Ansible reconciles one task against the live API.** Everything below is a
consequence of that.

## 2. Naming: resource → module FQCN

### 2.1 Resource map

Terraform names are `tencentcloud_<x>`; module names are
`susunola.tencentcloud.<x>`. Most pairs are a direct rename, because both
projects follow the product's own vocabulary. The ones that are not are the
reason this table exists.

| Terraform resource | Module | Why it differs |
| --- | --- | --- |
| `tencentcloud_instance` | `cvm_instance` | collection carries the product prefix on CVM |
| `tencentcloud_vpc` | `vpc` | — |
| `tencentcloud_subnet` | `subnet` | — |
| `tencentcloud_security_group` | `security_group` | — |
| `tencentcloud_route_table` | `route_table` | — |
| `tencentcloud_nat_gateway` | `nat_gateway` | — |
| `tencentcloud_eip` | `eip` | — |
| `tencentcloud_key_pair` | `key_pair` | — |
| `tencentcloud_cbs_storage` | `cbs_disk` | provider name predates the CBS rename |
| `tencentcloud_clb_instance` | `clb_load_balancer` | collection uses the console term |
| `tencentcloud_clb_listener` | `clb_listener` | — |
| `tencentcloud_kubernetes_cluster` | `tke_cluster` | provider uses the generic word, collection the product code |
| `tencentcloud_kubernetes_node_pool` | `tke_node_pool` | as above |
| `tencentcloud_mysql_instance` | `cdb_instance` | CDB is the product code for MySQL |
| `tencentcloud_redis_instance` | `redis_instance` | — |
| `tencentcloud_mongodb_instance` | `mongodb_instance` | — |
| `tencentcloud_postgresql_instance` | `postgresql_instance` | — |
| `tencentcloud_sqlserver_instance` | `sqlserver_instance` | — |
| `tencentcloud_cynosdb_cluster` | `cynosdb_cluster` | — |
| `tencentcloud_cos_bucket` | `cos_bucket` | — |
| `tencentcloud_cdn_domain` | `cdn_domain` | — |
| `tencentcloud_dnspod_record` | `dnspod_record` | — |
| `tencentcloud_vpn_gateway` | `vpn_gateway` | — |
| `tencentcloud_ssl_certificate` | `ssl_certificate` | — |
| `tencentcloud_cfs_file_system` | `cfs_file_system` | — |
| `tencentcloud_ckafka_instance` | `ckafka_instance` | — |
| `tencentcloud_scf_function` | `scf_function` | — |
| `tencentcloud_emr_cluster` | `emr_cluster` | — |
| `tencentcloud_elasticsearch_instance` | `elasticsearch_instance` | — |
| `tencentcloud_monitor_alarm_policy` | `monitor_alarm_policy` | — |

Two directions of mismatch are normal and neither is a bug:

* **one Terraform resource, several modules.** The provider models CLB as
  `clb_instance` + `clb_listener` + `clb_listener_rule` + attachments; the
  collection has `clb_load_balancer`, `clb_listener`, `clb_rule`,
  `clb_listener_target`, `clb_target_group`. Split the resource into one task
  per concern.
* **one module, several Terraform resources.** The provider splits
  post-creation settings into `postgresql_instance_ha_config`,
  `..._ssl_config`, `..._network_access` and a dozen more; a single
  `postgresql_instance` task owns them as options.

### 2.2 Data sources and lookups

| Terraform | Here |
| --- | --- |
| `data "tencentcloud_vpc" "x" { name = "prod" }` | `vpc_info`, or `lookup('susunola.tencentcloud.resource_id', 'prod', resource_type='vpc')` |
| `data.tencentcloud_vpc.x.id` in an argument | `"{{ lookup('susunola.tencentcloud.resource_id', 'prod', resource_type='vpc') }}"` |
| `data "tencentcloud_availability_zones"` | `vpc_info` / the `zone` option's own validation |

`plugins/lookup/resource_id.py` is the closest analogue of a Terraform data
source: it takes an **exact** name and fails when the name is absent or
ambiguous. It covers 41 resource families (VPC, subnet, security group, CVM,
CLB/ALB/GWLB, TKE, CDB, PostgreSQL, MariaDB, SQL Server, CynosDB, Redis,
MongoDB, Elasticsearch, CFS, CHDFS, CKafka, TDMQ, Prometheus, API Gateway,
TCR, TEM, and others). Anything outside that list goes through the
`<resource>_info` module instead — there are 435 of them.

### 2.3 Finding a module that is not in the table

Naming is `<product>_<resource>`, optionally `<product>_<resource>_<sub>`:

```
ansible-doc -l susunola.tencentcloud | grep -iE '^(cvm|vpc|tke|cdb|cos)_'
ls plugins/modules/ | grep -E '^tke_'
```

Product prefixes with the most modules: `tse` (65), `dlc` (58), `tdmq` (31),
`tsf` (24), `monitor` (24), `waf` (22), `cvm` (20), `teo` (18), `cos` (18),
`tione` (16), `oceanus` (16), `cam` (16). [`README.md`](../README.md) carries
the full FQCN index and [`product-capabilities.md`](product-capabilities.md)
the per-product matrix.

## 3. State: what replaces `terraform.tfstate`

### 3.1 Identity

There is no stored mapping from a resource address to a cloud id, so a module
re-derives it on every run. `plugins/module_utils/resolver.py` is the single
implementation, and its contract is worth knowing before you port anything:

* an **id** (`vpc_id`, `subnet_id`, …) is authoritative — rename the resource
  and the task still finds it;
* a **name** is matched exactly first. Tencent Cloud list filters are
  *substring* matches, so `vpc-name=prod` also returns `prod-old`; the resolver
  re-checks every row client-side and never lets a fuzzy filter widen the match;
* a single fuzzy candidate is accepted (backwards compatibility), two or more
  **fail** with `ambiguous=true` and the candidate list — never a silent
  `VpcSet[0]`;
* no selector at all returns `None`; it is never a wildcard listing.

**Porting consequence:** a Terraform config that relies on
`tencentcloud_vpc.main.id` being stable across runs has no equivalent hazard
here, but a config that relies on *names being unique* does. Pass the id when
you have it.

### 3.2 plan / apply / destroy

```bash
ansible-playbook site.yml --check --diff   # terraform plan
ansible-playbook site.yml                  # terraform apply
ansible-playbook teardown.yml              # terraform destroy  (state: absent)
```

All 875 modules declare `supports_check_mode=True`, and the contract is the one
`vpc` implements: resolve, compute the change set once with
`lifecycle.plan_changes`, then — if check mode — `exit_json(changed=True, ...)`
without calling a write API. Waiters skip themselves in check mode, so a
`--check` run never blocks on polling.

Terraform blocks for readiness automatically; this collection only blocks when
the module has a `waiter_*` option (default `waiter_delay` 5, `waiter_timeout`
120) or when you wait explicitly. When the module you are calling does not wait,
poll its `_info` sibling with the `tc_wait` action plugin
(`susunola.tencentcloud.tc_wait`) instead of hand-rolling a loop — that is the
controller-side equivalent of a Terraform provisioner wait.

Diff output follows the [`development.md`](development.md#diff-mode) rule:
`maybe_diff(module, before, after)` only emits a `diff` key under `--check` or
`--diff`, so a plain run stays small.

Deletion is `state: absent`. `lifecycle.delete_resource` treats an
already-absent resource as `changed=False` rather than an error; databases and
CVM go through `lifecycle.soft_delete(isolate, purge, force=...)`, which encodes
the isolate-then-purge two-step those products use.

### 3.3 Terraform features with no equivalent — and what to do instead

| Terraform | Here |
| --- | --- |
| `lifecycle { ignore_changes = [...] }` | **omit the option.** `None` means "this task does not manage the field"; it is left out of the change set even when the API would rewrite it. This is the default, not a switch. |
| `lifecycle { prevent_destroy = true }` | nothing built in. Guard with `when:`, a dedicated inventory group, or the product's own deletion-protection option (`tke_cluster` has `deletion_protection`). |
| `lifecycle { create_before_destroy = true }` | sequence it explicitly: create the replacement, then delete the old one. |
| `moved` / `removed` blocks | nothing to rewrite — change the selector in the task. |
| `terraform import` | run the task against the existing resource by id or name; it is adopted and converges. |
| `terraform state rm` | delete the task from the playbook. |
| `-target` | `--tags` on the play/task. |
| `timeouts { create = "20m" }` | `waiter_timeout` (default 120) and `waiter_delay` (default 5). |
| provider `alias` per region | `region:` on the task. No aliasing needed. |

### 3.4 `count`, `for_each`, `depends_on` and outputs

```yaml
# count = 3                     -> loop
- name: Three subnets
  susunola.tencentcloud.subnet:
    region: "{{ region }}"
    vpc_id: "{{ vpc.vpc.VpcId }}"
    name: "web-{{ item }}"
    cidr_block: "10.0.{{ item }}.0/24"
    zone: ap-guangzhou-3
  loop: [1, 2, 3]

# for_each = { web = "10.0.1.0/24", app = "10.0.2.0/24" }   -> dict2items
- name: Subnets from a map
  susunola.tencentcloud.subnet:
    region: "{{ region }}"
    vpc_id: "{{ vpc.vpc.VpcId }}"
    name: "{{ item.key }}"
    cidr_block: "{{ item.value }}"
    zone: ap-guangzhou-3
  loop: "{{ subnets | dict2items }}"
```

`cvm_instance` is the one module with a `count`-like primitive of its own:
`exact_count` plus `count_tag` maintain a *pool* of instances and correct drift
in both directions, which is what a Terraform `count` with a stable tag
effectively gives you. It is mutually exclusive with `instance_id`.

`depends_on` becomes ordering you can read: tasks in a play run in order, and
cross-play hand-off is a registered fact or a role result.
[`examples/README.md`](examples/README.md) documents the published result facts
(`tc_vpc_foundation_result`, `tc_web_stack_result`, `tc_tke_cluster_result`,
`tc_disaster_recovery_result`) and why teardown lists dependents first.

## 4. Credentials and region

### 4.1 Precedence

Both sides read parameter → environment → profile. This collection resolves
credentials and region in `client.create_credential`, which writes the resolved
region back into `module.params['region']`, so modules stay unaware of
profiles.

### 4.2 The differences that bite

| Concern | Terraform provider | This collection |
| --- | --- | --- |
| Secret id | provider arg / `TENCENTCLOUD_SECRET_ID` | `secret_id` / `TENCENTCLOUD_SECRET_ID` |
| Secret key | provider arg / `TENCENTCLOUD_SECRET_KEY` | `secret_key` / `TENCENTCLOUD_SECRET_KEY` |
| Session token | `security_token` / `TENCENTCLOUD_SECURITY_TOKEN` | **`token`** / **`TENCENTCLOUD_TOKEN`** — different name |
| Region | `region` / `TENCENTCLOUD_REGION`, **defaults to `ap-guangzhou`** | `region` / `TENCENTCLOUD_REGION`, **no default** — the module fails if none is found |
| Profile | `profile` / `TENCENTCLOUD_PROFILE` | `profile` / `TENCENTCLOUD_PROFILE` |
| Credentials file | `shared_credentials_dir`, default `~/.tccli` | fixed at `~/.tencentcloud/default.configure` (TCCLI INI) |
| File location override | `TENCENTCLOUD_SHARED_CREDENTIALS_DIR` | none |
| Assume role | `assume_role { role_arn, session_name, session_duration, policy, external_id }` | `role_arn`, `role_session_name` (default `ansible-tencentcloud`), `role_session_duration` (default 7200). **No policy document, no `external_id`.** |
| Endpoint | `domain`, `protocol` | `endpoint` |
| HTTP timeout | — | `timeout` (default 60) |
| Transient retries | provider-level | `retries` (default 5, exponential backoff) |

Practical consequence: `TENCENTCLOUD_SECRET_ID`, `TENCENTCLOUD_SECRET_KEY`,
`TENCENTCLOUD_REGION` and `TENCENTCLOUD_PROFILE` carry over unchanged, so a
Terraform environment that already exports them works here. `TENCENTCLOUD_TOKEN`
and the `~/.tccli` directory do not — export `TENCENTCLOUD_TOKEN`, and either
run `tccli configure` so that `~/.tencentcloud/default.configure` exists or pass
credentials as parameters.

### 4.3 Region is per task

There is no provider block, so multi-region is a loop rather than a set of
aliases:

```yaml
- name: Same VPC shape in three regions
  susunola.tencentcloud.vpc:
    region: "{{ item }}"
    name: prod-vpc
    cidr_block: 10.0.0.0/16
  loop: [ap-guangzhou, ap-singapore, ap-bangkok]
```

Inventory and lookup plugins have no parameters for credentials — they read the
same `TENCENTCLOUD_*` variables through `env:` fallbacks in their
`DOCUMENTATION`, so export them in the environment that runs `ansible-playbook`.

## 5. From a raw SDK script

### 5.1 API verb → module shape

| What the script calls | Where it lands |
| --- | --- |
| `DescribeXxx` + `Filters` | `find_xxx()` built on `resolver.resolve_one` |
| `CreateXxx` | the `state: present` branch when nothing was found |
| `ModifyXxxAttribute` | the update branch, gated on `lifecycle.plan_changes` |
| `DeleteXxx` / `IsolateXxx` + `DestroyXxx` | `state: absent`, via `lifecycle.delete_resource` / `soft_delete` |
| `TagXxxResources` | `build_sdk_tags` / `compare_tags` from `module_utils/tagging.py` |
| `while True: Describe…; sleep(5)` | `waiters.wait_for_state` / `wait_until_gone` / `wait_for_task` |
| `except TencentCloudSDKException` | `module.sdk_call` (retries with backoff) + `lifecycle.fail_from_sdk_error` |
| `DescribeTaskStatus(TaskId=…)` | `waiters.wait_for_task` |

### 5.2 Anatomy of a module

`plugins/modules/vpc.py` is the reference implementation. Trimmed to its
skeleton, every write module in this collection has this shape:

```python
def find_vpc(module, client, models, name, vpc_id):
    def describe(filters):                       # paginate here, match there
        request = build_describe_request(models, name, vpc_id)
        resolver.attach_filters(request, models, filters)
        response = module.sdk_call(client.DescribeVpcs, request)
        return resolver.records(response.VpcSet)

    return resolver.resolve_one(                 # id > exact name > fuzzy
        module, describe, resource="VPC",
        id_value=vpc_id, name_value=name,
        id_keys=("VpcId",), name_keys=("VpcName",),
        name_filters=("vpc-name",),
    )


def run_module():
    module = TencentCloudModule(argument_spec={...}, supports_check_mode=True)
    module.require_sdk()
    client = module.create_client(vpc_client.VpcClient, "vpc.tencentcloudapi.com")

    current = find_vpc(...)                      # 1. resolve

    changes = lifecycle.plan_changes(current_view, desired_view)   # 2. plan
    if not changes:
        module.exit_json(changed=False, vpc=current, msg="VPC is up to date")

    if module.check_mode:                        # 3. preview
        module.exit_json(changed=True, **(maybe_diff(...) or {}), msg="Would update VPC")

    _update_attributes(...)                      # 4. write
    updated = find_vpc(...)                      # 5. re-read and report
    module.exit_json(changed=True, vpc=updated, msg="VPC updated")
```

Resolve → plan → preview → write → re-read. Step 5 matters for porting: the
returned resource is read back from the API, not assembled from the request, so
`register` gives you server truth including server-assigned fields.

### 5.3 Errors and waiting

* `module.sdk_call(operation, request)` wraps every call; transient failures
  retry `retries` times (default 5) with exponential backoff before raising.
* `lifecycle.fail_from_sdk_error(module, exc, "DescribeVpcs")` converts the
  exception into one envelope — `msg`, `error`, `error_code`, `error_kind`,
  `request_id`, `operation` — with credentials redacted. Do not hand-roll
  `fail_json` for SDK errors.
* Lookups that may legitimately find nothing wrap in
  `lifecycle.missing_as_none`; a `ResourceNotFound` becomes `None`.
* Async work is polled by `plugins/module_utils/waiters.py`, never by a
  hand-written loop, and waiters no-op under check mode.

### 5.4 Idempotency checklist for a ported script

1. Does it resolve by id when an id is available?
2. Does an unchanged resource produce `changed=False`? (Run it twice.)
3. Does `--check` produce no API writes? (Check the `tc_calls` payload or the
   API console.)
4. Does a field the task does not manage stay `None` rather than being
   defaulted into the request?
5. Is every `Describe*Set[0]` gone?
6. Does a missing resource read as `None` rather than an exception?

## 6. The `_info` + write module pair

A write module and its `_info` sibling are one surface split in two: the write
module converges, the `_info` module reads. 230 of the 440 write modules ship
their own `<name>_info` sibling; the rest are covered either by a curated
mapping to another `_info` module that really returns the resource, or by a
recorded gap. `scripts/audit_info_coverage.py --check` is the authority — it is
the gate that stops a new write module landing without a deliberate read
decision, and `scripts/generate_info_modules.py` produces the generated half of
the pairs.

Use the pair in the same play: converge, then read back through a filter, which
is how a ported Terraform `output` block usually ends up looking.

```yaml
- name: Converge and report
  hosts: localhost
  gather_facts: false
  tasks:
    - name: Make sure the VPC exists
      susunola.tencentcloud.vpc:
        region: ap-guangzhou
        name: prod-vpc
        cidr_block: 10.0.0.0/16

    - name: Read it back through the pair
      susunola.tencentcloud.vpc_info:
        region: ap-guangzhou
        filters:
          vpc-name:
            - prod-vpc
      register: found

    - name: Report
      ansible.builtin.debug:
        msg: "{{ found.vpcs | map(attribute='VpcId') | list }}"
```

If the write module you need has no `_info` sibling, read the coverage table
first:

```bash
python scripts/audit_info_coverage.py --check
```

## 7. Worked example

The Terraform version:

```hcl
provider "tencentcloud" {
  region = "ap-guangzhou"
}

resource "tencentcloud_vpc" "main" {
  name       = "prod-vpc"
  cidr_block = "10.0.0.0/16"
}

resource "tencentcloud_subnet" "web" {
  vpc_id            = tencentcloud_vpc.main.id
  name              = "web-a"
  cidr_block        = "10.0.1.0/24"
  availability_zone = "ap-guangzhou-3"
}

output "vpc_id" {
  value = tencentcloud_vpc.main.id
}
```

The same thing here:

```yaml
- name: Network foundation
  hosts: localhost
  gather_facts: false
  vars:
    region: ap-guangzhou
  tasks:
    - name: VPC
      susunola.tencentcloud.vpc:
        region: "{{ region }}"
        state: present
        name: prod-vpc
        cidr_block: 10.0.0.0/16
      register: vpc_result

    - name: Subnet
      susunola.tencentcloud.subnet:
        region: "{{ region }}"
        state: present
        name: web-a
        vpc_id: "{{ vpc_result.vpc.VpcId }}"
        cidr_block: 10.0.1.0/24
        zone: ap-guangzhou-3

    - name: vpc_id output
      ansible.builtin.set_fact:
        vpc_id: "{{ vpc_result.vpc.VpcId }}"
```

What changed:

* `tencentcloud_vpc.main.id` became `vpc_result.vpc.VpcId` — a registered fact
  instead of a state lookup. Because the VPC is resolved by name on every run,
  the second run reports `changed=False` and the subnet task still gets the same
  id.
* `availability_zone` became `zone`. Option names follow the API parameter, not
  the provider's schema.
* `output` became `set_fact`; it lives for the rest of the play.
* Teardown is the same two tasks with `state: absent`, subnet first — a VPC with
  live dependencies cannot be deleted.

A fuller chain, including the web stack that consumes these ids, is
[`examples/06_full_chain.yml`](examples/06_full_chain.yml).

## 8. Common mistakes

| Mistake | Fix |
| --- | --- |
| Copying provider option names (`availability_zone`, `instance_name`, `security_groups`) | read the module's `DOCUMENTATION`: `ansible-doc susunola.tencentcloud.subnet` |
| Expecting a region default | there is none; set `region` or `TENCENTCLOUD_REGION` |
| Expecting `TENCENTCLOUD_SECURITY_TOKEN` to work | the variable is `TENCENTCLOUD_TOKEN` |
| Pointing `profile` at `~/.tccli` | the file is `~/.tencentcloud/default.configure` |
| Assuming `count = N` drifts back | use `cvm_instance`'s `exact_count` + `count_tag`, or reconcile a loop against an `_info` result |
| Turning a `prevent_destroy` into nothing | guard with `when:` or the product's deletion-protection option |
| Writing `try/except` around the SDK | use `module.sdk_call` and `lifecycle.fail_from_sdk_error` |
| Taking `XxxSet[0]` | use `resolver.resolve_one` |
| Thinking `--check` also polls | waiters no-op in check mode by design |

## 9. Before you open a PR

```bash
ansible-playbook your_playbook.yml --syntax-check
ansible-playbook your_playbook.yml --check --diff
python scripts/check_examples.py --check        # if it lands in docs/examples/ or playbooks/
python scripts/audit_info_coverage.py --check   # if you touched a write module
```

Module authoring conventions, tier rules and the unit-test harness are in
[`development.md`](development.md). The deprecation rules that govern renaming
anything named in this guide are in [`deprecation-policy.md`](deprecation-policy.md).

## 10. Version map and upgrade notes

`changelogs/changelog.yaml` records every release this collection has shipped.
This section is the upgrade path across them: which release you are coming
from, what changed under you, and the three releases where an upgrade is not a
no-op. Every version below is one this repository actually published.

### 10.1 Release index

| Version | Changes | Breaking | What it is |
| --- | --- | --- | --- |
| `0.5.0` | 7 major / 45 minor / 4 bugfix | — | TCCLI credential profiles, the first dynamic inventory plugin, the `ssm_parameter` and `sts_caller_identity` lookups, STS AssumeRole on every module, `--diff` on every write module, and the `*_info` generator |
| `0.6.0` | 14 minor / 1 bugfix | — | more generated `*_info` modules (API Gateway, Auto Scaling, CFS); `action_groups.all` fixed so `module_defaults` applies to generated modules |
| `0.7.0` | 14 minor | — | generated read surfaces for billing, CDN and CloudAudit, including the first token-paginated one |
| `0.8.0` | 4 minor | — | `scripts/discover_info_specs.py` starts nominating generator specs from SDK introspection; 126 generated `*_info` modules lift product coverage from 36 to 162 |
| `0.9.0` | 3 minor | — | coverage batch 5 closes every product on the official API index with a usable list API; new pagination modes (no total-count, custom token pairs) |
| `0.10.0` | 5 minor | — | the CLB write modules (`clb_load_balancer`, `clb_listener`, `clb_listener_target`) and the `wait_for_task` async-task helper |
| `0.11.0` | 4 minor / 23 bugfix | **yes** | the collection rename to `susunola.tencentcloud` — see 10.2 |
| `0.12.0` | 41 minor / 4 bugfix | **yes** | five `*_info` modules renamed and their return keys changed — see 10.2 |
| `0.13.0` | 93 minor / 9 bugfix | — | the API Gateway API lifecycle and Auto Scaling policy wave, plus the inherited retry/waiter documentation pass that makes strict validation succeed |
| `1.0.0` | 1 major / 155 minor / 4 bugfix | **yes** | first stable release; semantic versioning from here, and the ansible-core floor rises to 2.19 — see 10.2 |
| `1.1.0` | 11 minor / 2 bugfix | — | `docs/deprecation-policy.md`, the `audit_info_coverage.py` CI gate, the three-tier-web scenario playbook, and the SDK pin relaxed to a compatibility range |
| `1.2.0` | 311 minor / 36 bugfix | — | the large product-depth wave: DCDB accounts and encryption, DLC work groups, GAAP listeners and real servers, Oceanus clusters and jobs |
| `1.3.0` | 4 minor | — | the `tc_inventory` multi-product inventory plugin (CVM, TKE, Lighthouse, VPC) with cross-product de-duplication |
| `1.4.0` | 6 minor | — | `tc_inventory` second batch (CLB, CDB, CBS, COS) and the controller-side COS client builder that needs `cos-python-sdk-v5` on the controller |

Across the 14 releases: 8 major changes, 710 minor changes, 83 bugfixes and
7 breaking changes.

### 10.2 The three releases that need work

Everything else upgrades with `ansible-galaxy collection install --force`.
These three do not.

**`0.11.0` — the collection was renamed.** It moved from
`tencentcloud.cloud` to `susunola.tencentcloud` because a Galaxy namespace has
to match a GitHub account. Fully qualified collection names in every playbook
and role change (`tencentcloud.cloud.cvm_instance` becomes
`susunola.tencentcloud.cvm_instance`), the install command changes, the
tarball name changes, and any `ansible_collections.tencentcloud.cloud.*`
Python import changes. This is a mechanical find-and-replace, but it is
everywhere.

**`0.12.0` — five `*_info` modules were renamed, and their return keys moved
with them.** The old names dropped a duplicated product prefix:

| Before `0.12.0` | After | Return key | Ids option |
| --- | --- | --- | --- |
| `antiddos_d_do_s_block_record_info` | `antiddos_ddos_block_record_info` | `d_do_s_block_records` → `ddos_block_records` | — |
| `captcha_captcha_user_all_app_id_info` | `captcha_user_all_app_id_info` | `captcha_user_all_app_ids` → `user_all_app_ids` | — |
| `dcdb_dcdb_instance_info` | `dcdb_instance_info` | `dcdb_instances` → `instances` | `dcdb_instance_ids` → `instance_ids` |
| `sms_sms_sign_info` | `sms_sign_info` | `sms_signs` → `signs` | — |
| `vcube_vcube_resource_info` | `vcube_resource_info` | `vcube_resources` → `resources` | — |

A playbook that reads `result.ddos_block_records` keeps working; one that
still calls the old module name does not, because the old name is gone rather
than deprecated.

**`1.0.0` — the controller has to move first.** The collection now requires
ansible-core 2.19 or newer and Python 3.11 or newer on the controller.
ansible-core 2.16, 2.17 and 2.18 are end-of-life and no longer tested. Upgrade
ansible-core *before* upgrading the collection, or the install will succeed
and every module will fail to load.

### 10.3 Upgrading across several releases

Pick the highest row in 10.2 that you are still behind and do that work first;
the rest is additive. If you are coming from before `0.11.0`, the order is:

1. Rename every `tencentcloud.cloud.` reference to `susunola.tencentcloud.`
   (`0.11.0`).
2. Rename the five `*_info` modules and their return keys (`0.12.0`).
3. Move the controller to ansible-core 2.19+ and Python 3.11+ (`1.0.0`).
4. `ansible-galaxy collection install susunola.tencentcloud --force`.

`scripts/check_sdk_drift.py --check` tells you whether the SDK you have
installed still matches the version the generated `*_info` modules were
vouched for; run it after any upgrade that touches `requirements.txt`.
