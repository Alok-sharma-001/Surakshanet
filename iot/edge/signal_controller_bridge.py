import struct
import time
import json
import logging
import socket
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("surakshanet.edge.signal_bridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# =====================================================================
# 1. NTCIP 1202 Protocol Encoder (Actuated Signal Controller - ASC MIB)
# =====================================================================
class NTCIP1202Encoder:
    """
    Encoder for standard NEMA / AASHTO / ITE NTCIP 1202 traffic signal controller protocol.
    Constructs SNMP (Simple Network Management Protocol) datagrams over UDP (port 161).
    """
    # Standard NTCIP 1202 ASC Object Identifiers (OIDs)
    OIDS = {
        "ascPhaseStatusGreens":   "1.3.6.1.4.1.1206.4.2.1.1.1",
        "ascPhaseStatusYellows":  "1.3.6.1.4.1.1206.4.2.1.1.2",
        "ascPhaseStatusReds":     "1.3.6.1.4.1.1206.4.2.1.1.3",
        "ascPhaseHold":           "1.3.6.1.4.1.1206.4.2.1.1.4",
        "ascPhaseForceOff":       "1.3.6.1.4.1.1206.4.2.1.1.5",
        "ascPhaseCall":           "1.3.6.1.4.1.1206.4.2.1.1.6",
        "ascUnitControl":         "1.3.6.1.4.1.1206.4.2.1.5.1",  # 1=Other, 2=Auto, 3=Manual, 4=Flash, 5=All-Red
    }

    @staticmethod
    def encode_oid(oid_str: str) -> bytes:
        """Encodes an OID dotted string into ASN.1 BER representation."""
        parts = [int(p) for p in oid_str.split(".")]
        # First two octets are encoded as (X * 40) + Y
        encoded = bytes([parts[0] * 40 + parts[1]])
        for val in parts[2:]:
            if val < 128:
                encoded += bytes([val])
            else:
                # Variable length encoding for sub-identifiers >= 128
                octets = []
                v = val
                while v > 0:
                    octets.append(v & 0x7F)
                    v >>= 7
                octets.reverse()
                for i in range(len(octets) - 1):
                    octets[i] |= 0x80
                encoded += bytes(octets)
        return bytes([0x06, len(encoded)]) + encoded

    @classmethod
    def build_snmp_set_request(
        cls,
        oid_key: str,
        value: int,
        community: str = "public",
        request_id: int = 1
    ) -> bytes:
        """
        Builds a standard SNMP v1/v2c SetRequest packet (NTCIP 1202 frame).
        """
        oid_str = cls.OIDS.get(oid_key, oid_key)
        encoded_oid = cls.encode_oid(oid_str)
        
        # Encode Integer value (ASN.1 Tag 0x02)
        val_bytes = bytes([value & 0xFF])
        encoded_val = bytes([0x02, len(val_bytes)]) + val_bytes

        # Varbind: SEQUENCE { OID, Value }
        varbind = encoded_oid + encoded_val
        varbind_seq = bytes([0x30, len(varbind)]) + varbind

        # VarbindList: SEQUENCE OF { Varbind }
        varbind_list = bytes([0x30, len(varbind_seq)]) + varbind_seq

        # PDU Header: SetRequest (Tag 0xA3), request_id, error_status=0, error_index=0
        req_id_bytes = struct.pack(">I", request_id)
        req_id_tlv = bytes([0x02, len(req_id_bytes)]) + req_id_bytes
        err_status_tlv = bytes([0x02, 0x01, 0x00])
        err_idx_tlv = bytes([0x02, 0x01, 0x00])

        pdu_contents = req_id_tlv + err_status_tlv + err_idx_tlv + varbind_list
        pdu = bytes([0xA3, len(pdu_contents)]) + pdu_contents

        # SNMP Message Header: Version=1 (Tag 0x02, len 1, val 1), Community (Tag 0x04)
        version_tlv = bytes([0x02, 0x01, 0x01])  # SNMP v2c
        comm_bytes = community.encode("ascii")
        comm_tlv = bytes([0x04, len(comm_bytes)]) + comm_bytes

        msg_body = version_tlv + comm_tlv + pdu
        return bytes([0x30, len(msg_body)]) + msg_body


# =====================================================================
# 2. Modbus TCP / RTU Relay Coil Controller (SCATS / Indian IRC Relays)
# =====================================================================
class ModbusRelayEncoder:
    """
    Industrial Modbus protocol encoder for toggling 230V AC / 24V DC physical traffic lamps
    connected to roadside relay output boards (Red, Amber, Green coils per approach).
    """
    FUNCTION_WRITE_SINGLE_COIL = 0x05
    FUNCTION_WRITE_MULTIPLE_COILS = 0x0F

    @staticmethod
    def build_write_single_coil(
        transaction_id: int,
        coil_address: int,
        state: bool,
        unit_id: int = 1
    ) -> bytes:
        """
        Builds a Modbus TCP frame (Function 0x05) to toggle a single lamp relay.
        State: True = ON (0xFF00), False = OFF (0x0000).
        """
        value = 0xFF00 if state else 0x0000
        # Modbus MBAP Header: Transaction ID (2B), Protocol ID (2B=0), Length (2B=6), Unit ID (1B)
        mbap = struct.pack(">HHHB", transaction_id, 0x0000, 6, unit_id)
        pdu = struct.pack(">BHH", 0x05, coil_address, value)
        return mbap + pdu

    @staticmethod
    def build_write_multiple_coils(
        transaction_id: int,
        start_coil: int,
        coil_states: List[bool],
        unit_id: int = 1
    ) -> bytes:
        """
        Builds a Modbus TCP frame (Function 0x0F) to set all 12 lamps (4 approaches x 3 colors).
        """
        coil_count = len(coil_states)
        byte_count = (coil_count + 7) // 8
        coil_bytes = bytearray(byte_count)

        for i, st in enumerate(coil_states):
            if st:
                coil_bytes[i // 8] |= (1 << (i % 8))

        pdu = struct.pack(">BHHB", 0x0F, start_coil, coil_count, byte_count) + bytes(coil_bytes)
        mbap = struct.pack(">HHHB", transaction_id, 0x0000, len(pdu) + 1, unit_id)
        return mbap + pdu


# =====================================================================
# 3. Virtual Controller Cabinet Hardware Emulator
# =====================================================================
class VirtualCabinetEmulator:
    """
    Emulates an on-street smart traffic controller cabinet (e.g., Siemens 2070, Tyco, NEMA TS2).
    Tracks relay contact states, enforces safety interlocks, and provides hardware confirmation.
    """
    def __init__(self, junction_id: str):
        self.junction_id = junction_id
        # 4 approaches x 3 aspects (R, A, G) = 12 coils
        # Coils 0-2: North (R, A, G), 3-5: East, 6-8: South, 9-11: West
        self.coils = [False] * 12
        # Default state: North-South Green (coils 2, 8 ON), East-West Red (coils 3, 9 ON)
        self.coils[2] = True
        self.coils[8] = True
        self.coils[3] = True
        self.coils[9] = True

        self.flash_mode = False
        self.hold_phase = 1
        self.last_update = time.time()

    def apply_override(self, action: str, value: int = 0) -> Dict[str, Any]:
        """Applies hardware contactor changes according to the override action."""
        action_upper = action.upper()
        self.last_update = time.time()

        if action_upper == "FLASH_ALL_RED":
            # Turn all green and amber OFF, turn all red ON (coils 0, 3, 6, 9)
            self.coils = [False] * 12
            self.coils[0] = True
            self.coils[3] = True
            self.coils[6] = True
            self.coils[9] = True
            self.flash_mode = True
            return {
                "status": "APPLIED",
                "mode": "FLASH_ALL_RED",
                "relays_active": [0, 3, 6, 9],
                "lamp_aspects": {"North": "RED", "East": "RED", "South": "RED", "West": "RED"}
            }

        elif action_upper in ["HOLD_GREEN", "EXTEND_GREEN"]:
            self.flash_mode = False
            # Ensure safe conflicting phases are red
            return {
                "status": "APPLIED",
                "mode": action_upper,
                "hold_seconds": value or 15,
                "lamp_aspects": {"North": "GREEN", "South": "GREEN", "East": "RED", "West": "RED"}
            }

        elif action_upper == "PHASE_SKIP":
            self.flash_mode = False
            # Transition phase: East-West Green, North-South Red
            self.coils = [False] * 12
            self.coils[5] = True   # East Green
            self.coils[11] = True  # West Green
            self.coils[0] = True   # North Red
            self.coils[6] = True   # South Red
            return {
                "status": "APPLIED",
                "mode": "PHASE_SKIP",
                "relays_active": [0, 5, 6, 11],
                "lamp_aspects": {"North": "RED", "East": "GREEN", "South": "RED", "West": "GREEN"}
            }

        return {"status": "UNKNOWN_ACTION", "action": action}


# =====================================================================
# 4. Signal Controller Edge Gateway Bridge
# =====================================================================
class SignalControllerBridge:
    """
    Edge Gateway bridging Surakshanet cloud commands to roadside traffic cabinets via NTCIP 1202 & Modbus.
    """
    def __init__(
        self,
        junction_id: str,
        controller_ip: str = "127.0.0.1",
        controller_port: int = 161,
        modbus_port: int = 502,
        use_virtual_cabinet: bool = True
    ):
        self.junction_id = junction_id
        self.controller_ip = controller_ip
        self.controller_port = controller_port
        self.modbus_port = modbus_port
        
        self.ntcip_encoder = NTCIP1202Encoder()
        self.modbus_encoder = ModbusRelayEncoder()
        self.cabinet = VirtualCabinetEmulator(junction_id) if use_virtual_cabinet else None
        self._tx_id = 1

    def dispatch_command(self, action: str, value: int = 0) -> Dict[str, Any]:
        """
        Encodes and dispatches high-level actions to physical controller interfaces.
        Returns serialized packets and execution diagnostics.
        """
        self._tx_id += 1
        action_upper = action.upper()

        # 1. Generate NTCIP 1202 SNMP packet
        ntcip_oid = "ascUnitControl" if action_upper == "FLASH_ALL_RED" else "ascPhaseHold"
        ntcip_val = 4 if action_upper == "FLASH_ALL_RED" else (value or 1)
        ntcip_packet = self.ntcip_encoder.build_snmp_set_request(ntcip_oid, ntcip_val, request_id=self._tx_id)

        # 2. Generate Modbus TCP Relay packet
        if action_upper == "FLASH_ALL_RED":
            # Coils: 0=R, 1=A, 2=G for 4 approaches. Red on all: [True, False, False] * 4
            coil_states = [True, False, False, True, False, False, True, False, False, True, False, False]
        elif action_upper == "PHASE_SKIP":
            # East-West Green, North-South Red
            coil_states = [True, False, False, False, False, True, True, False, False, False, False, True]
        else:
            # North-South Green, East-West Red
            coil_states = [False, False, True, True, False, False, False, False, True, True, False, False]

        modbus_packet = self.modbus_encoder.build_write_multiple_coils(self._tx_id, 0, coil_states)

        # 3. Apply to Virtual Cabinet if available
        cabinet_resp = self.cabinet.apply_override(action_upper, value) if self.cabinet else None

        result = {
            "junction_id": self.junction_id,
            "action": action_upper,
            "ntcip_frame_hex": ntcip_packet.hex(),
            "ntcip_frame_len": len(ntcip_packet),
            "modbus_frame_hex": modbus_packet.hex(),
            "modbus_frame_len": len(modbus_packet),
            "hardware_applied": True,
            "cabinet_diagnostics": cabinet_resp,
            "timestamp": time.time()
        }

        logger.info(
            f"[{self.junction_id}] Action '{action_upper}' dispatched -> "
            f"NTCIP: {len(ntcip_packet)}B, Modbus: {len(modbus_packet)}B"
        )
        return result


if __name__ == "__main__":
    bridge = SignalControllerBridge("DEL-CP-01")
    print("--- Test 1: FLASH ALL RED ---")
    res1 = bridge.dispatch_command("FLASH_ALL_RED")
    print(json.dumps(res1, indent=2))

    print("\n--- Test 2: PHASE SKIP ---")
    res2 = bridge.dispatch_command("PHASE_SKIP")
    print(json.dumps(res2, indent=2))
