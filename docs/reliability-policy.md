# Reliability and release policy

A module may be labelled **real-cloud verified** only after its applicable E2E
contract has passed three consecutive runs and the cleanup target covers its
resource type. A release is blocked by a failing P0/P1 target, an unexplained
SDK drift, or an expired resource that the reaper cannot account for.

Bug fixes are backported to the two latest maintained minor branches. Security
fixes are backported to every maintained branch. Deprecations require one major
release of warning and a documented replacement. New features are not
backported unless they are required to restore compatibility with Tencent Cloud.

The supported Tencent Cloud SDK window is the committed generated SDK version
plus the newest compatible version exercised by the weekly drift job.
