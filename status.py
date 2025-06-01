import serial.tools.list_ports
from dataclasses import dataclass, field, asdict
from typing import Any, List, Optional

@dataclass
class TelemetryData:
    status: str = "TKO"
    batt_voltage: float = 0.0
    gps_sats: int = 0
    lat: float = 0.0
    lon: float = 0.0
    altitude: float = 10.3
    heading: float = 0.0

@dataclass
class SerialStatus:
    ports: List[str] = field(
        default_factory=lambda: [port.device for port in serial.tools.list_ports.comports()] + ["Testing"]
    )
    connected_port: str = ""
    connect_status: str = "Disconnected"

@dataclass
class MissionData:
    type: Optional[str] = None
    data: Optional[Any] = None

@dataclass
class SystemStatus:
    serial: SerialStatus = field(default_factory=SerialStatus)
    telemetry: TelemetryData = field(default_factory=TelemetryData)
    mission: MissionData = field(default_factory=MissionData)
    time: float = 0.0

    def to_dict(self):
        return {
            'serial': asdict(self.serial),
            'telemetry': asdict(self.telemetry),
            'mission': asdict(self.mission),
            'time': self.time
        }