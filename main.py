from status import SystemStatus
from websocket import WebSocket

if __name__ == "__main__":
    status = SystemStatus()
    websocket = WebSocket(status)
    websocket.start()