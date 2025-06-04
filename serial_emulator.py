from aplink.aplink_messages import *
import threading
import time
import math

class SerialEmulator:
    def __init__(self):
        self.aplink = APLink()
        self.rx_buff = []
        self.tx_buff = []
        self.num_items = 0
        self.last_item_received = 0
        threading.Thread(target=self._thread, daemon=True).start()
    
    def write(self, bytes):
        for byte in bytes:
            self.rx_buff.append(byte)

    def read(self, num):
        while len(self.tx_buff) < num:
            time.sleep(0.0001)
        return [struct.pack("=B", self.tx_buff.pop(0)) for i in range(num)]
    
    def _thread(self):
        while True:
            self._generate_fake_telemetry()
            self._generate_ack()
            time.sleep(0.03)
    
    def _generate_ack(self):
        while len(self.rx_buff) > 0:
            byte = struct.pack("=B", self.rx_buff.pop(0))
            result = self.aplink.parse_byte(ord(byte))
            if result is not None:
                payload, msg_id = result
                if msg_id == aplink_param_set.msg_id:
                    param_set = aplink_param_set()
                    param_set.unpack(payload)

                    # Return ack for param set by echoing payload back
                    for byte in aplink_param_set().pack(param_set.name, param_set.value, param_set.type):
                        self.tx_buff.append(byte) 
                elif msg_id == aplink_waypoints_count.msg_id:
                    waypoints_count = aplink_waypoints_count()
                    waypoints_count.unpack(payload)

                    self.num_items = waypoints_count.num_waypoints
                    self.last_item_received = 0

                    for byte in aplink_request_waypoint().pack(self.last_item_received):
                        self.tx_buff.append(byte)
                elif msg_id == aplink_mission_item.msg_id:
                    mission_item = aplink_mission_item()
                    mission_item.unpack(payload)

                    self.last_item_received += 1

                    if self.last_item_received == self.num_items:
                        for byte in aplink_waypoints_ack().pack(True):
                            self.tx_buff.append(byte)
                    else:
                        for byte in aplink_request_waypoint().pack(self.last_item_received):
                            self.tx_buff.append(byte)
    
    def _generate_fake_telemetry(self):
        for byte in aplink_vehicle_status_full().pack(
            roll=0,
            pitch=0,
            yaw=int(100 * (45 * math.sin(time.time() / 2))),
            alt=0,
            spd=0,
            lat=int(1e7 * (43.8791 + 0.0001 * math.sin(time.time()))),
            lon=int(1e7 * (-79.4135 + 0.0001 * math.sin(time.time()))),
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
            batt_volt=int(3 + 1 * math.sin(time.time() / 2)),
            batt_curr=0,
            batt_used=0,
            ap_curr=0
        ): 
            self.tx_buff.append(byte)