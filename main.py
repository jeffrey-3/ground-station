from queue import Queue
from websocket import WebSocket
from radio import Radio

if __name__ == "__main__":
    radio_input = Queue()
    ws_input = Queue()

    radio = Radio(radio_input, ws_input)
    websocket = WebSocket(ws_input, radio_input)

    websocket.start()