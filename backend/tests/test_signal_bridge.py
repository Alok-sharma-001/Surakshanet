import pytest
from iot.edge.signal_controller_bridge import (
    NTCIP1202Encoder,
    ModbusRelayEncoder,
    VirtualCabinetEmulator,
    SignalControllerBridge
)

def test_ntcip_encoder():
    """Verify NTCIP 1202 SNMP packet generation."""
    encoder = NTCIP1202Encoder()
    packet = encoder.build_snmp_set_request("ascUnitControl", 4, request_id=42)
    assert isinstance(packet, bytes)
    assert len(packet) > 30
    assert packet[0] == 0x30  # SNMP SEQUENCE tag
    # Verify community string 'public' is present
    assert b"public" in packet

def test_modbus_relay_encoder():
    """Verify Modbus TCP frame generation for single and multiple coils."""
    encoder = ModbusRelayEncoder()
    # Test single coil
    single_frame = encoder.build_write_single_coil(transaction_id=1, coil_address=2, state=True)
    assert len(single_frame) == 12  # MBAP (7B) + PDU (5B)
    assert single_frame[7] == 0x05  # Function Code 0x05

    # Test multiple coils
    coils = [True, False, False, True, False, False, True, False, False, True, False, False]
    multi_frame = encoder.build_write_multiple_coils(transaction_id=2, start_coil=0, coil_states=coils)
    assert len(multi_frame) == 15   # MBAP (7B) + PDU (8B)
    assert multi_frame[7] == 0x0F  # Function Code 0x0F

def test_virtual_cabinet_emulator():
    """Verify virtual cabinet relay logic for flash all-red and phase skip."""
    cabinet = VirtualCabinetEmulator("DEL-CP-01")
    
    # Flash all-red
    res = cabinet.apply_override("FLASH_ALL_RED")
    assert res["status"] == "APPLIED"
    assert res["mode"] == "FLASH_ALL_RED"
    assert all(aspect == "RED" for aspect in res["lamp_aspects"].values())

    # Phase skip
    res2 = cabinet.apply_override("PHASE_SKIP")
    assert res2["status"] == "APPLIED"
    assert res2["mode"] == "PHASE_SKIP"
    assert res2["lamp_aspects"]["East"] == "GREEN"
    assert res2["lamp_aspects"]["West"] == "GREEN"

def test_signal_controller_bridge_dispatch():
    """Verify high-level dispatch bridging to both NTCIP and Modbus outputs."""
    bridge = SignalControllerBridge("DEL-CP-01")
    res = bridge.dispatch_command("FLASH_ALL_RED")

    assert res["junction_id"] == "DEL-CP-01"
    assert res["action"] == "FLASH_ALL_RED"
    assert "ntcip_frame_hex" in res
    assert "modbus_frame_hex" in res
    assert res["hardware_applied"] is True
    assert res["cabinet_diagnostics"]["mode"] == "FLASH_ALL_RED"
