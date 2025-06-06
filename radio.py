from queue import Queue
import threading
import serial
from message_router import MessageRouter
from param_manager import ParamManager
import serial.tools.list_ports
from serial_emulator import SerialEmulator
from typing import Optional, Dict, Any
from aplink.aplink_messages import *

class Radio:
    def __init__(self, ws_commands: Queue[dict], telemetry_json_output: Queue[dict]):
        self.ws_commands = ws_commands
        self.telemetry_json_output = telemetry_json_output  # JSON data sent to websocket
        self.serial_conn: Optional[serial.Serial] = None
        self.serial_emulator: Optional[SerialEmulator] = None
        self.connected = False
        self.port = ""
        self.aplink = APLink()
        self.last_param_set = 0
        self.params = []
        self.mission_items = []

        self.router = MessageRouter()
        self.router.register("connect", self._handle_connect)
        self.router.register("status", self.emit_status)
        self.router.register("get_current_mission", self._handle_get_current_mission)
        # self.router.register("get_current_params", self._handle_get_current_params)
        self.router.register("send_altitude", self._handle_send_altitude)
        self.router.register("send_params", self._handle_send_params)
        self.router.register("send_mission", self._handle_send_mission)
        self.router.register("req_params", self._handle_request_params)
        self.router.register("req_mission", self._handle_request_mission)
        
        threading.Thread(target=self._main_thread, daemon=True).start()

    # Reads ws_commands queue for messages and calls the corresponding handler
    def _main_thread(self) -> None:
        while True:
            msg = self.ws_commands.get()
            print(f"Radio receive message: {msg}")
            self.router.handle(msg)

        # message_handlers = {
        #     "connect": self._handle_connect,
        #     "status": self._handle_status,
        #     "get_current_mission": self._handle_get_current_mission,
        #     # "get_current_params": print, # Get name of DIR
        #     "send_altitude": self._handle_send_altitude,
        #     "send_params": self._handle_send_params,
        #     "send_mission": self._handle_send_mission,
        #     "req_params": self._handle_request_params,
        #     "req_mission": self._handle_request_mission,
        # }
    
    def _handle_send_altitude(self, message):
        self._transmit(aplink_set_altitude().pack(message["data"]))
    
    def _handle_get_current_mission(self, message):
        if len(self.mission_items) > 0:
            self.telemetry_json_output.put({
                "type": "mission",
                "data": self.mission_items
            })

    def _handle_connect(self, message: Dict[str, Any]) -> None:
        """Handle connection request."""
        self.connect(message["port"])

    def _handle_status(self, _: Dict[str, Any]) -> None:
        """Handle status request."""
        self.emit_status()

    def _handle_send_params(self, message: Dict[str, Any]) -> None:
        """Handle parameter sending request."""
        self.send_params(message["data"])

    def _handle_send_mission(self, message: Dict[str, Any]) -> None:
        """Handle mission sending request."""
        self.send_mission(message["data"])

    def _handle_request_params(self, _: Dict[str, Any]) -> None:
        """Handle parameter request."""
        pass  # Implement as needed

    def _handle_request_mission(self, _: Dict[str, Any]) -> None:
        """Handle mission request."""
        pass  # Implement as needed

    # Polls serial data and calls self._process_message() if packet is complete
    def _serial_thread(self) -> None:
        """Thread for continuous serial communication."""
        while True:
            byte = self._read_byte()[0]
            result = self.aplink.parse_byte(ord(byte))
            if result is not None:
                self._process_message(*result)

    def connect(self, port: str) -> None:
        """Establish connection to the specified port."""
        try:
            if port == "Testing":
                self.serial_emulator = SerialEmulator()
            else:
                self.serial_conn = serial.Serial(port, 115200, timeout=1)
            
            self.port = port
            self.connected = True
            self.emit_status()
            threading.Thread(target=self._serial_thread, daemon=True).start()
        except Exception as e:
            print(f"Failed to connect to port: {e}")
            self.port = ""
            self.connected = False
            self.emit_status()
    
    def send_params(self, params) -> None:
        """Initiate parameter sending process."""
        self.params = params
        self.last_param_set = 0
        self._send_next_param()

    def emit_status(self, message=None) -> None:
        """Send current connection status to websocket."""
        available_ports = [port.device for port in serial.tools.list_ports.comports()]
        self.telemetry_json_output.put({
            "type": "serial_status",
            "connected": self.connected,
            "port": self.port,
            "available": available_ports + ["Testing"]
        })
    
    def send_mission(self, mission_items):
        self.mission_items = mission_items
        self.last_item_set = 0
        
        self._transmit(aplink_waypoints_count().pack(len(self.mission_items)))
    
    # Read byte from serial
    def _read_byte(self) -> bytes:
        """Read a single byte from the active connection."""
        if self.port == "Testing":
            return self.serial_emulator.read(1)
        return self.serial_conn.read(1)
    
    # Transmit bytes over serial
    def _transmit(self, data: bytes) -> None:
        """Send data through the active connection."""
        if self.port == "Testing":
            self.serial_emulator.write(data)
        else:
            self.serial_conn.write(data)
    
    # Calls the corresponding handler for serial messages which then sends message to websocket frontend
    def _process_message(self, payload: bytes, msg_id: int) -> None:
        """Process incoming messages based on their ID."""
        message_handlers = {
            aplink_vehicle_status_full.msg_id: self._handle_vehicle_status,
            aplink_gps_raw.msg_id: self._handle_gps_raw,
            aplink_power.msg_id: self._handle_power,
            aplink_param_set.msg_id: self._handle_param_set,
            aplink_request_waypoint.msg_id: self._handle_request_waypoint,
            aplink_waypoints_ack.msg_id: self._handle_waypoints_ack,
            aplink_set_altitude_result.msg_id: self._handle_set_altitude_result,
            aplink_control_setpoints.msg_id: self._handle_control_setpoints,
            aplink_cal_sensors.msg_id: self._handle_cal_sensors
        }
        
        handler = message_handlers.get(msg_id)
        if handler:
            handler(payload)
    
    def _handle_cal_sensors(self, payload):
        msg = aplink_cal_sensors()
        msg.unpack(payload)
        print(vars(msg))
    
    def _handle_gps_raw(self, payload):
        msg = aplink_gps_raw()
        msg.unpack(payload)

        json = vars(msg)
        json["type"] = "gps_raw"

        self.telemetry_json_output.put(json)

    def _handle_power(self, payload):
        msg = aplink_power()
        msg.unpack(payload)

        json = vars(msg)
        json["type"] = "power"
        json["batt_volt"] = float(json["batt_volt"]) / 1e2

        self.telemetry_json_output.put(json)
    
    def _handle_control_setpoints(self, payload):
        msg = aplink_control_setpoints()
        msg.unpack(payload)
        
        json = vars(msg)
        json["type"] = "control_setpoints"

        self.telemetry_json_output.put(json)

    def _handle_set_altitude_result(self, payload):
        msg = aplink_set_altitude_result()
        msg.unpack(payload)
        self.telemetry_json_output.put({
            "type": "set_altitude_result",
            "data": msg.success
        })
    
    def _handle_waypoints_ack(self, payload):
        waypoints_ack = aplink_waypoints_ack()
        waypoints_ack.unpack(payload)
        print(f"SENDING MISSION RESULT: {waypoints_ack.success}")

        mission_items = self.mission_items.copy()

        self.telemetry_json_output.put({
            "type": "mission",
            "data": mission_items
        })
    
    def _handle_request_waypoint(self, payload):
        request_waypoint = aplink_request_waypoint()
        request_waypoint.unpack(payload)

        mission_item = self.mission_items[request_waypoint.index]

        if mission_item["type"] == "waypoint":
            type = MISSION_ITEM_TYPE.WAYPOINT
        elif mission_item["type"] == "loiter":
            type = MISSION_ITEM_TYPE.LOITER
        elif mission_item["type"] == "land":
            type = MISSION_ITEM_TYPE.LAND
        
        if mission_item["direction"] == "left":
            direction = LOITER_DIRECTION.LEFT
        else:
            direction = LOITER_DIRECTION.RIGHT
        
        self._transmit(aplink_mission_item().pack(
            type=type,
            lat=int(mission_item["lat"] * 1e7),
            lon=int(mission_item["lon"] * 1e7),
            radius=mission_item["radius"],
            direction=direction,
            final_leg=mission_item["final_leg"],
            glideslope=mission_item["glideslope"],
            runway_heading=mission_item["runway_heading"]
        ))

    def _handle_vehicle_status(self, payload: bytes) -> None:
        """Handle vehicle status messages."""
        vehicle_status = aplink_vehicle_status_full()
        vehicle_status.unpack(payload)

        status_json = vars(vehicle_status)

        mode_mapping = {
            MODE_ID.CONFIG: "CFG",
            MODE_ID.TAKEOFF: "TKO",
            MODE_ID.LAND: "LND",
        }

        # Modify and scale
        status_json["type"] = "vehicle_status"
        status_json["yaw"] = float(status_json["yaw"]) / 1e2
        status_json["alt"] = float(status_json["alt"]) / 1e2
        status_json["lat"] = float(status_json["lat"]) / 1e7
        status_json["lon"] = float(status_json["lon"]) / 1e7
        status_json["mode"] = mode_mapping.get(vehicle_status.mode_id, "UNK")
        
        self.telemetry_json_output.put(status_json)
    
    def _handle_param_set(self, _: bytes) -> None:
        """Handle parameter set acknowledgment."""
        if self.last_param_set == len(self.params):
            self.telemetry_json_output.put({"type": "param_set_success"})
        else:
            self._send_next_param()
            self.telemetry_json_output.put({
                "type": "param_set_progress",
                "progress": self.last_param_set,
                "total": len(self.params)
            })
    
    def _send_next_param(self) -> None:
        """Send the next parameter in the queue."""
        param = self.params[self.last_param_set]
        param_name = list(param["name"].ljust(16, '\x00').encode('utf-8'))
        
        type_mapping = {
            "f": (PARAM_TYPE.FLOAT, '=f'),
            "i": (PARAM_TYPE.INT32, '=i'),
        }
        
        param_type, pack_format = type_mapping.get(param["type"], (None, None))
        if param_type is None:
            return
            
        param_value = list(struct.pack(pack_format, param["value"]))
        self._transmit(aplink_param_set().pack(param_name, param_value, int(param_type)))
        
        print(f"Sent parameter {param['name']}")
        self.last_param_set += 1