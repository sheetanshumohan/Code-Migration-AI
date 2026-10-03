"""Main application entrypoint."""

from src.models import LineItem, Order
from src.service import OrderService

def create_sample_order(order_id: str, customer_id: int) -> dict:
    items = [
        LineItem("SKU-001", 2, 29.99),
        LineItem("SKU-002", 1, 99.50),
        LineItem("SKU-003", 5, 4.25),
    ]
    order = Order(order_id, customer_id, items)
    service = OrderService()
    return service.process_order(order, "gold")

if __name__ == "__main__":
    res = create_sample_order("ORD-1001", 42)
    print(f"Processed order: {res['order_id']} Total: {res['formatted_total']}")
