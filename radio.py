from queue import Queue
import threading
import serial
import serial.tools.list_ports
from serial_emulator import SerialEmulator
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from aplink.aplink_messages import *

@dataclass
class Param:
    name: str
    value: float
    type: str

class Radio:
    def __init__(self, radio_input: Queue[dict], ws_input: Queue[dict]):
        self.radio_input = radio_input
        self.ws_input = ws_input  # JSON data sent to websocket
        self.serial_conn: Optional[serial.Serial] = None
        self.serial_emulator: Optional[SerialEmulator] = None
        self.connected = False
        self.port = ""
        self.aplink = APLink()
        self.last_param_set = 0
        self.params: List[Param] = []
        
        threading.Thread(target=self._main_thread, daemon=True).start()

    def _main_thread(self) -> None:
        """Main processing thread that handles incoming messages."""
        message_handlers = {
            "connect": self._handle_connect,
            "status": self._handle_status,
            "send_params": self._handle_send_params,
            "send_mission": self._handle_send_mission,
            "req_params": self._handle_request_params,
            "req_mission": self._handle_request_mission,
        }
        
        while True:
            message = self.radio_input.get()
            handler = message_handlers.get(message["type"])
            if handler:
                handler(message)

    def _handle_connect(self, message: Dict[str, Any]) -> None:
        """Handle connection request."""
        self.connect(message["port"])

    def _handle_status(self, _: Dict[str, Any]) -> None:
        """Handle status request."""
        self.emit_status()

    def _handle_send_params(self, message: Dict[str, Any]) -> None:
        """Handle parameter sending request."""
        self.send_params(message["params"])

    def _handle_send_mission(self, _: Dict[str, Any]) -> None:
        """Handle mission sending request."""
        pass  # Implement as needed

    def _handle_request_params(self, _: Dict[str, Any]) -> None:
        """Handle parameter request."""
        pass  # Implement as needed

    def _handle_request_mission(self, _: Dict[str, Any]) -> None:
        """Handle mission request."""
        pass  # Implement as needed

    def _serial_thread(self) -> None:
        """Thread for continuous serial communication."""
        while True:
            byte = self._read_byte()
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

    def emit_status(self) -> None:
        """Send current connection status to websocket."""
        available_ports = [port.device for port in serial.tools.list_ports.comports()]
        self.ws_input.put({
            "type": "serial_status",
            "connected": self.connected,
            "port": self.port,
            "available": available_ports + ["Testing"]
        })
    
    def send_params(self, params: List[Param]) -> None:
        """Initiate parameter sending process."""
        self.params = params
        self.last_param_set = 0
        self._send_next_param()
    
    def _read_byte(self) -> bytes:
        """Read a single byte from the active connection."""
        if self.port == "Testing":
            return self.serial_emulator.read(1)
        return self.serial_conn.read(1)
    
    def transmit(self, data: bytes) -> None:
        """Send data through the active connection."""
        if self.port == "Testing":
            self.serial_emulator.write(data)
        else:
            self.serial_conn.write(data)
    
    def _process_message(self, payload: bytes, msg_id: int) -> None:
        """Process incoming messages based on their ID."""
        message_handlers = {
            aplink_vehicle_status_full.msg_id: self._handle_vehicle_status,
            aplink_param_set.msg_id: self._handle_param_set,
        }
        
        handler = message_handlers.get(msg_id)
        if handler:
            handler(payload)

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

        status_json["type"] = "vehicle_status"
        status_json["mode"] = mode_mapping.get(vehicle_status.mode_id, "UNK")
        
        self.ws_input.put(status_json)

    def _handle_param_set(self, _: bytes) -> None:
        """Handle parameter set acknowledgment."""
        if self.last_param_set == len(self.params):
            self.ws_input.put({"type": "param_set_success"})
        else:
            self._send_next_param()
            self.ws_input.put({
                "type": "param_set_progress",
                "progress": self.last_param_set,
                "total": len(self.params)
            })
    
    def _send_next_param(self) -> None:
        """Send the next parameter in the queue."""
        param = self.params[self.last_param_set]
        param_name = list(param.name.ljust(16, '\x00').encode('utf-8'))
        
        type_mapping = {
            "f": (PARAM_TYPE.FLOAT, '=f'),
            "i": (PARAM_TYPE.INT32, '=i'),
        }
        
        param_type, pack_format = type_mapping.get(param.type, (None, None))
        if param_type is None:
            return
            
        param_value = list(struct.pack(pack_format, param.value))
        self.transmit(aplink_param_set().pack(param_name, param_value, int(param_type)))
        
        print(f"Sent parameter {param.name}")
        self.last_param_set += 1