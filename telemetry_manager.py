from aplink.aplink_messages import *
import csv
import time
from dataclasses import dataclass, fields

# Tab for web page has to be closed before closing the backend otherwise file will not save (corrupt)

@dataclass
class LogMessage:
    time: float = 0
    altitude: float = 0
    altitude_target: float = 0
    speed: float = 0
    speed_target: float = 0

class TelemetryManager:
    def __init__(self, send_fn, telemetry_json_output):
        self.send_fn = send_fn
        self.telemetry_json_output = telemetry_json_output

        self.start_time = None
        file = open(f"logs/log_{int(time.time())}.csv", "w", newline="")
        fieldnames = [field.name for field in fields(LogMessage)]
        self.writer = csv.DictWriter(file, fieldnames=fieldnames)
        self.writer.writeheader()
        self.log_message = LogMessage()
    
    def handle_cal_sensors(self, payload):
        msg = aplink_cal_sensors()
        msg.unpack(payload)
        print(vars(msg))
    
    def handle_gps_raw(self, payload):
        msg = aplink_gps_raw()
        msg.unpack(payload)

        json = vars(msg)
        json["type"] = "gps_raw"

        self.telemetry_json_output.put(json)

    def handle_power(self, payload):
        msg = aplink_power()
        msg.unpack(payload)

        json = vars(msg)
        json["type"] = "power"
        json["batt_volt"] = float(json["batt_volt"]) / 1e2

        self.telemetry_json_output.put(json)
    
    def handle_control_setpoints(self, payload):
        msg = aplink_control_setpoints()
        msg.unpack(payload)
        
        json = vars(msg)
        json["type"] = "control_setpoints"
        json["roll_sp"] /= 1e2
        json["pitch_sp"] /= 1e2
        json["alt_sp"] /= 1e2
        json["spd_sp"] /= 1e2

        self.telemetry_json_output.put(json)

    def handle_vehicle_status(self, payload: bytes) -> None:
        vehicle_status = aplink_vehicle_status_full()
        vehicle_status.unpack(payload)

        status_json = vars(vehicle_status)

        mode_mapping = {
            MODE_ID.CONFIG: "CFG",
            MODE_ID.STARTUP: "STR",
            MODE_ID.MANUAL: "MAN",
            MODE_ID.FBW: "FBW",
            MODE_ID.TAKEOFF: "TKO",
            MODE_ID.MISSION: "MIS",
        }

        # Modify and scale
        status_json["type"] = "vehicle_status"
        status_json["roll"] /= 1e2
        status_json["pitch"] /= 1e2
        status_json["yaw"] /= 1e2
        status_json["alt"] /= 1e2
        status_json["lat"] /= 1e7
        status_json["lon"] /= 1e7
        status_json["mode"] = mode_mapping.get(vehicle_status.mode_id, "UNK")
        
        self.telemetry_json_output.put(status_json)

        # Write to log
        self.log_message.speed = float(vehicle_status.spd) / 1e2
        self.log_message.altitude = float(vehicle_status.alt) / 1e2
        self._write_log()
    
    def _write_log(self):
        if not self.start_time:
            self.start_time = time.time()

        self.log_message.time = time.time() - self.start_time
        self.writer.writerows([vars(self.log_message)])