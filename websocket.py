from websockets.sync.server import serve
import websockets
import json
import threading
import time
from queue import Queue
from radio import Param
from typing import List

class WebSocket:
    def __init__(self, ws_input: Queue[dict], radio_input: Queue[dict]):
        self.ws_input = ws_input
        self.radio_input = radio_input
        self.last_ping = time.time()

    def start(self):
        print("Server started")
        serve(self.handle_client, "localhost", 8765).serve_forever()
    
    def handle_client(self, websocket):
        print("Client connected:", websocket.remote_address)
        self.active = True

        def send():
            while self.active:
                try:
                    if self.ws_input.empty():
                        if time.time() - self.last_ping > 0.02:
                            websocket.send(json.dumps({
                                "type": "ping"
                            }))
                            self.last_ping = time.time()
                        time.sleep(0.001)
                    else:
                        message = self.ws_input.get()
                        print(f"Websocket send: {message}")
                        websocket.send(json.dumps(message))
                except websockets.exceptions.ConnectionClosed:
                    print("Client disconnected")
                    self.active = False
                    break
                except Exception as e:
                    print(f"Error in send thread: {e}")
                    self.active = False
                    break
            
        def read():
            try:
                for message in websocket:
                    data = json.loads(message)
                    print("Received command:", data)
                    self.process_command(data)
            except websockets.exceptions.ConnectionClosed:
                print("Client disconnected during read")
            except Exception as e:
                print(f"Error in read thread: {e}")
            finally:
                self.active = False
        
        send_thread = threading.Thread(target=send, daemon=True)
        read_thread = threading.Thread(target=read, daemon=True)
       
        send_thread.start()
        read_thread.start()

        send_thread.join()
        read_thread.join()

    def process_command(self, command):
        print(f"Websocket receive command: {command}")
        if command["type"] == "connect":
            self.radio_input.put({
                "type": "connect",
                "port": command["port"]
            })
        elif command["type"] == "serial_status":
            self.radio_input.put({
                "type": "status"
            })
        elif command["type"] == "parameters":
            params_list: List[Param] = [Param(param["name"], param["value"], param["type"]) for param in command["data"]]
            print(params_list)
            self.radio_input.put({
                "type": "send_params",
                "params": params_list
            })