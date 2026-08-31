# tc_direct_connect_fabric

Provisions or adopts a physical Direct Connect circuit and reconciles its BGP or
static private tunnels. Circuit and tunnel names are exact lookup identities.
Tunnel tasks are hidden because BGP payloads may contain authentication keys.

Teardown always removes declared tunnels first. It retains the physical circuit
by default; set `tc_direct_connect_fabric_delete_physical_connection: true` only
when the cross-process, billable circuit application should also be deleted.
