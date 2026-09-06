# tc_tke_cluster

Provision a managed Tencent Kubernetes Engine (TKE) cluster in one call:
cluster, node pools and addons. Node pools and addons are described as lists
and are reconciled idempotently against the cluster.

## Role variables

| Variable | Default | Description |
| --- | --- | --- |
| `tc_tke_cluster_state` | `present` | `present` provisions, `absent` tears down (addons -> node pools -> cluster) |
| `tc_tke_cluster_region` | *(module default)* | Region override |
| `tc_tke_cluster_id` | `""` | Cluster id (existing cluster); required for teardown |
| `tc_tke_cluster_name` | `""` | Cluster name |
| `tc_tke_cluster_vpc_id` / `subnet_id` | `""` | Networking at creation |
| `tc_tke_cluster_version` | `""` | Kubernetes version, e.g. `1.28` |
| `tc_tke_cluster_desc` | `""` | Cluster description |
| `tc_tke_cluster_project_id` | `0` | Project the cluster belongs to |
| `tc_tke_cluster_type` | `MANAGED_CLUSTER` | Cluster type |
| `tc_tke_cluster_cidr` / `service_cidr` | `""` | Pod / service CIDR at creation |
| `tc_tke_cluster_max_node_pod_num` | `0` | Pods per node cap |
| `tc_tke_cluster_deletion_protection` | `false` | Block cluster deletion |
| `tc_tke_cluster_instance_delete_mode` | `""` | Node destroy mode on cluster deletion |
| `tc_tke_cluster_tags` | `{}` | Tags applied to the cluster |
| `tc_tke_cluster_node_pools` | `[]` | List of node pool definitions (see below) |
| `tc_tke_cluster_addons` | `[]` | List of addon definitions (see below) |
| `tc_tke_cluster_waiter_timeout` / `waiter_delay` | `600` / `5` | Waiter tuning |

Credentials and region follow the collection defaults (`TENCENTCLOUD_*`
environment variables, or `~/.tencentcloud/default.configure`).

## Node pool entries

Each `tc_tke_cluster_node_pools` entry maps the `tke_node_pool` options:
`name` (required), `launch_configuration_json`, `autoscaling_group_json`,
`enable_autoscale`, `max_nodes_num`, `min_nodes_num`, `labels`, `taints`,
`node_pool_os`, `deletion_protection`, `keep_instance`, `tags`.

## Addon entries

Each `tc_tke_cluster_addons` entry maps the `tke_addon` options: `name`
(required), `version`, `values`, `values_file`, `values_format`,
`update_strategy`, `api_dry_run`, `allow_downgrade`.

## Example

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_tke_cluster
      vars:
        tc_tke_cluster_region: ap-guangzhou
        tc_tke_cluster_name: prod-k8s
        tc_tke_cluster_vpc_id: vpc-xxxxxxxx
        tc_tke_cluster_subnet_id: subnet-xxxxxxxx
        tc_tke_cluster_version: "1.28"
        tc_tke_cluster_deletion_protection: true
        tc_tke_cluster_node_pools:
          - name: workers
            launch_configuration_json: '{"InstanceType":"S5.MEDIUM2","ImageId":"img-xxxxxxxx"}'
            autoscaling_group_json: '{"MinSize":2,"MaxSize":10,"DesiredCapacity":2}'
            enable_autoscale: true
            labels:
              app: workers
        tc_tke_cluster_addons:
          - name: cbs
            version: 1.4.0
            values:
              replicaCount: 2
```

## Teardown

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: susunola.tencentcloud.tc_tke_cluster
      vars:
        tc_tke_cluster_state: absent
        tc_tke_cluster_id: cls-xxxxxxxx
        # addons and node pools are removed first, in declaration order;
        # keep_instance defaults to false and releases the CVM nodes.
```

Note: teardown addresses addons and node pools by `tc_tke_cluster_id`, so the
id must be set when tearing down.
