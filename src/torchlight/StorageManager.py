from typing import Dict


class StorageManager:
    def __init__(self) -> None:
        self.storage: Dict = dict()

    def Reset(self) -> None:
        self.storage = dict()

    def __getitem__(self, key: str) -> Dict:
        if key not in self.storage:
            self.storage[key] = dict()

        return self.storage[key]
