# tc_gwlb_service_chain

Provisions or adopts a Gateway Load Balancer and reconciles target groups,
security-appliance endpoints and load-balancer associations. Both GWLBs and
target groups can be resolved by exact name during teardown.

Teardown disassociates each target group, deregisters every appliance, removes
the group, explicitly disables load-balancer deletion protection and deletes the
GWLB last.
