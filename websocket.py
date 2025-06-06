import asyncio
import json
from queue import Queue
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

class WebSocket:
    """Direct JSON passthrough to frontend via websocket"""
    def __init__(self, telemetry_json_output: Queue[dict], ws_commands: Queue[dict]):
        self.telemetry_json_output = telemetry_json_output
        self.ws_commands = ws_commands

    def start(self):
        print("Server starting on ws://localhost:8765")
        asyncio.run(self._start_server())

    async def _start_server(self):
        async with websockets.serve(self.handle_client, "localhost", 8765):
            await asyncio.Future()  # run forever

    async def handle_client(self, websocket):
        print("Client connected:", websocket.remote_address)

        async def send():
            try:
                while True:
                    if not self.telemetry_json_output.empty():
                        message = self.telemetry_json_output.get()
                        await websocket.send(json.dumps(message))
                    else:
                        await asyncio.sleep(0.0001)
            except (ConnectionClosedOK, ConnectionClosedError):
                print("Client disconnected (send loop).")
            except Exception as e:
                print(f"Error in send loop: {e}")

        async def receive():
            try:
                async for message in websocket:
                    data = json.loads(message)
                    self.ws_commands.put(data)
            except (ConnectionClosedOK, ConnectionClosedError):
                print("Client disconnected (receive loop).")
            except Exception as e:
                print(f"Error in receive loop: {e}")

        # Run both tasks concurrently
        await asyncio.gather(send(), receive())
