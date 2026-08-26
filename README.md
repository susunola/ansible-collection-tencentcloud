# Tencent Cloud Ansible Collection

[![CI](https://github.com/susunola/ansible-collection-tencentcloud/actions/workflows/ci.yml/badge.svg)](https://github.com/susunola/ansible-collection-tencentcloud/actions/workflows/ci.yml)

`tencentcloud.cloud` provides Ansible modules and plugins for managing Tencent
Cloud resources. It is developed as a community collection targeting inclusion
in the `ansible-collections` GitHub organization.

## Included modules

Resource modules (idempotent, `state: present|absent`, check mode and diff):

| Module | Purpose |
| --- | --- |
| `vpc` | Manage VPCs (CIDR, DNS servers, domain name, tags) |
| `subnet` | Manage subnets inside a VPC |
| `route_table` | Manage route tables and their user routes |
| `security_group` | Create, update and delete security groups |
| `security_group_rule` | Reconcile the ingress/egress rules of a security group |
| `eip` | Allocate, release and bind elastic IP addresses |
| `key_pair` | Create or import SSH key pairs |
| `cvm_instance` | Manage CVM instance lifecycle (present/absent/running/stopped) |

Read-only `_info` modules (return `changed=false`):

| Module | Purpose |
| --- | --- |
| `cvm_instance_info` | Query CVM instances with IDs or API filters |
| `vpc_info` | Query VPCs with IDs or API filters |
| `subnet_info` | Query subnets with IDs or API filters |
| `route_table_info` | Query route tables with IDs or API filters |
| `security_group_info` | Query security groups with IDs or API filters |
| `eip_info` | Query elastic IP addresses with IDs, IPs or API filters |
| `key_pair_info` | Query SSH key pairs with IDs or API filters |
| `clb_load_balancer_info` | Query CLB load balancers with IDs or API filters |
| `cdb_instance_info` | Query TencentDB for MySQL instances with IDs |
| `tke_cluster_info` | Query TKE clusters with IDs or API filters |
| `cbs_disk_info` | Query CBS cloud disks with IDs or API filters |
| `redis_instance_info` | Query TencentDB for Redis instances with IDs |
| `mongodb_instance_info` | Query TencentDB for MongoDB instances with IDs |
| `kms_key_info` | Query KMS keys (list all, or describe by key IDs) |
| `dnspod_record_info` | Query DNSPod records for a domain |

The modules from `clb_load_balancer_info` down are generated from SDK
metadata by `scripts/generate_info_modules.py` (run with `--check` to
verify they are up to date).

## Included plugins

| Plugin | Type | Purpose |
| --- | --- | --- |
| `tencentcloud_cvm` | inventory | Dynamic inventory of CVM instances with constructed groups and caching |

## Requirements

- ansible-core 2.16 or newer
- Python 3.10 or newer
- `tencentcloud-sdk-python` 3.0.1000 or newer
- `tencentcloud-sdk-python-tag` 3.0.1000 or newer (only for tag reconciliation)

Once 0.4.0 is published on Ansible Galaxy, install with:

```bash
ansible-galaxy collection install tencentcloud.cloud
```

Until then, install from source:

```bash
python -m pip install -r requirements.txt
ansible-galaxy collection build
ansible-galaxy collection install tencentcloud-cloud-*.tar.gz
```

## Authentication

Use environment variables (recommended):

```bash
export TENCENTCLOUD_SECRET_ID='...'
export TENCENTCLOUD_SECRET_KEY='...'
export TENCENTCLOUD_REGION='ap-guangzhou'
```

Temporary credentials can also set `TENCENTCLOUD_TOKEN`. Never commit keys.
Use `endpoint` for a private API endpoint or test double, and `timeout` to
control the SDK request timeout.

To operate through a CAM role instead of long-lived keys, set `role_arn`
(or `TENCENTCLOUD_ROLE_ARN`); the modules exchange the base credentials for
temporary ones via STS AssumeRole before calling any other API:

```yaml
- tencentcloud.cloud.vpc:
    region: ap-guangzhou
    role_arn: qcs::cam::uin/1000000000:roleName/AnsibleDeploy
    state: present
    name: app-vpc
    cidr_block: 10.0.0.0/16
```

The `tencentcloud_cvm` inventory plugin reads the same environment variables:

```yaml
# inventory.tencentcloud_cvm.yml
plugin: tencentcloud.cloud.tencentcloud_cvm
regions:
  - ap-guangzhou
keyed_groups:
  - key: Placement.Zone
    prefix: zone
```

## Example

```yaml
- hosts: localhost
  gather_facts: false
  module_defaults:
    group/tencentcloud.cloud.all:
      region: ap-guangzhou
  tasks:
    - name: Ensure a security group exists
      tencentcloud.cloud.security_group:
        state: present
        name: web-sg
        description: Web tier security group
        tags:
          env: prod
```

All modules accept the shared options (`region`, `endpoint`, `timeout`,
credentials and `role_arn`); `module_defaults` with the
`group/tencentcloud.cloud.all` action group applies them once per play.

See [`docs/roadmap.md`](docs/roadmap.md) for the suggested implementation order.
Contributor conventions are in [`docs/development.md`](docs/development.md).

## Development

```bash
python -m pip install -r requirements-dev.txt
ansible-test sanity --python 3.13
ansible-test units --python 3.13
ansible-galaxy collection build
```

Integration tests require Tencent Cloud credentials and run only when
`TENCENTCLOUD_SECRET_ID` / `TENCENTCLOUD_SECRET_KEY` are set (see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Code of Conduct

This collection follows the [Ansible Community Code of Conduct](https://docs.ansible.com/ansible/latest/community/code_of_conduct.html).
See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for details.

## License

GNU General Public License v3.0 or later. See [`COPYING`](COPYING).
