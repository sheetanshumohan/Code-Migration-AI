"""Unit tests for OrderService."""

from src.models import LineItem, Order
from src.service import OrderService
from src.utils import calculate_discount, validate_email

def test_calculate_discount():
    assert calculate_discount("gold", 100.0) == 10.0
    assert calculate_discount("platinum", 200.0) == 40.0
    assert calculate_discount("unknown", 50.0) == 0.0

def test_validate_email():
    assert validate_email("user@example.com") is True
    assert validate_email("invalid-email") is False

def test_order_processing():
    items = [LineItem("A", 2, 10.0), LineItem("B", 1, 30.0)]
    order = Order("TEST-1", 1, items)
    service = OrderService()
    result = service.process_order(order, "silver")
    assert result["subtotal"] == 50.0
    assert result["discount"] == 2.5
    assert result["final_amount"] == 47.5
    assert result["status"] == "PROCESSED"
