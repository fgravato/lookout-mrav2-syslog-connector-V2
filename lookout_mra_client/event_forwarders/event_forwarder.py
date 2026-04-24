class EventForwarder:
    """
    Generic interface for standardization of MRAv2StreamHandler
    """

    def write_all(self, events: list, ent_name: str):
        for event in events:
            self.write(event, ent_name)

    def write(self, _event: dict, _ent_name: str):
        raise NotImplementedError("Event forwarders must implement '.write()'")
