# End-to-end examples

Two directories hold runnable playbooks:

| Directory | What it is | Documented in |
| --- | --- | --- |
| `docs/examples/` | a numbered chain: one environment built up stage by stage | this page |
| `playbooks/` | standalone scenarios (query, static site, kubeconfig, three-tier) | [`../scenarios.md`](../scenarios.md) |

Moving a Terraform config onto this collection? [`../porting.md`](../porting.md)
maps each provider resource to a module FQCN and explains the state, region and
check-mode differences.

Everything targets `localhost` — the modules call the Tencent Cloud APIs
from the controller — and takes credentials from the `TENCENTCLOUD_*`
environment variables (or `~/.tencentcloud/default.configure`). Nothing
here is exercised by CI: running any of it creates real, billable
resources.

## The golden path

`01` and `02` are the two stages that most users need, split apart so each
can be read and re-run on its own. `06` is the same two stages in one file,
with the ids handed over automatically instead of by hand.

| File | Stage | Creates | Teardown |
| --- | --- | --- | --- |
| `01_network_foundation.yml` | network | VPC, 3 subnets across 2 AZs, route tables, NAT gateways, 2 security groups with exact-set rules | `tc_vpc_foundation_state: absent` |
| `02_web_stack.yml` | application | CVM pool, MySQL (CDB), Redis, public CLB with an HTTP listener and auto-registered backends | `tc_web_stack_state: absent` |
| `03_tke_cluster.yml` | platform | managed TKE cluster, one autoscaling node pool, addons | `tc_tke_cluster_state: absent` |
| `04_disaster_recovery.yml` | resilience | golden image of a source instance, cross-region COS bucket replication, standby CLB in the DR region | `tc_dr_state: absent` |
| `05_module_mix.yml` | raw modules | security group, EIP, an exact-count CVM pool, then reads it back and tears it down | `ansible-playbook docs/examples/05_module_mix.yml --tags teardown` |
| `06_full_chain.yml` | **the whole path** | `01` + `02` + a read-back stage in one invocation | `ansible-playbook docs/examples/06_full_chain.yml --tags teardown` |

`03` and `04` are branches off the same foundation, not further stages:
both take the `vpc_id` / `subnet_id` that `01` produced.

### Run it

```bash
export TENCENTCLOUD_SECRET_ID=...
export TENCENTCLOUD_SECRET_KEY=...

# The one-file chain. image_id is account- and region-specific.
ansible-playbook docs/examples/06_full_chain.yml \
  -e image_id=img-xxxxxxxx \
  -e web_password='ReplaceWith-AStrongPassword1'

# ... or the two stages, copying the ids 01 prints into 02:
ansible-playbook docs/examples/01_network_foundation.yml
ansible-playbook docs/examples/02_web_stack.yml \
  -e vpc_id=vpc-xxxxxxxx -e subnet_id=subnet-xxxxxxxx -e sg_id=sg-xxxxxxxx
```

Each role publishes its result as a fact, which is what makes the chain
work without copy-paste: `tc_vpc_foundation_result` (with `vpc_id`,
`subnets`, `security_groups`, `route_tables`, `nat_gateways`),
`tc_web_stack_result`, `tc_tke_cluster_result` and
`tc_disaster_recovery_result`. Stage 2 of `06_full_chain.yml` reads them
directly:

```yaml
tc_web_stack_vpc_id: "{{ tc_vpc_foundation_result.vpc_id }}"
tc_web_stack_subnet_id: "{{ tc_vpc_foundation_result.subnets[0].subnet.SubnetId }}"
```

### Tear it down

Every example is its own teardown runbook: flip the role's `*_state` to
`absent`, or run the tagged teardown play where one exists. Order matters —
the resources inside a VPC must go before the VPC, which is why
`06_full_chain.yml`'s teardown play lists the web stack role first and the
network role second.

## Keeping the examples honest

`python scripts/check_examples.py --check` runs in CI and fails when an
example references something that no longer exists. It is a static check —
it cannot prove a playbook works — but it catches the failures a copied
example hits first:

| Check | Catches |
| --- | --- |
| `yaml` | a file that no longer parses |
| `modules` | a `susunola.tencentcloud.*` action whose module was renamed or removed |
| `options` | an option a module no longer declares (doc fragments included, so `region` is understood) |
| `roles` | a role that was renamed or dropped |
| `role-vars` | a `tc_*` variable a role does not declare in `defaults/main.yml` |
| `vars` | a variable a play reads but never declares, registers, documents as `-e name=` or guards with `is defined` |

Run it locally before touching an example:

```bash
python scripts/check_examples.py --check          # fail on any problem
python scripts/check_examples.py                  # what each example uses
python scripts/check_examples.py --json           # same, for tooling
```

Variables a role publishes (`set_fact` and `register`) count as defined, so
a chained playbook that reads `tc_vpc_foundation_result` in a later play
does not trip the `vars` check.

## Adding an example

1. Drop the file in `docs/examples/` (numbered, if it is a stage) or
   `playbooks/` (if it stands alone). The check picks it up automatically.
2. Declare every account-specific value in `vars:` with an `xxxx`-style
   placeholder, or read it as an extra var and say so in the header
   comment — an undeclared variable fails the `vars` check.
3. Give it a teardown path and document it in the header comment.
4. Add a row to the table above.
