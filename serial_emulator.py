from aplink.aplink_messages import *
import threading
import time
from typing import List
import math

class SerialEmulator:
    def __init__(self):
        self.aplink = APLink()
        self.rx_buff = List[bytes]
        self.tx_buff = List[bytes]
        threading.Thread(self._thread, daemon=True).start()
    
    def write(self, bytes):
        for byte in bytes:
            self.rx_buff.append(byte)

    def read(self, num):
        return [self.tx_buff.pop(0) for i in range(num)]
    
    def _thread(self):
        while True:
            self._generate_fake_telemetry()
            self._generate_ack()
            time.sleep(0.03)
    
    def _generate_ack(self):
        while len(self.rx_buff) > 0:
            byte = self.rx_buff.pop(0)
            result = self.aplink.parse_byte(ord(byte))
            if result is not None:
                payload, msg_id = result
                if msg_id == aplink_param_set.msg_id:
                    for byte in payload:
                        self.tx_buff.append(byte) # Return ack for param set by echoing payload back
    
    def _generate_fake_telemetry(self):
        for byte in aplink_vehicle_status_full().pack(
            roll=0,
            roll_sp=0,
            pitch=0,
            pitch_sp=0,
            yaw=45 * math.sin(time.time() / 2),
            alt=0,
            alt_sp=0,
            spd=0,
            spd_sp=0,
            lat=43.8791 + 0.0001 * math.sin(time.time()),
            lon=-79.4135 + 0.0001 * math.sin(time.time()),
            current_waypoint=0,
            mode_id=0
        ): 
            self.tx_buff.append(byte) 

        for byte in aplink_gps_raw().pack(
            lat=0,
            lon=0,
            sats=int(16 + 4 * math.sin(time.time())),
            fix=True
        ): 
            self.tx_buff.append(byte)

        for byte in aplink_power().pack(
            batt_volt=3 + 1 * math.sin(time.time() / 2),
            batt_curr=0,
            batt_used=0,
            ap_curr=0
        ): 
            self.tx_buff.append(byte)