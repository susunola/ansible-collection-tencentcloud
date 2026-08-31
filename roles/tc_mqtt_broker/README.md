# tc_mqtt_broker

Provisions a Tencent Cloud MQTT instance with VPC or public access, topics,
username/password identities and ordered data-plane authorization policies.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_mqtt_broker
      vars:
        tc_mqtt_broker_region: ap-guangzhou
        tc_mqtt_broker_name: device-events
        tc_mqtt_broker_instance_type: PRO
        tc_mqtt_broker_sku_code: mqtt-pro
        tc_mqtt_broker_vpcs:
          - {vpc_id: vpc-xxxxxxxx, subnet_id: subnet-xxxxxxxx}
        tc_mqtt_broker_topics:
          - {topic: devices/telemetry, remark: Device telemetry}
        tc_mqtt_broker_users:
          - {username: device-gateway, password: "{{ vault_mqtt_password }}"}
        tc_mqtt_broker_policies:
          - name: device-publish
            priority: 10
            effect: allow
            actions: [connect, pub]
            resources: [devices/#]
            username: device-gateway
```

MQTT user passwords are write-only and the current Tencent Cloud API does not
provide password update. The role uses a password only for initial creation;
replace the user deliberately when a credential must change. Teardown removes
policies before topics, users and the instance.
