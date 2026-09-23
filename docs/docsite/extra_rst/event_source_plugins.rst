.. Document meta

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. Anchors

.. _ansible_collections.susunola.tencentcloud.event_source_plugins:

.. Title

Event source plugins (Event-Driven Ansible)
+++++++++++++++++++++++++++++++++++++++++++

The plugins on this page are event sources for Event-Driven Ansible:
each one polls a Tencent Cloud service and puts what it finds on the
rulebook event queue, so a rule condition can match on it.

.. note::
    ``event_source`` is not a plugin type ansible-core resolves, so
    ``ansible-doc`` cannot show these plugins and no sanity test
    renders their documentation. antsibull-docs does not know the
    type either, which is why this page is written by
    ``scripts/generate_event_source_docs.py`` instead of generated
    with the rest of the docsite. Its content comes from the plugins'
    own ``DOCUMENTATION`` and ``EXAMPLES`` blocks, and CI fails if the
    two ever disagree.

.. contents::
   :local:
   :depth: 1

.. _ansible_collections.susunola.tencentcloud.cls_topic_event_source:

susunola.tencentcloud.cls_topic event source -- Poll a Tencent Cloud CLS log topic for matching log records
-----------------------------------------------------------------------------------------------------------

.. rst-class:: ansible-version-added

New in susunola.tencentcloud 1.0.0

Synopsis
^^^^^^^^

- Polls a Tencent Cloud CLS (Cloud Log Service) log topic with a search query and yields each new matching log record as an event for Event-Driven Ansible (ansible-rulebook).

