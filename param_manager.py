from typing import Dict, Any
from aplink.aplink_messages import *

class ParamManager:
    def __init__(self, send_fn, telemetry_queue):
        self.last_param_set = 0
        self.params = []
        self.send_fn = send_fn
        self.telemetry = telemetry_queue
    
    def send_params(self, message: Dict[str, Any]):
        self.params = message["data"]
        self.last_param_set = 0
        self._send_next_param()
    
    def handle_param_set(self, _: bytes) -> None:
        if self.last_param_set == len(self.params):
            self.telemetry.put({"type": "param_set_success"})
        else:
            self._send_next_param()
            self.telemetry.put({
                "type": "param_set_progress",
                "progress": self.last_param_set,
                "total": len(self.params)
            })
    
    def _send_next_param(self) -> None:
        param = self.params[self.last_param_set]
        param_name = list(param["name"].ljust(16, '\x00').encode('utf-8'))
        
        type_mapping = {
            "f": (PARAM_TYPE.FLOAT, '=f'),
            "i": (PARAM_TYPE.INT32, '=i'),
        }
        
        param_type, pack_format = type_mapping.get(param["type"], (None, None))
        if param_type is None:
            return
            
        param_value = list(struct.pack(pack_format, param["value"]))
        self.send_fn(aplink_param_set().pack(param_name, param_value, int(param_type)))
        
        print(f"Sent parameter {param['name']}")
        self.last_param_set += 1