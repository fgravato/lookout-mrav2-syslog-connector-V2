class EventForwarder:
    """
    Generic interface for standardization of MRAv2StreamHandler
    """

    def write_all(self, events: list, entName: str):
        for event in events:
            self.write(event, entName)

    def write(self, _event: dict, _entName: str):
        raise NotImplementedError("Event forwarders must implement '.write()'")
