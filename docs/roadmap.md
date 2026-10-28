# Roadmap

> **2026-10-28 — P1 surface reduction landed.** The expansion-era roadmap
> that used to live here tracked growth to a very large module surface. That
> direction was rejected by the Ansible community inclusion review and is
> abandoned: the pre-reduction entries referred to modules, roles and plugins
> that no longer exist in this collection. The full historical text remains
> available in the git history of this file.

The roadmap from here is the remediation plan in
[`REMEDIATION.md`](REMEDIATION.md), which is binding. It is restated here
only as a status view; the freeze file is the source of truth.

## Phase status

| Phase | Goal | Status |
| --- | --- | --- |
| P0 | Freeze file, core allowlist and freeze guard on `main` | Done |
| P1 | Module count ≤ 120, zero generated modules, `plugins/event_source/` removed | **Done (2026-10-28)** |
| P2 | No `validate-modules` / forbidden sanity ignores | In progress |
| P3 | Allowlisted modules have human-readable option docs | Planned |
| P4 | Every allowlisted write module has the 8-step integration target | Planned |
| P5 | Second maintainer named | Planned |
| P6 | 2.0.0 breaking changelog published | Planned |
| P7 | Inclusion request reopened with an evidence pack | Planned |

## What "next" means

- The only modules that may exist in this collection are the ones in
  [`core-allowlist.yml`](core-allowlist.yml); the only roles are
  `tc_vpc_foundation`, `tc_clb_http` and `tc_tke_cluster`. Additions are
  ratcheted: a new name must replace an existing one in the same pull
  request, with a written reason.
- Depth work happens **inside** the allowlist: readable option
  documentation (P3) and real-cloud integration coverage on the 8-step
  contract (P4, see [`testing-e2e.md`](testing-e2e.md) and
  [`integration-env.md`](integration-env.md)).
- Releases: 1.4.x is security and defect fixes only; the next feature
  release is 2.0.0, published once the phase exits in
  [`REMEDIATION.md`](REMEDIATION.md) are met.
