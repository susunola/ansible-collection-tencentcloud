# Tencent Cloud Ansible Collection

`tencentcloud.cloud` provides Ansible modules and plugins for Tencent Cloud. The
initial release contains a read-only CVM instance information module and a
shared SDK client foundation for future resource modules.

## Included modules

| Module | Purpose |
| --- | --- |
| `cvm_instance_info` | Query CVM instances with IDs or API filters |
| `vpc_info` | Query VPCs with IDs or API filters |
| `security_group_info` | Query security groups with IDs or API filters |

## Requirements

- ansible-core 2.16 or newer
- Python 3.10 or newer
- `tencentcloud-sdk-python` 3.0.1000 or newer

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
    - name: Get running instances
      tencentcloud.cloud.cvm_instance_info:
        region: ap-guangzhou
        filters:
          instance-state: [RUNNING]
      register: result
```

See [`docs/roadmap.md`](docs/roadmap.md) for the suggested implementation order.
Contributor conventions are in [`docs/development.md`](docs/development.md).

## Development

```bash
python -m pip install -r requirements-dev.txt
ansible-test sanity --docker default
ansible-test units --docker default
ansible-galaxy collection build
```

## License

Apache License 2.0. This is a community scaffold and is not an official Tencent
Cloud product unless adopted by Tencent Cloud.
