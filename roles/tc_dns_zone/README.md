# tc_dns_zone

Provisions a DNSPod domain with custom routing lines, reusable line groups and
DNS records. Records are reconciled by domain, host, record type and line.

Teardown removes records before line groups, custom lines and the parent domain.
Declare every managed child in the role variables when removing the zone.
