"""Order processing service orchestrating business rules."""

from src.models import Order
from src.repository import OrderRepository
from src.utils import calculate_discount, format_currency

class OrderService:
    def __init__(self, repo: OrderRepository = None):
        self.repo = repo or OrderRepository()

    def process_order(self, order: Order, customer_tier: str) -> dict:
        subtotal = order.calculate_total()
        discount = calculate_discount(customer_tier, subtotal)
        final_amount = max(0.0, subtotal - discount)
        order.status = "PROCESSED"
        
        record = {
            "order_id": order.order_id,
            "customer_id": order.customer_id,
            "subtotal": subtotal,
            "discount": discount,
            "final_amount": final_amount,
            "formatted_total": format_currency(final_amount),
            "status": order.status,
        }
        self.repo.save(order.order_id, record)
        return record
