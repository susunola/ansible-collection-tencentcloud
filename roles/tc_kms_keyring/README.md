# tc_kms_keyring

Governs a set of Tencent Cloud KMS customer keys and their independent automatic
rotation policies. Key aliases are exact lookup identities and immutable key
attributes are enforced by the underlying module.

Teardown never deletes immediately: it schedules provider-side deletion using
each key's 7–30 day window. The role refuses every teardown unless
`tc_kms_keyring_allow_deletion: true` is explicitly supplied. Reapplying
`state: present` during the waiting window cancels scheduled deletion.
