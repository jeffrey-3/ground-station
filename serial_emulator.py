from aplink.aplink_messages import *
import threading
import time
import math
import struct

class SerialEmulator:
    def __init__(self):
        self.aplink = APLink()
        self.rx_buff = []
        self.tx_buff = []
        self.num_items = 0
        self.last_item_received = 0
        threading.Thread(target=self._thread, daemon=True).start()

    def write(self, bytes):
        self.rx_buff.extend(bytes)

    def read(self, num):
        while len(self.tx_buff) < num:
            time.sleep(0.0001)
        data = bytes(self.tx_buff[:num])
        del self.tx_buff[:num]
        return data

    def _thread(self):
        while True:
            self._process_incoming_data()
            self._generate_fake_telemetry()
            time.sleep(0.03)

    def _process_incoming_data(self):
        while self.rx_buff:
            byte = struct.pack("=B", self.rx_buff.pop(0))
            result = self.aplink.parse_byte(ord(byte))
            if result is not None:
                payload, msg_id = result
                self._handle_message(msg_id, payload)

    def _handle_message(self, msg_id, payload):
        if msg_id == aplink_param_set.msg_id:
            self._handle_param_set(payload)
        elif msg_id == aplink_waypoints_count.msg_id:
            self._handle_waypoints_count(payload)
        elif msg_id == aplink_mission_item.msg_id:
            self._handle_mission_item(payload)
        elif msg_id == aplink_set_altitude.msg_id:
            self._handle_set_altitude(payload)
        elif msg_id == aplink_request_cal_sensors.msg_id:
            self._handle_request_cal_sensors(payload)

    def _handle_param_set(self, payload):
        msg = aplink_param_set()
        msg.unpack(payload)
        self._send_bytes(msg.pack(msg.name, msg.value, msg.type))

    def _handle_set_altitude(self, payload):
        self._send_bytes(aplink_set_altitude_result().pack(True))

    def _handle_waypoints_count(self, payload):
        msg = aplink_waypoints_count()
        msg.unpack(payload)
        self.num_items = msg.num_waypoints
        self.last_item_received = 0
        self._send_bytes(aplink_request_waypoint().pack(self.last_item_received))

    def _handle_mission_item(self, payload):
        msg = aplink_mission_item()
        msg.unpack(payload)
        self.last_item_received += 1
        if self.last_item_received == self.num_items:
            self._send_bytes(aplink_waypoints_ack().pack(True))
        else:
            self._send_bytes(aplink_request_waypoint().pack(self.last_item_received))
    
    def _handle_request_cal_sensors(self, payload):
        self._send_bytes(aplink_cal_sensors().pack(
            gx=0.5,
            gy=0.13434,
            gz=0.2,
            ax=0,
            ay=0,
            az=0,
            mx=0,
            my=0,
            mz=0
        ))

    def _generate_fake_telemetry(self):
        t = time.time()
        self._send_bytes(aplink_vehicle_status_full().pack(
            roll=int(100 * (20 * math.sin(t / 2))),
            pitch=int(100 * (40 * math.sin(t / 2))),
            yaw=int(100 * (45 * math.sin(t / 2))),
            alt=int(100 * (11 + 1 * math.sin(t))),
            spd=0,
            lat=int(1e7 * (43.8791 + 0.0001 * math.sin(t))),
            lon=int(1e7 * (-79.4135 + 0.0001 * math.sin(t))),
            mode_id=0
        ))

        self._send_bytes(aplink_control_setpoints().pack(
            roll_sp=0,
            pitch_sp=0,
            alt_sp=int(15 + 10 * math.sin(t / 2)),
            spd_sp=0,
            current_waypoint=0
        ))

        self._send_bytes(aplink_gps_raw().pack(
            lat=0,
            lon=0,
            sats=int(16 + 4 * math.sin(t)),
            fix=True
        ))

        self._send_bytes(aplink_power().pack(
            batt_volt=int(100 * (3 + 1 * math.sin(t / 2))),
            batt_curr=0,
            batt_used=0,
            ap_curr=0
        ))

    def _send_bytes(self, byte_seq):
        self.tx_buff.extend(byte_seq)