- The source keeps a rolling ``from`` timestamp (now minus ``lookback`` at start, then the previous poll's ``to``) so logs between polls are not skipped and each log is yielded exactly once under normal operation.

- The CLS search API runs in a worker thread so the event loop stays responsive; polling happens every ``interval`` seconds.

- Every event carries the log record under the ``cls`` key, so a JSON log with a ``level`` field is matched as ``event.cls.level``; a raw log that does not parse as JSON arrives as ``event.cls.message``. ``topic_id`` and ``region`` are added alongside. Search failures are emitted as ``cls.error`` events and never crash the source.

Parameters
^^^^^^^^^^

.. list-table::
   :widths: 20 12 68
   :header-rows: 1

   * - Parameter
     - Type
     - Description
   * - ``batch_size``
     - ``int``
     - Maximum number of log records returned per search page. Default: ``20``.
   * - ``endpoint``
     - ``str``
     - API endpoint override, defaults to ``cls.tencentcloudapi.com``.
   * - ``interval``
     - ``float``
     - Seconds between polls. Default: ``5``.
   * - ``lookback``
     - ``float``
     - Seconds of history searched on the first poll before the rolling window starts. Default: ``30``.
   * - ``query``
     - ``str``
     - CLS search query, e.g. ``level:ERROR``. Defaults to all records. Default: ``*``.
   * - ``region``
     - ``str``
     - Region of the log topic (fallback ``TENCENTCLOUD_REGION``), e.g. ``ap-guangzhou``.
   * - ``secret_id``
     - ``str``
     - Tencent Cloud secret id (fallback ``TENCENTCLOUD_SECRET_ID``).
   * - ``secret_key``
     - ``str``
     - Tencent Cloud secret key (fallback ``TENCENTCLOUD_SECRET_KEY``).
   * - ``token``
     - ``str``
     - Temporary session token (fallback ``TENCENTCLOUD_TOKEN``).
   * - ``topic_id``
     - ``str``
     - Id of the CLS log topic to search, e.g. ``dc9b3c16-xxxx``.
   * - ``topic_name``
     - ``str``
     - Name of the log topic; resolved to an id when ``topic_id`` is not given.

Event payload
^^^^^^^^^^^^^

Rules match on these fields of the event the source puts on the
queue:

- ``event.cls.level``
- ``event.cls.message``

Example
^^^^^^^

.. code-block:: yaml

   - name: react to error logs in a CLS topic
     hosts: all
     sources:
       - susunola.tencentcloud.cls_topic:
           region: ap-guangzhou
           topic_id: 6a2b7c9e-1f0d-4a3b-8c5d-0e9f1a2b3c4d
           query: level:ERROR
           interval: 10
     rules:
       - name: page on an error record
         condition: event.cls.level == "ERROR"
         action:
           run_playbook:
             name: playbooks/on_error.yml

.. _ansible_collections.susunola.tencentcloud.cmq_queue_event_source:

susunola.tencentcloud.cmq_queue event source -- Poll a Tencent Cloud CMQ queue for messages
-------------------------------------------------------------------------------------------

.. rst-class:: ansible-version-added

New in susunola.tencentcloud 1.0.0

Synopsis
^^^^^^^^

- Long-polls a Tencent Cloud CMQ queue and yields each received message as an event for Event-Driven Ansible (ansible-rulebook).

- The SDK ReceiveMessage call blocks for up to ``polling_wait_seconds`` seconds and runs in a worker thread so the event loop stays responsive.

- When ``acknowledge`` is true (the default) each message is deleted after it is yielded, so the queue drains as events are processed; set it to false to keep messages in the queue (they become visible again after the visibility timeout).

- Every event carries the message under the ``cmq`` key, e.g. ``event.cmq.msg_body``; ``msg_body_json`` is added when the body parses as JSON. Poll failures are emitted as ``cmq.error`` events and never crash the source.

Parameters
^^^^^^^^^^

.. list-table::
   :widths: 20 12 68
   :header-rows: 1

   * - Parameter
     - Type
     - Description
   * - ``acknowledge``
     - ``bool``
     - Delete each message after it is yielded (true) or leave it in the queue (false). Default: ``true``.
   * - ``endpoint``
     - ``str``
     - API endpoint override, defaults to ``cmq.tencentcloudapi.com``.
   * - ``idle_interval``
     - ``float``
     - Seconds to wait before polling again when a poll returns no message. Default: ``1``.
   * - ``polling_wait_seconds``
     - ``int``
     - Seconds the ReceiveMessage call blocks waiting for a message (0-30). Default: ``20``.
   * - ``queue_name``
     - ``str``
     - Name of the CMQ queue to poll.
   * - ``region``
     - ``str``
     - Region of the queue (fallback ``TENCENTCLOUD_REGION``), e.g. ``ap-guangzhou``.
   * - ``secret_id``
     - ``str``
     - Tencent Cloud secret id (fallback ``TENCENTCLOUD_SECRET_ID``).
   * - ``secret_key``
     - ``str``
     - Tencent Cloud secret key (fallback ``TENCENTCLOUD_SECRET_KEY``).
   * - ``token``
     - ``str``
     - Temporary session token (fallback ``TENCENTCLOUD_TOKEN``).

Event payload
^^^^^^^^^^^^^

Rules match on these fields of the event the source puts on the
queue:

- ``event.cmq.msg_body``

Example
^^^^^^^

.. code-block:: yaml

   - name: react to CMQ messages
     hosts: all
     sources:
       - susunola.tencentcloud.cmq_queue:
           region: ap-guangzhou
           queue_name: order-events
           polling_wait_seconds: 10
     rules:
       - name: process an order
         condition: event.cmq.msg_body is defined
         action:
           run_playbook:
             name: playbooks/process_order.yml

.. _ansible_collections.susunola.tencentcloud.cos_bucket_event_source:

susunola.tencentcloud.cos_bucket event source -- Poll a Tencent Cloud COS bucket for new or changed objects
-----------------------------------------------------------------------------------------------------------

.. rst-class:: ansible-version-added

New in susunola.tencentcloud 1.0.0

Synopsis
^^^^^^^^

- Polls a Tencent Cloud COS bucket's object listing and yields each new (or changed) object as an event for Event-Driven Ansible (ansible-rulebook), the polling equivalent of a bucket event notification.

- The first poll establishes a baseline; objects already in the bucket are recorded but not emitted unless ``initial`` is true. Afterwards an event is yielded for every object whose key is new or whose last-modified time has changed since the previous poll.

- COS object keys are ordered lexicographically, so the listing is walked in full each poll; ``max_objects`` caps the walk for very large buckets (a cap can hide objects sorted after the cut-off, so it is off by default).

- The listing runs in a worker thread; polling happens every ``interval`` seconds.

- Every event carries the object under the ``cos`` key, e.g. ``event.cos.key``, ``event.cos.size`` and ``event.cos.last_modified``; ``bucket``, ``region`` and ``event.cos.event_type`` are added alongside. The event type is always ``ObjectCreated`` because an object listing cannot tell a new object from a modified one. Listing failures are emitted as ``cos.error`` events and never crash the source.

Parameters
^^^^^^^^^^

.. list-table::
   :widths: 20 12 68
   :header-rows: 1

   * - Parameter
     - Type
     - Description
   * - ``appid``
     - ``str``
     - Tencent Cloud appid used to expand a short bucket name (fallback ``TENCENTCLOUD_APPID``).
   * - ``bucket``
     - ``str``
     - Bucket to poll, as a short name (with ``appid``) or a full ``bucket-appid`` name.
   * - ``endpoint``
     - ``str``
     - COS endpoint override.
   * - ``initial``
     - ``bool``
     - Emit events for objects present at the first (baseline) poll. Default: ``false``.
   * - ``interval``
     - ``float``
     - Seconds between polls. Default: ``5``.
   * - ``max_objects``
     - ``int``
     - Cap the number of objects walked per poll (off by default; can hide objects).
   * - ``prefix``
     - ``str``
     - Only yield objects whose key starts with this prefix.
   * - ``region``
     - ``str``
     - Region of the bucket (fallback ``TENCENTCLOUD_REGION``), e.g. ``ap-guangzhou``.
   * - ``secret_id``
     - ``str``
     - Tencent Cloud secret id (fallback ``TENCENTCLOUD_SECRET_ID``).
   * - ``secret_key``
     - ``str``
     - Tencent Cloud secret key (fallback ``TENCENTCLOUD_SECRET_KEY``).
   * - ``token``
     - ``str``
     - Temporary session token (fallback ``TENCENTCLOUD_TOKEN``).

Event payload
^^^^^^^^^^^^^

Rules match on these fields of the event the source puts on the
queue:

- ``event.cos.key``
- ``event.cos.size``
- ``event.cos.last_modified``
- ``event.cos.event_type``

Example
^^^^^^^

.. code-block:: yaml

   - name: react to objects uploaded to a COS bucket
     hosts: all
     sources:
       - susunola.tencentcloud.cos_bucket:
           region: ap-guangzhou
           bucket: mybucket
           appid: "1300000000"
           prefix: images/
     rules:
       - name: process a new object
         condition: event.cos.event_type == "ObjectCreated"
         action:
           run_playbook:
             name: playbooks/on_upload.yml

.. _ansible_collections.susunola.tencentcloud.tke_cluster_event_source:

susunola.tencentcloud.tke_cluster event source -- Poll Tencent Cloud TKE cluster state changes
----------------------------------------------------------------------------------------------

.. rst-class:: ansible-version-added

New in susunola.tencentcloud 1.0.0

Synopsis
^^^^^^^^

- Polls the Tencent Cloud TKE ``DescribeClusterStatus`` API and yields an event whenever a cluster's state changes (for example Running to Abnormal, or a node count moving) for Event-Driven Ansible (ansible-rulebook).

- The first poll records every cluster's current state as the baseline; no event is emitted unless ``initial`` is true. Afterwards an event is yielded for each state transition, a ``ClusterDeleted`` event for a cluster that was seen before and no longer appears in the listing, and the previous state is attached as ``previous_state``.

- TKE ships Kubernetes object-level events (Pod restarts etc.) to CLS when cluster event log collection is enabled; the ``cls_topic`` source covers that path, while this source surfaces the cluster lifecycle state the API exposes.

- The status call runs in a worker thread; polling happens every ``interval`` seconds.

- Every event carries the cluster under the ``tke`` key, so a transition is matched as ``event.tke.event_type`` with ``event.tke.cluster_state``, ``event.tke.cluster_instance_state``, the node counts and the previous value attached as ``event.tke.previous_state``; ``region`` is added alongside. A cluster that disappears from the listing is emitted as ``event.tke.cluster_id`` with ``ClusterDeleted``. Poll failures are emitted as ``tke.error`` events and never crash the source.

Parameters
^^^^^^^^^^

.. list-table::
   :widths: 20 12 68
   :header-rows: 1

   * - Parameter
     - Type
     - Description
   * - ``cluster_ids``
     - ``list``
     - Clusters to watch; when omitted, every cluster in the region is polled.
   * - ``endpoint``
     - ``str``
     - API endpoint override, defaults to ``tke.tencentcloudapi.com``.
   * - ``initial``
     - ``bool``
     - Emit events for the clusters' state at the first (baseline) poll. Default: ``false``.
   * - ``interval``
     - ``float``
     - Seconds between polls. Default: ``5``.
   * - ``region``
     - ``str``
     - Region of the clusters (fallback ``TENCENTCLOUD_REGION``), e.g. ``ap-guangzhou``.
   * - ``secret_id``
     - ``str``
     - Tencent Cloud secret id (fallback ``TENCENTCLOUD_SECRET_ID``).
   * - ``secret_key``
     - ``str``
     - Tencent Cloud secret key (fallback ``TENCENTCLOUD_SECRET_KEY``).
   * - ``token``
     - ``str``
     - Temporary session token (fallback ``TENCENTCLOUD_TOKEN``).

Event payload
^^^^^^^^^^^^^

Rules match on these fields of the event the source puts on the
queue:

- ``event.tke.event_type``
- ``event.tke.cluster_state``
- ``event.tke.cluster_instance_state``
- ``event.tke.previous_state``
- ``event.tke.cluster_id``

Example
^^^^^^^

.. code-block:: yaml

   - name: react to TKE cluster state changes
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
