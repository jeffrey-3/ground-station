from status import SystemStatus
import math
import time
import threading
import serial
from base_radio import BaseRadio
from dataclasses import dataclass
from typing import List
from aplink.aplink_messages import *

@dataclass
class Param:
    name: str
    value: float
    type: str

class SerialRadio(BaseRadio):    
    testing: bool
    ser: serial.Serial
    status: SystemStatus
    aplink: APLink = APLink()
    last_param_set: int
    params: List[Param]

    test_bytes = []

    def __init__(self, status: SystemStatus):
        self.status = status
        self.testing = False
        self.last_param_set = 0

    def connect(self, port):
        try:
            if port == "Testing":
                self.testing = True
                threading.Thread(target=self.generate_fake_telemetry, daemon=True).start()
            else:
                self.ser = serial.Serial(port, 115200, timeout=1)

            threading.Thread(target=self.loop, daemon=True).start()
            self.status.serial.connected_port = port
            self.status.serial.connect_status = "Connected"
        except:
            print("Failed to connect to port")
            self.status.serial.connect_status = "Fail"
    
    def loop(self):
        while True:
            byte = self.read()
            result = self.aplink.parse_byte(ord(byte))
            if result is not None:
                payload, msg_id = result

                print(f"Radio Received msg_id: {msg_id}")

                self.process_message(payload, msg_id)
    
    def read(self):
        if self.testing:
            return self.test_bytes.pop(0)
        else:
            return self.ser.read(1)

    def upload_params(self, params: List[Param]):
        self.params = params
        self.last_param_set = 0

        self.send_next_param()
    
    def send_next_param(self):
        param = self.params[self.last_param_set]
        param_name = list(param.name.ljust(16, '\x00').encode('utf-8'))
        if param.type == "f":
            param_type = int(PARAM_TYPE.FLOAT)
            param_value = list(struct.pack('=f', param.value))
        elif param.type == "i":
            param_type = int(PARAM_TYPE.INT32)
            param_value = list(struct.pack('=i', param.value))

        self.radio.transmit(aplink_param_set().pack(param_name, param_value, param_type))

        print(f"Sent parameter {param_name}")

        self.last_param_set += 1
    
    def generate_fake_telemetry(self):
        # Instead, generate bytes with aplink

        # self.status.telemetry.batt_voltage = 3 + 1 * math.sin(time.time() / 2)
        # self.status.telemetry.heading = 45 * math.sin(time.time() / 2)
        # self.status.telemetry.lat = 43.8791 + 0.0001 * math.sin(time.time())
        # self.status.telemetry.lon = -79.4135 + 0.0001 * math.sin(time.time())
        # self.status.telemetry.gps_sats = int(16 + 4 * math.sin(time.time()))

        return
    
    def process_message(self, payload, msg_id):
        if msg_id == aplink_vehicle_status_full.msg_id:
            vehicle_status = aplink_vehicle_status_full()
            vehicle_status.unpack(payload)
            if vehicle_status.mode_id == MODE_ID.CONFIG:
                self.status.telemetry.status = "CFG"
            elif vehicle_status.mode_id == MODE_ID.TAKEOFF:
                self.status.telemetry.status = "TKO"
            elif vehicle_status.mode_id == MODE_ID.LAND:
                self.status.telemetry.status = "LND"
        elif msg_id == aplink_param_set.msg_id:
            if self.last_param_set == len(self.params):
                return # Success
            else:
                self.send_next_param()