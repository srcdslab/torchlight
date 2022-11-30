from typing import Dict


class StorageManager:
    def __init__(self) -> None:
        self.Storage: Dict = dict()

    def Reset(self) -> None:
        self.Storage = dict()

    def __getitem__(self, key: str) -> Dict:
        if not key in self.Storage:
            self.Storage[key] = dict()

        return self.Storage[key]
