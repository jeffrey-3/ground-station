from websockets.sync.server import serve
import websockets
import json
import threading
import time
from queue import Queue

# TODO: Use async instead of threading

class WebSocket:
    """Direct JSON passthrough to frontend via websocket"""
    def __init__(self, telemetry_json_output: Queue[dict], ws_commands: Queue[dict]):
        self.telemetry_json_output = telemetry_json_output
        self.ws_commands = ws_commands

    def start(self):
        print("Server started")
        serve(self.handle_client, "localhost", 8765).serve_forever()
    
    def handle_client(self, websocket):
        print("Client connected:", websocket.remote_address)
        self.active = True

        def send():
            while self.active:
                try:
                    if self.telemetry_json_output.empty():
                        time.sleep(0.0001)
                    else:
                        message = self.telemetry_json_output.get()
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
                    self.ws_commands.put(data)
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