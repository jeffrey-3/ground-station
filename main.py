from serial_radio import SerialRadio
from status import SystemStatus
from websocket import WebSocket

if __name__ == "__main__":
    status = SystemStatus()
    serial_radio = SerialRadio(status)
    websocket = WebSocket(status, serial_radio)
    websocket.start()