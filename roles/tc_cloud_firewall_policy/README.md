# tc_cloud_firewall_policy

Operates a reusable Cloud Firewall policy spanning address templates, internet
border ACLs, NAT ACLs, inter-VPC ACLs and NAT DNAT forwarding.

Templates are created before dependent rules and removed only after every rule
family. Rule descriptions are the stable lookup identity when a rule UUID is not
provided; production policy should therefore keep descriptions unique.
