from aplink.aplink_messages import *

class TelemetryManager:
    def __init__(self, send_fn, telemetry_queue):
        self.send_fn = send_fn
        self.telemetry_queue = telemetry_queue
    
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

        self.telemetry_json_output.put(json)

    def handle_vehicle_status(self, payload: bytes) -> None:
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