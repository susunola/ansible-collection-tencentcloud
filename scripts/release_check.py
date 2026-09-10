#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pre-release guard and dry run for susunola.tencentcloud.

Releasing this collection means pushing a ``v*`` tag: ``.github/workflows/
release.yml`` then folds the changelog fragments, creates the GitHub release
and publishes to Galaxy. That trigger is also the problem -- the only way to
find out a release is broken is to push the tag, and by the time the job
fails a GitHub release object already exists and Galaxy may already have a
copy. Nothing before the tag push tells you whether the release is ready.

This script answers that question before the tag exists. It checks the
things that make a release publishable and refuses otherwise:

  version-format   galaxy.yml version is X.Y.Z (ansible-galaxy rejects the rest)
  version-bumped   galaxy.yml is strictly ahead of the newest released tag
  tag-free         the tag this release would push does not already exist
  tag-matches      --tag TAG agrees with galaxy.yml (what the workflow asserts)
  fragments        there is at least one changelog fragment to fold
  no-duplicate     changelogs/changelog.yaml has no entry for this version yet
  clean-worktree   no uncommitted changes

``--lint`` adds one more:

  fragment-lint    antsibull-changelog lint is clean

That one is opt-in because it is slow -- about two minutes for the ~180
fragments currently queued -- and because ``release.yml`` already runs it as
its own step, so omitting it here does not lower the bar on release day. A
guard you run before deciding whether to tag has to answer in under a second.

``--dry-run`` goes further and proves the artefact works: it builds the
tarball into a temporary directory, checks MANIFEST.json against galaxy.yml,
fails if the tarball is implausibly large, asserts nothing from
``build_ignore`` leaked in, installs the tarball into a throwaway collections
root and lists its documentation. It tags nothing, pushes nothing, publishes
nothing and leaves no files behind.

Usage:

    python scripts/release_check.py                  # guard, exit 1 on failure
    python scripts/release_check.py --tag v1.2.0     # also assert the tag
    python scripts/release_check.py --lint           # also lint the fragments
    python scripts/release_check.py --ignore clean-worktree
    python scripts/release_check.py --dry-run        # guard, then build + smoke
    python scripts/release_check.py --dry-run --no-smoke
    python scripts/release_check.py --json           # machine-readable

