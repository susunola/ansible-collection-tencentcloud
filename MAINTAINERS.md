# Maintainers

This file lists the maintainers of the `tencentcloud.cloud` Ansible
collection and their responsibilities. It follows the
[Ansible guidelines for collection maintainers](https://docs.ansible.com/ansible/latest/community/maintainers.html).

## Current maintainers

| GitHub handle | Role |
|---|---|
| [@susunola](https://github.com/susunola) | Collection maintainer |

## Maintainer responsibilities

Maintainers of this collection are expected to:

- Act in accordance with the
  [Ansible Community Code of Conduct](https://docs.ansible.com/ansible/latest/community/code_of_conduct.html).
- Watch the repository (GitHub *Watch > All activity*) and stay responsive
  in issues and pull requests.
- Keep the `README`, `CONTRIBUTING.md`, and other general documentation
  current.
- Review and merge contributions using the Ansible
  [review checklist for collection PRs](https://docs.ansible.com/ansible/latest/community/review_checklist.html).
- Keep CI (sanity and unit tests) green on the `main` branch.
- Plan and perform releases, keeping `changelogs/` up to date with
  `antsibull-changelog` and following semantic versioning.
- Ensure the collection continues to adhere to the
  [Ansible community package collection requirements](https://docs.ansible.com/ansible/latest/community/collection_contributors/collection_requirements.html).
- Track announcements through the
  [news-for-maintainers](https://forum.ansible.com/tag/news-for-maintainers)
  forum tag and update the collection accordingly.
- Never commit or log Tencent Cloud credentials; treat credential leaks as
  security incidents (see [`SECURITY.md`](SECURITY.md)).

## Becoming a maintainer

If you are an active contributor and would like to help maintain this
collection, open a GitHub issue nominating yourself (or another
contributor). See the
[Ansible maintainer guidelines](https://docs.ansible.com/ansible/latest/community/maintainers_guidelines.html)
for the general process, and `CONTRIBUTING.md` for how to start
contributing.

## Stepping down

A maintainer who can no longer fulfil the responsibilities above should
open an issue announcing their intent to step down and, where possible,
help hand over to a new maintainer before leaving.
