# tc_gaap_accelerator

Creates and starts a GAAP proxy, registers reusable origins, creates TCP/UDP
listeners, and exactly reconciles every listener's origin set. Teardown requires
`tc_gaap_accelerator_allow_destroy=true`; reusable origin registry entries are
retained because they may be shared by other proxies.
