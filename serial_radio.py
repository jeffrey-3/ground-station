from status import SystemStatus
import math
import time
import threading
import serial

class SerialRadio():    
    testing: bool
    ser: serial.Serial
    status: SystemStatus

    def __init__(self, status: SystemStatus):
        self.status = status
        self.testing = False

    def connect(self, port):
        try:
            if port == "Testing":
                self.testing = True
            else:
                self.ser = serial.Serial(port, 115200, timeout=1)

            threading.Thread(target=self.read, daemon=True).start()
            self.status.serial.connected_port = port
            self.status.serial.connect_status = "Connected"
        except:
            print("Failed to connect to port")
            self.status.serial.connect_status = "Fail"
    
    def read(self):
        while True:
            if self.testing:
                self.status.telemetry.batt_voltage = 3 + 1 * math.sin(time.time() / 2)
                self.status.telemetry.heading = 45 * math.sin(time.time() / 2)
                self.status.telemetry.lat = 43.8791 + 0.0001 * math.sin(time.time())
                self.status.telemetry.lon = -79.4135 + 0.0001 * math.sin(time.time())
                self.status.telemetry.gps_sats = int(16 + 4 * math.sin(time.time()))
                time.sleep(0.03)
            else:
                byte = self.ser.read(1)
                print(byte)