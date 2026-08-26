# Contributing

Keep SDK calls in small testable functions and do not log credentials. New
state-changing modules must be idempotent and support check mode where possible.

```bash
ansible-test sanity --docker default
ansible-test units --docker default
ansible-galaxy collection build
```

## Releasing

Releases are cut from tags and published by
[`.github/workflows/release.yml`](.github/workflows/release.yml):

1. Bump `version` in `galaxy.yml` and add changelog fragments for the
   changes under `changelogs/fragments/` (lint them with
   `antsibull-changelog lint`).
2. Optionally fold the fragments into `changelogs/changelog.yaml` and
   `CHANGELOG.rst` and commit the result:

   ```bash
   antsibull-changelog release --version X.Y.Z
   ```

3. Tag the release and push the tag:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

The workflow runs the sanity/unit tests, lints the changelog fragments,
fails if the tag does not match `galaxy.yml` `version`, builds the tarball,
and creates a GitHub release with the tarball attached. Publishing to
Ansible Galaxy additionally requires the `GALAXY_API_KEY` repository secret;
without it the publish step is skipped with a warning.
