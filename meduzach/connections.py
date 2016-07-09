class Connector():
    """
    Simple signal-slot connector
    """
    def __init__(self):
        self.connections = {}
        self._nextid = 0

    def emit(self, signal_id, payload):
        if signal_id in self.connections:
            for action in self.connections[signal_id].values():
                action(self, payload)

    def connect(self, signal_id, action):
        if signal_id not in self.connections:
            self.connections[signal_id] = {}
        connection_id = self._nextid
        self._nextid += 1
        self.connections[signal_id][connection_id] = action
        return connection_id

    def disconnect(self, connection_id):
        for action_dict in self.connections.values():
            if connection_id in action_dict:
                del action_dict[connection_id]
                return True
        return False
