# Scenario playbooks

The `playbooks/` directory ships runnable end-to-end scenarios. All of them
target `localhost` (the modules call the Tencent Cloud APIs from the
controller) and take credentials from the shared `TENCENTCLOUD_*`
environment variables; the region defaults to `ap-guangzhou` and can be
overridden with `-e tencentcloud_region=<region>`.

Run one with:

```bash
ansible-playbook playbooks/<scenario>.yml
```

## discover_network.yml — read-only network inventory

- **Architecture**: nothing is created; the playbook gathers VPCs and
  security groups and prints the counts.
- **Modules**: `vpc_info`, `security_group_info`.
- **Prerequisites**: read-only CAM permissions (`DescribeVpcs`,
  `DescribeSecurityGroups`).
- **Cost**: none (read-only API calls).

## cvm_instance_info.yml — instance query

- **Architecture**: read-only; lists CVM instances in the region.
- **Modules**: `cvm_instance_info`.
- **Prerequisites**: read-only CAM permission `DescribeInstances`.
- **Cost**: none.

## tke_kubeconfig.yml — TKE cluster access bootstrap

- **Architecture**: fetches the intranet (default) or extranet
  (`-e is_extranet=true`) kubeconfig of an existing TKE cluster and writes
  it to a local file with 0600 permissions.
- **Modules**: `tke_cluster_kubeconfig`.
- **Prerequisites**: an existing TKE cluster (`-e tke_cluster_id=cls-...`);
  for the extranet kubeconfig, public access must be enabled on the cluster
  first (see the `tke_cluster_endpoint` module).
- **Cost**: none (read-only API call).

## cos_static_site.yml — static website hosting on COS

- **Architecture**: a public-read COS bucket with static website hosting
  enabled, a set of local files uploaded as objects, and short-lived
  pre-signed URLs (PUT for uploads, GET for downloads).
- **Modules**: `cos_bucket`, `cos_bucket_website`, `cos_object`.
- **Prerequisites**: COS write permissions; the source directory
  (`-e site_dir=...`, default `playbooks/site`) must contain the files
  listed in `site_files`.
- **Cost**: COS storage and request pricing apply to the bucket and
  objects; deleting the bucket afterwards stops storage charges.

## three_tier_web.yml — VPC + CVM pool + CLB three-tier web tier

- **Architecture**: a VPC with one subnet and a security group allowing
  HTTP/HTTPS ingress, a pool of web CVM instances kept at `exact_count`
  (matched by a `count_tag`), and a public CLB load balancer with an HTTP
  listener whose targets are exactly the pool instances.
- **Modules**: `vpc`, `subnet`, `security_group`, `security_group_rule`,
  `cvm_instance` (`exact_count`), `clb_load_balancer`, `clb_listener`,
  `clb_listener_target`.
- **Prerequisites**: a valid image ID (`-e web_image_id=img-...`), an
  instance password (`-e web_instance_password=...`), CVM and CLB quota in
  the region. Rerunning the playbook is idempotent; scaling the pool is a
  matter of changing `exact_count`.
- **Cost**: CVM instances and the CLB instance bill by the hour while they
  exist; CLB traffic is billed separately. Flip every `state: present` to
  `absent` (in reverse order) or delete the resources in the console to
  stop charges.
