# Releasing

A release is triggered by pushing a `v*` tag. `.github/workflows/release.yml`
then lints the changelog fragments, runs sanity and unit tests, folds the
fragments into `changelogs/changelog.yaml` and `CHANGELOG.rst`, commits that
back to `main`, builds the tarball, creates the GitHub release and — if
`GALAXY_API_KEY` is set — publishes to Ansible Galaxy.

The awkward part of that design is that the tag push is both the trigger and
the point of no return. Nothing before it tells you whether the release is
actually ready, and by the time the workflow fails you may already have a
GitHub release object and a published artefact. `scripts/release_check.py`
exists to move that discovery earlier.

## Before you tag

```console
$ python scripts/release_check.py
release guard: susunola.tencentcloud 1.2.0
  PASS  version-format  galaxy.yml version 1.2.0
  PASS  version-bumped  1.2.0 is ahead of the newest tag v1.1.0
  PASS  tag-free        tag v1.2.0 is free (and is not on origin)
  SKIP  tag-matches     no --tag given
  PASS  fragments       176 changelog fragment(s) waiting to be folded
  PASS  no-duplicate    1.2.0 has no entry in changelog.yaml
  PASS  clean-worktree  working tree is clean
  SKIP  fragment-lint   not run; pass --lint to include it

release check OK: 1.2.0 is ready to tag
```

It exits non-zero on any `FAIL`. The checks:

| Check | Fails when | Why it matters |
| --- | --- | --- |
| `version-format` | `galaxy.yml` version is not `X.Y.Z` | `ansible-galaxy` rejects anything else, and the workflow only finds out after the tag exists |
| `version-bumped` | `galaxy.yml` is not strictly ahead of the newest tag | Re-tagging a shipped version; Galaxy refuses the upload and the tag is already pushed |
| `tag-free` | the tag exists locally or on `origin` | GitHub silently does nothing when you push an existing tag — the workflow runs against the old commit |
| `tag-matches` | `--tag TAG` disagrees with `galaxy.yml` | Same assertion the workflow makes, available before you push |
| `fragments` | `changelogs/fragments/` is empty | `antsibull-changelog release` would fold a release with nothing in it |
| `no-duplicate` | `changelogs/changelog.yaml` already has this version | Folding again rewrites a shipped release entry |
| `clean-worktree` | there are uncommitted changes | The workflow commits the folded changelog to `main`; a dirty tree makes that commit unpredictable |
| `fragment-lint` | `antsibull-changelog lint` fails | Bad fragment YAML. Opt-in (`--lint`) because it takes minutes; `release.yml` runs it separately anyway |

`SKIP` never fails the guard. A check is skipped when it cannot be answered
here rather than when it passes by accident: no `--tag` given, no tags or
remote to compare against, `antsibull-changelog` not installed, or the check
was excluded with `--ignore`.

Two notes on the honest edges:

- `tag-free` needs to reach `origin` to be meaningful. Offline it reports
  `SKIP` with "remote tags unreachable" — that is not a pass, and it is worth
  re-running from a network you trust before you push.
- `version-bumped` compares only against tags, so it cannot tell you that the
  version jump is the *right* size. `1.1.0` to `2.0.0` is a call you make;
  see `docs/deprecation-policy.md` for what warrants a major bump.

## Dry run

```console
$ python scripts/release_check.py --dry-run
```

Once the guard passes, this builds the collection into a temporary directory
and proves the artefact works: it fails if the tarball is over 16 MiB, reads
`MANIFEST.json` and asserts the version matches `galaxy.yml`, checks that
`.github/`, `tests/`, `.git/` and the generated docsite output did not leak
past `build_ignore`, then installs the tarball into a throwaway collections
root and runs `ansible-doc -l` against it.

Neither the size ceiling nor the install step is ceremony.
`ansible-galaxy` reads `build_ignore` but not `.gitignore`, so two classes
of junk used to reach the tarball on any machine that was not a clean
checkout: `docs/docsite/build` (generated, gitignored, 252 MB — 36.6 MB and
nine minutes instead of 1.9 MB and three) and the tool caches
(`.pytest_cache`, `.ruff_cache`, coverage output), which are rewritten while
tooling runs, so a tarball containing them can disagree with its own
`FILES.json` checksums and be rejected on install. CI never saw either
problem, because CI builds from a clean tree. `--max-size` raises the
ceiling if the collection genuinely grows past it.

It tags nothing, pushes nothing, publishes nothing and deletes the temporary
directory on the way out. `--no-smoke` stops after inspecting the tarball if
you only want the build half. With `--dry-run` it also prints the plan —
what pushing the tag would do, step by step — so you can read the whole
release before committing to it.

The dry run is skipped when the guard fails: there is nothing to build until
the version is right.

## Cutting the release

1. `python scripts/release_check.py` — fix whatever it flags. Usually that
   means bumping `galaxy.yml`.
2. Commit the bump on its own, apart from feature work. The workflow commits
   the folded changelog to `main` immediately after, and a release commit
   mixed into a feature branch is awkward to unwind.
3. `python scripts/release_check.py --dry-run` — confirm the artefact builds,
   installs and documents itself.
4. `python scripts/release_check.py --lint` if you have a few minutes and want
   the fragments checked before the workflow does it.
5. `git tag vX.Y.Z && git push origin vX.Y.Z`.
6. Watch the run: `gh run watch`. The `test` job publishes the GitHub release
   only after sanity and unit tests pass.

`GALAXY_API_KEY` is not set for forks, so a fork build skips the publish step
with a warning rather than failing. That is intentional: the tag already
exists by then, and failing the whole release over a missing secret would
leave you with a tagged commit and no release notes.

## When it goes wrong

**Wrong version tagged.** Delete the tag (`git tag -d vX.Y.Z && git push
origin :refs/tags/vX.Y.Z`), bump `galaxy.yml`, tag again. If the workflow
already folded the changelog, the `chore(release)` commit on `main` has to be
reverted first — `no-duplicate` will keep failing until it is.

**Tag pushed, workflow failed.** Fix `main`, delete and re-push the tag. The
workflow is keyed on the tag, not on a release marker, so it simply runs
again.

**Galaxy rejected the upload.** Galaxy versions are immutable: the fix is
always a new version, never a re-upload. Bump the patch number and start
again.

## What is not automated

Deciding *when* to release, and choosing the version number. The guard tells
you whether the version you picked is publishable; it has no opinion on
whether 176 pending fragments should ship as one `1.2.0` or be split. There
is no scheduled release job and no auto-bump — releases are still a person
pushing a tag.
