from aplink.aplink_messages import *
from enum import Enum
from dataclasses import dataclass

@dataclass
class Data:
    x: float
    y: float
    z: float

class Mode(Enum):
    GYRO = 0
    ACCEL = 1
    MAG = 2

class CalibrationManager:
    def __init__(self, send_fn, telemetry_json_output):
        self.send_fn = send_fn
        self.telemetry_json_output = telemetry_json_output
        self.mode = Mode.GYRO
        self.buffer = []
    
    def start_calibration(self, mode: Mode):
        self.send_fn(aplink_request_cal_sensors().pack(0))
        self.mode = mode
        self.buffer = []

    def handle_cal_sensors(self, payload):
        msg = aplink_cal_sensors()
        msg.unpack(payload)

        if self.mode == Mode.GYRO:
            self.buffer.append(Data(
                msg.gx,
                msg.gy,
                msg.gz
            ))
        elif self.mode == Mode.ACCEL:
            self.buffer.append(Data(
                msg.ax,
                msg.ay,
                msg.az
            ))
        elif self.mode == Mode.MAG:
            self.buffer.append(Data(
                msg.mx,
                msg.my,
                msg.mz
            ))

        self.send_fn(aplink_request_cal_sensors().pack(0))