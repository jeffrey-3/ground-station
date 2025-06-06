from queue import Queue
import threading
import serial
import serial.tools.list_ports
from serial_emulator import SerialEmulator
from typing import Optional, Dict, Any
from aplink.aplink_messages import *
from param_manager import ParamManager
from mission_manager import MissionManager

class Radio:
    def __init__(self, ws_commands: Queue[dict], telemetry_json_output: Queue[dict]):
        self.ws_commands = ws_commands
        self.telemetry_json_output = telemetry_json_output  # JSON data sent to websocket
        self.serial_conn: Optional[serial.Serial] = None
        self.serial_emulator: Optional[SerialEmulator] = None
        self.connected = False
        self.port = ""
        self.aplink = APLink()

        self.mission_manager = MissionManager(self._transmit, self.telemetry_json_output)
        self.param_manager = ParamManager(self._transmit, self.telemetry_json_output)
        
        threading.Thread(target=self._main_thread, daemon=True).start()

    # Reads ws_commands queue for messages and calls the corresponding handler
    def _main_thread(self) -> None:
        message_handlers = {
            "connect": self._handle_connect,
            "status": self._handle_status,
            "get_current_mission": self.mission_manager.handle_get_current_mission,
            "get_current_params": self._handle_get_current_params,
            "send_altitude": self._handle_send_altitude,
            "send_params": self.param_manager.send_params,
            "send_mission": self.mission_manager.send_mission,
            "req_params": self._handle_request_params,
            "req_mission": self._handle_request_mission,
        }
        
        while True:
            message = self.ws_commands.get()
            print(f"Radio receive message: {message}")
            handler = message_handlers.get(message["type"])
            if handler:
                handler(message)
    
    def _handle_get_current_params(self, message):
        pass
    
    def _handle_send_altitude(self, message):
        self._transmit(aplink_set_altitude().pack(message["data"]))

    def _handle_connect(self, message: Dict[str, Any]) -> None:
        self.connect(message["port"])

    def _handle_status(self, _: Dict[str, Any]) -> None:
        self.emit_status()

    def _handle_request_params(self, _: Dict[str, Any]) -> None:
        pass

    def _handle_request_mission(self, _: Dict[str, Any]) -> None:
        pass

    # Polls serial data and calls self._process_message() if packet is complete
    def _serial_thread(self) -> None:
        while True:
            byte = self._read_byte()[0]
            result = self.aplink.parse_byte(ord(byte))
            if result is not None:
                self._process_message(*result)

    def connect(self, port: str) -> None:
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

    def emit_status(self) -> None:
        available_ports = [port.device for port in serial.tools.list_ports.comports()]
        self.telemetry_json_output.put({
            "type": "serial_status",
            "connected": self.connected,
            "port": self.port,
            "available": available_ports + ["Testing"]
        })
    
    # Read byte from serial
    def _read_byte(self) -> bytes:
        if self.port == "Testing":
            return self.serial_emulator.read(1)
        return self.serial_conn.read(1)
    
    # Transmit bytes over serial
    def _transmit(self, data: bytes) -> None:
        if self.port == "Testing":
            self.serial_emulator.write(data)
        else:
            self.serial_conn.write(data)
    
    # Calls the corresponding handler for serial messages which then sends message to websocket frontend
    def _process_message(self, payload: bytes, msg_id: int) -> None:
        message_handlers = {
            aplink_vehicle_status_full.msg_id: self._handle_vehicle_status,
            aplink_gps_raw.msg_id: self._handle_gps_raw,
            aplink_power.msg_id: self._handle_power,
            aplink_param_set.msg_id: self.param_manager.handle_param_set,
            aplink_request_waypoint.msg_id: self.mission_manager.handle_request_waypoint,
            aplink_waypoints_ack.msg_id: self.mission_manager.handle_waypoints_ack,
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

    def _handle_vehicle_status(self, payload: bytes) -> None:
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