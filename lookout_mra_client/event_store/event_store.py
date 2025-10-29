class EventStore:
    """
    Generic interface for saving the last received event.
    On restart the event thread will load this store and pick up from the saved event.
    """

    DEFAULT_EVENT_THRESHOLD = 5

    def __init__(self):
        self.__event_count = 0
        self.__event_threshold = self.DEFAULT_EVENT_THRESHOLD

    def received_event(self, id: int):
        self.__event_count += 1
        if self.__event_count >= self.__event_threshold:
            self.save(id)
            self.__event_count = 0

    def save(self, id: str):
        raise NotImplementedError("Event stores must implement '.save()'")

    def load(self) -> str:
        raise NotImplementedError("Event stores must implement '.load()'")
