from aplink.aplink_messages import *

class AltitudeManager:
    def __init__(self, send_fn, telemetry_json_output):
        self.send_fn = send_fn
        self.telemetry_json_output = telemetry_json_output
    
    def send_altitude(self, message):
        self._transmit(aplink_set_altitude().pack(message["data"]))
    
    def handle_set_altitude_result(self, payload):
        msg = aplink_set_altitude_result()
        msg.unpack(payload)
        self.telemetry_json_output.put({
            "type": "set_altitude_result",
            "data": msg.success
        })