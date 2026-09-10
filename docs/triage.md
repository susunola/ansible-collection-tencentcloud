# Triage and the first-response SLA

An issue nobody answers is worse than a slow answer: the reporter cannot tell
silence from rejection, and the queue grows while everyone assumes somebody
else is looking at it. This collection promises a **first response within 48
hours** on every issue and pull request.

## What counts as a first response

A first response is the first *human* signal that somebody has read the item:

- a comment by anyone other than the author;
- on a pull request, a submitted review — a reviewer who leaves only a review
  has still responded.

Bot comments do not count. Dependabot and the changelog bot answer within
seconds of an item opening, and counting them would make every number look
perfect while hiding a queue that nobody has read.

A response does not have to be a fix. "Reproduced, this needs the `tc_wait`
rework, targeting next week" answers the reporter as well as a merged PR
does: what it has to do is say what happens next and whether anything is
needed from them.

## Measuring it

`scripts/triage_sla.py` computes first-response times from the GitHub API:

```console
$ python scripts/triage_sla.py                     # open issues and PRs
$ python scripts/triage_sla.py --closed 30         # also the last 30 days
$ python scripts/triage_sla.py --json              # machine-readable
$ python scripts/triage_sla.py --check             # exit 1 on any BREACH
$ python scripts/triage_sla.py --exclude-author X  # skip X's own items
```

It prints one row per item with its age, its response time, and one of four
statuses:

| Status | Meaning | Fails `--check` |
| --- | --- | --- |
| `OK` | answered within the window | — |
| `LATE` | answered, but after the deadline | — |
| `WAITING` | unanswered, still inside the window | — |
| `BREACH` | unanswered and overdue | yes |

Only `BREACH` is an alarm, because only `BREACH` is actionable: a reporter is
still waiting and there is something to do about it. `LATE` is history — the
reporter has been answered — and counting it as a failure would leave the job
red on an open item nobody can clear except by closing it.

Authentication is optional — `GITHUB_TOKEN`, `GH_TOKEN`, or `gh auth token` —
but unauthenticated requests are rate-limited to 60 per hour, which a repo
with a few hundred issues will exhaust in one run.

`--exclude-author LOGIN` drops items that account opened. A maintainer's own
tracking issue can never receive a first response, by definition, and the
promise is to reporters rather than to oneself; counting it would be noise.
The flag is repeatable.

## Labels

| Label | Meaning | Who sets it |
| --- | --- | --- |
| `triage` | Nobody has looked at it yet. This is the queue. | by hand on open, removed at first response |
| `needs-info` | Blocked on the reporter: a reproduction, a version, a playbook. | maintainer |
| `module` | Affects one or more modules in the collection. | maintainer |
| `dependencies` | A dependency version bump, usually from dependabot. | by hand |
| `sla-breach` | First response is overdue. | maintainer when `--check` goes red, removed once answered |
| `good first issue` | Small, well-scoped, and safe to hand to a newcomer. | maintainer |

None of this is automated yet: labelling on open needs an `issues: opened`
workflow and the repository has none, so a new item is unlabelled until a
maintainer touches it. That is the gap this label set makes visible rather
than the state it claims to have fixed.

`triage` is the queue: an item either carries it or it does not, and the
first response is what removes it. The rest describe what the item *is*, so a
maintainer can read the shape of the backlog off the label list without
opening every title.

`sla-breach` exists so a breach is visible on the issues page and not only in
a script's output. Remove it once the item is answered; do not leave it as a
permanent mark against an old issue.

## Security reports

Reports that arrive through the private advisory flow in
[`SECURITY.md`](../SECURITY.md) are not part of the public triage queue and
are not measured here. They are handled privately and get a disclosure
timeline instead of a first-response SLA.

## When nobody can answer

If 48 hours is not achievable — a holiday, a release week — say so on the
issue rather than letting it slide. A comment that says "travelling, will
look on Monday" is a first response, and it costs less than the silence it
replaces.
