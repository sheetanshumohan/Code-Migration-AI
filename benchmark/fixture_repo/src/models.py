"""Domain models for Legacy Order Processing System."""

class Customer:
    def __init__(self, customer_id: int, name: str, email: str, tier: str):
        self.customer_id = customer_id
        self.name = name
        self.email = email
        self.tier = tier

class LineItem:
    def __init__(self, item_id: str, quantity: int, unit_price: float):
        self.item_id = item_id
        self.quantity = quantity
        self.unit_price = unit_price

    def get_subtotal(self) -> float:
        return self.quantity * self.unit_price

class Order:
    def __init__(self, order_id: str, customer_id: int, items: list):
        self.order_id = order_id
        self.customer_id = customer_id
        self.items = items
        self.status = "PENDING"
        self.total_amount = 0.0

    def calculate_total(self) -> float:
        self.total_amount = sum(item.get_subtotal() for item in self.items)
        return self.total_amount
