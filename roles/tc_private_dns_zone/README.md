# tc_private_dns_zone

Provisions a Private DNS zone, same-account and cross-account VPC associations,
authorized primary accounts, and records. Cross-account targets must complete
Tencent Cloud authorization before the role runs.

Teardown requires `tc_private_dns_zone_allow_destroy: true` and an explicit
`zone.zone_id`; it deletes declared records, the zone, then account relationships.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_private_dns_zone
      vars:
        tc_private_dns_zone:
          domain: services.internal
          vpcs:
            - region: ap-guangzhou
              vpc_id: vpc-xxxxxxxx
        tc_private_dns_zone_records:
          - subdomain: api
            record_type: A
            value: 10.0.0.8
```
