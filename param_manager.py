class ParamManager:
    def __init__(self, send_func, telemetry_queue):
        self.params = []
        self.last_param_set = 0
        self.send_func = send_func
        self.telemetry = telemetry_queue
    
    def start(self, params):
        self.params = params
        self.last_param_set = 0
        self._send_next()
    
    def ack_received(self):
        