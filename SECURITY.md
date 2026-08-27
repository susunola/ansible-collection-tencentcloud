# Security Policy

## Supported versions

Security fixes are applied to the latest minor release line of the
`susunola.tencentcloud` collection.

| Version | Supported |
|---|---|
| 0.4.x   | Yes       |
| < 0.4.0 | No        |

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub
issues.**

Report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/susunola/ansible-collection-tencentcloud/security/advisories/new)
for this repository. This gives the maintainers a private channel to
confirm, reproduce, and fix the issue before any public disclosure.

Please include:

- The collection version and `ansible-core` version you are running.
- The affected module or plugin and a minimal reproducer (playbook or
  steps) where possible.
- The impact you believe the vulnerability has.

You can expect an acknowledgement within a few days. If the report is
accepted, a fix is developed in a private fork, released as a security
fix release, and credited to you (unless you prefer to stay anonymous).

## Credential handling

Modules in this collection authenticate to Tencent Cloud through the
`TENCENTCLOUD_SECRET_ID` / `TENCENTCLOUD_SECRET_KEY` environment variables
(or the corresponding module parameters). When contributing or reporting
issues:

- **Never commit real credentials** (API keys, secret keys, session
  tokens) to the repository, to issues, or to pull requests.
- Never paste real credentials into issue templates, logs, or playbook
  output attached to a report; redact them first.
- Do not add logging that prints credentials or request signatures.

If you believe credentials have been committed or leaked, report it
immediately through a private security advisory as described above so the
maintainers can coordinate revocation and history cleanup.
