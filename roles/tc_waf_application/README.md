# tc_waf_application

Adopts an existing WAF instance and manages protected domains, protection
groups, IP controls, custom and CC rules, allow rules, anti-tamper and
information-leak controls, geographic blocking, automatic deny and global
threat intelligence.

Both `tc_waf_application_instance_id` and `tc_waf_application_region` are
required because the role forwards complete dynamic rule dictionaries.

Teardown removes cross-domain protection groups first, disables singleton
controls, deletes every declared domain rule, and removes protected hosts last.
The externally managed WAF instance remains intact.