See docs/release.md for the full runbook.
"""

from __future__ import absolute_import, division, print_function

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
GALAXY_PATH = REPO_ROOT / "galaxy.yml"
FRAGMENTS_DIR = REPO_ROOT / "changelogs" / "fragments"
CHANGELOG_PATH = REPO_ROOT / "changelogs" / "changelog.yaml"

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

# Paths that must never appear in a published tarball. galaxy.yml lists them
# in build_ignore; asserting it here means an edit that drops them from the
# ignore list fails the dry run instead of shipping .github, the integration
# test suite or 250 MB of generated Sphinx HTML to Galaxy.
FORBIDDEN_PREFIXES = (
    ".github/",
    "tests/",
    ".git/",
    "docs/docsite/build/",
    "docs/docsite/rst/collections/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".ansible/",
    ".coverage",
    "coverage.xml",
    "coverage-html/",
)

# Ceiling for the built tarball, in MiB. A correct build is about 2 MiB; one
# that packaged docs/docsite/build was 35 MiB, hence a ceiling well below that
# but with room to grow. This is a catch-all for "something large and
# generated stopped being excluded" -- the specific known cases are named in
# FORBIDDEN_PREFIXES above.
DEFAULT_MAX_SIZE_MIB = 16

CHECK_NAMES = [
    "version-format",
    "version-bumped",
    "tag-free",
    "tag-matches",
    "fragments",
    "no-duplicate",
    "clean-worktree",
    "fragment-lint",
]


def run(cmd, cwd=REPO_ROOT, env=None, timeout=300):
    """Run a command, returning ``(returncode, stdout, stderr)``.

    ``returncode`` is ``None`` when the command could not be run at all
    (missing binary, timeout); callers turn that into a SKIP rather than a
    failure, because a missing local tool is not a broken release.
    """
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout)
    except FileNotFoundError:
        return None, "", "%s is not installed or not on PATH" % cmd[0]
    except subprocess.TimeoutExpired:
        return None, "", "%s timed out after %ss" % (cmd[0], timeout)
    decode = lambda blob: blob.decode("utf-8", "replace")
    return proc.returncode, decode(proc.stdout), decode(proc.stderr)


def version_tuple(value):
    """Return ``(major, minor, patch)`` for X.Y.Z, else None."""
    match = SEMVER_RE.match((value or "").strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def local_tags():
    rc, out, _ = run(["git", "tag", "--list"])
    if rc != 0:
        return set()
    return set(line.strip() for line in out.splitlines() if line.strip())


def remote_tags():
    """Tags on origin, or None when the remote cannot be reached.

    A release pushed to a tag that already exists on the remote is the worst
    failure mode here -- GitHub silently moves nothing and the workflow runs
    against the old commit. But this is a network call that fails on a plane
    or in a sandbox, and offline is not the same as unsafe, so an unreachable
    remote downgrades the check to SKIP rather than failing the guard.
    """
    rc, out, _ = run(["git", "ls-remote", "--tags", "origin"], timeout=60)
    if rc != 0:
        return None
    return set(line.split("\t")[-1].replace("refs/tags/", "").rstrip("^{}")
               for line in out.splitlines() if "\t" in line)


def build_state(tag=None):
    galaxy = yaml.safe_load(GALAXY_PATH.read_text(encoding="utf-8")) or {}
    return {
        "namespace": galaxy.get("namespace", ""),
        "name": galaxy.get("name", ""),
        "version": str(galaxy.get("version", "")).strip(),
        "tag": tag,
        "local_tags": local_tags(),
        "remote_tags": remote_tags(),
    }


def check_version_format(state):
    version = state["version"]
    if version_tuple(version):
        return PASS, "galaxy.yml version %s" % version
    return FAIL, ("galaxy.yml version %r is not X.Y.Z; ansible-galaxy rejects "
                  "anything else" % version)


def check_version_bumped(state):
    version = state["version"]
    current = version_tuple(version)
    if current is None:
        return SKIP, "version is not X.Y.Z, nothing to compare"
    released = [parsed for parsed in
                (version_tuple(tag.lstrip("v")) for tag in state["local_tags"])
                if parsed]
    if not released:
        return PASS, "no tags yet, %s would be the first release" % version
    latest = max(released)
    latest_text = ".".join(str(part) for part in latest)
    if current > latest:
        return PASS, "%s is ahead of the newest tag v%s" % (version, latest_text)
    if current == latest:
        return FAIL, ("galaxy.yml still says %s and tag v%s already released "
                      "it; bump the version before tagging" % (version, latest_text))
    return FAIL, ("galaxy.yml version %s is behind the newest tag v%s"
                  % (version, latest_text))


def check_tag_free(state):
    tag = "v" + state["version"]
    problems = []
    if tag in state["local_tags"]:
        problems.append("tag %s already exists locally" % tag)
    remote = state["remote_tags"]
    if remote is None:
        note = " (remote tags unreachable, origin not checked)"
    elif tag in remote:
        problems.append("tag %s already exists on origin" % tag)
    else:
        note = " (and is not on origin)"
    if problems:
        return FAIL, "; ".join(problems)
    return (PASS if remote is not None else SKIP), "tag %s is free%s" % (tag, note)


def check_tag_matches(state):
    tag = state["tag"]
    if not tag:
        return SKIP, "no --tag given"
    expected = tag[1:] if tag.startswith("v") else tag
    if expected == state["version"]:
        return PASS, "tag %s matches galaxy.yml %s" % (tag, state["version"])
    return FAIL, ("tag %s does not match galaxy.yml version %s"
                  % (tag, state["version"]))


def check_fragments(state):
    if not FRAGMENTS_DIR.is_dir():
        return FAIL, "changelogs/fragments/ does not exist"
    files = sorted(path for path in FRAGMENTS_DIR.iterdir()
                   if path.suffix in (".yml", ".yaml"))
    if not files:
        return FAIL, ("no changelog fragments in changelogs/fragments/; "
                      "`antsibull-changelog release` would fold an empty release")
    return PASS, "%d changelog fragment(s) waiting to be folded" % len(files)


def check_no_duplicate(state):
    if not CHANGELOG_PATH.is_file():
        return SKIP, "changelogs/changelog.yaml not found"
    data = yaml.safe_load(CHANGELOG_PATH.read_text(encoding="utf-8")) or {}
    releases = data.get("releases") or {}
    version = state["version"]
    if version in releases:
        released = (releases[version] or {}).get("release_date") or "already"
        return FAIL, ("changelogs/changelog.yaml already holds a %s entry "
                      "(%s); folding it again would rewrite a shipped release"
                      % (version, released))
    return PASS, "%s has no entry in changelog.yaml" % version


def check_clean_worktree(state):
    rc, out, err = run(["git", "status", "--porcelain"])
    if rc is None:
        return SKIP, err
    changed = [line for line in out.splitlines() if line.strip()]
    if changed:
        preview = ", ".join(line.strip() for line in changed[:3])
        if len(changed) > 3:
            preview += ", ..."
        return FAIL, ("%d uncommitted change(s) (%s); release from a clean tree"
                      % (len(changed), preview))
    return PASS, "working tree is clean"


def check_fragment_lint(state):
    rc, out, err = run(["antsibull-changelog", "lint"])
    if rc is None:
        return SKIP, err
    if rc == 0:
        return PASS, "antsibull-changelog lint is clean"
    detail = (out + err).strip().splitlines()
    last = detail[-1] if detail else "no output"
    return FAIL, "antsibull-changelog lint failed: %s" % last


CHECKS = [
    (check_version_format, "version-format"),
    (check_version_bumped, "version-bumped"),
    (check_tag_free, "tag-free"),
    (check_tag_matches, "tag-matches"),
    (check_fragments, "fragments"),
    (check_no_duplicate, "no-duplicate"),
    (check_clean_worktree, "clean-worktree"),
    (check_fragment_lint, "fragment-lint"),
]

# Checks that only run when explicitly asked for, because they cost minutes
# rather than milliseconds. See the module docstring.
OPTIONAL_CHECKS = ("fragment-lint",)


def run_checks(state, ignored, lint=False):
    results = []
    for func, name in CHECKS:
        if name in ignored:
            results.append((name, SKIP, "ignored via --ignore"))
            continue
        if name in OPTIONAL_CHECKS and not lint:
            results.append((name, SKIP, "not run; pass --lint to include it"))
            continue
        status, detail = func(state)
        results.append((name, status, detail))
    return results


def plan(state, out):
    """Print what pushing the tag would do, without doing any of it."""
    version = state["version"]
    collection = "%s.%s" % (state["namespace"], state["name"])
    fragments = len(sorted(FRAGMENTS_DIR.glob("*.y*ml"))) if FRAGMENTS_DIR.is_dir() else 0
    out.write("\nWould release %s %s:\n" % (collection, version))
    out.write("  1. push tag v%s            -> .github/workflows/release.yml\n" % version)
    out.write("  2. fold %d fragment(s)     -> changelogs/changelog.yaml, CHANGELOG.rst\n" % fragments)
    out.write("  3. build and upload        -> susunola-tencentcloud-%s.tar.gz\n" % version)
    out.write("  4. create GitHub release   -> gh release create v%s --generate-notes\n" % version)
    out.write("  5. publish to Galaxy       -> only if GALAXY_API_KEY is set\n")
    out.write("\nNothing above happened. To proceed: bump galaxy.yml, commit, "
              "then\n    git tag v%s && git push origin v%s\n" % (version, version))


def dry_run(state, out, smoke=True, max_size_mib=DEFAULT_MAX_SIZE_MIB):
    """Build the artefact and inspect it. Returns a list of (name, status, detail)."""
    results = []
    version = state["version"]
    workdir = Path(tempfile.mkdtemp(prefix="tencentcloud-release-"))
    try:
        rc, out_b, err_b = run(["ansible-galaxy", "collection", "build",
                                "--output-path", str(workdir), "--force"],
                               timeout=1800)
        if rc is None:
            return [(("dry-run-build"), SKIP, err_b)]
        if rc != 0:
            detail = (out_b + err_b).strip().splitlines()
            return [("dry-run-build", FAIL,
                     "ansible-galaxy collection build failed: %s"
                     % (detail[-1] if detail else "no output"))]

        tarballs = sorted(workdir.glob("*.tar.gz"))
        if not tarballs:
            return [("dry-run-build", FAIL, "build produced no tarball")]
        tarball = tarballs[0]
        size_mib = tarball.stat().st_size / 1048576.0
        if size_mib > max_size_mib:
            results.append(("dry-run-build", FAIL,
                            "%s is %.1f MiB, over the %d MiB ceiling; something "
                            "generated is being packaged"
                            % (tarball.name, size_mib, max_size_mib)))
        else:
            results.append(("dry-run-build", PASS,
                            "%s (%.1f MiB)" % (tarball.name, size_mib)))

        with tarfile.open(tarball) as tar:
            names = tar.getnames()
            manifest_member = next((n for n in names if n == "MANIFEST.json"), None)
            if manifest_member is None:
                results.append(("dry-run-manifest", FAIL, "MANIFEST.json missing from the tarball"))
                manifest = {}
            else:
                manifest = json.loads(tar.extractfile(manifest_member).read().decode("utf-8"))
        results.append(("dry-run-contents", PASS, "%d files in the tarball" % len(names)))

        shipped = ((manifest.get("collection_info") or {}).get("version") or "").strip()
        if not shipped:
            results.append(("dry-run-version", FAIL, "MANIFEST.json carries no collection_info.version"))
        elif shipped == version:
            results.append(("dry-run-version", PASS, "MANIFEST.json says %s" % shipped))
        else:
            results.append(("dry-run-version", FAIL,
                            "MANIFEST.json says %s but galaxy.yml says %s" % (shipped, version)))

        leaked = sorted({prefix for name in names for prefix in FORBIDDEN_PREFIXES
                         if name.startswith(prefix)})
        if leaked:
            results.append(("dry-run-build-ignore", FAIL,
                            "tarball contains %s; galaxy.yml build_ignore no "
                            "longer covers them" % ", ".join(leaked)))
        else:
            results.append(("dry-run-build-ignore", PASS,
                            "nothing from build_ignore in the tarball"))

        if not smoke:
            results.append(("dry-run-smoke", SKIP, "skipped via --no-smoke"))
            return results

        root = workdir / "collections"
        rc, out_i, err_i = run(["ansible-galaxy", "collection", "install",
                                str(tarball), "-p", str(root), "--force"])
        if rc is None:
            results.append(("dry-run-smoke", SKIP, err_i))
        elif rc != 0:
            detail = (out_i + err_i).strip().splitlines()
            results.append(("dry-run-smoke", FAIL,
                            "collection install failed: %s"
                            % (detail[-1] if detail else "no output")))
        else:
            env = dict(os.environ)
            env["ANSIBLE_COLLECTIONS_PATH"] = str(root)
            rc, out_d, err_d = run(
                ["ansible-doc", "-l", "%s.%s" % (state["namespace"], state["name"])],
                env=env, timeout=300)
            if rc is None:
                results.append(("dry-run-smoke", SKIP, err_d))
            elif rc != 0:
                detail = (out_d + err_d).strip().splitlines()
                results.append(("dry-run-smoke", FAIL,
                                "ansible-doc failed on the installed collection: %s"
                                % (detail[-1] if detail else "no output")))
            else:
                documented = [line for line in out_d.splitlines() if line.strip()]
                results.append(("dry-run-smoke", PASS,
                                "installs and documents %d plugin(s)" % len(documented)))
        return results
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def render(results, out):
    width = max(len(name) for name, _, _ in results)
    for name, status, detail in results:
        out.write("  %-4s  %-*s  %s\n" % (status, width, name, detail))


def main(argv=None, out=None, err=None):
    parser = argparse.ArgumentParser(
        description="Pre-release guard and dry run for the collection.")
    parser.add_argument("--tag", metavar="TAG",
                        help="assert this tag matches galaxy.yml before releasing")
    parser.add_argument("--check", action="store_true",
                        help="accepted for symmetry with the other scripts/*_check.py "
                             "gates; this guard always exits non-zero on failure")
    parser.add_argument("--lint", action="store_true",
                        help="also run `antsibull-changelog lint` (slow: minutes, "
                             "not seconds; release.yml runs it separately anyway)")
    parser.add_argument("--ignore", action="append", default=[], metavar="CHECK",
                        help="skip a check by name (repeatable): %s"
                             % ", ".join(CHECK_NAMES))
    parser.add_argument("--dry-run", action="store_true",
                        help="after the guard passes, build the tarball in a "
                             "temporary directory and inspect it; publishes nothing")
    parser.add_argument("--max-size", type=int, default=DEFAULT_MAX_SIZE_MIB,
                        metavar="MIB",
                        help="with --dry-run, fail if the tarball exceeds this "
                             "size (default: %(default)s MiB)")
    parser.add_argument("--no-smoke", action="store_true",
                        help="with --dry-run, stop after inspecting the tarball "
                             "instead of installing it and listing its docs")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable results")
    args = parser.parse_args(argv)
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr

    unknown = [name for name in args.ignore if name not in CHECK_NAMES]
    if unknown:
        err.write("release check failed: unknown check name(s): %s\n"
                  % ", ".join(unknown))
        return 2

    state = build_state(args.tag)
    results = run_checks(state, set(args.ignore), lint=args.lint)

    failures = [name for name, status, _ in results if status == FAIL]
    if args.json:
        payload = {
            "version": state["version"],
            "collection": "%s.%s" % (state["namespace"], state["name"]),
            "ready": not failures,
            "results": [{"check": name, "status": status, "detail": detail}
                        for name, status, detail in results],
        }
        out.write(json.dumps(payload, indent=2) + "\n")
        return 1 if failures else 0

    out.write("release guard: %s.%s %s\n"
              % (state["namespace"], state["name"], state["version"]))
    render(results, out)

    if args.dry_run:
        if failures:
            out.write("\nDry run skipped: the guard failed, there is nothing to build.\n")
        else:
            dry_results = dry_run(state, out, smoke=not args.no_smoke,
                                  max_size_mib=args.max_size)
            results.extend(dry_results)
            render(dry_results, out)
            # A dry run that failed is a release that must not be tagged, so it
            # counts here and not just in the section above.
            failures = [name for name, status, _ in results if status == FAIL]
            if not failures:
                plan(state, out)

    if failures:
        err.write("\nrelease check failed: %s\n" % ", ".join(failures))
        return 1
    out.write("\nrelease check OK: %s is ready to tag\n" % state["version"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
