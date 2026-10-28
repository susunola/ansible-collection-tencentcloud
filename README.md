# Tencent Cloud Collection for Ansible

[![CI](https://github.com/susunola/ansible-collection-tencentcloud/actions/workflows/ci.yml/badge.svg)](https://github.com/susunola/ansible-collection-tencentcloud/actions/workflows/ci.yml)
[![Ansible Galaxy](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgalaxy.ansible.com%2Fapi%2Fv3%2Fcollections%2Fsusunola%2Ftencentcloud%2F&query=highest_version.version&label=Ansible%20Galaxy&color=blue)](https://galaxy.ansible.com/susunola/tencentcloud)

The `susunola.tencentcloud` collection provides Ansible modules and plugins
for managing [Tencent Cloud](https://www.tencentcloud.com/) resources through
the Tencent Cloud API 3.0.

It covers the core Tencent Cloud products:

- **Identity** — CAM users, groups, roles and policies
- **Compute** — CVM instances, images and key pairs; Lighthouse instances,
  firewall rules and key pairs
- **Network** — VPCs, subnets, security groups and rules, route tables,
  EIPs, NAT gateways; CLB load balancers, listeners, rules and target groups
- **Storage** — COS buckets, objects and bucket policies; CBS disks and
  snapshots
- **Containers** — TKE clusters, node pools and addons; TCR instances,
  namespaces and repositories
- **Databases** — TencentDB for MySQL (CDB) instances and accounts; Redis
  instances
- **Secrets** — KMS keys; SSM parameters and secrets
- **Auto Scaling** — scaling groups

The collection also ships inventory plugins for CVM, CLB, COS, security
groups and TKE, lookup plugins for SSM parameters and STS
caller identity, a `tat` connection plugin for running commands through the
TencentCloud Automation Tools agent, and three reusable roles:
`tc_vpc_foundation`, `tc_clb_http` and `tc_tke_cluster`.

## A note on the 1.x to 2.0 surface reduction

The 1.x releases of this collection shipped a very large, partially generated
module surface that did not meet the Ansible community package bar. Release
2.0.0 removes that surface: only a curated core set of hand-maintained
modules, listed in [`docs/core-allowlist.yml`](docs/core-allowlist.yml),
remains in this collection. The binding plan, the reasons behind it, and the
phase gates are documented in [`docs/REMEDIATION.md`](docs/REMEDIATION.md).

If a module you used in 1.x is gone, pin the last 1.x release
(`ansible-galaxy collection install susunola.tencentcloud:==1.4.0`) while you
migrate, and see [`docs/porting.md`](docs/porting.md) for migration guidance.

## Requirements

- ansible-core 2.19 or newer (the minimum declared in `meta/runtime.yml`)
- Python 3.11 or newer on the control node; use a Python version supported by
  your chosen ansible-core release
- [`tencentcloud-sdk-python`](https://pypi.org/project/tencentcloud-sdk-python/)
  3.1.174 or newer
- [`cos-python-sdk-v5`](https://pypi.org/project/cos-python-sdk-v5/) 1.9.44 or
  newer (only for the `cos_*` modules)
- `tencentcloud-sdk-python-tat` (only for the `tat` connection plugin)

```bash
python -m pip install -r requirements.txt
```

## Installation

Install from Ansible Galaxy:

```bash
ansible-galaxy collection install susunola.tencentcloud
```

Or build and install from source:

```bash
ansible-galaxy collection build
ansible-galaxy collection install susunola-tencentcloud-*.tar.gz
```

## Authentication

Use environment variables (recommended):

```bash
export TENCENTCLOUD_SECRET_ID='...'
export TENCENTCLOUD_SECRET_KEY='...'
export TENCENTCLOUD_REGION='ap-guangzhou'
```

Temporary credentials can also set `TENCENTCLOUD_TOKEN`. Never commit keys.

Credentials and region can also come from a TCCLI-style profile file at
`~/.tencentcloud/default.configure`; select a section with the `profile`
option (or `TENCENTCLOUD_PROFILE`, default `[default]`). Precedence is:
module parameter > environment variable > profile file.

To operate through a CAM role instead of long-lived keys, set `role_arn`
(or `TENCENTCLOUD_ROLE_ARN`); the modules exchange the base credentials for
temporary ones via STS AssumeRole before calling any other API.

## Quickstart

```yaml
- name: Stand up a small web footprint
  hosts: localhost
  gather_facts: false
  module_defaults:
    group/susunola.tencentcloud.all:
      region: ap-guangzhou
  tasks:
    - name: Ensure the VPC exists
      susunola.tencentcloud.vpc:
        state: present
        name: app-vpc
        cidr_block: 10.0.0.0/16
      register: vpc_result

    - name: Ensure a subnet exists in the VPC
      susunola.tencentcloud.subnet:
        state: present
        vpc_id: "{{ vpc_result.vpc.VpcId }}"
        name: web-subnet
        cidr_block: 10.0.1.0/24
        zone: ap-guangzhou-3
      register: subnet_result

    - name: Ensure a security group exists
      susunola.tencentcloud.security_group:
        state: present
        name: web-sg
        description: Web tier security group
      register: sg_result

    - name: Ensure a CVM instance is running in the subnet
      susunola.tencentcloud.cvm_instance:
        state: present
        instance_name: web-01
        image_id: img-xxxxxxxx
        instance_type: S5.MEDIUM2
        vpc_id: "{{ vpc_result.vpc.VpcId }}"
        subnet_id: "{{ subnet_result.subnet.SubnetId }}"
        security_group_ids:
          - "{{ sg_result.security_group.SecurityGroupId }}"
```

All modules accept the shared options (`region`, `endpoint`, `timeout`,
credentials and `role_arn`); `module_defaults` with the
`group/susunola.tencentcloud.all` action group applies them once per play.

Runnable end-to-end playbooks live in [`docs/examples/`](docs/examples/README.md).

## Documentation

The `ansible-doc` reference for every module and plugin is built from their
`DOCUMENTATION` blocks by [`docs/docsite/build.sh`](docs/docsite/README.md).
Further guides live under [`docs/`](docs/), including runnable
[examples](docs/examples/README.md), [porting guidance](docs/porting.md) for
users coming from Terraform or the raw SDKs, and the
[2.0.0 core allowlist](docs/core-allowlist.yml).

## Communication

This collection is discussed on the [Ansible forum](https://forum.ansible.com/),
the asynchronous home of the Ansible community.

- Questions and help: post in the [Get Help](https://forum.ansible.com/c/help/6)
  category and use the [`tencentcloud` tag](https://forum.ansible.com/tag/tencentcloud).
- Bug reports and feature requests: open an
  [issue](https://github.com/susunola/ansible-collection-tencentcloud/issues).

## Contributing

Contributions are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md)
before opening a pull request, and note that the remediation freeze in
[`docs/REMEDIATION.md`](docs/REMEDIATION.md) governs what may be added.

- Changelog: [`changelogs/CHANGELOG.rst`](changelogs/CHANGELOG.rst)
- Security issues: [`SECURITY.md`](SECURITY.md)
- Maintainers: [`MAINTAINERS.md`](MAINTAINERS.md)

## Code of Conduct

This collection follows the
[Ansible Community Code of Conduct](https://docs.ansible.com/ansible/latest/community/code_of_conduct.html).
See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for details.

## License

GNU General Public License v3.0 or later. See [`COPYING`](COPYING).
