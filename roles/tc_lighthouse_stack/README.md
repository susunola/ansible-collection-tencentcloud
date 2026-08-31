# tc_lighthouse_stack

Provisions or adopts a Lighthouse instance and reconciles SSH key associations,
the exact firewall rule set, attached data disks and instance snapshots.

Teardown removes snapshots, firewall rules, disks and key associations before
isolating the instance. Lighthouse `state: absent` is isolation, not permanent
account-level deletion; the result and task names intentionally preserve that
product distinction.
