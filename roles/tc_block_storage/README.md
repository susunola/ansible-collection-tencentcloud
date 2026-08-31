# tc_block_storage

Provisions or adopts a CBS cloud disk, optionally attaches it to CVM, and
reconciles snapshots, cross-account snapshot sharing, disk backup points and
automatic snapshot retention policies.

Teardown clears snapshot sharing, removes declared recovery points, forcibly
unbinds automatic policies, detaches the disk when an instance is declared and
only then terminates the disk. Destructive snapshot removal remains opt-in.
