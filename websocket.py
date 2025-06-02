from websockets.sync.server import serve
import json
import time
import threading
from queue import Queue
from serial_radio import Param
from typing import List
from status import SystemStatus
from serial_radio import SerialRadio

class WebSocket():
    status: SystemStatus
    radio: SerialRadio

    def __init__(self, status: SystemStatus):
        self.status = status
        self.radio = SerialRadio()

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