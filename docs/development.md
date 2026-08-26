# Development guide

## Module conventions

- Read-only modules end in `_info`, return `changed=false`, and support check mode.
- Resource modules accept `state: present|absent` and must be idempotent.
- Credentials, SDK profiles, serialization, and error handling belong in
  `plugins/module_utils/tencentcloud.py`.
- API responses use the Tencent Cloud SDK field names. Do not silently rename
  fields until the collection has a documented normalization policy.
- ID-list parameters and API filters are mutually exclusive when the API says so.
- Every module needs request-builder unit tests and an integration target before
  being declared stable.

## Local collection layout

`ansible-test` requires the checkout to appear below
`ansible_collections/tencentcloud/cloud`. Clone it into that layout or create a
temporary copy before running tests.

## Adding a service

1. Verify request types and limits in the official Tencent Cloud API docs.
2. Add the minimum SDK product dependency if dependencies are split later.
3. Implement and test the `_info` module first.
4. Add state-changing modules with check-mode diff calculation.
5. Add integration tests using credentials from environment variables.
6. Add a changelog fragment under `changelogs/fragments`.
