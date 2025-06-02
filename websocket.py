from websockets.sync.server import serve
import json
import time
import threading
from queue import Queue
from radio import Param
from typing import List
from radio import Radio


# # Not all fields need to be filled out. For path you don't need to fill out final leg or glideslope.
# @dataclass
# class MissionItem:
#     type: str
#     lat: float
#     lon: float
#     radius: float
#     direction: str
#     final_leg: Optional[float]
#     glideslope: Optional[float]

# # Store in array
# # For land or loiter, you would have one mission item in array
# # For path, you have multiple mission items in array
# mission = []

class WebSocket:
    def __init__(self, ws_input: Queue[dict], radio_input: Queue[dict]):
        self.ws_input = ws_input
        self.radio_input = radio_input
        self.radio = Radio()

    def start(self):
        serve(self.handle_client, "localhost", 8765).serve_forever()
    
    def handle_client(self, websocket):
        print("Client connected:", websocket.remote_address)

        command_queue = Queue()
    
        def send():
            while True:
                self.status.time = time.time()

                websocket.send(json.dumps(self.status.to_dict()))

                while not command_queue.empty():
                    command = command_queue.get_nowait()
                    self.process_command(command)
                    command_queue.task_done()
                
                time.sleep(0.016)
            
        def read():
            for message in websocket:
                data = json.loads(message)
                print("Received command:", data)
                command_queue.put(data)
        
        send_thread = threading.Thread(target=send, daemon=True)
        read_thread = threading.Thread(target=read, daemon=True)
       
        send_thread.start()
        read_thread.start()

        send_thread.join()
        read_thread.join()

    def process_command(self, command):
        if command["type"] == "connect":
            self.radio.connect(command["port"])
        elif command["type"] == "loiter":
            self.status.mission.type = command["type"]
            self.status.mission.data = command["data"]
        elif command["type"] == "path":
            self.status.mission.type = command["type"]
            self.status.mission.data = command["data"]
        elif command["type"] == "land":
            self.status.mission.type = command["type"]
            self.status.mission.data = command["data"]
        elif command["type"] == "parameters":
            params_list: List[Param] = [Param(param["name"], param["value"], param["type"]) for param in command["data"]]
            print(params_list)
            self.radio.upload_params(params_list)