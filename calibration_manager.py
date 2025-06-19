from aplink.aplink_messages import *
from enum import Enum
from dataclasses import dataclass
from queue import Queue
import numpy as np
from typing import List

# Have stop buttons for everything instead of NUM_GYRO

@dataclass
class Data:
    x: float
    y: float
    z: float

class Mode(Enum):
    GYRO = 0
    ACCEL = 1
    MAG = 2

def calibrate_accelerometer(data_points: List[Data]):
    """
    Perform accelerometer calibration using ellipsoid fitting (PX4-style).
    
    Args:
        data_points: List of accelerometer readings in different static orientations.
        
    Returns:
        bias (offset): [b_x, b_y, b_z]
        scale factors: [s_x, s_y, s_z]
        fitted ellipsoid residuals (RMSE)
    """
    # Convert data to numpy array
    accel_data = np.array([[d.x, d.y, d.z] for d in data_points])
    N = accel_data.shape[0]  # Number of data points
    
    # Construct the design matrix D for least-squares fitting
    # Equation: a_x^2 + a_y^2 + a_z^2 + 2b_x a_x + 2b_y a_y + 2b_z a_z + c = 0
    # Rewritten as: D * p = 1 (where p = [A, B, C, D, E, F, G, H, K])
    D = np.zeros((N, 9))
    D[:, 0] = accel_data[:, 0] ** 2  # x²
    D[:, 1] = accel_data[:, 1] ** 2  # y²
    D[:, 2] = accel_data[:, 2] ** 2  # z²
    D[:, 3] = 2 * accel_data[:, 0] * accel_data[:, 1]  # 2xy
    D[:, 4] = 2 * accel_data[:, 0] * accel_data[:, 2]  # 2xz
    D[:, 5] = 2 * accel_data[:, 1] * accel_data[:, 2]  # 2yz
    D[:, 6] = 2 * accel_data[:, 0]  # 2x
    D[:, 7] = 2 * accel_data[:, 1]  # 2y
    D[:, 8] = 2 * accel_data[:, 2]  # 2z
    
    # Target: all points lie on the ellipsoid → D * p ≈ 1
    target = np.ones(N)
    
    # Solve least-squares problem: D * p = target
    p, residuals, _, _ = np.linalg.lstsq(D, target, rcond=None)
    
    # Extract parameters
    A, B, C, D, E, F, G, H, K = p
    
    # Form the ellipsoid matrix and center (bias)
    M = np.array([
        [A, D, E],
        [D, B, F],
        [E, F, C]
    ])
    center = -np.linalg.solve(M, np.array([G, H, K]))
    b_x, b_y, b_z = center
    
    # Compute scale factors via Cholesky decomposition
    T = np.eye(4)
    T[:3, :3] = M
    T[3, :3] = center
    T[:3, 3] = center
    T[3, 3] = -1
    
    # Normalize M to satisfy: (a - b)^T S^T S (a - b) = g²
    scale = np.sqrt(G * b_x + H * b_y + K * b_z + 1)
    M_normalized = M / scale
    
    # Cholesky decomposition: M_normalized = L^T L
    L = np.linalg.cholesky(M_normalized)
    s_x, s_y, s_z = np.diag(L) * 9.81  # Scale factors (assuming g = 9.81 m/s²)
    
    # Compute RMSE of residuals
    rmse = np.sqrt(residuals[0] / N) if len(residuals) > 0 else 0.0
    
    return {
        "bias": [b_x, b_y, b_z],
        "scale": [s_x, s_y, s_z],
        "rmse": rmse
    }

