from .models import IndiaOrderNotification


STATUS_MESSAGES = {
    "Pending": (
        "ORDER_PLACED",
        "Order placed successfully",
        "Your order has been placed and is awaiting confirmation.",
    ),
    "Confirmed": (
        "CONFIRMED",
        "Order confirmed",
        "Your order has been confirmed.",
    ),
    "Processing": (
        "PROCESSING",
        "Order is being prepared",
        "Your order is now being prepared for shipment.",
    ),
    "Shipped": (
        "SHIPPED",
        "Order shipped",
        "Your order has been shipped.",
    ),
    "Delivered": (
        "DELIVERED",
        "Order delivered",
        "Your order has been marked as delivered.",
    ),
    "Cancelled": (
        "CANCELLED",
        "Order cancelled",
        "Your order has been cancelled.",
    ),
}


def create_order_notification(order, event, title, message):
    """Create at most one notification per order and event."""
    notification, created = IndiaOrderNotification.objects.get_or_create(
        user=order.user,
        order=order,
        event=event,
        defaults={
            "title": title,
            "message": message,
        },
    )
    return notification, created


def notify_order_status(order):
    """Create a notification matching the order's current status."""
    details = STATUS_MESSAGES.get(order.status)
    if details is None:
        return None, False

    event, title, message = details

    if order.status == "Shipped" and order.tracking_number:
        message += f" Tracking number: {order.tracking_number}"

    message = f"Order {order.order_number}: {message}"

    return create_order_notification(
        order=order,
        event=event,
        title=title,
        message=message,
    )


def notify_payment_success(order):
    """Create a separate notification after payment is verified."""
    return create_order_notification(
        order=order,
        event="PAYMENT_CONFIRMED",
        title="Payment confirmed",
        message=(
            f"Payment for order {order.order_number} "
            "has been verified successfully."
        ),
    )
