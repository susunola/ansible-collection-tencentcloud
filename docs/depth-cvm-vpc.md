# Depth plan — CVM & VPC/networking (superseded)

> **2026-10-28 — superseded by the remediation freeze.** This page listed
> candidate CVM and VPC/networking modules to scaffold with the `_info`
> generator. Both the generator and the expansion direction are gone: the P1
> surface reduction removed every module outside
> [`core-allowlist.yml`](core-allowlist.yml), and
> [`REMEDIATION.md`](REMEDIATION.md) forbids growing the surface again except
> through the allowlist ratchet. The original candidate tables remain in the
> git history of this file.

Depth work on the retained CVM and VPC/networking modules is now governed by
the remediation phases: human-readable option documentation (P3) and the
8-step real-cloud integration contract (P4). Proposals for additional modules
in these families must amend `docs/core-allowlist.yml` with a written
justification, dropping another name or lowering no other ceiling, per the
freeze.
