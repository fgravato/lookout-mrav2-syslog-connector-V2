import os
from .event_store import EventStore


class FileEventStore(EventStore):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.__current_value = ""

    def save(self, id):
        if self.__current_value == id:
            return  # No need to save if value hasn't changed
        with open(self.file_path, "w+") as file_store:
            file_store.write(id)
            self.__current_value = id

    def load(self):
        if not os.path.exists(self.file_path):
            return ""
        with open(self.file_path, "r+") as file_store:
            store_value = file_store.read()
            if store_value is None:
                return ""
            self.__current_value = store_value
            return store_value
