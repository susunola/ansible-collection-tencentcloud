# Tencent Cloud Ansible Collection

[![CI](https://github.com/susunola/ansible-collection-tencentcloud/actions/workflows/ci.yml/badge.svg)](https://github.com/susunola/ansible-collection-tencentcloud/actions/workflows/ci.yml)

`tencentcloud.cloud` provides Ansible modules and plugins for managing Tencent
Cloud resources. It is developed as a community collection targeting inclusion
in the `ansible-collections` GitHub organization.

## Included modules

| Module | Purpose |
| --- | --- |
| `security_group` | Create, update and delete security groups (idempotent, supports check mode and diff) |
| `cvm_instance_info` | Query CVM instances with IDs or API filters |
| `vpc_info` | Query VPCs with IDs or API filters |
| `security_group_info` | Query security groups with IDs or API filters |

## Requirements

- ansible-core 2.16 or newer
- Python 3.10 or newer
- `tencentcloud-sdk-python` 3.0.1000 or newer
- `tencentcloud-sdk-python-tag` 3.0.1000 or newer (only for tag reconciliation)

Install from source:

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

## Example

```yaml
- hosts: localhost
  gather_facts: false
  tasks:
    - name: Ensure a security group exists
      tencentcloud.cloud.security_group:
        region: ap-guangzhou
        state: present
        name: web-sg
        description: Web tier security group
        tags:
          env: prod
```

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
