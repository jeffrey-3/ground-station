from queue import Queue
from websocket import WebSocket
from radio import Radio

if __name__ == "__main__":
    ws_commands = Queue()
    telemetry_json_output = Queue()

    radio = Radio(ws_commands, telemetry_json_output)
    websocket = WebSocket(telemetry_json_output, ws_commands)

    websocket.start()