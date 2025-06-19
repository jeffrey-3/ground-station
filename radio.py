from queue import Queue
import threading
import serial
import serial.tools.list_ports
from serial_emulator import SerialEmulator
from typing import Optional, Dict, Any
from aplink.aplink_messages import *
from param_manager import ParamManager
from mission_manager import MissionManager
from telemetry_manager import TelemetryManager
from altitude_manager import AltitudeManager
from calibration_manager import CalibrationManager

class Radio:
    def __init__(self, ws_commands: Queue[dict], telemetry_json_output: Queue[dict]):
        self.ws_commands = ws_commands
        self.telemetry_json_output = telemetry_json_output  # JSON data sent to websocket
        self.serial_conn: Optional[serial.Serial] = None
        self.serial_emulator: Optional[SerialEmulator] = None
        self.connected = False
        self.port = ""
        self.aplink = APLink()

        self.telemetry_manager = TelemetryManager(self._transmit, self.telemetry_json_output)
        self.mission_manager = MissionManager(self._transmit, self.telemetry_json_output)
        self.param_manager = ParamManager(self._transmit, self.telemetry_json_output)
        self.altitude_manager = AltitudeManager(self._transmit, self.telemetry_json_output)
        self.calibration_manager = CalibrationManager(self._transmit, self.telemetry_json_output)

        threading.Thread(target=self._main_thread, daemon=True).start()

    # Reads ws_commands queue for messages and calls the corresponding handler
    def _main_thread(self) -> None:
        message_handlers = {
            "connect": self._handle_connect,
            "status": self._handle_status,
            "get_current_mission": self.mission_manager.handle_get_current_mission,
            # "get_current_params": self._handle_get_current_params,
            "send_altitude": self.altitude_manager.send_altitude,
            "send_params": self.param_manager.send_params,
            "send_mission": self.mission_manager.send_mission,
            # "req_params": self._handle_request_params,
            # "req_mission": self._handle_request_mission,
            "cal_gyro": self.calibration_manager.cal_gyro
        }
        
        while True:
            message = self.ws_commands.get()

            print(f"Radio receive message: {message}")
            
            handler = message_handlers.get(message["type"])
            if handler:
                handler(message)

    def _handle_connect(self, message: Dict[str, Any]) -> None:
        try:
            if message["port"] == "Testing":
                self.serial_emulator = SerialEmulator()
            else:
                self.serial_conn = serial.Serial(message["port"], 115200, timeout=None)
            
            self.port = message["port"]
            self.connected = True
            self._emit_status()
            threading.Thread(target=self._serial_thread, daemon=True).start()
        except Exception as e:
            print(f"Failed to connect to port: {e}")
            self.port = ""
            self.connected = False
            self._emit_status()

    def _handle_status(self, _: Dict[str, Any]) -> None:
        self._emit_status()

    # Polls serial data and calls self._process_message() if packet is complete
    def _serial_thread(self) -> None:
        while True:
            byte = self._read_byte()
            result = self.aplink.parse_byte(ord(byte))
            if result is not None:
                self._process_message(*result)
    
    # Calls the corresponding handler for serial messages which then sends message to websocket frontend
    def _process_message(self, payload: bytes, msg_id: int) -> None:
        message_handlers = {
            aplink_vehicle_status_full.msg_id: self.telemetry_manager.handle_vehicle_status,
            aplink_gps_raw.msg_id: self.telemetry_manager.handle_gps_raw,
            aplink_power.msg_id: self.telemetry_manager.handle_power,
            aplink_control_setpoints.msg_id: self.telemetry_manager.handle_control_setpoints,
            aplink_cal_sensors.msg_id: self.calibration_manager.handle_cal_sensors,
            aplink_param_set.msg_id: self.param_manager.handle_param_set,
            aplink_request_waypoint.msg_id: self.mission_manager.handle_request_waypoint,
            aplink_waypoints_ack.msg_id: self.mission_manager.handle_waypoints_ack,
            aplink_set_altitude_result.msg_id: self.altitude_manager.handle_set_altitude_result
        }
        
        handler = message_handlers.get(msg_id)
        if handler:
            handler(payload)

    def _emit_status(self) -> None:
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