class CalibrationManager:
    GYRO_NUM_SAMPLES = 10
    MAG_NUM_SAMPLES = 10

    def __init__(self, send_fn, telemetry_json_output: Queue):
        self.send_fn = send_fn
        self.telemetry_json_output = telemetry_json_output
        self.mode = Mode.GYRO
        self.buffer = []
        self.accel_direction = None
        self.accel_buffer_level = []
        self.accel_buffer_inverted = []
        self.accel_buffer_nose_up = []
        self.accel_buffer_nose_down = []
        self.accel_buffer_roll_right = []
        self.accel_buffer_roll_left = []
    
    def cal_gyro(self, message):
        print("start gyro calibration")
        self.send_fn(aplink_request_cal_sensors().pack(0))
        self.buffer = []
        self.mode = Mode.GYRO
    
    def cal_accel(self, message):
        self.accel_direction = message["direction"]
        self.send_fn(aplink_request_cal_sensors().pack(0))
        self.buffer = []
        
    def cal_mag(self, message):
        self.send_fn(aplink_request_cal_sensors().pack(0))
        self.buffer = []

    def handle_cal_sensors(self, payload):
        msg = aplink_cal_sensors()
        msg.unpack(payload)

        print(vars(msg))

        complete = False

        if self.mode == Mode.GYRO:
            self.telemetry_json_output.put({
                "type": "cal_gyro_progress",
                "percentage": 100 * len(self.buffer) / self.GYRO_NUM_SAMPLES
            })

            self.buffer.append(Data(
                msg.gx,
                msg.gy,
                msg.gz
            ))

            if len(self.buffer) == self.GYRO_NUM_SAMPLES:
                self._gyro_finish()
                complete = True
        elif self.mode == Mode.ACCEL:
            self.telemetry_json_output.put({
                "type": "cal_accel_progress",
                "percentage": 100 * len(self.buffer) / self.ACCEL_NUM_SAMPLES
            })

            if self.accel_direction == "LEVEL":
                self.accel_buffer_level.append(Data(
                    msg.ax,
                    msg.ay,
                    msg.az
                ))
            elif self.accel_direction == "INVERTED":
                self.accel_buffer_inverted.append(Data(
                    msg.ax,
                    msg.ay,
                    msg.az
                ))
            elif self.accel_direction == "NOSE_UP":
                self.accel_buffer_nose_up.append(Data(
                    msg.ax,
                    msg.ay,
                    msg.az
                ))
            elif self.accel_direction == "NOSE_DOWN":
                self.accel_buffer_nose_down.append(Data(
                    msg.ax,
                    msg.ay,
                    msg.az
                ))
            elif self.accel_direction == "ROLL_RIGHT":
                self.accel_buffer_roll_right.append(Data(
                    msg.ax,
                    msg.ay,
                    msg.az
                ))
            elif self.accel_direction == "ROLL_LEFT":
                self.accel_buffer_roll_left.append(Data(
                    msg.ax,
                    msg.ay,
                    msg.az
                ))
            elif self.accel_direction == "FINISH":
                self._accel_finish()
                complete = True
        elif self.mode == Mode.MAG:
            self.telemetry_json_output.put({
                "type": "cal_mag_progress",
                "percentage": 100 * len(self.buffer) / self.MAG_NUM_SAMPLES
            })

            self.buffer.append(Data(
                msg.mx,
                msg.my,
                msg.mz
            ))

            if len(self.buffer) == self.MAG_NUM_SAMPLES:
                self._mag_finish()
                complete = True

        if not complete:
            self.send_fn(aplink_request_cal_sensors().pack(0))
    
    def _gyro_finish(self):
        offsets = self._calc_buffer_average(self.buffer, self.GYRO_NUM_SAMPLES)

        self.telemetry_json_output.put({
            "type": "gyro_cal_result",
            "x": offsets.x,
            "y": offsets.y,
            "z": offsets.z
        })
    
    def _accel_finish(self):
        print(calibrate_accelerometer([
            self._calc_buffer_average(self.accel_buffer_level, self.ACCEL_NUM_SAMPLES),
            self._calc_buffer_average(self.accel_buffer_inverted, self.ACCEL_NUM_SAMPLES),
            self._calc_buffer_average(self.accel_buffer_nose_up, self.ACCEL_NUM_SAMPLES),
            self._calc_buffer_average(self.accel_buffer_nose_down, self.ACCEL_NUM_SAMPLES),
            self._calc_buffer_average(self.accel_buffer_roll_right, self.ACCEL_NUM_SAMPLES),
            self._calc_buffer_average(self.accel_buffer_roll_left, self.ACCEL_NUM_SAMPLES)  
        ]))
    
    def _mag_finish(self):
        return

    def _calc_buffer_average(self, buffer, num_samples) -> Data:
        avg = Data(0, 0, 0)

        for data in buffer:
            avg.x += data.x
            avg.y += data.y
            avg.z += data.z
            
        avg.x /= num_samples
        avg.y /= num_samples
        avg.z /= num_samples

        return avg