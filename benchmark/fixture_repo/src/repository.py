"""Data access repository for order records."""

class OrderRepository:
    def __init__(self):
        self._storage = {}

    def save(self, order_id: str, data: dict) -> bool:
        self._storage[order_id] = data
        return True

    def find_by_id(self, order_id: str) -> dict:
        return self._storage.get(order_id)

    def list_all(self) -> list:
        return list(self._storage.values())

    def delete(self, order_id: str) -> bool:
        if order_id in self._storage:
            del self._storage[order_id]
            return True
        return False
