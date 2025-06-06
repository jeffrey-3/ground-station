class MessageRouter:
    def __init__(self):
        self.handlers = {}

    def register(self, msg_type, handler):
        self.handlers[msg_type] = handler

    def handle(self, message):
        handler = self.handlers.get(message["type"])
        if handler:
            handler(message)
