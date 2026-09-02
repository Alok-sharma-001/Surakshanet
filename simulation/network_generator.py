import os
import random
import xml.etree.ElementTree as ET
from xml.dom import minidom
import subprocess
import logging

logger = logging.getLogger(__name__)

class NetworkGenerator:
    """Generate SUMO network files for a 4-junction arterial corridor."""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_corridor_network(self, num_junctions: int = 4, spacing_m: float = 300, 
                                  lanes: int = 2, speed_limit: float = 50):
        nod_file = os.path.join(self.output_dir, "corridor.nod.xml")
        edg_file = os.path.join(self.output_dir, "corridor.edg.xml")
        net_file = os.path.join(self.output_dir, "corridor.net.xml")
        
        # Nodes
        nodes_root = ET.Element("nodes")
        
        # Create mainline nodes
        for i in range(num_junctions):
            x = i * spacing_m
            ET.SubElement(nodes_root, "node", id=f"J{i}", x=str(x), y="0", type="traffic_light")
            # Create cross-street nodes (N and S)
            ET.SubElement(nodes_root, "node", id=f"N{i}", x=str(x), y="100", type="priority")
            ET.SubElement(nodes_root, "node", id=f"S{i}", x=str(x), y="-100", type="priority")
            
        # Entry/Exit nodes for arterial
        ET.SubElement(nodes_root, "node", id="W_entry", x="-100", y="0", type="priority")
        ET.SubElement(nodes_root, "node", id=f"E_exit", x=str((num_junctions-1)*spacing_m + 100), y="0", type="priority")
        
        # Write nodes
        self._write_xml(nodes_root, nod_file)
        
        # Edges
        edges_root = ET.Element("edges")
        
        # Mainline edges
        speed_ms = speed_limit * (1000 / 3600)
        
        # W entry to J0
        ET.SubElement(edges_root, "edge", {"id": "E_W_to_J0", "from": "W_entry", "to": "J0", "numLanes": str(lanes), "speed": str(speed_ms)})
        ET.SubElement(edges_root, "edge", {"id": "E_J0_to_W", "from": "J0", "to": "W_entry", "numLanes": str(lanes), "speed": str(speed_ms)})
        
        for i in range(num_junctions - 1):
            ET.SubElement(edges_root, "edge", {"id": f"E_J{i}_to_J{i+1}", "from": f"J{i}", "to": f"J{i+1}", "numLanes": str(lanes), "speed": str(speed_ms)})
            ET.SubElement(edges_root, "edge", {"id": f"E_J{i+1}_to_J{i}", "from": f"J{i+1}", "to": f"J{i}", "numLanes": str(lanes), "speed": str(speed_ms)})
            
        # Last J to E exit
        last_j = num_junctions - 1
        ET.SubElement(edges_root, "edge", {"id": f"E_J{last_j}_to_E", "from": f"J{last_j}", "to": "E_exit", "numLanes": str(lanes), "speed": str(speed_ms)})
        ET.SubElement(edges_root, "edge", {"id": f"E_E_to_J{last_j}", "from": "E_exit", "to": f"J{last_j}", "numLanes": str(lanes), "speed": str(speed_ms)})
        
        # Cross streets
        for i in range(num_junctions):
            ET.SubElement(edges_root, "edge", {"id": f"E_N{i}_to_J{i}", "from": f"N{i}", "to": f"J{i}", "numLanes": "1", "speed": str(speed_ms)})
            ET.SubElement(edges_root, "edge", {"id": f"E_J{i}_to_N{i}", "from": f"J{i}", "to": f"N{i}", "numLanes": "1", "speed": str(speed_ms)})
            ET.SubElement(edges_root, "edge", {"id": f"E_S{i}_to_J{i}", "from": f"S{i}", "to": f"J{i}", "numLanes": "1", "speed": str(speed_ms)})
            ET.SubElement(edges_root, "edge", {"id": f"E_J{i}_to_S{i}", "from": f"J{i}", "to": f"S{i}", "numLanes": "1", "speed": str(speed_ms)})
            
        self._write_xml(edges_root, edg_file)
        
        # Run netconvert
        try:
            subprocess.run([
                "netconvert", 
                "--node-files", nod_file, 
                "--edge-files", edg_file, 
                "--output-file", net_file,
                "--tls.default-type", "static"
            ], check=True, capture_output=True)
            logger.info(f"Generated network file: {net_file}")
        except FileNotFoundError:
            logger.warning("netconvert not found. Generating dummy net.xml for placeholder.")
            with open(net_file, "w") as f:
                f.write("<net></net>")
        except subprocess.CalledProcessError as e:
            logger.error(f"netconvert failed: {e.stderr}")
            
    def generate_routes(self, net_file: str, num_vehicles: int = 1000, vehicle_mix: dict = None):
        rou_file = os.path.join(self.output_dir, "corridor.rou.xml")
        routes_root = ET.Element("routes")
        
        if not vehicle_mix:
            vehicle_mix = {'motorcycle': 0.4, 'car': 0.25, 'auto_rickshaw': 0.15, 'bus': 0.10, 'truck': 0.10}
            
        # VTypes
        ET.SubElement(routes_root, "vType", id="car", vClass="passenger", length="4.0")
        ET.SubElement(routes_root, "vType", id="motorcycle", vClass="motorcycle", length="2.0")
        ET.SubElement(routes_root, "vType", id="bus", vClass="bus", length="10.0")
        ET.SubElement(routes_root, "vType", id="truck", vClass="truck", length="8.0")
        ET.SubElement(routes_root, "vType", id="auto_rickshaw", vClass="passenger", length="2.8", width="1.4")
        
        # Simple routes
        ET.SubElement(routes_root, "route", id="r_WE", edges="E_W_to_J0 E_J0_to_J1 E_J1_to_J2 E_J2_to_J3 E_J3_to_E")
        ET.SubElement(routes_root, "route", id="r_EW", edges="E_E_to_J3 E_J3_to_J2 E_J2_to_J1 E_J1_to_J0 E_J0_to_W")
        
        for i in range(4):
            ET.SubElement(routes_root, "route", id=f"r_N{i}S{i}", edges=f"E_N{i}_to_J{i} E_J{i}_to_S{i}")
            ET.SubElement(routes_root, "route", id=f"r_S{i}N{i}", edges=f"E_S{i}_to_J{i} E_J{i}_to_N{i}")
            
        # Generate vehicles
        routes = ["r_WE", "r_EW"] + [f"r_N{i}S{i}" for i in range(4)] + [f"r_S{i}N{i}" for i in range(4)]
        
        vtypes = list(vehicle_mix.keys())
        vweights = list(vehicle_mix.values())
        departs = sorted([random.uniform(0, 3600) for _ in range(num_vehicles)])
        
        for i in range(num_vehicles):
            vtype = random.choices(vtypes, weights=vweights)[0]
            route = random.choice(routes)
            depart = f"{departs[i]:.2f}"
            ET.SubElement(routes_root, "vehicle", {"id": f"v_{i}", "type": vtype, "route": route, "depart": depart})
            
        self._write_xml(routes_root, rou_file)
        
    def generate_demand_profile(self, profile: str = 'peak') -> dict:
        """Returns time-distribution dict based on profile."""
        if profile == 'morning_peak' or profile == 'evening_peak':
            return {
                'phases': [
                    {'start': 0, 'end': 600, 'flow_pct': 0.15},
                    {'start': 600, 'end': 2400, 'flow_pct': 0.70},
                    {'start': 2400, 'end': 3600, 'flow_pct': 0.15}
                ]
            }
        else:
            return {
                'phases': [
                    {'start': 0, 'end': 3600, 'flow_pct': 1.0}
                ]
            }
            
    def generate_config(self, net_file: str, route_file: str, begin: int = 0, end: int = 3600):
        cfg_file = os.path.join(self.output_dir, "corridor.sumocfg")
        
        root = ET.Element("configuration")
        input_elem = ET.SubElement(root, "input")
        ET.SubElement(input_elem, "net-file", value=os.path.basename(net_file))
        ET.SubElement(input_elem, "route-files", value=os.path.basename(route_file))
        
        time_elem = ET.SubElement(root, "time")
        ET.SubElement(time_elem, "begin", value=str(begin))
        ET.SubElement(time_elem, "end", value=str(end))
        
        self._write_xml(root, cfg_file)
        return cfg_file
        
    def generate_all(self):
        self.generate_corridor_network()
        net_file = os.path.join(self.output_dir, "corridor.net.xml")
        self.generate_routes(net_file)
        route_file = os.path.join(self.output_dir, "corridor.rou.xml")
        self.generate_config(net_file, route_file)
        
    def _write_xml(self, element, filepath):
        rough_string = ET.tostring(element, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        with open(filepath, "w") as f:
            f.write(reparsed.toprettyxml(indent="    "))
