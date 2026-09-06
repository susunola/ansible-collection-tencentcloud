# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""TKE cluster state event source for Event-Driven Ansible.

Polls ``DescribeClusterStatus`` and yields an event whenever a cluster's
state changes (for example Running -> Abnormal, or a node count moving)::

    - name: react to cluster state changes
      hosts: all
      sources:
        - susunola.tencentcloud.tke_cluster:
            region: ap-guangzhou
            cluster_ids:
              - cls-xxxxxxxx
      rules:
        - name: page when a cluster turns abnormal
          condition: event.tke.event_type == "ClusterStateChanged" and event.tke.cluster_state == "Abnormal"
          action:
            run_playbook:
              name: playbooks/on_abnormal.yml

The first poll establishes a baseline: every cluster's current state is
recorded but no event is emitted unless ``initial`` is true. Afterwards an
event is yielded for each state transition, a ``ClusterDeleted`` event for a
cluster that was seen before and no longer appears in the listing, and the
previous state is attached as ``previous_state``. TKE ships Kubernetes
object-level events (Pod restarts etc.) to CLS when cluster event log
collection is enabled; the ``cls_topic`` source covers that path, while this
source surfaces the cluster lifecycle state the API exposes. Polling is
``interval`` seconds apart and the status call runs in a worker thread so the
event loop stays responsive.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import argparse
import asyncio
import json
import os


def _env_or(args_key, args, env_name, default=None):
    value = args.get(args_key)
    if value:
        return value
    return os.environ.get(env_name, default)


def build_status_request(models, cluster_ids):
    """Build a DescribeClusterStatus request; empty ids query all clusters."""
    request = models.DescribeClusterStatusRequest()
    if cluster_ids:
        request.ClusterIds = cluster_ids
    return request


def describe_cluster_status(client, models, cluster_ids):
    """Run one DescribeClusterStatus call; return clusters as plain dicts."""
    request = build_status_request(models, cluster_ids)
    response = client.DescribeClusterStatus(request)
    clusters = []
    for status in response.ClusterStatusSet or []:
        clusters.append({
            "cluster_id": getattr(status, "ClusterId", None),
            "cluster_state": getattr(status, "ClusterState", None),
            "cluster_instance_state": getattr(status, "ClusterInstanceState", None),
            "running_node_num": getattr(status, "ClusterRunningNodeNum", None),
            "failed_node_num": getattr(status, "ClusterFailedNodeNum", None),
            "closed_node_num": getattr(status, "ClusterClosedNodeNum", None),
            "init_node_num": getattr(status, "ClusterInitNodeNum", None),
        })
    return clusters


def _build_client(args):
    """Construct the TKE SDK client from args with environment fallbacks."""
    from tencentcloud.tke.v20180525 import models, tke_client
    from tencentcloud.common import credential as tc_credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile

    secret_id = _env_or("secret_id", args, "TENCENTCLOUD_SECRET_ID")
    secret_key = _env_or("secret_key", args, "TENCENTCLOUD_SECRET_KEY")
    token = _env_or("token", args, "TENCENTCLOUD_TOKEN")
    region = _env_or("region", args, "TENCENTCLOUD_REGION")
    if not secret_id or not secret_key:
        raise RuntimeError(
            "tke_cluster requires secret_id/secret_key (or the "
            "TENCENTCLOUD_SECRET_ID/TENCENTCLOUD_SECRET_KEY environment variables)"
        )
    if not region:
        raise RuntimeError(
            "tke_cluster requires region (or TENCENTCLOUD_REGION)"
        )
    http_profile = HttpProfile()
    http_profile.endpoint = args.get("endpoint") or "tke.tencentcloudapi.com"
    http_profile.reqTimeout = 60
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client_profile.language = "en-US"
    credential = tc_credential.Credential(secret_id, secret_key, token)
    return tke_client.TkeClient(credential, region, client_profile), models


async def main(queue, args):
    """Poll cluster states and put each state transition on the queue.

    :param queue: asyncio.Queue consumed by ansible-rulebook.
    :param args: dict with region, cluster_ids (optional), interval,
        initial and endpoint.
    """
    client, models = _build_client(args)
    region = _env_or("region", args, "TENCENTCLOUD_REGION")
    cluster_ids = args.get("cluster_ids") or None
    interval = float(args.get("interval", 5))
    initial = bool(args.get("initial", False))
    states = {}

    while True:
        try:
            clusters = await asyncio.to_thread(
                describe_cluster_status, client, models, cluster_ids,
            )
            current = {cluster["cluster_id"]: cluster for cluster in clusters}
            first_poll = not states
            for cluster_id, cluster in current.items():
                signature = (cluster["cluster_state"], cluster["cluster_instance_state"])
                previous = states.get(cluster_id)
                if previous is not None and previous["signature"] == signature:
                    continue
                if first_poll and not initial:
                    states[cluster_id] = {"signature": signature, "cluster": cluster}
                    continue
                event = dict(cluster)
                event["previous_state"] = previous["cluster"]["cluster_state"] if previous else None
                event["previous_instance_state"] = previous["cluster"]["cluster_instance_state"] if previous else None
                event["event_type"] = "ClusterStateChanged"
                states[cluster_id] = {"signature": signature, "cluster": cluster}
                await queue.put({"tke": event, "region": region})
            if not first_poll:
                for cluster_id in list(states):
                    if cluster_id not in current:
                        await queue.put({
                            "tke": {
                                "cluster_id": cluster_id,
                                "event_type": "ClusterDeleted",
                                "region": region,
                            },
                            "region": region,
                        })
                        del states[cluster_id]
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Keep the source alive across transient API failures; the
            # rulebook surface shows the error only if it persists.
            await queue.put({
                "tke": {"region": region, "error": str(exc)},
            })
        await asyncio.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TKE cluster event source")
    parser.add_argument("--region", default=os.environ.get("TENCENTCLOUD_REGION"))
    parser.add_argument("--cluster-ids", nargs="*")
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--initial", type=bool, default=False)
    cli_args = parser.parse_args()

    async def _standalone():
        sink = asyncio.Queue()
        task = asyncio.create_task(main(sink, vars(cli_args)))
        try:
            while True:
                event = await sink.get()
                print(json.dumps(event, ensure_ascii=False, default=str))
        except KeyboardInterrupt:
            task.cancel()

    asyncio.run(_standalone())
