"""Tests for GAAP layer-4 listener helpers."""
from ansible_collections.susunola.tencentcloud.plugins.modules.gaap_layer4_listener import target


def params(protocol="TCP"):
    return {"name": "database", "port": 3306, "scheduler": "wrr", "real_server_type": "IP",
            "health_check": True, "failover": False, "delay_loop": 10, "connect_timeout": 3,
            "healthy_threshold": 2, "unhealthy_threshold": 3, "client_ip_method": 1,
            "udp_check_type": None, "udp_check_port": None, "send_context": None,
            "receive_context": None, "protocol": protocol}


def test_target_maps_common_listener_fields():
    value = target(params())
    assert value["ListenerName"] == "database"
    assert value["Port"] == 3306
    assert value["HealthCheck"] == 1
    assert value["FailoverSwitch"] == 0
    assert value["ClientIPMethod"] == 1


def test_target_maps_udp_probe_fields():
    value = params("UDP")
    value.update({"udp_check_type": "PORT", "udp_check_port": 8080,
                  "send_context": "ping", "receive_context": "pong"})
    result = target(value)
    assert result["CheckType"] == "PORT"
    assert result["CheckPort"] == 8080
    assert result["RecvContext"] == "pong"
