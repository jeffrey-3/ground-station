from queue import Queue
import threading
import serial
import serial.tools.list_ports
import time
import math
from aplink.aplink_messages import *

class SerialRadio():    
    ser: serial.Serial
    dummy_serial_rx_buff: Queue[bytes] = Queue()
    dummy_serial_tx_buff: Queue[bytes] = Queue()
    connected: bool = False
    port: str = ""

    def __init__(self, radio_input: Queue[dict], ws_input: Queue[dict]):
        self.radio_input: Queue = radio_input
        self.ws_input: Queue = ws_input # JSON data sent to websocket
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while True:
            input = self.radio_input.get()

            if input.type == "connect":
                self.connect(input.port)
            elif input.type == "status":
                self.emit_status()

    def connect(self, port: str):
        try:
            if self.port == "Testing":
                threading.Thread(target=self.dummy_serial_thread, daemon=True).start()
            else:
                self.ser = serial.Serial(port, 115200, timeout=1)
            self.port = port
            self.connected = True
            self.emit_status()
            threading.Thread(target=self.read, daemon=True).start()
        except:
            print("Failed to connect to port")
            self.port = ""
            self.connected = False
            self.emit_status()

    def emit_status(self):
        self.ws_input.put({
            "type": "serial_status",
            "connected": self.connected,
            "port": self.port,
            "available": [port.device for port in serial.tools.list_ports.comports()] + ["Testing"]
        })
    
    def read(self):
        while True:
            byte = self.read_byte()
            result = self.aplink.parse_byte(ord(byte))
            if result is not None:
                self.process_message(*result)
    
    def read_byte(self):
        if self.port == "Testing":
            return self.dummy_serial_rx_buff.get()
        else:
            return self.ser.read(1)
    
    def transmit(self, bytes):
        if self.port == "Testing":
            self.dummy_serial_tx_buff.put(bytes)
        else:
            self.ser.write(bytes)
    
    def process_message(self, payload, msg_id):
        if msg_id == aplink_vehicle_status_full.msg_id:
            vehicle_status = aplink_vehicle_status_full()
            vehicle_status.unpack(payload)

            if vehicle_status.mode_id == MODE_ID.CONFIG:
                status = "CFG"
            elif vehicle_status.mode_id == MODE_ID.TAKEOFF:
                status = "TKO"
            elif vehicle_status.mode_id == MODE_ID.LAND:
                status = "LND"
            
            self.ws_input.put({
                "type": "vehicle_status",
                "mode": status,
                "roll": vehicle_status.roll,
                "pitch": vehicle_status.pitch,
                "heading": vehicle_status.yaw
            })
        elif msg_id == aplink_param_set.msg_id:
            if self.last_param_set == len(self.params):
                self.ws_input.put({
                    "type": "param_set_success"
                })
            else:
                self.send_next_param()
                self.ws_input.put({
                    "type": "param_set_progress",
                    "progress": self.last_param_set,
                    "total": len(self.params)
                })
    
    def send_next_param(self):
        param = self.params[self.last_param_set]
        param_name = list(param.name.ljust(16, '\x00').encode('utf-8'))
        if param.type == "f":
            param_type = int(PARAM_TYPE.FLOAT)
            param_value = list(struct.pack('=f', param.value))
        elif param.type == "i":
            param_type = int(PARAM_TYPE.INT32)
            param_value = list(struct.pack('=i', param.value))

        self.transmit(aplink_param_set().pack(param_name, param_value, param_type))

        print(f"Sent parameter {param_name}")

        self.last_param_set += 1
    
    def dummy_serial_thread(self):
        while True:
            self.dummy_serial_rx_buff.put(aplink_vehicle_status_full().pack(
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                43.8791 + 0.0001 * math.sin(time.time()),
                -79.4135 + 0.0001 * math.sin(time.time()),
                0,
                0
            ))

            self.dummy_serial_rx_buff.put(aplink_gps_raw().pack(
                0,
                0,
                int(16 + 4 * math.sin(time.time())),
                True
            ))

            time.sleep(0.03)